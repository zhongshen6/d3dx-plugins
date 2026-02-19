# Licensed under the GNU General Public License v3.0
# d3dxSkinManage Plugin: windows_touch_scroll

__version__ = "v1.1.0"

import ctypes
import json
import os
import threading

import core


PLUGIN_TAG = "(windows_touch_scroll)"
_DEBUG_LOG = False

CONFIG_BASENAME = "config.json"

DEFAULT_CONFIG = {
    "enabled": True,
    "onlytouch": True,
    "consume_drag_events": True,
    "allow_text_drag_selection": True,
    "widget_rebind_ms": 1200,
    "profile": "balanced",
    "scroll_sensitivity": 1.0,
    "drag_threshold_px": 8,
    "pixels_per_unit": 36,
    "log_debug": False,
}

PROFILE_OVERRIDES = {
    "balanced": {
        "scroll_sensitivity": 1.0,
        "drag_threshold_px": 8,
        "pixels_per_unit": 36,
    },
    "fine": {
        "scroll_sensitivity": 0.75,
        "drag_threshold_px": 10,
        "pixels_per_unit": 44,
    },
    "fast": {
        "scroll_sensitivity": 1.25,
        "drag_threshold_px": 6,
        "pixels_per_unit": 28,
    },
}


MI_WP_SIGNATURE = 0xFF515700
SIGNATURE_MASK = 0xFFFFFF00

if os.name == "nt":
    USER32 = ctypes.WinDLL("user32", use_last_error=True)
    USER32.GetMessageExtraInfo.argtypes = []
    USER32.GetMessageExtraInfo.restype = ctypes.c_void_p
else:
    USER32 = None


def _log_info(message: str) -> None:
    core.log.info(f"{PLUGIN_TAG} {message}")


def _log_warning(message: str) -> None:
    core.log.warning(f"{PLUGIN_TAG} {message}")


def _log_error(message: str) -> None:
    core.log.error(f"{PLUGIN_TAG} {message}")


def _log_debug(message: str) -> None:
    if _DEBUG_LOG:
        core.log.debug(f"{PLUGIN_TAG} {message}")


def _is_touch_or_pen_message() -> bool:
    if USER32 is None:
        return False

    try:
        extra_info = int(USER32.GetMessageExtraInfo()) & 0xFFFFFFFFFFFFFFFF
    except Exception:
        return False

    return (extra_info & SIGNATURE_MASK) == MI_WP_SIGNATURE


def _normalize_bool(value, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return default


def _normalize_float(value, default: float, minimum: float) -> float:
    try:
        number = float(value)
    except Exception:
        return default
    if number < minimum:
        return minimum
    return number


def _normalize_int(value, default: int, minimum: int) -> int:
    try:
        number = int(value)
    except Exception:
        return default
    if number < minimum:
        return minimum
    return number


def load_config() -> dict:
    plugin_dir = os.path.dirname(__file__)
    config_path = os.path.join(plugin_dir, CONFIG_BASENAME)

    raw = {}
    if os.path.isfile(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as file_object:
                temp = json.load(file_object)
            if isinstance(temp, dict):
                raw = temp
        except Exception as exc:
            _log_error(f"配置文件读取失败，使用默认配置 {exc.__class__.__name__}: {exc}")

    profile_name = str(raw.get("profile", DEFAULT_CONFIG["profile"])).strip().lower()
    if profile_name not in PROFILE_OVERRIDES:
        profile_name = DEFAULT_CONFIG["profile"]

    config = dict(DEFAULT_CONFIG)
    config.update(PROFILE_OVERRIDES.get(profile_name, {}))
    config["profile"] = profile_name

    for key in DEFAULT_CONFIG:
        if key == "profile":
            continue
        if key in raw:
            config[key] = raw[key]

    # Backward compatibility for older config formats.
    if "input_mode" in raw:
        mode = str(raw.get("input_mode", "touch_only")).strip().lower()
        config["onlytouch"] = mode != "touch_and_drag"
    if "force_drag_scroll" in raw:
        config["onlytouch"] = not _normalize_bool(raw.get("force_drag_scroll"), False)

    config["enabled"] = _normalize_bool(config.get("enabled"), True)
    config["onlytouch"] = _normalize_bool(config.get("onlytouch"), True)
    config["consume_drag_events"] = _normalize_bool(config.get("consume_drag_events"), True)
    config["allow_text_drag_selection"] = _normalize_bool(config.get("allow_text_drag_selection"), True)
    config["widget_rebind_ms"] = _normalize_int(config.get("widget_rebind_ms"), 1200, 200)
    config["scroll_sensitivity"] = _normalize_float(config.get("scroll_sensitivity"), 1.0, 0.01)
    config["drag_threshold_px"] = _normalize_int(config.get("drag_threshold_px"), 8, 1)
    config["pixels_per_unit"] = _normalize_float(config.get("pixels_per_unit"), 36.0, 1.0)
    config["log_debug"] = _normalize_bool(config.get("log_debug"), False)

    return config


class ScrollRouter:
    def __init__(self, config: dict):
        self.scroll_sensitivity = float(config.get("scroll_sensitivity", 1.0))
        self.pixels_per_unit = float(config.get("pixels_per_unit", 36.0))
        self._residual_pixels = {}
        self._lock = threading.RLock()

    def scroll_at_screen(self, x_root: int, y_root: int, delta_y: float) -> bool:
        try:
            widget = core.window.mainwindow.winfo_containing(int(x_root), int(y_root))
        except Exception:
            return False

        target = self._resolve_scroll_target(widget)
        if target is None:
            return False

        return self._scroll_widget(target, delta_y)

    def _resolve_scroll_target(self, widget):
        current = widget
        while current is not None:
            try:
                canvas = getattr(current, "w_canvas", None)
                if self._is_vertical_scroll_widget(canvas):
                    return canvas

                if self._is_vertical_scroll_widget(current):
                    return current
            except Exception:
                pass

            current = getattr(current, "master", None)

        return None

    @staticmethod
    def _is_vertical_scroll_widget(widget) -> bool:
        if widget is None:
            return False

        yview = getattr(widget, "yview", None)
        yview_scroll = getattr(widget, "yview_scroll", None)
        if not callable(yview) or not callable(yview_scroll):
            return False

        try:
            widget.winfo_exists()
        except Exception:
            return False

        return True

    @staticmethod
    def _pixels_to_units(total_pixels: float, pixels_per_unit: float) -> int:
        if total_pixels >= 0:
            return int(total_pixels // pixels_per_unit)
        return -int((-total_pixels) // pixels_per_unit)

    def _scroll_widget(self, widget, delta_y: float) -> bool:
        if abs(delta_y) < 0.5:
            return False

        scaled_pixels = -float(delta_y) * self.scroll_sensitivity
        key = str(widget)

        with self._lock:
            total = self._residual_pixels.get(key, 0.0) + scaled_pixels
            units = self._pixels_to_units(total, self.pixels_per_unit)

            if units == 0:
                self._residual_pixels[key] = total
                return False

            self._residual_pixels[key] = total - (units * self.pixels_per_unit)

        try:
            widget.yview_scroll(units, "units")
            return True
        except Exception:
            return False


class TkDragScrollBridge:
    _TEXT_CLASS_NAME_SET = {"Entry", "Text", "TEntry"}

    def __init__(self, router: ScrollRouter, config: dict):
        self.router = router
        self.onlytouch = bool(config.get("onlytouch", True))
        self.consume_drag_events = bool(config.get("consume_drag_events", True))
        self.allow_text_drag_selection = bool(config.get("allow_text_drag_selection", True))
        self.threshold_px = int(config.get("drag_threshold_px", 8))
        self.widget_rebind_ms = int(config.get("widget_rebind_ms", 1200))

        self._active = False
        self._root = None
        self._refresh_job = None
        self._bound_widgets = set()
        self._last_bound_count = -1

        self._pressed = False
        self._press_is_touch = False
        self._locked_vertical = False
        self._ignore_widget = False
        self._touch_seen = False
        self._start_x = 0
        self._start_y = 0
        self._last_x = 0
        self._last_y = 0

    def start(self, root) -> None:
        if self._active:
            return

        self._root = root
        self._active = True
        self._bind_widget_tree()
        self._schedule_widget_refresh()

    def stop(self) -> None:
        if self._refresh_job is not None and self._root is not None:
            try:
                self._root.after_cancel(self._refresh_job)
            except Exception:
                pass
            self._refresh_job = None

        self._active = False
        self._pressed = False
        self._press_is_touch = False
        self._locked_vertical = False
        self._ignore_widget = False

    def _iter_widgets(self):
        if self._root is None:
            return

        stack = [self._root]
        while stack:
            widget = stack.pop()
            yield widget
            try:
                stack.extend(widget.winfo_children())
            except Exception:
                continue

    def _bind_widget_tree(self):
        for widget in self._iter_widgets():
            try:
                widget_id = str(widget)
            except Exception:
                continue

            if widget_id in self._bound_widgets:
                continue

            try:
                widget.bind("<ButtonPress-1>", self._on_press, add="+")
                widget.bind("<B1-Motion>", self._on_motion, add="+")
                widget.bind("<ButtonRelease-1>", self._on_release, add="+")
                self._bound_widgets.add(widget_id)
            except Exception:
                continue

        bound_count = len(self._bound_widgets)
        if bound_count != self._last_bound_count:
            _log_debug(f"TkBind widgets={bound_count}")
            self._last_bound_count = bound_count

    def _schedule_widget_refresh(self):
        if not self._active or self._root is None:
            return
        self._refresh_job = self._root.after(self.widget_rebind_ms, self._refresh_widget_bindings)

    def _refresh_widget_bindings(self):
        self._refresh_job = None
        if not self._active:
            return

        try:
            self._bind_widget_tree()
        except Exception as exc:
            _log_debug(f"TkBindRefresh error {exc.__class__.__name__}: {exc}")

        self._schedule_widget_refresh()

    def _should_ignore_widget(self, widget) -> bool:
        if self.allow_text_drag_selection:
            return False

        try:
            return widget.winfo_class() in self._TEXT_CLASS_NAME_SET
        except Exception:
            return False

    def _on_press(self, event):
        if not self._active:
            return None

        self._press_is_touch = _is_touch_or_pen_message()
        if self._press_is_touch and not self._touch_seen:
            self._touch_seen = True
            _log_info("检测到触控注入事件（Tk 输入通道）")

        if self.onlytouch and (not self._press_is_touch):
            self._pressed = False
            self._locked_vertical = False
            self._ignore_widget = False
            return None

        self._ignore_widget = self._should_ignore_widget(event.widget)
        if self._ignore_widget:
            self._pressed = False
            self._locked_vertical = False
            return None

        self._pressed = True
        self._locked_vertical = False
        self._start_x = int(event.x_root)
        self._start_y = int(event.y_root)
        self._last_x = int(event.x_root)
        self._last_y = int(event.y_root)
        _log_debug(f"TkPress ({self._start_x}, {self._start_y}) touch={self._press_is_touch}")
        return None

    def _on_motion(self, event):
        if not self._active or not self._pressed or self._ignore_widget:
            return None

        if self.onlytouch and (not self._press_is_touch):
            return None

        now_x = int(event.x_root)
        now_y = int(event.y_root)
        dx_total = now_x - self._start_x
        dy_total = now_y - self._start_y

        if not self._locked_vertical:
            if abs(dy_total) < self.threshold_px:
                return None
            if abs(dy_total) < abs(dx_total):
                return None
            self._locked_vertical = True
            _log_debug(f"TkLockVertical dx={dx_total} dy={dy_total}")

        delta_y = now_y - self._last_y
        self._last_x = now_x
        self._last_y = now_y

        if abs(delta_y) < 1:
            return None

        hit = self.router.scroll_at_screen(now_x, now_y, delta_y)
        if hit:
            _log_debug(f"TkScroll y={delta_y} at ({now_x}, {now_y})")

        if hit and self.consume_drag_events:
            return "break"
        return None

    def _on_release(self, _event):
        if not self._active:
            return None

        was_locked = self._locked_vertical and (not self._ignore_widget)
        self._pressed = False
        self._press_is_touch = False
        self._locked_vertical = False
        self._ignore_widget = False

        if was_locked and self.consume_drag_events:
            return "break"
        return None


class TouchScrollPlugin:
    def __init__(self, config: dict):
        self.config = config
        self.router = ScrollRouter(config)
        self.bridge = TkDragScrollBridge(self.router, config)
        self._started = False
        self._exit_hook_registered = False

    def bootstrap(self):
        if self._started:
            return
        self._started = True

        if not self.config.get("enabled", True):
            _log_info("插件已禁用")
            return

        self.bridge.start(core.window.mainwindow)

        if self.config.get("onlytouch", True):
            _log_info("输入模式: onlytouch（仅触控）")
        else:
            _log_info("输入模式: touch+drag（触控 + 拖动）")

        self._register_exit_hook()

    def _register_exit_hook(self):
        if self._exit_hook_registered:
            return
        self._exit_hook_registered = True
        try:
            core.action.askexit.add_task(self.shutdown, 9000, "windows_touch_scroll.shutdown", False)
        except Exception:
            pass

    def shutdown(self):
        self.bridge.stop()


_PLUGIN_INSTANCE = None


def main():
    global _PLUGIN_INSTANCE
    global _DEBUG_LOG

    try:
        config = load_config()
        _DEBUG_LOG = bool(config.get("log_debug", False))
        _PLUGIN_INSTANCE = TouchScrollPlugin(config)
        core.window.mainwindow.after(0, _PLUGIN_INSTANCE.bootstrap)
        _log_info(
            f"插件已加载 version={__version__} profile={config.get('profile', 'balanced')} "
            f"onlytouch={config.get('onlytouch', True)} debug={_DEBUG_LOG}"
        )

    except Exception as exc:
        _log_error(f"插件初始化失败 {exc.__class__.__name__}: {exc}")

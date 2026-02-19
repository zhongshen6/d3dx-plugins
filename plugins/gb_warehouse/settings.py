# Licensed under the GNU General Public License v3.0
# d3dxSkinManage Plugin: gb_warehouse (Settings)

import ttkbootstrap
from ttkbootstrap.constants import *

import core
import constants as const

LOG_TAG = "(gb_warehouse/settings)"


class SettingsMixin:
    def _get_env_name(self):
        return getattr(core.userenv, "user_name", None)

    def _normalize_game_id(self, value):
        if value is None:
            return None
        try:
            text = str(value).strip()
        except Exception:
            return None
        if not text:
            return None
        if not text.isdigit():
            return None
        try:
            return int(text)
        except Exception:
            return None

    def _get_saved_game_id(self):
        conf = getattr(core.userenv, "configuration", None)
        if not conf:
            return None
        value = getattr(conf, "gb_game_id", None)
        return self._normalize_game_id(value)

    def _set_saved_game_id(self, game_id):
        conf = getattr(core.userenv, "configuration", None)
        if not conf:
            return
        conf.gb_game_id = int(game_id)
        core.log.debug(f"{LOG_TAG} game_id.saved env={self._get_env_name()} id={game_id}")

    def _get_saved_root_category_id(self):
        conf = getattr(core.userenv, "configuration", None)
        if not conf:
            return None
        value = getattr(conf, "gb_root_category_id", None)
        return self._normalize_game_id(value)

    def _set_saved_root_category_id(self, category_id):
        conf = getattr(core.userenv, "configuration", None)
        if not conf:
            return
        conf.gb_root_category_id = int(category_id)
        core.log.debug(f"{LOG_TAG} root_category.saved env={self._get_env_name()} id={category_id}")

    def get_root_category_id(self):
        saved = self._get_saved_root_category_id()
        if saved:
            return saved
        env_name = self._get_env_name()
        return const.ENV_ROOT_CATEGORY_ID_MAP.get(env_name)

    def get_game_id(self):
        env_name = self._get_env_name()
        if self.current_env_name != env_name:
            self.current_env_name = env_name
            self.current_game_id = None
        if self.current_game_id:
            return self.current_game_id
        saved = self._get_saved_game_id()
        if saved:
            self.current_game_id = saved
            return saved
        if env_name in const.ENV_GAME_ID_MAP:
            mapped = const.ENV_GAME_ID_MAP.get(env_name)
            if mapped:
                self._set_saved_game_id(mapped)
                self.current_game_id = mapped
                return mapped
        self.current_game_id = const.DEFAULT_GAME_ID
        return self.current_game_id

    def ensure_game_id(self, prompt_if_missing=False):
        env_name = self._get_env_name()
        if self.current_env_name != env_name:
            core.log.debug(f"{LOG_TAG} env.changed from={self.current_env_name} to={env_name}")
            self.current_env_name = env_name
            self.current_game_id = None
            self._env_prompted = False

        saved = self._get_saved_game_id()
        if saved:
            if self.current_game_id != saved:
                self.apply_game_id_change(saved, reload=self.is_visible)
            return
        mapped = const.ENV_GAME_ID_MAP.get(env_name) if env_name else None
        if mapped:
            self._set_saved_game_id(mapped)
            self.apply_game_id_change(mapped, reload=self.is_visible)
            return
        if prompt_if_missing and not self._env_prompted:
            self._env_prompted = True
            self.open_game_id_settings(force_prompt=True)

    def open_game_id_settings(self, force_prompt=False):
        if self._game_id_window and self._game_id_window.winfo_exists():
            try:
                self._game_id_window.lift()
                self._game_id_window.focus()
            except Exception:
                pass
            return

        env_name = self._get_env_name() or "<未登录>"
        initial_value = self._get_saved_game_id() or const.ENV_GAME_ID_MAP.get(env_name) or const.DEFAULT_GAME_ID
        initial_root = self._get_saved_root_category_id() or const.ENV_ROOT_CATEGORY_ID_MAP.get(env_name) or ""

        win = ttkbootstrap.Toplevel("GB 数据源设置")
        self._game_id_window = win
        win.transient(self.master)
        win.grab_set()
        win.resizable(False, False)

        frame = ttkbootstrap.Frame(win, padding=12)
        frame.pack(fill=BOTH, expand=True)

        label_env = ttkbootstrap.Label(frame, text=f"当前环境：{env_name}")
        label_env.pack(anchor=W, pady=(0, 6))

        row = ttkbootstrap.Frame(frame)
        row.pack(fill=X, pady=(0, 6))
        label = ttkbootstrap.Label(row, text="当前环境数据源")
        label.pack(side=LEFT)
        entry = ttkbootstrap.Entry(row, width=12)
        entry.pack(side=LEFT, padx=(10, 0))
        entry.insert(0, str(initial_value))

        row_root = ttkbootstrap.Frame(frame)
        row_root.pack(fill=X, pady=(0, 6))
        label_root = ttkbootstrap.Label(row_root, text="根分类 ID")
        label_root.pack(side=LEFT)
        entry_root = ttkbootstrap.Entry(row_root, width=12)
        entry_root.pack(side=LEFT, padx=(10, 0))
        if initial_root:
            entry_root.insert(0, str(initial_root))

        hint = ttkbootstrap.Label(frame, text="输入 GameBanana Game ID，例如 8552 / 18366", bootstyle=SECONDARY)
        hint.pack(anchor=W, pady=(0, 8))

        err = ttkbootstrap.Label(frame, text="", bootstyle=DANGER)
        err.pack(anchor=W)

        btn_row = ttkbootstrap.Frame(frame)
        btn_row.pack(fill=X, pady=(10, 0))

        def _commit(value_text, root_text):
            value_text = (value_text or "").strip()
            if not value_text:
                game_id = const.DEFAULT_GAME_ID
            elif not value_text.isdigit():
                err.configure(text="请输入纯数字的 Game ID")
                return
            else:
                game_id = int(value_text)
            root_text = (root_text or "").strip()
            if root_text:
                if not root_text.isdigit():
                    err.configure(text="根分类 ID 必须是纯数字")
                    return
                root_id = int(root_text)
            else:
                root_id = None
            core.log.info(f"{LOG_TAG} game_id.manual_set env={env_name} id={game_id} root={root_id}")
            self._set_saved_game_id(game_id)
            if root_id is not None:
                self._set_saved_root_category_id(root_id)
            self.apply_game_id_change(game_id)
            try:
                win.destroy()
            except Exception:
                pass
            pending = getattr(self, "_pending_open_category", False)
            self._pending_open_category = False
            if pending and self.get_root_category_id():
                try:
                    self.master.after(0, self.open_category_browser)
                except Exception:
                    pass

        def _cancel():
            if force_prompt and not self._get_saved_game_id():
                self._set_saved_game_id(const.DEFAULT_GAME_ID)
                self.apply_game_id_change(const.DEFAULT_GAME_ID)
            try:
                win.destroy()
            except Exception:
                pass

        btn_save = ttkbootstrap.Button(
            btn_row,
            text="保存",
            bootstyle=SUCCESS,
            command=lambda: _commit(entry.get(), entry_root.get()),
        )
        btn_cancel = ttkbootstrap.Button(btn_row, text="取消", bootstyle=OUTLINE, command=_cancel)
        btn_cancel.pack(side=RIGHT)
        btn_save.pack(side=RIGHT, padx=(0, 8))

        def _on_close():
            _cancel()

        win.protocol("WM_DELETE_WINDOW", _on_close)
        try:
            win.update_idletasks()
            core.window.methods.center_window_for_window(win, core.window.mainwindow)
        except Exception:
            pass

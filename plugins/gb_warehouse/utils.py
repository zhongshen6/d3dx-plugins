import datetime
import re
import weakref

def safe_call(fn, *args, default=None, **kwargs):
    if not fn:
        return default
    try:
        return fn(*args, **kwargs)
    except Exception:
        return default

def safe_after(widget, delay_ms, fn, *args, **kwargs):
    if not widget:
        return None
    try:
        return widget.after(delay_ms, lambda: safe_call(fn, *args, **kwargs))
    except Exception:
        return None

def destroy_many(items):
    for item in list(items or []):
        safe_call(getattr(item, "destroy", None))

def clear_children(widget):
    destroy_many(safe_call(getattr(widget, "winfo_children", None), default=[]))

def format_ts(ts, fmt="%y.%m.%d", empty="--.--.--"):
    if not ts:
        return empty
    try:
        dt = datetime.datetime.fromtimestamp(ts)
        return dt.strftime(fmt)
    except Exception:
        return empty

def normalize_explain(explain):
    if not explain:
        return ""
    if "\\n" in explain and "\n" not in explain:
        return explain.replace("\\n", "\n")
    return explain

def parse_gb_explain(explain):
    explain = normalize_explain(explain)
    match = re.search(r"\[GB\][^\n]*id\s*=\s*(\d+)[^\n]*last\s*=\s*(\d+)", explain, re.IGNORECASE)
    if not match:
        return None, None
    try:
        return int(match.group(1)), int(match.group(2))
    except Exception:
        return None, None

def merge_gb_explain(explain, mod_id, ts):
    line = f"[GB] id={mod_id} last={ts}"
    if not explain:
        return line
    sep = "\n"
    if "\\n" in explain and "\n" not in explain:
        sep = "\\n"
        lines = explain.split("\\n")
    else:
        lines = explain.splitlines()
    replaced = False
    for i, l in enumerate(lines):
        if l.strip().startswith("[GB]"):
            lines[i] = line
            replaced = True
            break
    if not replaced:
        lines.append(line)
    return sep.join(lines)

class DebouncedCall:
    _instances = weakref.WeakSet()

    def __init__(self, widget, delay_ms, is_paused_fn=None):
        self.widget = widget
        self.delay_ms = delay_ms
        self.is_paused_fn = is_paused_fn or (lambda: False)
        self._job = None
        self._pending = None
        self._callback = None
        self._has_pending = False
        DebouncedCall._instances.add(self)

    def schedule(self, value, callback):
        self._pending = value
        self._callback = callback
        self._has_pending = True
        if self.is_paused_fn():
            if self._job is not None:
                safe_call(self.widget.after_cancel, self._job)
                self._job = None
            return
        if self._job is not None:
            safe_call(self.widget.after_cancel, self._job)
        self._job = self.widget.after(self.delay_ms, self._run)

    def cancel(self):
        if self._job is not None:
            safe_call(self.widget.after_cancel, self._job)
            self._job = None
        self._pending = None
        self._callback = None
        self._has_pending = False

    def flush(self):
        if self.is_paused_fn():
            return False
        if not self._has_pending:
            return False
        if self._job is not None:
            safe_call(self.widget.after_cancel, self._job)
            self._job = None
        value = self._pending
        callback = self._callback
        self._pending = None
        self._callback = None
        self._has_pending = False
        if callback:
            callback(value)
        return True

    @classmethod
    def flush_all(cls):
        for inst in list(cls._instances):
            safe_call(inst.flush)

    def _run(self):
        self._job = None
        if self.is_paused_fn():
            self._has_pending = True
            return
        value = self._pending
        callback = self._callback
        self._pending = None
        self._callback = None
        self._has_pending = False
        if callback:
            callback(value)

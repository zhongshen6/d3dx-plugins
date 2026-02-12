# Licensed under the GNU General Public License v3.0
# d3dxSkinManage Plugin: gb_warehouse (Utils)

import datetime
import re


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
    def __init__(self, widget, delay_ms, is_paused_fn=None):
        self.widget = widget
        self.delay_ms = delay_ms
        self.is_paused_fn = is_paused_fn or (lambda: False)
        self._job = None
        self._pending = None
        self._callback = None

    def schedule(self, value, callback):
        self._pending = value
        self._callback = callback
        if self.is_paused_fn():
            if self._job is None:
                self._job = self.widget.after(self.delay_ms, self._run)
            return
        if self._job is not None:
            try:
                self.widget.after_cancel(self._job)
            except Exception:
                pass
        self._job = self.widget.after(self.delay_ms, self._run)

    def cancel(self):
        if self._job is not None:
            try:
                self.widget.after_cancel(self._job)
            except Exception:
                pass
            self._job = None

    def _run(self):
        self._job = None
        if self.is_paused_fn():
            try:
                self._job = self.widget.after(self.delay_ms, self._run)
            except Exception:
                self._job = None
            return
        value = self._pending
        callback = self._callback
        self._pending = None
        if callback:
            callback(value)

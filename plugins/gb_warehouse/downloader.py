import os
import re
import time
import hashlib
import threading
from urllib.parse import urlsplit, unquote
import core
from constant import K
from utils import merge_gb_explain, safe_call, safe_after
LOG_TAG = "(gb_warehouse/download)"

class DownloadMixin:
    def _ui_call(self, ui, action, *args):
        if ui:
            safe_call(ui.get(action), *args)

    def download_and_import(self, url, filename=None, mod_id=None, ui=None):
        if not url:
            return
        core.log.info(f"{LOG_TAG} start mod_id={mod_id} name={filename}")
        core.log.debug(f"{LOG_TAG} start.url mod_id={mod_id} url={url}")
        if not hasattr(self, "download_tasks"):
            self.download_tasks = set()
        if url in self.download_tasks:
            self._set_status("下载任务已存在", 2)
            return

        self.download_tasks.add(url)
        display_name = filename or self._guess_filename(url, None) or "文件"
        self._set_status(f"正在下载: {display_name}", 2)
        self._ui_call(ui, "enabled", False)
        self._ui_call(ui, "show_progress", True)

        taskpool = getattr(core.construct, "taskpool", None)
        if not taskpool:
            self.download_tasks.discard(url)
            self._set_status("任务池不可用，无法下载", 1)
            self._ui_call(ui, "hide_progress", 0)
            self._ui_call(ui, "enabled", True)
            return
        taskpool.newtask(self.async_download_and_import, (url, filename, mod_id, ui), {}, False)

    def async_download_and_import(self, url, filename=None, mod_id=None, ui=None):
        try:
            path = self._download_file(url, filename, ui)
            if not path:
                self.master.after(0, lambda: self._set_status("下载失败", 1))
                self._ui_call(ui, "hide_progress", 0)
                return
            core.log.info(f"{LOG_TAG} done mod_id={mod_id} file={os.path.basename(path)}")
            core.log.debug(f"{LOG_TAG} done.path path={path}")
            self.master.after(0, lambda: self._set_status("下载完成，打开导入窗口", 0))
            self._ui_call(ui, "progress", 100)
            self._ui_call(ui, "hide_progress", 1000)
            self.master.after(0, lambda: self._open_import_window(path))
            if mod_id:
                sha = self._calc_sha(path)
                if sha:
                    core.log.debug(f"{LOG_TAG} sha.ok value={sha}")
                    self._schedule_import_mark(sha, mod_id)
        except Exception as e:
            core.log.error(f"{LOG_TAG} failed err={e}")
            self.master.after(0, lambda: self._set_status("下载失败", 1))
            self._ui_call(ui, "hide_progress", 0)
        finally:
            if hasattr(self, "download_tasks"):
                self.download_tasks.discard(url)
            self._ui_call(ui, "enabled", True)

    def _download_file(self, url, filename=None, ui=None):
        session = getattr(self, "session", None)
        if session is None:
            import requests
            session = requests

        res = session.get(url, timeout=30, stream=True, allow_redirects=True)
        if res.status_code != 200:
            core.log.warn(f"{LOG_TAG} http_error status={res.status_code} url={url}")
            self._ui_call(ui, "hide_progress", 0)
            return None

        name = filename or self._guess_filename(url, res.headers.get("content-disposition"))
        name = self._sanitize_filename(name)
        if not name:
            name = "gb_download"

        base_dir = core.env.directory.resources.cache
        os.makedirs(base_dir, exist_ok=True)
        path = self._ensure_unique_path(base_dir, name)

        total = 0
        try:
            total = int(res.headers.get("content-length", 0) or 0)
        except Exception:
            total = 0
        self._ui_call(ui, "show_progress", total <= 0)
        if total > 0:
            self._ui_call(ui, "progress", 0)

        last_ts = time.time()
        last_bytes = 0
        downloaded = 0
        with open(path, "wb") as f:
            for chunk in res.iter_content(chunk_size=256 * 1024):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    now = time.time()
                    if now - last_ts >= 0.3:
                        speed = (downloaded - last_bytes) / max(0.001, now - last_ts)
                        last_ts = now
                        last_bytes = downloaded
                        if ui and total > 0:
                            self._ui_call(ui, "progress", int(downloaded * 100 / total))
        return path

    def _open_import_window(self, path):
        add_mod2 = getattr(core.additional, "add_mod2", None)
        if not add_mod2 or not hasattr(add_mod2, "add_mods"):
            self._set_status("导入模块不可用", 1)
            return
        add_mod2.add_mods([path])

    def _calc_sha(self, path):
        try:
            sha1 = hashlib.sha1()
            with open(path, "rb") as f:
                for chunk in iter(lambda: f.read(1024 * 1024), b""):
                    sha1.update(chunk)
            return sha1.hexdigest().upper()
        except Exception as e:
            core.log.error(f"{LOG_TAG} sha.failed err={e}")
            return None

    def _schedule_import_mark(self, sha, mod_id):
        if not sha or not mod_id:
            return
        if not hasattr(self, "pending_gb_marks"):
            self.pending_gb_marks = set()
        key = f"{sha}:{mod_id}"
        if key in self.pending_gb_marks:
            return
        self.pending_gb_marks.add(key)
        ts = int(time.time())
        core.log.debug(f"{LOG_TAG} mark.wait sha={sha} mod_id={mod_id} ts={ts}")
        t = threading.Thread(
            target=self._wait_and_mark_import,
            args=(sha, mod_id, ts, key),
            daemon=True,
        )
        t.start()

    def _wait_and_mark_import(self, sha, mod_id, ts, key):
        try:
            deadline = time.time() + 180
            while time.time() < deadline:
                item = core.module.mods_index.get_item(sha)
                if item:
                    core.log.debug(f"{LOG_TAG} mark.detected sha={sha}")
                    explain = item.get(K.INDEX.EXPLAIN) or ""
                    updated = merge_gb_explain(explain, mod_id, ts)
                    if updated != explain:
                        core.module.mods_index.item_data_update(sha, {K.INDEX.EXPLAIN: updated})
                        core.log.debug(f"{LOG_TAG} mark.saved sha={sha} mod_id={mod_id}")
                    return
                time.sleep(1.0)
            core.log.warn(f"{LOG_TAG} mark.timeout sha={sha} mod_id={mod_id}")
        finally:
            if hasattr(self, "pending_gb_marks"):
                self.pending_gb_marks.discard(key)

    def _guess_filename(self, url, content_disposition):
        if content_disposition:
            m = re.search(r'filename\\*?=(?:UTF-8\'\')?"?([^\";]+)"?', content_disposition, re.IGNORECASE)
            if m:
                return unquote(m.group(1))
        try:
            path = urlsplit(url).path
            base = os.path.basename(path)
            return unquote(base) if base else None
        except Exception:
            return None

    def _sanitize_filename(self, name):
        if not name:
            return ""
        name = name.strip().strip(".")
        name = re.sub(r'[<>:\"/\\\\|?*]+', "_", name)
        if len(name) > 180:
            name = name[:180]
        return name

    def _ensure_unique_path(self, base_dir, filename):
        path = os.path.join(base_dir, filename)
        if not os.path.exists(path):
            return path
        root, ext = os.path.splitext(filename)
        idx = 1
        while True:
            candidate = os.path.join(base_dir, f"{root}({idx}){ext}")
            if not os.path.exists(candidate):
                return candidate
            idx += 1

# Licensed under the GNU General Public License v3.0
# d3dxSkinManage Plugin: gb_warehouse (Downloader)

import os
import re
import time
import hashlib
import threading
from urllib.parse import urlsplit, unquote

import core
from constant import K


class DownloadMixin:
    def download_and_import(self, url, filename=None, mod_id=None):
        if not url:
            return
        core.log.info(f"(gb_warehouse) 下载请求: url={url} mod_id={mod_id} name={filename}")
        if not hasattr(self, "download_tasks"):
            self.download_tasks = set()
        if url in self.download_tasks:
            core.window.status.set_status("下载任务已存在", 1)
            return

        self.download_tasks.add(url)
        display_name = filename or self._guess_filename(url, None) or "文件"
        core.window.status.set_status(f"正在下载: {display_name}", 0)

        taskpool = getattr(core.construct, "taskpool", None)
        if not taskpool:
            self.download_tasks.discard(url)
            core.window.status.set_status("任务池不可用，无法下载", 1)
            return
        taskpool.newtask(self.async_download_and_import, (url, filename, mod_id), {}, False)

    def async_download_and_import(self, url, filename=None, mod_id=None):
        try:
            path = self._download_file(url, filename)
            if not path:
                self.master.after(0, lambda: core.window.status.set_status("下载失败", 1))
                return
            core.log.info(f"(gb_warehouse) 下载完成: {path}")
            self.master.after(0, lambda: core.window.status.set_status("下载完成，打开导入窗口", 0))
            self.master.after(0, lambda: self._open_import_window(path))
            if mod_id:
                sha = self._calc_sha(path)
                if sha:
                    core.log.info(f"(gb_warehouse) 计算 SHA: {sha}")
                    self._schedule_import_mark(sha, mod_id)
        except Exception as e:
            core.log.error(f"(gb_warehouse) 下载失败: {e}")
            self.master.after(0, lambda: core.window.status.set_status("下载失败", 1))
        finally:
            if hasattr(self, "download_tasks"):
                self.download_tasks.discard(url)

    def _download_file(self, url, filename=None):
        session = getattr(self, "session", None)
        if session is None:
            import requests
            session = requests

        res = session.get(url, timeout=30, stream=True, allow_redirects=True)
        if res.status_code != 200:
            core.log.error(f"(gb_warehouse) 下载状态码异常: {res.status_code}")
            return None

        name = filename or self._guess_filename(url, res.headers.get("content-disposition"))
        name = self._sanitize_filename(name)
        if not name:
            name = "gb_download"

        base_dir = core.env.directory.resources.cache
        os.makedirs(base_dir, exist_ok=True)
        path = self._ensure_unique_path(base_dir, name)

        with open(path, "wb") as f:
            for chunk in res.iter_content(chunk_size=256 * 1024):
                if chunk:
                    f.write(chunk)
        return path

    def _open_import_window(self, path):
        add_mod2 = getattr(core.additional, "add_mod2", None)
        if not add_mod2 or not hasattr(add_mod2, "add_mods"):
            core.window.status.set_status("导入模块不可用", 1)
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
            core.log.error(f"(gb_warehouse) 计算 SHA 失败: {e}")
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
        core.log.info(f"(gb_warehouse) 等待导入完成: sha={sha} id={mod_id} ts={ts}")
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
                    core.log.info(f"(gb_warehouse) 导入完成检测到: sha={sha}")
                    explain = item.get(K.INDEX.EXPLAIN) or ""
                    updated = self._merge_gb_explain(explain, mod_id, ts)
                    if updated != explain:
                        core.module.mods_index.item_data_update(sha, {K.INDEX.EXPLAIN: updated})
                        core.log.info(f"(gb_warehouse) 写入附加信息: sha={sha} id={mod_id}")
                    return
                time.sleep(1.0)
            core.log.warn(f"(gb_warehouse) 等待导入超时: sha={sha} id={mod_id}")
        finally:
            if hasattr(self, "pending_gb_marks"):
                self.pending_gb_marks.discard(key)

    def _merge_gb_explain(self, explain, mod_id, ts):
        line = f"[GB] id={mod_id} last={ts}"
        if not explain:
            return line
        lines = [x for x in explain.splitlines() if x.strip() != ""]
        replaced = False
        for i, l in enumerate(lines):
            if l.strip().startswith("[GB]"):
                lines[i] = line
                replaced = True
                break
        if not replaced:
            lines.append(line)
        return "\n".join(lines)

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

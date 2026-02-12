# Licensed under the GNU General Public License v3.0
# d3dxSkinManage Plugin: gb_warehouse (Update Check)

import re
import time
import threading

import ttkbootstrap
from ttkbootstrap.constants import OUTLINE, NORMAL, DISABLED

import core
import constants as const
from constant import K

CMD_UNLOAD = "--X--"


class UpdateMixin:
    def install_update_hooks(self):
        self._ensure_status_check_label()
        self._ensure_mods_manage_button()
        if getattr(core, "_gb_update_hooks_installed", False):
            return
        core._gb_update_hooks_installed = True
        if not hasattr(core, "gb_updates"):
            core.gb_updates = {"shas": set(), "objects": set()}
        self._patch_mods_manage_methods()

    def _ensure_status_check_label(self):
        status = getattr(core.window, "status", None)
        if not status:
            return
        if hasattr(status, "label_gb_check"):
            try:
                status.label_gb_check.bind("<Button-1>", lambda *_: self.check_gb_updates())
            except Exception:
                pass
            return
        label = ttkbootstrap.Label(status.master, text="[ 检查更新 ]", cursor="hand2")
        label.pack(side="right", padx=(10, 0), pady=5)
        label.bind("<Button-1>", lambda *_: self.check_gb_updates())
        status.label_gb_check = label

    def _ensure_mods_manage_button(self):
        mods_manage = getattr(core.window.interface, "mods_manage", None)
        if not mods_manage:
            return
        if hasattr(mods_manage, "btn_gb_detail"):
            try:
                mods_manage.btn_gb_detail.configure(command=self.open_gb_detail_from_manage)
            except Exception:
                pass
            self._refresh_mods_manage_gb_button()
            return
        btn = ttkbootstrap.Button(
            mods_manage.frame_preview,
            text="打开详情页",
            bootstyle=OUTLINE,
            command=self.open_gb_detail_from_manage,
            state=DISABLED
        )
        try:
            mods_manage.label_SHA.pack_forget()
        except Exception:
            pass
        btn.pack(side="bottom", fill="x", padx=0, pady=(0, 6))
        try:
            mods_manage.label_SHA.pack(side="bottom", fill="x", padx=0, pady=0)
        except Exception:
            pass
        mods_manage.btn_gb_detail = btn
        self._refresh_mods_manage_gb_button()

    def _patch_mods_manage_methods(self):
        mods_manage = getattr(core.window.interface, "mods_manage", None)
        if not mods_manage or getattr(mods_manage, "_gb_update_patched", False):
            return
        mods_manage._gb_update_patched = True

        mods_manage._gb_update_orig_update_objects_list = mods_manage.update_objects_list
        mods_manage._gb_update_orig_update_choices_list = mods_manage.update_choices_list
        mods_manage._gb_update_orig_sbin_update_preview = mods_manage.sbin_update_preview

        def update_objects_list_wrapped(*args, **kwargs):
            mods_manage._gb_update_orig_update_objects_list(*args, **kwargs)
            self._apply_object_highlight(mods_manage)

        def update_choices_list_wrapped(*args, **kwargs):
            mods_manage._gb_update_orig_update_choices_list(*args, **kwargs)
            self._apply_choice_highlight(mods_manage)
            self._refresh_mods_manage_gb_button()

        def sbin_update_preview_wrapped(*args, **kwargs):
            mods_manage._gb_update_orig_sbin_update_preview(*args, **kwargs)
            self._refresh_mods_manage_gb_button()

        mods_manage.update_objects_list = update_objects_list_wrapped
        mods_manage.update_choices_list = update_choices_list_wrapped
        mods_manage.sbin_update_preview = sbin_update_preview_wrapped

    def _apply_object_highlight(self, mods_manage):
        gb_updates = getattr(core, "gb_updates", None)
        updated_objects = gb_updates.get("objects", set()) if isinstance(gb_updates, dict) else set()
        for object_name in mods_manage.treeview_objects.get_children():
            if object_name in updated_objects:
                try:
                    mods_manage.treeview_objects.tag_configure(object_name, foreground="green")
                except Exception:
                    pass
            else:
                try:
                    mods_manage.treeview_objects.tag_configure(object_name, foreground="")
                except Exception:
                    pass

    def _apply_choice_highlight(self, mods_manage):
        gb_updates = getattr(core, "gb_updates", None)
        updated_shas = gb_updates.get("shas", set()) if isinstance(gb_updates, dict) else set()
        for sha in mods_manage.treeview_choices.get_children():
            if sha == CMD_UNLOAD:
                continue
            if sha in updated_shas:
                try:
                    mods_manage.treeview_choices.tag_configure(sha, foreground="green")
                except Exception:
                    pass
            else:
                try:
                    mods_manage.treeview_choices.tag_configure(sha, foreground="")
                except Exception:
                    pass

    def _refresh_mods_manage_gb_button(self):
        mods_manage = getattr(core.window.interface, "mods_manage", None)
        if not mods_manage or not hasattr(mods_manage, "btn_gb_detail"):
            return
        btn = mods_manage.btn_gb_detail
        sha = mods_manage.sbin_get_select_choices()
        if not sha or sha == CMD_UNLOAD:
            try:
                btn.configure(state=DISABLED)
            except Exception:
                pass
            return
        item = core.module.mods_index.get_item(sha)
        if not item:
            try:
                btn.configure(state=DISABLED)
            except Exception:
                pass
            return
        explain = item.get(K.INDEX.EXPLAIN) or ""
        mod_id, _last = self._parse_gb_explain(explain)
        core.log.info(f"(gb_warehouse) 详情按钮检测: sha={sha} mod_id={mod_id} last={_last}")
        try:
            btn.configure(state=NORMAL if mod_id else DISABLED)
        except Exception:
            pass

    def check_gb_updates(self):
        if getattr(self, "_gb_update_running", False):
            core.window.status.set_status("更新检查正在进行中", 1)
            return
        self._gb_update_running = True
        core.window.status.set_status("正在检查更新...", 0)
        core.log.info("(gb_warehouse) 开始检查更新")
        t = threading.Thread(target=self._async_check_gb_updates, daemon=True)
        t.start()

    def _async_check_gb_updates(self):
        updated_shas = set()
        updated_objects = set()
        try:
            targets = self._collect_gb_targets()
            core.log.info(f"(gb_warehouse) 需要检查的 GB Mod 数量: {len(targets)}")
            total = len(targets)
            for idx, (sha, mod_id, last_ts, obj_name) in enumerate(targets, start=1):
                remote_ts = self._fetch_remote_ts(mod_id)
                if remote_ts and remote_ts > last_ts:
                    updated_shas.add(sha)
                    if obj_name:
                        updated_objects.add(obj_name)
                if idx % 3 == 0:
                    msg = f"更新检查中 {idx}/{total}" if total else "更新检查中"
                    self.master.after(0, lambda m=msg: core.window.status.set_status(m, 0))
        finally:
            self.master.after(0, lambda: self._apply_update_results(updated_shas, updated_objects))

    def _collect_gb_targets(self):
        targets = []
        try:
            sha_list = core.module.mods_index.get_all_sha_list()
        except Exception:
            return targets
        for sha in sha_list:
            item = core.module.mods_index.get_item(sha)
            if not item:
                continue
            explain = item.get(K.INDEX.EXPLAIN) or ""
            mod_id, last_ts = self._parse_gb_explain(explain)
            if not mod_id and "[GB]" in explain:
                core.log.warn(f"(gb_warehouse) GB 标记解析失败: sha={sha} explain={explain}")
            if not mod_id or not last_ts:
                continue
            obj_name = item.get(K.INDEX.OBJECT, "")
            targets.append((sha, mod_id, last_ts, obj_name))
        return targets

    def _fetch_remote_ts(self, mod_id):
        try:
            url = const.GB_MOD_API_TMPL.format(mod_id=mod_id)
            res = self.session.get(url, timeout=10)
            if res.status_code != 200:
                core.log.warn(f"(gb_warehouse) 详情请求失败: id={mod_id} status={res.status_code}")
                return 0
            data = res.json()
            return data.get("_tsDateUpdated") or data.get("_tsDateModified") or data.get("_tsDateAdded") or 0
        except Exception:
            core.log.warn(f"(gb_warehouse) 详情请求异常: id={mod_id}")
            return 0

    def _apply_update_results(self, updated_shas, updated_objects):
        try:
            core.gb_updates = {
                "shas": set(updated_shas),
                "objects": set(updated_objects),
            }
            count = len(updated_shas)
            msg = f"更新检查完成：{count} 个有更新" if count else "更新检查完成：未发现更新"
            core.window.status.set_status(msg, 0 if count == 0 else 1)

            mods_manage = getattr(core.window.interface, "mods_manage", None)
            if mods_manage:
                try:
                    mods_manage.update_objects_list()
                    mods_manage.update_choices_list()
                except Exception:
                    pass
        finally:
            self._gb_update_running = False

    def open_gb_detail_from_manage(self, *_):
        mods_manage = getattr(core.window.interface, "mods_manage", None)
        if not mods_manage:
            return
        sha = mods_manage.sbin_get_select_choices()
        if not sha or sha == CMD_UNLOAD:
            return
        item = core.module.mods_index.get_item(sha)
        if not item:
            return
        explain = item.get(K.INDEX.EXPLAIN) or ""
        mod_id, _last = self._parse_gb_explain(explain)
        if not mod_id:
            core.log.warn(f"(gb_warehouse) 打开详情失败: sha={sha} 未找到 GB 标记")
            return

        new_explain = self._merge_gb_explain(explain, mod_id, int(time.time()))
        core.module.mods_index.item_data_update(sha, {K.INDEX.EXPLAIN: new_explain})
        self._clear_update_flag(sha, item.get(K.INDEX.OBJECT, ""))

        warehouse = getattr(core.window.interface, "mods_warehouse", None)
        if not warehouse:
            return
        notebook = getattr(core.window.interface, "notebook", None)
        if notebook and hasattr(warehouse, "master"):
            try:
                notebook.select(warehouse.master)
            except Exception:
                pass
        gb_ctrl = getattr(warehouse, "gb_ctrl", None)
        if gb_ctrl:
            gb_ctrl.load_detail(mod_id)

    def _clear_update_flag(self, sha, obj_name):
        gb_updates = getattr(core, "gb_updates", None)
        if not isinstance(gb_updates, dict):
            return
        shas = gb_updates.get("shas", set())
        if sha in shas:
            shas.discard(sha)
        if obj_name:
            remaining = False
            for other_sha in shas:
                item = core.module.mods_index.get_item(other_sha)
                if item and item.get(K.INDEX.OBJECT) == obj_name:
                    remaining = True
                    break
            if not remaining:
                gb_updates.get("objects", set()).discard(obj_name)
        gb_updates["shas"] = shas
        self._refresh_lists_after_clear()

    def _refresh_lists_after_clear(self):
        mods_manage = getattr(core.window.interface, "mods_manage", None)
        if mods_manage:
            try:
                mods_manage.update_objects_list()
                mods_manage.update_choices_list()
            except Exception:
                pass

    def _parse_gb_explain(self, explain):
        explain = self._normalize_explain(explain)
        match = re.search(r"\[GB\][^\n]*id\s*=\s*(\d+)[^\n]*last\s*=\s*(\d+)", explain, re.IGNORECASE)
        if not match:
            return None, None
        try:
            return int(match.group(1)), int(match.group(2))
        except Exception:
            return None, None

    def _merge_gb_explain(self, explain, mod_id, ts):
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

    def _normalize_explain(self, explain):
        if not explain:
            return ""
        if "\\n" in explain and "\n" not in explain:
            return explain.replace("\\n", "\n")
        return explain

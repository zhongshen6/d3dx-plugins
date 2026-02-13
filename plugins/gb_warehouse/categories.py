# Licensed under the GNU General Public License v3.0
# d3dxSkinManage Plugin: gb_warehouse (Categories)

import json
import os
import re
import threading
import ttkbootstrap
from ttkbootstrap.constants import *

import core
import constants as const


class CategoryMixin:
    _word_table = None
    _word_index = None
    _word_lock = threading.Lock()

    _word_sources = [
        {
            "game": "GI",
            "name": "原神角色",
            "url": "https://api.hakush.in/gi/data/character.json",
            "keys": ["CHS", "EN", "JP", "KR"],
            "clean": False
        },
        {
            "game": "GI",
            "name": "原神武器",
            "url": "https://api.hakush.in/gi/data/weapon.json",
            "keys": ["CHS", "EN", "JP", "KR"],
            "clean": False
        },
        {
            "game": "HSR",
            "name": "星穹铁道角色",
            "url": "https://api.hakush.in/hsr/data/character.json",
            "keys": ["cn", "en", "jp", "kr"],
            "clean": True
        },
        {
            "game": "ZZZ",
            "name": "绝区零角色",
            "url": "https://api.hakush.in/zzz/data/character.json",
            "keys": ["CHS", "EN", "JA", "KO"],
            "clean": False
        },
        {
            "game": "ZZZ",
            "name": "绝区零音擎",
            "url": "https://api.hakush.in/zzz/data/weapon.json",
            "keys": ["CHS", "EN", "JA", "KO"],
            "clean": False
        }
    ]

    def open_category_browser(self):
        root_id = self.get_root_category_id() if hasattr(self, "get_root_category_id") else None
        if not root_id:
            self._pending_open_category = True
            if hasattr(self, "open_game_id_settings"):
                self.open_game_id_settings(force_prompt=True)
            return
        core.log.info(f"(gb_warehouse) 打开子分类列表: root_id={root_id}")

        if getattr(self, "_category_window", None) and self._category_window.winfo_exists():
            try:
                self._category_window.lift()
                self._category_window.focus()
            except Exception:
                pass
            return

        win = ttkbootstrap.Toplevel("GB 子分类")
        self._category_window = win
        win.transient(self.master)
        win.grab_set()
        win.resizable(False, False)

        frame = ttkbootstrap.Frame(win, padding=12)
        frame.pack(fill=BOTH, expand=True)

        label = ttkbootstrap.Label(frame, text=f"根分类 ID：{root_id}")
        label.pack(anchor=W, pady=(0, 6))

        manual_row = ttkbootstrap.Frame(frame)
        manual_row.pack(fill=X, pady=(0, 6))
        manual_label = ttkbootstrap.Label(manual_row, text="手动分类 ID")
        manual_label.pack(side=LEFT)
        manual_entry = ttkbootstrap.Entry(manual_row, width=12)
        manual_entry.pack(side=LEFT, padx=(10, 0))
        manual_btn = ttkbootstrap.Button(
            manual_row,
            text="打开",
            bootstyle=OUTLINE,
            command=lambda: self._open_manual_category(manual_entry.get())
        )
        manual_btn.pack(side=LEFT, padx=(8, 0))

        tree = ttkbootstrap.Treeview(frame, columns=("name", "id", "count"), show="headings", height=14)
        tree.heading("name", text="分类名称")
        tree.heading("id", text="分类 ID")
        tree.heading("count", text="数量")
        tree.column("name", width=220, anchor=W)
        tree.column("id", width=100, anchor=W)
        tree.column("count", width=60, anchor=E)
        tree.pack(fill=BOTH, expand=True)
        self._category_tree = tree

        btn_row = ttkbootstrap.Frame(frame)
        btn_row.pack(fill=X, pady=(8, 0))
        btn_update = ttkbootstrap.Button(btn_row, text="更新翻译表", bootstyle=INFO, command=self._update_words_async)
        btn_open = ttkbootstrap.Button(btn_row, text="打开分类", bootstyle=SUCCESS, command=self._open_selected_category)
        btn_close = ttkbootstrap.Button(btn_row, text="关闭", bootstyle=OUTLINE, command=win.destroy)
        btn_close.pack(side=RIGHT)
        btn_open.pack(side=RIGHT, padx=(0, 8))
        btn_update.pack(side=LEFT)

        tree.bind("<Double-1>", lambda *_: self._open_selected_category(), add="+")

        self._load_subcategories(root_id)
        self._ensure_words_loaded_async()

        try:
            win.update_idletasks()
            core.window.methods.center_window_for_window(win, core.window.mainwindow)
        except Exception:
            pass

    def _load_subcategories(self, root_id):
        taskpool = getattr(core.construct, "taskpool", None)
        if not taskpool:
            return
        token = getattr(self, "_category_token", 0) + 1
        self._category_token = token
        taskpool.newtask(self._async_fetch_subcategories, (root_id, token), {}, False)

    def _async_fetch_subcategories(self, root_id, token):
        try:
            url = const.GB_SUBCATEGORY_URL_TMPL.format(root_id=root_id)
            core.log.info(f"(gb_warehouse) 请求子分类 API: {url}")
            res = self.session.get(url, timeout=10)
            if res.status_code == 200:
                try:
                    payload = res.json()
                except Exception as e:
                    core.log.error(f"(gb_warehouse) 子分类 JSON 解析失败: {e}")
                    self.master.after(0, lambda: self._render_subcategories(token, []))
                    return
                categories = self._parse_subcategories(payload)
                core.log.info(f"(gb_warehouse) 子分类数量: {len(categories)}")
                self.master.after(0, lambda: self._render_subcategories(token, categories))
            else:
                core.log.error(f"(gb_warehouse) 子分类请求失败: status={res.status_code}")
                self.master.after(0, lambda: self._render_subcategories(token, []))
        except Exception as e:
            core.log.error(f"(gb_warehouse) 获取子分类失败: {e}")
            self.master.after(0, lambda: self._render_subcategories(token, []))

    def _parse_subcategories(self, payload):
        items = []
        if isinstance(payload, list):
            items = payload
        elif isinstance(payload, dict):
            items = payload.get("_aRecords") or payload.get("_aSubCategories") or payload.get("aRecords") or []
        else:
            core.log.error(f"(gb_warehouse) 子分类数据类型异常: {type(payload).__name__}")
        results = []
        for item in items:
            if not isinstance(item, dict):
                continue
            name = item.get("_sName") or item.get("name") or ""
            cid = item.get("_idRow") or item.get("id")
            if not cid:
                url = item.get("_sUrl") or item.get("url") or ""
                m = re.search(r"/mods/cats/(\d+)", url)
                if m:
                    cid = m.group(1)
            if not cid:
                continue
            count = item.get("_nItemCount") or item.get("count") or 0
            display_name = self._translate_name(str(name))
            results.append((display_name, int(cid), int(count), str(name)))
        return results

    def _render_subcategories(self, token, categories):
        if token != getattr(self, "_category_token", None):
            return
        tree = getattr(self, "_category_tree", None)
        if not tree or not tree.winfo_exists():
            return
        tree.delete(*tree.get_children())
        for name, cid, count, raw_name in categories:
            item_id = tree.insert("", "end", values=(name, cid, count))
            tree.item(item_id, text=raw_name)
        if not categories:
            tree.insert("", "end", values=("未获取到分类", "", ""))

    def _open_selected_category(self):
        tree = getattr(self, "_category_tree", None)
        if not tree or not tree.winfo_exists():
            return
        focus = tree.focus()
        if not focus:
            return
        values = tree.item(focus).get("values", [])
        if not values or len(values) < 2:
            return
        name = str(values[0])
        try:
            cid = int(values[1])
        except Exception:
            return
        if hasattr(self, "set_list_mode"):
            self.set_list_mode("category", category_id=cid, category_name=name)
        if getattr(self, "_category_window", None) and self._category_window.winfo_exists():
            try:
                self._category_window.destroy()
            except Exception:
                pass

    def _open_manual_category(self, value):
        text = (value or "").strip()
        if not text.isdigit():
            return
        cid = int(text)
        if hasattr(self, "set_list_mode"):
            self.set_list_mode("category", category_id=cid, category_name=f"#{cid}")
        if getattr(self, "_category_window", None) and self._category_window.winfo_exists():
            try:
                self._category_window.destroy()
            except Exception:
                pass

    def _word_file_path(self):
        return os.path.join(os.path.dirname(__file__), "word.json")

    def _clean_hsr_text(self, text):
        if not text or not isinstance(text, str):
            return text
        return re.sub(r'\{RUBY_[BE]#.*?\}', '', text)

    def _normalize_key(self, text):
        if not text:
            return ""
        return text.lower().replace(" ", "").replace("_", "").replace("-", "")

    def _ensure_words_loaded_async(self):
        if self._word_table is not None:
            return
        path = self._word_file_path()
        if os.path.isfile(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self._set_word_table(data)
                return
            except Exception as e:
                core.log.error(f"(gb_warehouse) 读取翻译表失败: {e}")
        self._update_words_async()

    def _set_word_table(self, table):
        if not isinstance(table, list):
            return
        with self._word_lock:
            self._word_table = table
            index = {}
            for entry in table:
                chs = entry.get("chs")
                alts = entry.get("alts") or []
                if not chs:
                    continue
                for alt in alts:
                    key = self._normalize_key(alt)
                    if not key:
                        continue
                    # longest match wins
                    prev = index.get(key)
                    if not prev or len(alt) > prev[1]:
                        index[key] = (chs, len(alt))
            self._word_index = {k: v[0] for k, v in index.items()}

    def _update_words_async(self):
        t = threading.Thread(target=self._update_words_json, daemon=True)
        t.start()

    def _update_words_json(self):
        core.log.info("(gb_warehouse) 开始更新翻译表")
        new_table = []
        seen = set()
        try:
            import requests
            for src in self._word_sources:
                res = requests.get(src["url"], timeout=15)
                if res.status_code != 200:
                    core.log.error(f"(gb_warehouse) 翻译表获取失败: {src['name']} status={res.status_code}")
                    continue
                data = res.json()
                for entry_id in data:
                    item = data[entry_id]
                    chs_key = "CHS" if "CHS" in item else ("cn" if "cn" in item else None)
                    if not chs_key:
                        continue
                    chs_name = item.get(chs_key)
                    if src["clean"]:
                        chs_name = self._clean_hsr_text(chs_name)
                    if not chs_name or chs_name in seen:
                        continue
                    alts = []
                    for k in src["keys"]:
                        val = item.get(k)
                        if val:
                            if src["clean"]:
                                val = self._clean_hsr_text(val)
                            alts.append(val)
                    if alts:
                        new_table.append({"chs": chs_name, "alts": list(set(alts))})
                        seen.add(chs_name)
        except Exception as e:
            core.log.error(f"(gb_warehouse) 更新翻译表失败: {e}")
            return

        if not new_table:
            core.log.error("(gb_warehouse) 翻译表为空")
            return
        try:
            with open(self._word_file_path(), "w", encoding="utf-8") as f:
                json.dump(new_table, f, ensure_ascii=False, indent=2)
        except Exception as e:
            core.log.error(f"(gb_warehouse) 保存翻译表失败: {e}")
            return

        self._set_word_table(new_table)
        core.log.info(f"(gb_warehouse) 翻译表更新完成: {len(new_table)} 条")
        try:
            self.master.after(0, lambda: self._refresh_category_names())
        except Exception:
            pass

    def _translate_name(self, name):
        key = self._normalize_key(name)
        if not key or not self._word_index:
            return name
        return self._word_index.get(key, name)

    def _refresh_category_names(self):
        tree = getattr(self, "_category_tree", None)
        if not tree or not tree.winfo_exists():
            return
        for item_id in tree.get_children():
            raw = tree.item(item_id).get("text", "")
            if not raw or raw == "未获取到分类":
                continue
            translated = self._translate_name(raw)
            try:
                tree.set(item_id, "name", translated)
            except Exception:
                pass

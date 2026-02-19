import json
import os
import re
import threading
import ttkbootstrap
from ttkbootstrap.constants import *
import core
import constants as const
from utils import safe_call, safe_after
LOG_TAG = "(gb_warehouse/category)"
class CategoryMixin:
    _word_table = None
    _word_index = None
    _word_lock = threading.Lock()
    _word_update_running = False
    _word_games = (
        ("genshin", "原神"),
        ("starrail", "星穹铁道"),
    )
    _word_langs = ("chs", "en", "jp")
    def _close_category_window(self):
        win = getattr(self, "_category_window", None)
        if win and win.winfo_exists():
            safe_call(win.destroy)

    def _apply_category(self, cid, name):
        if hasattr(self, "set_list_mode"):
            self.set_list_mode("category", category_id=cid, category_name=name)
        self._close_category_window()

    def open_category_browser(self):
        root_id = self.get_root_category_id() if hasattr(self, "get_root_category_id") else None
        if not root_id:
            self._pending_open_category = True
            if hasattr(self, "open_game_id_settings"):
                self.open_game_id_settings(force_prompt=True)
            return
        core.log.debug(f"{LOG_TAG} browser.open root_id={root_id}")

        if getattr(self, "_category_window", None) and self._category_window.winfo_exists():
            safe_call(self._category_window.lift)
            safe_call(self._category_window.focus)
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
        self._category_btn_update = btn_update
        btn_open = ttkbootstrap.Button(btn_row, text="打开分类", bootstyle=SUCCESS, command=self._open_selected_category)
        btn_close = ttkbootstrap.Button(btn_row, text="关闭", bootstyle=OUTLINE, command=win.destroy)
        btn_close.pack(side=RIGHT)
        btn_open.pack(side=RIGHT, padx=(0, 8))
        btn_update.pack(side=LEFT)
        if self._word_update_running:
            safe_call(btn_update.configure, state=DISABLED)

        tree.bind("<Double-1>", lambda *_: self._open_selected_category(), add="+")

        self._load_subcategories(root_id)
        self._ensure_words_loaded_async()

        safe_call(win.update_idletasks)
        safe_call(core.window.methods.center_window_for_window, win, core.window.mainwindow)

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
            core.log.debug(f"{LOG_TAG} subcat.request root_id={root_id}")
            res = self.session.get(url, timeout=10)
            if res.status_code == 200:
                try:
                    payload = res.json()
                except Exception as e:
                    core.log.warn(f"{LOG_TAG} subcat.json_error root_id={root_id} err={e}")
                    self.master.after(0, lambda: self._render_subcategories(token, []))
                    return
                categories = self._parse_subcategories(payload)
                core.log.debug(f"{LOG_TAG} subcat.loaded root_id={root_id} count={len(categories)}")
                self.master.after(0, lambda: self._render_subcategories(token, categories))
            else:
                core.log.warn(f"{LOG_TAG} subcat.http_error root_id={root_id} status={res.status_code}")
                self.master.after(0, lambda: self._render_subcategories(token, []))
        except Exception as e:
            core.log.error(f"{LOG_TAG} subcat.exception root_id={root_id} err={e}")
            self.master.after(0, lambda: self._render_subcategories(token, []))

    def _parse_subcategories(self, payload):
        items = []
        if isinstance(payload, list):
            items = payload
        elif isinstance(payload, dict):
            items = payload.get("_aRecords") or payload.get("_aSubCategories") or payload.get("aRecords") or []
        else:
            core.log.warn(f"{LOG_TAG} subcat.invalid_payload type={type(payload).__name__}")
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
        self._apply_category(cid, name)

    def _open_manual_category(self, value):
        text = (value or "").strip()
        if not text.isdigit():
            return
        cid = int(text)
        self._apply_category(cid, f"#{cid}")

    def _word_file_path(self):
        return os.path.join(os.path.dirname(__file__), "word.json")

    def _set_category_update_button_state(self, enabled):
        btn = getattr(self, "_category_btn_update", None)
        if not btn or not btn.winfo_exists():
            return
        try:
            if enabled:
                btn.configure(state=NORMAL, text="更新翻译表")
            else:
                btn.configure(state=DISABLED, text="更新中...")
        except Exception:
            pass

    def _word_dict_url(self, game, lang):
        return f"https://api.uigf.org/dict/{game}/{lang}.json"

    def _fetch_word_dict(self, game, lang):
        import requests

        url = self._word_dict_url(game, lang)
        try:
            res = requests.get(url, timeout=15)
        except Exception as e:
            core.log.debug(f"{LOG_TAG} dict.request_failed game={game} lang={lang} err={e}")
            return None

        if res.status_code != 200:
            core.log.debug(f"{LOG_TAG} dict.http_error game={game} lang={lang} status={res.status_code}")
            return None
        try:
            data = res.json()
        except Exception as e:
            core.log.debug(f"{LOG_TAG} dict.json_error game={game} lang={lang} err={e}")
            return None

        if not isinstance(data, dict):
            core.log.debug(f"{LOG_TAG} dict.invalid_payload game={game} lang={lang} type={type(data).__name__}")
            return None
        return data

    def _invert_name_id_map(self, name_to_id, game, lang):
        id_to_name = {}
        for name, item_id in name_to_id.items():
            if not isinstance(name, str):
                continue
            name = name.strip()
            if not name:
                continue
            try:
                item_id = int(item_id)
            except Exception:
                continue
            if item_id not in id_to_name:
                id_to_name[item_id] = name
        core.log.debug(f"{LOG_TAG} dict.loaded game={game} lang={lang} count={len(id_to_name)}")
        return id_to_name

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
                core.log.warn(f"{LOG_TAG} dict.local_read_failed err={e}")
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
                    prev = index.get(key)
                    if not prev or len(alt) > prev[1]:
                        index[key] = (chs, len(alt))
            self._word_index = {k: v[0] for k, v in index.items()}

    def _update_words_async(self):
        if self._word_update_running:
            return
        self._word_update_running = True
        self._set_category_update_button_state(False)
        t = threading.Thread(target=self._update_words_json, daemon=True)
        t.start()

    def _finish_update_words(self):
        self._word_update_running = False
        self._set_category_update_button_state(True)

    def _update_words_json(self):
        total_steps = max(1, len(self._word_games) * len(self._word_langs))
        current_step = 0

        def _status(message, level=0):
            safe_after(self.master, 0, self._set_status, message, level)

        def _progress(value):
            safe_after(self.master, 0, self._set_progress, value)

        try:
            core.log.info(f"{LOG_TAG} dict.update_start")
            _status("正在更新翻译表...", 2)
            _progress(0)
            new_table = []
            entry_by_chs = {}
            for game, game_name in self._word_games:
                lang_maps = {}
                for lang in self._word_langs:
                    payload = self._fetch_word_dict(game, lang)
                    current_step += 1
                    _progress(int(current_step * 100 / total_steps))
                    if payload is None:
                        continue
                    id_map = self._invert_name_id_map(payload, game, lang)
                    if id_map:
                        lang_maps[lang] = id_map

                if not lang_maps:
                    core.log.warn(f"{LOG_TAG} dict.game_unavailable game={game_name}")
                    continue

                missing = [lang for lang in self._word_langs if lang not in lang_maps]
                if missing:
                    core.log.warn(f"{LOG_TAG} dict.partial game={game_name} missing={','.join(missing)}")

                all_ids = set()
                for id_map in lang_maps.values():
                    all_ids.update(id_map.keys())

                for item_id in sorted(all_ids):
                    name_chs = lang_maps.get("chs", {}).get(item_id)
                    name_en = lang_maps.get("en", {}).get(item_id)
                    name_jp = lang_maps.get("jp", {}).get(item_id)

                    chs_name = name_chs or name_jp or name_en
                    if not chs_name:
                        continue

                    alts = []
                    for val in (name_chs, name_en, name_jp):
                        if val and val not in alts:
                            alts.append(val)
                    if not alts:
                        continue

                    entry = entry_by_chs.get(chs_name)
                    if entry is None:
                        entry = {"chs": chs_name, "alts": list(alts)}
                        entry_by_chs[chs_name] = entry
                        new_table.append(entry)
                    else:
                        for val in alts:
                            if val not in entry["alts"]:
                                entry["alts"].append(val)
            if not new_table:
                core.log.error(f"{LOG_TAG} dict.empty_after_merge")
                _status("翻译表更新失败: 结果为空", 1)
                return
            try:
                with open(self._word_file_path(), "w", encoding="utf-8") as f:
                    json.dump(new_table, f, ensure_ascii=False, indent=2)
            except Exception as e:
                core.log.error(f"{LOG_TAG} dict.save_failed err={e}")
                _status("翻译表更新失败: 保存失败", 1)
                return

            self._set_word_table(new_table)
            core.log.info(f"{LOG_TAG} dict.update_done count={len(new_table)}")
            _status(f"翻译表更新完成: {len(new_table)} 条", 0)
            _progress(100)
            if safe_after(self.master, 1200, self._set_progress, 0) is None:
                self._set_progress(0)
            safe_after(self.master, 0, self._refresh_category_names)
        except Exception as e:
            core.log.error(f"{LOG_TAG} dict.update_failed err={e}")
            _status("翻译表更新失败", 1)
            _progress(0)
        finally:
            if safe_after(self.master, 0, self._finish_update_words) is None:
                self._finish_update_words()

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
            safe_call(tree.set, item_id, "name", translated)

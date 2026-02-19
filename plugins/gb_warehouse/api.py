# Licensed under the GNU General Public License v3.0
# d3dxSkinManage Plugin: gb_warehouse (API)

import core

import constants as const

LOG_TAG = "(gb_warehouse/api)"


class ApiMixin:
    def async_fetch_json(self, page, prefetch=False, game_id=None, mode="list", query=None, category_id=None):
        try:
            if game_id is None:
                getter = getattr(self, "get_game_id", None)
                if callable(getter):
                    game_id = getter()
            if not game_id:
                game_id = const.DEFAULT_GAME_ID
            url, params = self._build_list_request(game_id, page, mode, query, category_id)
            core.log.debug(
                f"{LOG_TAG} list.request mode={mode} game_id={game_id} page={page} prefetch={int(bool(prefetch))}"
            )
            res = self.session.get(url, params=params, timeout=10)
            if res.status_code == 200:
                payload = res.json()
                records = payload.get("_aRecords", [])
                meta = payload.get("_aMetadata", {})
                page_count = meta.get("_nPageCount") or meta.get("_nPages")
                self.master.after(0, lambda: self.on_page_loaded(page, records, page_count, prefetch, game_id, mode, query, category_id))
                self.master.after(0, lambda: self.hide_retry_notice() if hasattr(self, "hide_retry_notice") else None)
                if not prefetch:
                    self.master.after(0, lambda: self._set_status(f"列表已更新，第 {page} 页", 0))
            else:
                if prefetch:
                    self.prefetching_pages.discard(page)
                core.log.warn(f"{LOG_TAG} list.http_error status={res.status_code} page={page} prefetch={int(bool(prefetch))}")
                if not prefetch:
                    self.master.after(0, lambda: self._set_status(f"列表加载失败: {res.status_code}", 1))
                if not prefetch and hasattr(self, "show_retry_notice"):
                    self.master.after(0, lambda: self.show_retry_notice(f"连接 GB 失败: {res.status_code}", page))
        except Exception as e:
            if prefetch:
                self.prefetching_pages.discard(page)
            core.log.warn(f"{LOG_TAG} list.exception page={page} prefetch={int(bool(prefetch))} err={e}")
            if not prefetch:
                self.master.after(0, lambda: self._set_status("列表加载失败: 网络异常", 1))
            if not prefetch and hasattr(self, "show_retry_notice"):
                self.master.after(0, lambda: self.show_retry_notice("连接 GB 失败", page))

    def _build_list_request(self, game_id, page, mode, query, category_id):
        if mode == "search":
            return const.GB_SEARCH_URL, {
                "_sOrder": "best_match",
                "_idGameRow": game_id,
                "_sSearchString": query or "",
                "_nPage": page,
            }
        if mode == "category":
            return const.GB_CATEGORY_LIST_URL, {
                "_nPerpage": const.GB_LIST_PERPAGE,
                "_aFilters[Generic_Category]": int(category_id or 0),
                "_nPage": page,
            }
        return const.GB_API_URL_TMPL.format(game_id=game_id, page=page), None

    def async_fetch_detail(self, mod_id, token):
        try:
            url = const.GB_MOD_API_TMPL.format(mod_id=mod_id)
            core.log.debug(f"{LOG_TAG} detail.request mod_id={mod_id} token={token}")
            res = self.session.get(url, timeout=10)
            if res.status_code == 200:
                try:
                    data = res.json()
                except Exception as e:
                    core.log.warn(f"{LOG_TAG} detail.json_error mod_id={mod_id} err={e}")
                    self.master.after(0, lambda: self.show_detail_error("详情解析失败"))
                    return
                core.log.debug(f"{LOG_TAG} detail.ok mod_id={mod_id}")
                self.master.after(0, lambda: self.on_detail_loaded(token, data))
            else:
                core.log.warn(f"{LOG_TAG} detail.http_error mod_id={mod_id} status={res.status_code}")
                self.master.after(0, lambda: self.show_detail_error(f"详情加载失败: {res.status_code}"))
        except Exception as e:
            core.log.warn(f"{LOG_TAG} detail.exception mod_id={mod_id} err={e}")
            self.master.after(0, lambda: self.show_detail_error("详情加载失败"))

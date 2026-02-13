# Licensed under the GNU General Public License v3.0
# d3dxSkinManage Plugin: gb_warehouse (API)

import core

import constants as const


class ApiMixin:
    def async_fetch_json(self, page, prefetch=False, game_id=None):
        try:
            if game_id is None:
                getter = getattr(self, "get_game_id", None)
                if callable(getter):
                    game_id = getter()
            if not game_id:
                game_id = const.DEFAULT_GAME_ID
            url = const.GB_API_URL_TMPL.format(game_id=game_id, page=page)
            core.log.info(f"(gb_warehouse) 请求列表 API: game_id={game_id} page={page} prefetch={prefetch}")
            res = self.session.get(url, timeout=10)
            if res.status_code == 200:
                payload = res.json()
                records = payload.get("_aRecords", [])
                meta = payload.get("_aMetadata", {})
                page_count = meta.get("_nPageCount") or meta.get("_nPages")
                self.master.after(0, lambda: self.on_page_loaded(page, records, page_count, prefetch, game_id))
                self.master.after(0, lambda: self.hide_retry_notice() if hasattr(self, "hide_retry_notice") else None)
                self.master.after(0, lambda: core.window.status.set_status("高清列表同步成功", 0))
            else:
                if prefetch:
                    self.prefetching_pages.discard(page)
                self.master.after(0, lambda: core.window.status.set_status(f"API 异常: {res.status_code}", 1))
                if not prefetch and hasattr(self, "show_retry_notice"):
                    self.master.after(0, lambda: self.show_retry_notice(f"连接 GB 失败: {res.status_code}", page))
        except Exception as e:
            if prefetch:
                self.prefetching_pages.discard(page)
            core.log.error(f"(gb_warehouse) 获取 JSON 失败: {e}")
            self.master.after(0, lambda: core.window.status.set_status("连接 GB 失败", 1))
            if not prefetch and hasattr(self, "show_retry_notice"):
                self.master.after(0, lambda: self.show_retry_notice("连接 GB 失败", page))

    def async_fetch_detail(self, mod_id, token):
        try:
            url = const.GB_MOD_API_TMPL.format(mod_id=mod_id)
            core.log.info(f"(gb_warehouse) 请求详情 API: {url}")
            res = self.session.get(url, timeout=10)
            if res.status_code == 200:
                try:
                    data = res.json()
                except Exception as e:
                    core.log.error(f"(gb_warehouse) 详情 JSON 解析失败: {e}")
                    self.master.after(0, lambda: self.show_detail_error("详情解析失败"))
                    return
                core.log.info(f"(gb_warehouse) 详情 API 成功: id={mod_id}")
                self.master.after(0, lambda: self.on_detail_loaded(token, data))
            else:
                core.log.error(f"(gb_warehouse) 详情 API 失败: id={mod_id} status={res.status_code}")
                self.master.after(0, lambda: self.show_detail_error(f"详情加载失败: {res.status_code}"))
        except Exception as e:
            core.log.error(f"(gb_warehouse) 获取详情失败: {e}")
            self.master.after(0, lambda: self.show_detail_error("详情加载失败"))

# Licensed under the GNU General Public License v3.0
# d3dxSkinManage Plugin: gb_warehouse (List UI)

import io
import tkinter.font as tkfont

import PIL.Image
import PIL.ImageTk
import ttkbootstrap
from ttkbootstrap.constants import *

import core
import constants as const
from utils import DebouncedCall, format_ts


class GBListItem(ttkbootstrap.Frame):
    """单个 Mod 列表项组件 - 支持响应式宽度和换行"""

    def __init__(self, master, data, on_image_click=None):
        super().__init__(master, bootstyle=SECONDARY)
        self.data = data
        self._on_image_click = on_image_click
        self.is_destroyed = False
        self._wrap_debounce = DebouncedCall(
            self,
            const.RESIZE_DEBOUNCE_MS,
            lambda: const.UI_RESIZE_PAUSED,
        )

        # 主容器：fill=X 确保宽度随父容器变化
        self.container = ttkbootstrap.Frame(self, padding=10, bootstyle=SECONDARY)
        self.container.pack(fill=X, padx=5, pady=5)

        # 左侧大图容器 - 固定 450x250
        self.img_container = ttkbootstrap.Frame(
            self.container,
            width=const.LIST_THUMB_W,
            height=const.LIST_THUMB_H
        )
        self.img_container.pack(side=LEFT)
        self.img_container.pack_propagate(False)

        self.cover_label = ttkbootstrap.Label(
            self.img_container,
            text="正在加载封面...",
            anchor=CENTER,
            bootstyle="secondary-inverse"
        )
        self.cover_label.pack(fill=BOTH, expand=True)
        self.img_container.configure(cursor="hand2")
        self.cover_label.configure(cursor="hand2")
        self.img_container.bind("<Button-1>", self.on_image_click)
        self.cover_label.bind("<Button-1>", self.on_image_click)

        # 信息区域 - 采用垂直堆叠布局
        self.info_frame = ttkbootstrap.Frame(self.container, bootstyle=SECONDARY, padding=(20, 10))
        self.info_frame.pack(side=LEFT, fill=BOTH, expand=True)

        # 1. Mod 名称
        name = data.get("_sName", "Unknown Mod")
        self.name_label = ttkbootstrap.Label(self.info_frame, text=name, font=("", 12, "bold"), bootstyle=LIGHT)
        self.name_label.pack(side=TOP, anchor=W, pady=(0, 5))
        self.name_text = name
        self.name_font = tkfont.Font(font=self.name_label.cget("font"))

        # 2. 作者与浏览量 (移除了点赞)
        submitter = data.get("_aSubmitter", {})
        author = submitter.get("_sName", "Anon") if isinstance(submitter, dict) else "Anon"
        views = data.get("_nViewCount", 0)

        ts = data.get("_tsDateUpdated") or data.get("_tsDateModified") or data.get("_tsDateAdded")
        updated = format_ts(ts)
        detail_text = f"👤{author}\n👁️{views}\n🕒{updated}"
        self.detail_label = ttkbootstrap.Label(
            self.info_frame,
            text=detail_text,
            font=("", 10),
            bootstyle=INFO,
            justify=LEFT
        )
        self.detail_label.pack(side=TOP, anchor=W, pady=(0, 15))

        # 监听信息区域大小变化，动态调整文字换行宽度
        self.info_frame.bind("<Configure>", self.on_info_resize)

    def on_info_resize(self, event):
        """动态更新标签的换行宽度"""
        new_wraplength = event.width - 40  # 预留边距
        if new_wraplength <= 100:
            return
        self._wrap_debounce.schedule(new_wraplength, self.apply_info_resize)

    def apply_info_resize(self, new_wraplength):
        if self.is_destroyed:
            return
        if not new_wraplength:
            return
        self.name_label.configure(wraplength=new_wraplength)
        self.detail_label.configure(wraplength=new_wraplength)
        self.update_name_ellipsis(new_wraplength)

    def update_name_ellipsis(self, wraplength):
        text = self.name_text or ""
        if not text:
            return

        idx = 0
        lines = []
        for _ in range(2):
            current = ""
            while idx < len(text):
                ch = text[idx]
                if self.name_font.measure(current + ch) <= wraplength:
                    current += ch
                    idx += 1
                else:
                    break
            lines.append(current)
            if idx >= len(text):
                break

        if idx < len(text):
            ellipsis = "…"
            last = lines[-1] if lines else ""
            while last and self.name_font.measure(last + ellipsis) > wraplength:
                last = last[:-1]
            lines[-1] = (last + ellipsis) if last else ellipsis

        self.name_label.configure(text="\n".join(lines[:2]))

    def update_image(self, tk_img):
        if self.is_destroyed:
            return
        try:
            self.cover_label.configure(image=tk_img, text="")
            self.image_ref = tk_img
        except Exception:
            pass

    def on_image_click(self, _event=None):
        if self._on_image_click:
            self._on_image_click(self.data)

    def destroy(self):
        self.is_destroyed = True
        self._wrap_debounce.cancel()
        super().destroy()


class ListMixin:
    def on_item_image_click(self, record):
        mod_id = record.get("_idRow")
        name = record.get("_sName", "")
        core.log.info(f"(gb_warehouse) 详情点击: id={mod_id} name={name}")
        if not mod_id:
            core.log.error("(gb_warehouse) 详情点击缺少 mod_id")
            return
        self.load_detail(mod_id)

    def update_page_label(self):
        if self.page_count:
            self.page_label.configure(text=f"第 {self.current_page} / {self.page_count} 页")
        else:
            self.page_label.configure(text=f"第 {self.current_page} 页")
        self.btn_prev.configure(state=DISABLED if self.current_page <= 1 else NORMAL)
        if self.page_count:
            self.btn_next.configure(state=DISABLED if self.current_page >= self.page_count else NORMAL)
        else:
            self.btn_next.configure(state=NORMAL)

    def go_prev_page(self):
        if self.current_page <= 1:
            return
        self.load_page(self.current_page - 1)

    def go_next_page(self):
        if self.page_count and self.current_page >= self.page_count:
            return
        self.load_page(self.current_page + 1)

    def prefetch_next_page(self):
        next_page = self.current_page + 1
        if self.page_count and next_page > self.page_count:
            return
        self.prefetch_page(next_page)

    def prefetch_page(self, page):
        if page < 1 or page in self.page_cache or page in self.prefetching_pages:
            return
        self.prefetching_pages.add(page)
        game_id = self.get_game_id() if hasattr(self, "get_game_id") else const.DEFAULT_GAME_ID
        core.construct.taskpool.newtask(self.async_fetch_json, (page, True, game_id), {}, False)

    def trigger_load(self):
        self.load_page(1)

    def load_page(self, page):
        if page < 1:
            return
        if hasattr(self, "hide_retry_notice"):
            try:
                self.hide_retry_notice()
            except Exception:
                pass
        self.current_page = page
        if page in self.page_cache:
            self.render_list(self.page_cache[page], page)
            if self.is_visible:
                self.prefetch_next_page()
            return
        core.window.status.set_status(f"正在同步高清仓库列表... 第 {page} 页", 0)
        game_id = self.get_game_id() if hasattr(self, "get_game_id") else const.DEFAULT_GAME_ID
        core.construct.taskpool.newtask(self.async_fetch_json, (page, False, game_id), {}, False)

    def on_page_loaded(self, page, records, page_count=None, prefetch=False, game_id=None):
        if game_id and hasattr(self, "get_game_id") and game_id != self.get_game_id():
            return
        if page_count:
            self.page_count = page_count
        self.page_cache[page] = records
        if page in self.prefetching_pages:
            self.prefetching_pages.discard(page)
        if prefetch:
            self.update_page_label()
            core.construct.taskpool.newtask(self.prefetch_images, (records,), {}, False)
            return
        self.render_list(records, page)
        if self.is_visible:
            self.prefetch_next_page()

    def render_list(self, records, page=None):
        if page is not None:
            self.current_page = page
            self.update_page_label()
        for item in self.items:
            try:
                item.destroy()
            except Exception:
                pass
        self.items = []

        for rec in records:
            item_widget = GBListItem(self.scroll_frame, rec, self.on_item_image_click)
            item_widget.pack(side=TOP, fill=X, padx=15, pady=8)
            self.items.append(item_widget)

        self.scroll_frame.bin_update()
        self.scroll_frame.w_canvas.yview_moveto(0)
        self.scroll_frame.bin_child_widgets_bind()
        core.construct.taskpool.newtask(self.parallel_load_images, (records,), {}, False)

    def parallel_load_images(self, records):
        for item_widget, rec in zip(self.items, records):
            core.construct.taskpool.newtask(self.fetch_list_image, (rec, item_widget), {}, False)

    def prefetch_images(self, records):
        for rec in records:
            core.construct.taskpool.newtask(self.fetch_list_image, (rec,), {}, False)

    def build_img_url(self, record):
        media = record.get("_aPreviewMedia", {}).get("_aImages", [])
        if not media:
            return None
        img = media[0]
        base = img.get("_sBaseUrl")
        file_name = img.get("_sFile530") or img.get("_sFile220") or img.get("_sFile") or img.get("_sFile100")
        if not base or not file_name:
            return None
        return f"{base}/{file_name}"

    def fetch_processed_image(self, img_url):
        res = self.session.get(img_url, timeout=15)
        if res.status_code != 200:
            return None
        pil_img = PIL.Image.open(io.BytesIO(res.content))
        return core.module.image.image_canvas(pil_img, const.LIST_THUMB_W, const.LIST_THUMB_H, tkimg=False)

    def apply_cached_image(self, item_widget, img_url, pil_img):
        if item_widget.is_destroyed:
            return
        tk_img = self.tk_image_cache.get(img_url)
        if tk_img is None:
            tk_img = PIL.ImageTk.PhotoImage(pil_img)
            self.tk_image_cache[img_url] = tk_img
        item_widget.update_image(tk_img)

    def fetch_list_image(self, record, item_widget=None):
        try:
            img_url = self.build_img_url(record)
            if not img_url:
                return
            if item_widget is not None and item_widget.is_destroyed:
                return
            cached = self.image_cache.get(img_url)
            if cached is None:
                cached = self.fetch_processed_image(img_url)
                if cached is not None:
                    self.image_cache[img_url] = cached
            if cached is not None and item_widget is not None:
                self.master.after(0, lambda: self.apply_cached_image(item_widget, img_url, cached))
        except Exception as e:
            core.log.debug(f"(gb_warehouse) 图片获取失败: {e}")

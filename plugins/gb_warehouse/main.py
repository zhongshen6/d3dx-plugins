# Licensed under the GNU General Public License v3.0
# d3dxSkinManage Plugin: gb_warehouse (High-Def Responsive List Edition)

import os
import sys

import requests
import urllib3
import ttkbootstrap
from ttkbootstrap.constants import *
from requests.adapters import HTTPAdapter

import core
import widgets
from window.interface.mods_warehouse import ModsWarehouse

# Ensure local modules can be imported when loaded by path
_PLUGIN_DIR = os.path.dirname(__file__)
if _PLUGIN_DIR not in sys.path:
    sys.path.insert(0, _PLUGIN_DIR)

import constants as const
from api import ApiMixin
from downloader import DownloadMixin
from update_check import UpdateMixin
from ui_list import ListMixin
from ui_detail import DetailMixin

__version__ = "v1.4.1"

# 抑制 InsecureRequestWarning 警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class GBListUI(ListMixin, DetailMixin, ApiMixin, DownloadMixin, UpdateMixin):
    """列表 UI 控制器"""

    def __init__(self, warehouse_instance):
        self.instance = warehouse_instance
        self.master = warehouse_instance.master
        self.items = []
        self.canvas_window_id = None
        self._resize_job = None
        self._pending_layout_w = None
        self._pending_canvas_w = None
        self.current_page = 1
        self.page_count = None
        self.page_cache = {}
        self.image_cache = {}
        self.tk_image_cache = {}
        self.prefetching_pages = set()
        self.is_visible = False
        self._notebook_bound = False
        self.current_detail_id = None
        self.current_detail_url = ""
        self._detail_request_id = 0
        self.detail_image_urls = []
        self.detail_image_cache = {}
        self.detail_image_fetching = set()
        self.detail_image_index = 0
        self._pending_detail_w = None
        self._pending_detail_h = None
        self._pending_detail_text_w = None
        self._pending_download_w = None
        self.download_buttons = []
        self.download_empty = None
        self.download_tasks = set()
        self._last_failed_page = None

        self.session = requests.Session()
        self.session.trust_env = False
        self.session.verify = False
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
            "Connection": "keep-alive"
        })
        adapter = HTTPAdapter(pool_connections=20, pool_maxsize=30)
        self.session.mount("https://", adapter)

    def setup_ui(self):
        for widget in self.master.winfo_children():
            try:
                widget.destroy()
            except Exception:
                pass

        self.Frame_main = ttkbootstrap.Frame(self.master)
        self.Frame_main.pack(fill=BOTH, expand=True, padx=10, pady=10)

        # Panels: list (left), details (middle), downloads (right)
        self.Frame_list = ttkbootstrap.Frame(self.Frame_main, bootstyle=SECONDARY, width=const.LIST_BASE_W)
        self.Frame_detail = ttkbootstrap.Frame(self.Frame_main, bootstyle=SECONDARY, width=const.DETAIL_BASE_W)
        self.Frame_download = ttkbootstrap.Frame(self.Frame_main, bootstyle=SECONDARY, width=const.DOWNLOAD_W)

        for panel in (self.Frame_list, self.Frame_detail, self.Frame_download):
            panel.pack_propagate(False)

        self.Frame_list.pack(side=LEFT, fill=BOTH, expand=False)
        self.Frame_detail.pack(side=LEFT, fill=BOTH, expand=False)
        self.Frame_download.pack(side=RIGHT, fill=BOTH, expand=False)
        self.Frame_detail.bind("<Configure>", self.on_detail_resize, add="+")
        self.Frame_download.bind("<Configure>", self.on_download_resize, add="+")

        self.Frame_pager = ttkbootstrap.Frame(self.Frame_list, padding=(10, 6))
        self.Frame_pager.pack(side=BOTTOM, fill=X)

        self.btn_prev = ttkbootstrap.Button(
            self.Frame_pager,
            text="上一页",
            bootstyle=OUTLINE,
            width=8,
            command=self.go_prev_page
        )
        self.page_label = ttkbootstrap.Label(self.Frame_pager, text="第 1 页")
        self.btn_next = ttkbootstrap.Button(
            self.Frame_pager,
            text="下一页",
            bootstyle=OUTLINE,
            width=8,
            command=self.go_next_page
        )
        self.btn_prev.pack(side=LEFT)
        self.page_label.pack(side=LEFT, padx=10)
        self.btn_next.pack(side=LEFT)
        self.update_page_label()

        self.list_notice = ttkbootstrap.Frame(self.Frame_list, padding=(10, 6))
        self.list_notice_label = ttkbootstrap.Label(self.list_notice, text="连接 GB 失败", bootstyle=WARNING)
        self.list_notice_retry = ttkbootstrap.Button(
            self.list_notice,
            text="重试",
            bootstyle=OUTLINE,
            width=8,
            command=self.retry_load
        )
        self.list_notice_label.pack(side=LEFT, fill=X, expand=True)
        self.list_notice_retry.pack(side=RIGHT)

        self.scroll_frame = widgets.ScrollFrame(self.Frame_list, scb_pad=5)
        self.scroll_frame.pack(fill=BOTH, expand=True)
        self.canvas_window_id = self.scroll_frame.w_canvas.find_all()[0]
        self.scroll_frame.w_canvas.bind("<Configure>", self.on_canvas_resize, add="+")
        self.Frame_main.bind("<Configure>", self.on_layout_resize, True)

        # Detail area (image + text)
        self.detail_inner = ttkbootstrap.Frame(self.Frame_detail, padding=12)
        self.detail_inner.pack(fill=BOTH, expand=True)

        self.detail_image_block = ttkbootstrap.Frame(self.detail_inner)
        self.detail_image_block.pack(fill=X)
        self.detail_image_block.pack_propagate(False)

        self.detail_image_outer = ttkbootstrap.Frame(self.detail_image_block)
        self.detail_image_outer.pack(fill=BOTH, expand=True)
        self.detail_image_outer.pack_propagate(False)

        self.detail_image_label = ttkbootstrap.Label(
            self.detail_image_outer,
            text="暂无图片",
            anchor=CENTER,
            bootstyle="secondary-inverse"
        )
        self.detail_image_label.pack(fill=BOTH, expand=True)
        self.detail_image_label.configure(cursor="plus")
        self.detail_image_label.bind("<Button-1>", self.open_detail_image_fullscreen)

        self.detail_image_ctrl = ttkbootstrap.Frame(self.detail_image_block)
        self.detail_image_ctrl.pack(fill=X, pady=(6, 0))
        self.detail_image_ctrl.pack_propagate(False)
        self.detail_image_ctrl_inner = ttkbootstrap.Frame(self.detail_image_ctrl)
        self.detail_image_ctrl_inner.place(x=0, y=0)

        self.btn_detail_prev = ttkbootstrap.Button(
            self.detail_image_ctrl_inner,
            text="上一张",
            bootstyle=OUTLINE,
            width=8,
            command=self.show_prev_detail_image,
            state=DISABLED
        )
        self.detail_image_index_label = ttkbootstrap.Label(self.detail_image_ctrl_inner, text="0/0")
        self.btn_detail_next = ttkbootstrap.Button(
            self.detail_image_ctrl_inner,
            text="下一张",
            bootstyle=OUTLINE,
            width=8,
            command=self.show_next_detail_image,
            state=DISABLED
        )
        self.btn_detail_prev.pack(side=LEFT)
        self.detail_image_index_label.pack(side=LEFT, padx=10)
        self.btn_detail_next.pack(side=LEFT)

        self.detail_text_frame = widgets.ScrollFrame(self.detail_inner, scb_pad=5, horizontal_scroller=False)
        self.detail_text_frame.pack(fill=BOTH, expand=True, pady=(8, 0))
        self.detail_text_label = ttkbootstrap.Label(
            self.detail_text_frame,
            text="点击左侧图片加载详情",
            justify=LEFT,
            anchor=NW
        )
        self.detail_text_label.pack(fill=X, expand=True, padx=2, pady=2)
        self.detail_text_frame.bin_child_widgets_bind()
        self.detail_text_frame.w_canvas.bind("<Configure>", self.on_detail_text_resize, add="+")

        self.detail_action_bar = ttkbootstrap.Frame(self.detail_inner)
        self.detail_action_bar.pack(side=BOTTOM, fill=X, pady=(8, 0))
        self.detail_action_bar.pack_propagate(False)
        self.detail_view_btn = ttkbootstrap.Button(
            self.detail_action_bar,
            text="浏览器查看",
            bootstyle=(INFO, OUTLINE),
            command=self.open_detail_in_browser,
            state=DISABLED
        )
        self.detail_view_btn.place(x=0, y=0)

        # Download area
        self.download_inner = ttkbootstrap.Frame(self.Frame_download, padding=12)
        self.download_inner.pack(fill=BOTH, expand=True)

        self.download_title = ttkbootstrap.Label(
            self.download_inner,
            text="下载文件",
            font=("", 11, "bold")
        )
        self.download_title.pack(fill=X, pady=(0, 8))

        self.download_empty = ttkbootstrap.Label(
            self.download_inner,
            text="点击左侧图片加载详情",
            justify=LEFT,
            anchor=NW
        )
        self.download_empty.pack(fill=X)

        notebook = getattr(core.window.interface, "notebook", None)
        if notebook and not self._notebook_bound:
            self._notebook_bound = True
            notebook.bind("<<NotebookTabChanged>>", self.on_tab_changed, add="+")
        self.update_visibility()
        self.install_update_hooks()
        self.master.after(0, self.apply_detail_ctrl_layout)

    def show_retry_notice(self, message="连接 GB 失败", page=None):
        if page:
            self._last_failed_page = page
        try:
            self.list_notice_label.configure(text=message)
        except Exception:
            pass
        if not self.list_notice.winfo_manager():
            try:
                self.list_notice.pack(side=TOP, fill=X, before=self.scroll_frame)
            except Exception:
                self.list_notice.pack(side=TOP, fill=X)

    def hide_retry_notice(self):
        if self.list_notice.winfo_manager():
            try:
                self.list_notice.pack_forget()
            except Exception:
                pass

    def retry_load(self):
        page = self._last_failed_page or self.current_page or 1
        self.hide_retry_notice()
        self.load_page(page)

    def on_canvas_resize(self, event):
        self._pending_canvas_w = event.width
        self.schedule_resize_apply()

    def on_layout_resize(self, event):
        self._pending_layout_w = event.width
        self.schedule_resize_apply()

    def on_detail_resize(self, event):
        self._pending_detail_w = event.width
        self._pending_detail_h = event.height
        self.schedule_resize_apply()

    def on_download_resize(self, event):
        self._pending_download_w = event.width
        self.schedule_resize_apply()

    def on_detail_text_resize(self, event):
        self._pending_detail_text_w = event.width
        self.schedule_resize_apply()

    def schedule_resize_apply(self):
        const.UI_RESIZE_PAUSED = True
        if self._resize_job is not None:
            try:
                self.master.after_cancel(self._resize_job)
            except Exception:
                pass
        self._resize_job = self.master.after(const.RESIZE_DEBOUNCE_MS, self.apply_resize_updates)

    def apply_resize_updates(self):
        self._resize_job = None
        if self._pending_canvas_w is not None:
            self.scroll_frame.w_canvas.itemconfig(self.canvas_window_id, width=self._pending_canvas_w)
            self.scroll_frame.bin_update()
            self._pending_canvas_w = None
        if self._pending_layout_w is not None:
            self.apply_layout_resize(self._pending_layout_w)
            self._pending_layout_w = None
        if self._pending_detail_w is not None or self._pending_detail_h is not None:
            self.apply_detail_resize(self._pending_detail_w, self._pending_detail_h)
            self._pending_detail_w = None
            self._pending_detail_h = None
        if self._pending_detail_text_w is not None:
            self.update_detail_text_wraplength(self._pending_detail_text_w)
            self._pending_detail_text_w = None
        if self._pending_download_w is not None:
            self.update_download_wraplength(self._pending_download_w)
            self._pending_download_w = None
        const.UI_RESIZE_PAUSED = False

    def apply_layout_resize(self, total_w):
        if total_w < const.LAYOUT_FULL_W:
            list_w = const.LIST_BASE_W
            detail_w = const.DETAIL_BASE_W
            down_w = const.DOWNLOAD_W

            self.Frame_list.configure(width=list_w)
            self.Frame_download.configure(width=down_w)

            if self.Frame_detail.winfo_manager() == "pack":
                self.Frame_detail.pack_forget()
            if self.Frame_download.winfo_manager() == "pack":
                self.Frame_download.pack_forget()

            download_x = total_w - down_w
            if download_x < 0:
                download_x = 0

            detail_x = download_x - detail_w
            if detail_x < 0:
                detail_x = 0

            self.Frame_detail.place(x=detail_x, y=0, width=detail_w, relheight=1)
            self.Frame_download.place(x=download_x, y=0, width=down_w, relheight=1)
            self.Frame_detail.tkraise()
            self.Frame_download.tkraise()
        else:
            extra = total_w - const.LAYOUT_FULL_W
            list_add = extra // 3
            list_w = const.LIST_BASE_W + list_add
            if list_w > const.LIST_MAX_W:
                list_w = const.LIST_MAX_W
                detail_w = total_w - const.DOWNLOAD_W - list_w
            else:
                detail_add = extra - list_add
                detail_w = const.DETAIL_BASE_W + detail_add
            down_w = const.DOWNLOAD_W

            self.Frame_list.configure(width=list_w)
            self.Frame_detail.configure(width=detail_w)
            self.Frame_download.configure(width=down_w)

            if self.Frame_detail.winfo_manager() == "place":
                self.Frame_detail.place_forget()
            if self.Frame_download.winfo_manager() == "place":
                self.Frame_download.place_forget()

            if self.Frame_detail.winfo_manager() != "pack":
                self.Frame_detail.pack(side=LEFT, fill=BOTH, expand=False)
            if self.Frame_download.winfo_manager() != "pack":
                self.Frame_download.pack(side=RIGHT, fill=BOTH, expand=False)

    def apply_detail_resize(self, width=None, height=None):
        if not hasattr(self, "detail_image_block"):
            return
        if width is None:
            width = self.Frame_detail.winfo_width()
        if height is None:
            height = self.Frame_detail.winfo_height()
        if width <= 20 or height <= 20:
            return
        img_block_h = max(160, int(height * 0.4))
        self.detail_image_block.configure(height=img_block_h)

        ctrl_h = 0
        try:
            self.detail_image_ctrl.update_idletasks()
            ctrl_h = self.detail_image_ctrl.winfo_height()
        except Exception:
            pass
        img_area_h = max(80, img_block_h - ctrl_h - 6)
        try:
            self.detail_image_outer.configure(height=img_area_h)
        except Exception:
            pass

        self.update_detail_text_wraplength()
        self.refresh_detail_image()
        self.apply_detail_ctrl_layout()

    def apply_detail_ctrl_layout(self):
        try:
            self.detail_image_ctrl.update_idletasks()
            ctrl_w = self.detail_image_ctrl.winfo_width()
            ctrl_h = self.detail_image_ctrl.winfo_height()
            inner_w = self.detail_image_ctrl_inner.winfo_reqwidth()
            inner_h = self.detail_image_ctrl_inner.winfo_reqheight()
            if ctrl_h <= 1:
                ctrl_h = inner_h
                self.detail_image_ctrl.configure(height=inner_h)
            x = max(0, (ctrl_w - inner_w) // 2)
            y = max(0, (ctrl_h - inner_h) // 2)
            self.detail_image_ctrl_inner.place(x=x, y=y, width=inner_w, height=inner_h)
        except Exception:
            pass

        try:
            self.detail_action_bar.update_idletasks()
            action_w = self.detail_action_bar.winfo_width()
            btn_h = self.detail_view_btn.winfo_reqheight()
            if btn_h <= 1:
                btn_h = 26
            self.detail_action_bar.configure(height=btn_h)
            if action_w > 1:
                self.detail_view_btn.place(x=0, y=0, width=action_w, height=btn_h)
            else:
                self.detail_view_btn.place(x=0, y=0, height=btn_h)
        except Exception:
            pass

    def on_tab_changed(self, _event=None):
        self.update_visibility()

    def update_visibility(self):
        notebook = getattr(core.window.interface, "notebook", None)
        if not notebook:
            self.is_visible = True
        else:
            try:
                self.is_visible = (notebook.select() == str(self.instance.master))
            except Exception:
                self.is_visible = True
        if self.is_visible:
            self.prefetch_next_page()


# --- 挂载补丁 ---

def patched_install(self, master, *args, **kwds):
    self.master = master
    self.gb_ctrl = GBListUI(self)
    self.gb_ctrl.setup_ui()


def patched_initial(self):
    self.gb_ctrl.trigger_load()


def main():
    core.log.info(f"GB Warehouse {__version__} (HD Vertical Info Edition) 已加载")
    ModsWarehouse.install = patched_install
    ModsWarehouse.initial = patched_initial

    try:
        warehouse = core.window.interface.mods_warehouse
        if hasattr(warehouse, 'master') and warehouse.master.winfo_exists():
            warehouse.install(warehouse.master)
            warehouse.initial()
    except Exception:
        pass

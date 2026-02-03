# Licensed under the GNU General Public License v3.0
# d3dxSkinManage Plugin: gb_warehouse (High-Def Responsive List Edition)

import os
import io
import time
import socket
import requests
import threading
import urllib3
import webbrowser
from concurrent.futures import ThreadPoolExecutor
from requests.adapters import HTTPAdapter
import PIL.Image
import PIL.ImageTk
import ttkbootstrap
from ttkbootstrap.constants import *

import core
import widgets
from window.interface.mods_warehouse import ModsWarehouse

__version__ = "v1.4.1"

# 抑制 InsecureRequestWarning 警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 配置常量 - 升级为大图模式
GB_API_URL = "https://gamebanana.com/apiv11/Game/8552/Subfeed?_sSort=default&_csvModelInclusions=Mod&_nPage=1"
LIST_THUMB_W = 500
LIST_THUMB_H = 300
IMG_RATIO = 1.666 # 5:3 比例
MAX_WORKERS = 8

class GBListItem(ttkbootstrap.Frame):
    """单个 Mod 列表项组件 - 支持响应式宽度和换行"""
    def __init__(self, master, data):
        super().__init__(master, bootstyle=SECONDARY)
        self.data = data
        self.is_destroyed = False
        
        # 主容器：fill=X 确保宽度随父容器变化
        self.container = ttkbootstrap.Frame(self, padding=10, bootstyle=SECONDARY)
        self.container.pack(fill=X, padx=5, pady=5)

        # 左侧大图容器 - 固定 500x300
        self.img_container = ttkbootstrap.Frame(self.container, width=LIST_THUMB_W, height=LIST_THUMB_H)
        self.img_container.pack(side=LEFT)
        self.img_container.pack_propagate(False)

        self.cover_label = ttkbootstrap.Label(self.img_container, text="正在加载封面...", anchor=CENTER, bootstyle="secondary-inverse")
        self.cover_label.pack(fill=BOTH, expand=True)
        
        # 信息区域 - 采用垂直堆叠布局
        self.info_frame = ttkbootstrap.Frame(self.container, bootstyle=SECONDARY, padding=(20, 10))
        self.info_frame.pack(side=LEFT, fill=BOTH, expand=True)
        
        # 1. Mod 名称
        name = data.get("_sName", "Unknown Mod")
        self.name_label = ttkbootstrap.Label(self.info_frame, text=name, font=("", 12, "bold"), bootstyle=LIGHT)
        self.name_label.pack(side=TOP, anchor=W, pady=(0, 5))
        
        # 2. 作者与浏览量 (移除了点赞)
        submitter = data.get("_aSubmitter", {})
        author = submitter.get("_sName", "Anon") if isinstance(submitter, dict) else "Anon"
        views = data.get("_nViewCount", 0)
        ver = data.get("_sVersion", "")
        
        detail_text = f"👤 作者: {author}\n\n👁️ 浏览: {views}"
        if ver: detail_text += f"\n\n📦 版本: v{ver}"
        
        self.detail_label = ttkbootstrap.Label(self.info_frame, text=detail_text, font=("", 10), bootstyle=INFO, justify=LEFT)
        self.detail_label.pack(side=TOP, anchor=W, pady=(0, 15))

        # 3. 浏览器查看按钮 - 现在放在信息下方形成垂直序列
        self.view_btn = ttkbootstrap.Button(
            self.info_frame, 
            text="浏览器查看", 
            bootstyle=(INFO, OUTLINE), 
            width=12, 
            cursor="hand2",
            command=lambda: webbrowser.open(data.get("_sProfileUrl", ""))
        )
        self.view_btn.pack(side=TOP, anchor=W)

        # 监听信息区域大小变化，动态调整文字换行宽度
        self.info_frame.bind("<Configure>", self.on_info_resize)

    def on_info_resize(self, event):
        """动态更新标签的换行宽度"""
        new_wraplength = event.width - 40 # 预留边距
        if new_wraplength > 100:
            self.name_label.configure(wraplength=new_wraplength)
            self.detail_label.configure(wraplength=new_wraplength)

    def update_image(self, tk_img):
        if self.is_destroyed: return
        try:
            self.cover_label.configure(image=tk_img, text="")
            self.image_ref = tk_img 
        except: pass

    def destroy(self):
        self.is_destroyed = True
        super().destroy()

class GBListUI:
    """列表 UI 控制器"""
    def __init__(self, warehouse_instance):
        self.instance = warehouse_instance
        self.master = warehouse_instance.master
        self.items = []
        self.canvas_window_id = None
        
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
            try: widget.destroy()
            except: pass
        
        self.scroll_frame = widgets.ScrollFrame(self.master, scb_pad=5)
        self.scroll_frame.pack(fill=BOTH, expand=True)
        self.canvas_window_id = self.scroll_frame.w_canvas.find_all()[0]
        self.scroll_frame.w_canvas.bind("<Configure>", self.on_canvas_resize, add="+")

    def on_canvas_resize(self, event):
        canvas = event.widget
        canvas.itemconfig(self.canvas_window_id, width=event.width)
        self.scroll_frame.bin_update()

    def trigger_load(self):
        core.window.status.set_status("正在同步高清仓库列表...", 0)
        core.construct.taskpool.newtask(self.async_fetch_json, (), {}, False)

    def async_fetch_json(self):
        try:
            res = self.session.get(GB_API_URL, timeout=10)
            if res.status_code == 200:
                records = res.json().get("_aRecords", [])
                self.master.after(0, lambda: self.render_list(records))
                self.master.after(0, lambda: core.window.status.set_status("高清列表同步成功", 0))
            else:
                self.master.after(0, lambda: core.window.status.set_status(f"API 异常: {res.status_code}", 1))
        except Exception as e:
            core.log.error(f"(gb_warehouse) 获取 JSON 失败: {e}")
            self.master.after(0, lambda: core.window.status.set_status("连接 GB 失败", 1))

    def render_list(self, records):
        for item in self.items: 
            try: item.destroy()
            except: pass
        self.items = []
        
        for rec in records:
            item_widget = GBListItem(self.scroll_frame, rec)
            item_widget.pack(side=TOP, fill=X, padx=15, pady=8)
            self.items.append(item_widget)
            
        self.scroll_frame.bin_update()
        core.construct.taskpool.newtask(self.parallel_load_images, (records,), {}, False)

    def parallel_load_images(self, records):
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            for i, rec in enumerate(records):
                executor.submit(self.download_single_image, i, rec)

    def download_single_image(self, index, record):
        try:
            if index >= len(self.items) or self.items[index].is_destroyed: return
            media = record.get("_aPreviewMedia", {}).get("_aImages", [])
            if not media: return
            
            img_url = f"{media[0].get('_sBaseUrl')}/{media[0].get('_sFile530')}"
            
            res = self.session.get(img_url, timeout=15)
            if res.status_code == 200:
                pil_img = PIL.Image.open(io.BytesIO(res.content))
                w, h = pil_img.size
                target_h_for_w = int(w / IMG_RATIO)
                if h > target_h_for_w:
                    pil_img = pil_img.crop((0, (h - target_h_for_w)//2, w, (h + target_h_for_w)//2))
                else:
                    target_w_for_h = int(h * IMG_RATIO)
                    pil_img = pil_img.crop(((w - target_w_for_h)//2, 0, (w + target_w_for_h)//2, h))
                
                pil_img = pil_img.resize((LIST_THUMB_W, LIST_THUMB_H), PIL.Image.LANCZOS)
                tk_img = PIL.ImageTk.PhotoImage(pil_img)
                self.master.after(0, lambda: self.items[index].update_image(tk_img))
        except Exception as e:
            core.log.debug(f"(gb_warehouse) 图片下载失败 {index}: {e}")

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
    except: pass

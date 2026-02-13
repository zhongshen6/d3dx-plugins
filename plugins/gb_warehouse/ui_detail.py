# Licensed under the GNU General Public License v3.0
# d3dxSkinManage Plugin: gb_warehouse (Detail UI)

import html
import io
import re
import traceback
import webbrowser
import tkinter.font as tkfont

import PIL.Image
import PIL.ImageOps
import PIL.ImageTk
import ttkbootstrap
from ttkbootstrap.constants import *

import core
import constants as const
from additional import screen_preview
from utils import DebouncedCall, format_ts


class DetailMixin:
    def load_detail(self, mod_id):
        self.current_detail_id = mod_id
        self._detail_request_id += 1
        token = self._detail_request_id
        core.log.info(f"(gb_warehouse) 开始加载详情: id={mod_id} token={token}")
        self.show_detail_loading()
        core.window.status.set_status("正在加载 Mod 详情...", 0)
        taskpool = getattr(core.construct, "taskpool", None)
        if not taskpool:
            core.log.error("(gb_warehouse) taskpool 不可用，无法加载详情")
            self.show_detail_error("任务池不可用")
            return
        try:
            taskpool.newtask(self.async_fetch_detail, (mod_id, token), {}, False)
            core.log.info(f"(gb_warehouse) 详情任务已提交: id={mod_id} token={token}")
        except Exception as e:
            core.log.error(f"(gb_warehouse) 详情任务提交失败: {e}")
            self.show_detail_error("任务提交失败")

    def on_detail_loaded(self, token, data):
        if token != self._detail_request_id:
            core.log.info(f"(gb_warehouse) 详情响应被丢弃: token={token} current={self._detail_request_id}")
            return
        core.log.info(f"(gb_warehouse) 详情数据类型: {type(data).__name__}")
        self.render_detail(data)

    def show_detail_loading(self):
        self.detail_image_urls = []
        self.detail_image_cache = {}
        self.detail_image_fetching = set()
        self.detail_image_index = 0
        self.detail_image_label.configure(text="正在加载图片...", image="")
        self.detail_image_index_label.configure(text="0/0")
        self.btn_detail_prev.configure(state=DISABLED)
        self.btn_detail_next.configure(state=DISABLED)
        self.detail_text_label.configure(text="正在加载详情...")
        self.detail_text_frame.bin_update()
        self.set_download_empty("正在加载下载列表...")
        self.current_detail_url = ""
        if hasattr(self, "detail_view_btn"):
            self.detail_view_btn.configure(state=DISABLED)

    def show_detail_error(self, message):
        core.log.error(f"(gb_warehouse) 详情渲染错误: {message}")
        self.detail_text_label.configure(text=message)
        self.detail_text_frame.bin_update()
        self.detail_image_label.configure(text="暂无图片", image="")
        self.detail_image_index_label.configure(text="0/0")
        self.btn_detail_prev.configure(state=DISABLED)
        self.btn_detail_next.configure(state=DISABLED)
        self.set_download_empty("暂无下载内容")
        self.current_detail_url = ""
        if hasattr(self, "detail_view_btn"):
            self.detail_view_btn.configure(state=DISABLED)

    def open_detail_in_browser(self):
        url = self.current_detail_url
        if url:
            webbrowser.open(url)

    def render_detail(self, data):
        try:
            if not isinstance(data, dict):
                raise ValueError(f"详情数据非字典类型: {type(data).__name__}")
            text = self.clean_detail_text(data.get("_sText", ""))
            if not text:
                text = "暂无描述"
            self.detail_text_label.configure(text=text)
            self.detail_text_frame.bin_update()
            self.detail_text_frame.bin_child_widgets_bind()
            self.detail_text_frame.w_canvas.yview_moveto(0)
            self.update_detail_text_wraplength()

            files = data.get("_aFiles", []) or []
            self.render_downloads(files)

            self.detail_image_urls = self.extract_detail_image_urls(data)
            core.log.info(
                f"(gb_warehouse) 详情渲染: text_len={len(text)} files={len(files)} images={len(self.detail_image_urls)}"
            )
            self.detail_image_cache = {}
            self.detail_image_fetching = set()
            self.detail_image_index = 0
            if not self.detail_image_urls:
                self.detail_image_label.configure(text="暂无图片", image="")
                self.update_detail_image_controls()
            else:
                self.prefetch_detail_images(self._detail_request_id)
                self.show_detail_image()
            self.current_detail_url = data.get("_sProfileUrl", "") or ""
            if hasattr(self, "detail_view_btn"):
                state = NORMAL if self.current_detail_url else DISABLED
                self.detail_view_btn.configure(state=state)
        except Exception as e:
            core.log.error(f"(gb_warehouse) 详情渲染异常: {e}")
            core.log.error(traceback.format_exc())
            self.show_detail_error("详情渲染异常")

    def extract_detail_image_urls(self, data):
        preview = data.get("_aPreviewMedia") or {}
        images = preview.get("_aImages", []) or []
        urls = []
        for img in images:
            base = img.get("_sBaseUrl")
            file_name = img.get("_sFile530") or img.get("_sFile220") or img.get("_sFile") or img.get("_sFile100")
            if base and file_name:
                urls.append(f"{base}/{file_name}")
        core.log.info(f"(gb_warehouse) 解析详情图片: total={len(urls)}")
        return urls

    def update_detail_image_controls(self):
        total = len(self.detail_image_urls)
        if total <= 0:
            self.detail_image_index_label.configure(text="0/0")
            self.btn_detail_prev.configure(state=DISABLED)
            self.btn_detail_next.configure(state=DISABLED)
            return
        self.detail_image_index_label.configure(text=f"{self.detail_image_index + 1}/{total}")
        self.btn_detail_prev.configure(state=NORMAL if self.detail_image_index > 0 else DISABLED)
        self.btn_detail_next.configure(state=NORMAL if self.detail_image_index < total - 1 else DISABLED)

    def show_prev_detail_image(self):
        if self.detail_image_index <= 0:
            return
        self.detail_image_index -= 1
        self.show_detail_image()

    def show_next_detail_image(self):
        if self.detail_image_index >= len(self.detail_image_urls) - 1:
            return
        self.detail_image_index += 1
        self.show_detail_image()

    def show_detail_image(self):
        self.update_detail_image_controls()
        if not self.detail_image_urls:
            self.detail_image_label.configure(text="暂无图片", image="")
            return
        url = self.detail_image_urls[self.detail_image_index]
        cached = self.detail_image_cache.get(url)
        if cached is not None:
            self.render_detail_image(cached)
            return
        self.detail_image_label.configure(text="正在加载图片...", image="")
        token = self._detail_request_id
        core.log.info(f"(gb_warehouse) 请求详情图片: idx={self.detail_image_index} url={url}")
        taskpool = getattr(core.construct, "taskpool", None)
        if not taskpool:
            core.log.error("(gb_warehouse) taskpool 不可用，无法加载详情图片")
            self.detail_image_label.configure(text="图片任务不可用", image="")
            return
        try:
            self.detail_image_fetching.add(url)
            taskpool.newtask(self.async_fetch_detail_image, (url, token), {}, False)
        except Exception as e:
            core.log.error(f"(gb_warehouse) 详情图片任务提交失败: {e}")
            self.detail_image_label.configure(text="图片任务提交失败", image="")

    def open_detail_image_fullscreen(self, _event=None):
        if not self.detail_image_urls:
            return
        url = self.detail_image_urls[self.detail_image_index]
        pil_img = self.detail_image_cache.get(url)
        if pil_img is None:
            return
        width = self.master.winfo_screenwidth()
        height = self.master.winfo_screenheight()
        try:
            resized = PIL.ImageOps.contain(pil_img, (width, height), PIL.Image.LANCZOS)
        except Exception:
            resized = pil_img
        tk_img = PIL.ImageTk.PhotoImage(resized)
        screen_preview.FullScreenPreview(tk_img)

    def async_fetch_detail_image(self, url, token):
        try:
            res = self.session.get(url, timeout=15)
            if res.status_code == 200:
                pil_img = PIL.Image.open(io.BytesIO(res.content))
                self.master.after(0, lambda: self.on_detail_image_loaded(token, url, pil_img))
            else:
                core.log.error(f"(gb_warehouse) 详情图片请求失败: status={res.status_code} url={url}")
                self.master.after(0, lambda: self.on_detail_image_error(token, url))
        except Exception as e:
            core.log.debug(f"(gb_warehouse) 详情图片下载失败: {e}")
            self.master.after(0, lambda: self.on_detail_image_error(token, url))

    def on_detail_image_loaded(self, token, url, pil_img):
        self.detail_image_fetching.discard(url)
        if token != self._detail_request_id:
            core.log.info(f"(gb_warehouse) 详情图片响应被丢弃: token={token} current={self._detail_request_id}")
            return
        self.detail_image_cache[url] = pil_img
        if self.detail_image_urls and url == self.detail_image_urls[self.detail_image_index]:
            self.render_detail_image(pil_img)

    def on_detail_image_error(self, token, url):
        self.detail_image_fetching.discard(url)
        if token != self._detail_request_id:
            return
        core.log.error(f"(gb_warehouse) 详情图片渲染失败: url={url}")
        if self.detail_image_urls and url == self.detail_image_urls[self.detail_image_index]:
            self.detail_image_label.configure(text="图片加载失败", image="")

    def prefetch_detail_images(self, token):
        if token != self._detail_request_id:
            return
        taskpool = getattr(core.construct, "taskpool", None)
        if not taskpool:
            return
        for url in self.detail_image_urls:
            if url in self.detail_image_cache or url in self.detail_image_fetching:
                continue
            self.detail_image_fetching.add(url)
            try:
                taskpool.newtask(self.async_fetch_detail_image, (url, token), {}, False)
            except Exception:
                self.detail_image_fetching.discard(url)

    def render_detail_image(self, pil_img):
        if pil_img is None:
            return
        self.detail_image_outer.update_idletasks()
        width = self.detail_image_outer.winfo_width()
        height = self.detail_image_outer.winfo_height()
        if width <= 10 or height <= 10:
            core.log.info(f"(gb_warehouse) 详情图片尺寸无效: w={width} h={height}")
            return
        core.log.info(f"(gb_warehouse) 渲染详情图片: w={width} h={height}")
        resized = PIL.ImageOps.contain(pil_img, (width, height), PIL.Image.LANCZOS)
        tk_img = PIL.ImageTk.PhotoImage(resized)
        self.detail_image_label.configure(image=tk_img, text="")
        self.detail_image_label.image_ref = tk_img

    def refresh_detail_image(self):
        if not self.detail_image_urls:
            return
        url = self.detail_image_urls[self.detail_image_index]
        cached = self.detail_image_cache.get(url)
        if cached is not None:
            self.render_detail_image(cached)

    def clean_detail_text(self, raw_text):
        if not raw_text:
            return ""
        text = raw_text
        text = re.sub(r"(?i)<br\s*/?>", "\n", text)
        text = re.sub(r"(?i)</p\s*>", "\n\n", text)
        text = re.sub(r"(?i)<p[^>]*>", "", text)
        text = re.sub(r"(?i)<img[^>]*>", "", text)
        text = re.sub(r"<[^>]+>", "", text)
        text = html.unescape(text)
        return text.strip()

    def render_downloads(self, files):
        for item in self.download_buttons:
            try:
                item["item_frame"].destroy()
            except Exception:
                pass
        self.download_buttons = []

        if not files:
            core.log.debug("(gb_warehouse) 下载列表为空")
            self.set_download_empty("无可下载文件")
            return

        if self.download_empty.winfo_manager():
            self.download_empty.pack_forget()

        files_sorted = sorted(files, key=lambda x: x.get("_tsDateAdded", 0) or 0, reverse=True)
        for item in files_sorted:
            name = item.get("_sFile", "Unknown")
            size_bytes = item.get("_nFilesize")
            size_text = self.format_filesize(size_bytes)
            date_text = format_ts(item.get("_tsDateAdded"))
            count = item.get("_nDownloadCount", 0)
            url = item.get("_sDownloadUrl") or ""
            if not url:
                core.log.error(f"(gb_warehouse) 下载链接缺失: file={name}")
            else:
                core.log.info(f"(gb_warehouse) 下载项: file={name} size={size_text} url_ok=1")

            state = NORMAL if url else DISABLED
            meta_text = f"🕒 {date_text}\n💾 {size_text}\n📥 {count}"

            item_frame = ttkbootstrap.Frame(self.download_inner)
            item_frame.pack(fill=X, pady=(0, 8))

            meta_row = ttkbootstrap.Frame(item_frame)
            meta_row.pack(fill=X, pady=(0, 2))

            meta_label = ttkbootstrap.Label(
                meta_row,
                text=meta_text,
                font=("", 9),
                bootstyle=SECONDARY,
                foreground="white",
                justify=LEFT,
                anchor=W
            )
            meta_label.pack(fill=X)

            bar_wrap = ttkbootstrap.Frame(item_frame)
            bar_wrap.pack(fill=X)
            bar_wrap.pack_propagate(False)

            progress = ttkbootstrap.Progressbar(
                bar_wrap,
                maximum=100,
                mode="determinate"
            )
            btn = ttkbootstrap.Button(
                bar_wrap,
                text="",
                bootstyle=OUTLINE,
                command=None,
                state=state
            )
            bar_wrap.update_idletasks()
            btn_h = btn.winfo_reqheight()
            if btn_h <= 1:
                btn_h = 26
            visible_h = 6
            wrap_h = btn_h
            bar_wrap.configure(height=wrap_h)
            bar_wrap._gb_wrap_h = wrap_h
            bar_wrap._gb_visible_h = visible_h

            progress.place(x=0, y=wrap_h - visible_h, relwidth=1, height=visible_h)
            btn.place(x=0, y=0, relwidth=1, height=wrap_h)
            progress.place_forget()

            def _click_download(u=url, n=name, mid=self.current_detail_id, pb=progress, b=btn, bw=bar_wrap):
                if not u:
                    return
                ui = self._make_download_ui(pb, b, bw)
                self.download_and_import(u, n, mid, ui=ui)

            btn.configure(command=lambda u=url, n=name, mid=self.current_detail_id, pb=progress, b=btn, bw=bar_wrap: _click_download(u, n, mid, pb, b, bw))
            self.download_buttons.append({
                "item_frame": item_frame,
                "meta_row": meta_row,
                "meta_label": meta_label,
                "button": btn,
                "progress": progress,
                "bar_wrap": bar_wrap,
                "name": name,
                "url": url
            })

        self.master.after(0, self.update_download_wraplength)

    def set_download_empty(self, message):
        for item in self.download_buttons:
            try:
                item["item_frame"].destroy()
            except Exception:
                pass
        self.download_buttons = []
        self.download_empty.configure(text=message)
        try:
            self.download_empty.configure(foreground="white")
        except Exception:
            pass
        self.download_empty.pack(fill=X)
        self.update_download_wraplength()

    def format_filesize(self, size_bytes):
        if not size_bytes:
            return "未知大小"
        size_mb = size_bytes / (1024 * 1024)
        text = f"{size_mb:.3g}"
        if "e" in text or "E" in text:
            text = f"{size_mb:.2f}"
        return f"{text}MB"

    def get_download_wrap_width(self, width=None):
        try:
            self.download_inner.update_idletasks()
        except Exception:
            pass
        inner_w = self.download_inner.winfo_width()
        if inner_w <= 20:
            if width is None or width <= 20:
                return None
            inner_w = max(0, width - 24)
        return max(40, inner_w - (const.DOWNLOAD_WRAP_SIDE * 2))

    def update_download_wraplength(self, width=None):
        if not hasattr(self, "download_inner"):
            return
        if width is not None:
            self._apply_download_wrap(width)
            return
        if not hasattr(self, "_download_wrap_debounce"):
            self._download_wrap_debounce = DebouncedCall(
                self.master,
                const.RESIZE_DEBOUNCE_MS,
                lambda: const.UI_RESIZE_PAUSED,
            )
        self._download_wrap_debounce.schedule(width, self._apply_download_wrap)

    def _apply_download_wrap(self, width=None):
        self.rewrap_download_buttons(width)

    def rewrap_download_buttons(self, width=None):
        wrap_width = self.get_download_wrap_width(width)
        if not wrap_width:
            return
        if self.download_empty and self.download_empty.winfo_exists():
            self.download_empty.configure(wraplength=wrap_width)
        for item in self.download_buttons:
            meta_label = item.get("meta_label")
            btn = item.get("button")
            progress = item.get("progress")
            bar_wrap = item.get("bar_wrap")
            name = item.get("name")
            if meta_label and meta_label.winfo_exists():
                try:
                    meta_label.configure(wraplength=wrap_width)
                except Exception:
                    pass
            if not btn or not btn.winfo_exists():
                continue
            try:
                font = tkfont.Font(font=btn.cget("font"))
            except Exception:
                font = tkfont.nametofont("TkDefaultFont")
            text = self.wrap_text_by_pixels(name, wrap_width, font, const.DOWNLOAD_TEXT_FUDGE)
            try:
                btn.configure(text=text)
            except Exception:
                pass
            try:
                btn.update_idletasks()
                req_h = btn.winfo_reqheight()
                if req_h <= 1:
                    req_h = 26
                if bar_wrap and bar_wrap.winfo_exists():
                    bar_wrap.configure(height=req_h)
                    bar_wrap._gb_wrap_h = req_h
                visible_h = getattr(bar_wrap, "_gb_visible_h", 6) if bar_wrap else 6
                if progress and progress.winfo_exists() and progress.winfo_manager():
                    if bar_wrap and bar_wrap.winfo_exists():
                        progress.place_configure(y=max(0, req_h - visible_h), height=visible_h)
                    btn.place_configure(height=max(10, req_h - visible_h))
                else:
                    btn.place_configure(height=req_h)
            except Exception:
                pass

    def _make_download_ui(self, progress, button, bar_wrap):
        def _set_progress(value):
            if not progress or not progress.winfo_exists():
                return
            progress.configure(mode="determinate")
            progress["value"] = value

        def _show_progress(indeterminate=False):
            if not progress or not progress.winfo_exists():
                return
            if indeterminate:
                try:
                    progress.configure(mode="indeterminate")
                    progress.start(30)
                except Exception:
                    pass
            else:
                try:
                    progress.stop()
                except Exception:
                    pass
                progress.configure(mode="determinate")
            if not progress.winfo_manager():
                wrap_h = getattr(bar_wrap, "_gb_wrap_h", button.winfo_reqheight())
                visible_h = getattr(bar_wrap, "_gb_visible_h", 6)
                progress.place(x=0, y=max(0, wrap_h - visible_h), relwidth=1, height=visible_h)
            if button and button.winfo_exists():
                wrap_h = getattr(bar_wrap, "_gb_wrap_h", button.winfo_reqheight())
                visible_h = getattr(bar_wrap, "_gb_visible_h", 6)
                button.place_configure(height=max(10, wrap_h - visible_h))
                try:
                    button.lift()
                except Exception:
                    pass

        def _hide_progress(delay_ms=0):
            def _do_hide():
                if not progress or not progress.winfo_exists():
                    return
                try:
                    progress.stop()
                except Exception:
                    pass
                if progress.winfo_manager():
                    progress.place_forget()
                if button and button.winfo_exists():
                    wrap_h = getattr(bar_wrap, "_gb_wrap_h", button.winfo_reqheight())
                    button.place_configure(height=wrap_h)
            if delay_ms and delay_ms > 0:
                try:
                    self.master.after(delay_ms, _do_hide)
                except Exception:
                    _do_hide()
            else:
                _do_hide()

        def _set_enabled(enabled):
            if not button or not button.winfo_exists():
                return
            try:
                button.configure(state=NORMAL if enabled else DISABLED)
            except Exception:
                pass

        def _safe_call(fn, *args):
            try:
                self.master.after(0, lambda: fn(*args))
            except Exception:
                pass

        return {
            "progress": lambda value: _safe_call(_set_progress, value),
            "show_progress": lambda indeterminate=False: _safe_call(_show_progress, indeterminate),
            "hide_progress": lambda delay_ms=0: _safe_call(_hide_progress, delay_ms),
            "enabled": lambda enabled: _safe_call(_set_enabled, enabled),
        }

    def wrap_text_by_pixels(self, text, max_width, font, fudge=0):
        if not text:
            return ""
        effective_width = max_width - fudge
        if effective_width < 20:
            effective_width = max_width
        lines = []
        current = ""
        for ch in text:
            if ch == "\n":
                lines.append(current)
                current = ""
                continue
            if font.measure(current + ch) <= effective_width:
                current += ch
            else:
                if current:
                    lines.append(current)
                    current = ch
                else:
                    lines.append(ch)
                    current = ""
        if current:
            lines.append(current)
        return "\n".join(lines)

    def get_detail_text_wrap_width(self, width=None):
        if not hasattr(self, "detail_text_frame"):
            return None
        try:
            self.detail_text_frame.w_canvas.update_idletasks()
        except Exception:
            pass
        canvas_w = self.detail_text_frame.w_canvas.winfo_width()
        if canvas_w <= 20:
            if width is None or width <= 20:
                return None
            canvas_w = max(0, width - 24)
        return max(120, canvas_w - const.DETAIL_TEXT_WRAP_PAD - const.DETAIL_TEXT_FUDGE)

    def update_detail_text_wraplength(self, width=None):
        if not hasattr(self, "_detail_wrap_debounce"):
            self._detail_wrap_debounce = DebouncedCall(
                self.master,
                const.RESIZE_DEBOUNCE_MS,
                lambda: const.UI_RESIZE_PAUSED,
            )
        if width is not None:
            self._apply_detail_text_wrap(width)
        else:
            self._detail_wrap_debounce.schedule(width, self._apply_detail_text_wrap)

    def _apply_detail_text_wrap(self, width=None):
        wrap_width = self.get_detail_text_wrap_width(width)
        if not wrap_width:
            return
        try:
            self.detail_text_label.configure(wraplength=wrap_width)
        except Exception:
            pass
        try:
            self.detail_text_frame.bin_update()
        except Exception:
            pass

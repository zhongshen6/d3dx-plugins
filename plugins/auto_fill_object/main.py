# Licensed under the GNU General Public License v3.0
# d3dxSkinManage Plugin: auto_fill_object
# Author: Gemini / numlinka expert

__version__ = "v1.4.0"

import os
import json
import threading
import requests
import ttkbootstrap
from ttkbootstrap.constants import *

import core
from additional.add_mod2.add_mod_unit import AddModUnit

# 使用 UIGF 字典接口，按游戏与语言分别下载
DICT_LANGS = ["chs", "en", "jp"]
DICT_GAMES = {
    "genshin": "原神",
    "starrail": "星穹铁道"
}
DICT_URL_TEMPLATE = "https://api.uigf.org/dict/{game}/{lang}.json"

TEXT_UPDATE_WORDS = """
更新多游戏翻译表

同步获取原神、星铁的中/英/日词典数据
支持名称自动匹配识别
按游戏与语言分别下载，避免 all 聚合接口
"""

# 全局存储翻译表数据 (标准化格式: [{"chs": "...", "alts": ["...", "..."]}, ...])
WORD_TABLE = []

def load_word_table():
    global WORD_TABLE
    plugin_dir = os.path.dirname(__file__)
    json_path = os.path.join(plugin_dir, "words.json")
    
    if os.path.exists(json_path):
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                WORD_TABLE = json.load(f)
            core.log.info(f"(auto_fill_object) 已加载标准化词库，共 {len(WORD_TABLE)} 条词条")
        except Exception as e:
            core.log.error(f"(auto_fill_object) 词库加载失败: {e}")
    else:
        core.log.warn("(auto_fill_object) words.json 不存在，请执行更新操作")

def update_words_json():
    """从 UIGF 字典 API 获取 GI/HSR 的中英日词典并标准化"""
    core.window.status.set_status("(auto_fill_object) 正在同步多游戏数据...", 2)
    table_by_chs = {}

    try:
        for game_code, game_name in DICT_GAMES.items():
            core.log.info(f"(auto_fill_object) 正在获取 {game_name} 词典...")
            reverse_by_lang = {}

            for lang in DICT_LANGS:
                url = DICT_URL_TEMPLATE.format(game=game_code, lang=lang)
                response = requests.get(url, timeout=15)
                if response.status_code != 200:
                    core.log.error(f"(auto_fill_object) 获取 {game_name} {lang} 词典失败: HTTP {response.status_code}")
                    continue

                raw_data = response.json()
                # 接口格式：名称 -> ID，需反转为 ID -> 名称
                reverse_by_lang[lang] = {str(value): key for key, value in raw_data.items()}

            chs_dict = reverse_by_lang.get("chs", {})
            for item_id, chs_name in chs_dict.items():
                if not chs_name:
                    continue

                alts = []
                for lang in DICT_LANGS:
                    name = reverse_by_lang.get(lang, {}).get(item_id)
                    if name and name not in alts:
                        alts.append(name)

                if not alts:
                    continue

                if chs_name not in table_by_chs:
                    table_by_chs[chs_name] = {
                        "chs": chs_name,
                        "alts": alts
                    }
                else:
                    for name in alts:
                        if name not in table_by_chs[chs_name]["alts"]:
                            table_by_chs[chs_name]["alts"].append(name)

        new_standard_table = list(table_by_chs.values())

        if new_standard_table:
            # 保存标准化后的数据
            plugin_dir = os.path.dirname(__file__)
            json_path = os.path.join(plugin_dir, "words.json")
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(new_standard_table, f, ensure_ascii=False, indent=2)
            
            global WORD_TABLE
            WORD_TABLE = new_standard_table
            core.window.status.set_status("(auto_fill_object) 词库同步成功", 0)
            core.window.messagebox.showinfo("更新成功", f"已成功同步 {len(new_standard_table)} 条数据。\n仅包含 GI/HSR 的中英日词典。")
        else:
            raise Exception("未获取到任何有效数据")

    except Exception as e:
        core.log.error(f"(auto_fill_object) 在线更新异常: {e}")
        core.window.status.set_status("(auto_fill_object) 更新失败", 1)
        core.window.messagebox.showerror("更新失败", f"同步数据时出错：\n{e}")

# --- 补丁逻辑保持最小化侵入 ---

original_install = AddModUnit.install
def patched_install(self):
    original_install(self)
    self.w_button_recommend = ttkbootstrap.Button(
        self.information, 
        text="推荐: ", 
        bootstyle=(LINK, SUCCESS), 
        cursor="hand2",
        command=lambda: self.action_apply_recommend()
    )
    self.w_button_recommend.grid_forget()

    def action_apply_recommend():
        rec_val = getattr(self, "_recommended_value", "")
        if rec_val:
            self.v_object.set(rec_val)
            self.w_button_recommend.grid_forget()
    self.action_apply_recommend = action_apply_recommend

original_calculate = AddModUnit.calculate
def patched_calculate(self, *args, **kwargs):
    original_calculate(self, *args, **kwargs)
    
    filename_prefix = self.v_name.get()
    if not filename_prefix or not WORD_TABLE:
        return

    found_name = ""
    max_match_len = 0
    # 模糊匹配：忽略空格和分隔符
    clean_filename = filename_prefix.lower().replace(" ", "").replace("_", "").replace("-", "")

    for entry in WORD_TABLE:
        for alt in entry['alts']:
            clean_alt = alt.lower().replace(" ", "").replace("_", "").replace("-", "")
            if clean_alt and clean_alt in clean_filename:
                # 最长匹配优先原则
                if len(alt) > max_match_len:
                    max_match_len = len(alt)
                    found_name = entry['chs']
    
    if found_name:
        self._recommended_value = found_name
        def update_ui():
            self.w_button_recommend.configure(text=f"推荐: {found_name}")
            self.w_button_recommend.grid(row=1, column=2, sticky=W, padx=(5, 0), pady=(5, 0))
        self.master.after(0, update_ui)
    else:
        self.master.after(0, lambda: self.w_button_recommend.grid_forget())

AddModUnit.install = patched_install
AddModUnit.calculate = patched_calculate

def main():
    load_word_table()
    try:
        core.window.interface.tools.add_button(
            text=TEXT_UPDATE_WORDS, 
            command=lambda: threading.Thread(target=update_words_json, daemon=True).start(),
            column=2
        )
    except Exception as e:
        core.log.error(f"(auto_fill_object) 注入工具按钮失败: {e}")
    core.log.info("插件 auto_fill_object (多游戏适配版) 已初始化")

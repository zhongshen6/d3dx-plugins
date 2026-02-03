# Licensed under the GNU General Public License v3.0
# d3dxSkinManage Plugin: auto_fill_object
# Author: Gemini / numlinka expert

__version__ = "v1.3.0"

import os
import json
import threading
import re
import requests
import ttkbootstrap
from ttkbootstrap.constants import *

import core
from additional.add_mod2.add_mod_unit import AddModUnit

# 定义 5 个确定的数据源及其解析配置
DATA_SOURCES = [
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
        "name": "铁道角色",
        "url": "https://api.hakush.in/hsr/data/character.json",
        "keys": ["cn", "en", "jp", "kr"],
        "clean": True  # HSR 需要清洗 Ruby 标签
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

TEXT_UPDATE_WORDS = """
更新多游戏翻译表

同步获取原神、星铁、绝区零的最新数据
支持角色名、武器、音擎自动匹配识别
针对不同游戏 API 结构进行精准适配
"""

# 全局存储翻译表数据 (标准化格式: [{"chs": "...", "alts": ["...", "..."]}, ...])
WORD_TABLE = []

def clean_hsr_text(text):
    """剔除星铁数据中的 Ruby 标签，例如 {RUBY_B#...}内容{RUBY_E#}"""
    if not text or not isinstance(text, str): return text
    return re.sub(r'\{RUBY_[BE]#.*?\}', '', text)

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
    """从 5 个特定 API 获取并标准化数据"""
    core.window.status.set_status("(auto_fill_object) 正在同步多游戏数据...", 2)
    new_standard_table = []
    seen_chs = set()

    try:
        for src in DATA_SOURCES:
            core.log.info(f"(auto_fill_object) 正在获取 {src['name']}...")
            response = requests.get(src['url'], timeout=15)
            if response.status_code == 200:
                raw_data = response.json()
                # 遍历 API 返回的字典 (Key 通常是 ID)
                for entry_id in raw_data:
                    item = raw_data[entry_id]
                    
                    # 确定简中名称 (不同 API 的简中 Key 不同)
                    chs_key = "CHS" if "CHS" in item else ("cn" if "cn" in item else None)
                    if not chs_key: continue
                    
                    chs_name = item[chs_key]
                    if src['clean']: chs_name = clean_hsr_text(chs_name)
                    
                    if not chs_name or chs_name in seen_chs: continue
                    
                    # 提取并清洗所有备选名称
                    alts = []
                    for k in src['keys']:
                        val = item.get(k)
                        if val:
                            if src['clean']: val = clean_hsr_text(val)
                            alts.append(val)
                    
                    if alts:
                        new_standard_table.append({
                            "chs": chs_name,
                            "alts": list(set(alts)) # 去重
                        })
                        seen_chs.add(chs_name)
            else:
                core.log.error(f"(auto_fill_object) 获取 {src['name']} 失败: HTTP {response.status_code}")

        if new_standard_table:
            # 保存标准化后的数据
            plugin_dir = os.path.dirname(__file__)
            json_path = os.path.join(plugin_dir, "words.json")
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(new_standard_table, f, ensure_ascii=False, indent=2)
            
            global WORD_TABLE
            WORD_TABLE = new_standard_table
            core.window.status.set_status("(auto_fill_object) 词库同步成功", 0)
            core.window.messagebox.showinfo("更新成功", f"已成功从 5 个数据源同步 {len(new_standard_table)} 条数据。\n支持 GI/HSR/ZZZ 角色与装备识别。")
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

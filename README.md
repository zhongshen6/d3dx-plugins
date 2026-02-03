# auto_fill_object 
### d3dxSkinManage 模组智能对象识别填充插件

[![Version](https://img.shields.io/badge/version-v1.3.0-blue.svg)](https://github.com/numlinka/d3dxSkinManage)
[![License](https://img.shields.io/badge/license-GPL%20v3.0-lightgrey.svg)](https://www.gnu.org/licenses/gpl-3.0.html)
[![Platform](https://img.shields.io/badge/platform-Windows-orange.svg)](https://github.com/numlinka/d3dxSkinManage)

`auto_fill_object` 是为 [d3dxSkinManage](https://github.com/numlinka/d3dxSkinManage) 模组管理器量身定制的增强插件。它旨在解决用户在导入 Mod 时反复手动输入“作用对象”（角色名/武器名）的痛点。

通过智能分析文件名并对比多语言翻译词库，插件能实现“即拖即识别，一键准填充”。

---

## 🌟 核心特性

- **🎮 跨游戏支持**：完美适配米哈游旗下三款主流游戏：
  - **《原神》** (Genshin Impact)：角色、武器。
  - **《崩坏：星穹铁道》** (Honkai: Star Rail)：角色（支持 Ruby 标签自动清洗）。
  - **《绝区零》** (Zenless Zone Zero)：代理人、音擎。
- **🔍 智能匹配算法**：
  - **最长匹配优先 (LMP)**：在存在包含关系（如 "Raiden" 与 "Raiden Shogun"）时，确保推荐最精准的条目。
  - **模糊兼容**：匹配时自动忽略大小写、空格、下划线及横杠。
- **☁️ 实时词库更新**：集成自 5 个特定官方数据 API，支持在工具页面一键同步最新版本数据。
- **⚡ 非侵入式设计**：采用补丁（Patching）机制注入，完美融入原生“添加 Mod”界面，不影响原有逻辑稳定性。

---

## 🛠️ 安装方法

1. **下载插件**：获取 `auto_fill_object` 文件夹。
2. **放置目录**：将文件夹解压至 `d3dxSkinManage` 的 `plugins` 目录下，结构如下：
   ```text
   d3dxSkinManage/
   └── plugins/
       └── auto_fill_object/
           ├── main.py
           ├── description.txt
           └── words.json (更新后生成)
   ```
3. **重启程序**：运行 `d3dxSkinManage.exe`，在“插件”页面确认已加载。

---

## 📖 使用指南

### 第一步：同步词库
首次使用或游戏更新后，请前往主界面的 **【工具】** 页面，点击 **【更新多游戏翻译表】** 按钮。插件将从后台下载最新的角色及装备对照数据。

### 第二步：导入 Mod
将 Mod 压缩包或文件夹拖入管理器。如果文件名中包含识别范围内的名称（如：`Mod_Acheron_Outfit.7z`）：
1. 识别成功后，**“作用对象”** 输入框右侧会出现绿色的 **【推荐: 黄泉】** 按钮。
2. 点击该按钮，即可自动填充对应名称。

---

## 📝 更新日志

### [v1.3.0] - 当前版本
- **新增**：针对《原神》、《星铁》、《绝区零》5 个特定 API 实现了精准的数据适配器。
- **优化**：针对星铁数据引入了 Ruby 标签清洗过滤机制。
- **优化**：匹配算法升级，支持忽略文件名中的特殊分隔符。

### [v1.2.0]
- **新增**：将更新功能整合进原生“工具”页面。
- **新增**：异步下载机制，更新词库不再造成界面卡死。

---

## 🤝 贡献与感谢
- **数据来源**：感谢 [Hakush.in](https://hakush.in) 提供的多语言 API 支持。
- **项目支持**：由 **Gemini / d3dxSkinManage 专家团队** 维护开发。

## 📄 开源协议
本插件遵循 **GNU General Public License v3.0** 开源协议，与主项目保持一致。

---

### 💡 提示
如果您发现某个新角色无法识别，请先尝试点击工具页面的“更新词库”。如果仍有问题，欢迎通过官方群组或 GitHub Issue 反馈词条缺失。

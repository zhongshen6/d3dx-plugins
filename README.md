# d3dx-plugins

本仓库为 [d3dxSkinManage](https://github.com/numlinka/d3dxSkinManage)  提供插件代码与插件文档，

- 协议：`GNU GPL v3.0`（见 `LICENSE`）

## 当前插件清单

| 插件 | 版本 | 目录 | 主要用途 |
| --- | --- | --- | --- |
| `auto_fill_object` | `v1.4.0` | `plugins/auto_fill_object` | 导入 Mod 时按文件名智能匹配角色名，一键填充对象名 |
| `gb_warehouse` | `v1.4.1` | `plugins/gb_warehouse` | 在管理器内浏览和下载 GameBanana 模组（列表/详情/下载三栏） |
| `windows_touch_scroll` | `v1.1.0` | `plugins/windows_touch_scroll` | 让管理器正确响应触控操作 |

## 插件说明

### auto_fill_object

- 词条范围：`GI` / `HSR`（中/英/日词典）。
- 翻译表接口已切换为 UIGF 字典 API，修复翻译表更新失败问题。
- 按游戏与语言分别拉取并标准化保存到 `words.json`。
- 匹配策略为“最长匹配优先”，减少误匹配。
- 在添加 Mod 界面提供“推荐名称”按钮。

### gb_warehouse

- 对接 GameBanana 接口获取列表与详情。
- 支持分页、搜索、分类浏览、图片缓存、预取。
- 支持下载进度显示和下载后导入流程联动。
- 支持更新检查、环境级 Game ID/分类 ID 设置。

### windows_touch_scroll

- 统一路由可滚动控件（`Treeview`、`Text`、`Canvas`、`ScrollFrame` 等）。
- 支持触控专用模式与触控+鼠标双模式。
- 支持动态控件重绑定和滚动手感调节。

## 安装与使用（插件）

1. 将插件目录放入目标运行环境的 `plugins/` 目录。
2. 重启程序并确认插件加载。
3. 按需进行插件内配置：
   - `auto_fill_object`：执行词库更新。
   - `gb_warehouse`：在页面中设置数据源与分类。
   - `windows_touch_scroll`：编辑 `config.json` 调整输入行为。

## 配置说明

### windows_touch_scroll/config.json

- `enabled`：启用/禁用插件。
- `onlytouch`：是否仅响应触控/触笔事件。
- `consume_drag_events`：滚动锁定后是否吞掉拖动事件。
- `allow_text_drag_selection`：是否保留文本控件拖选行为。
- `widget_rebind_ms`：动态重绑定周期（毫秒）。
- `drag_threshold_px`：进入滚动拖动的位移阈值。
- `profile`：预设档位（`balanced` / `fine` / `fast`）。
- `scroll_sensitivity`、`pixels_per_unit`：滚动手感参数。

## 目录结构

```text
.
├─plugins/                  # 插件代码
│  ├─auto_fill_object/
│  ├─gb_warehouse/
│  └─windows_touch_scroll/
├─docs/                     # 插件文档站点源码（VitePress）
├─.github/workflows/        # 文档部署工作流
├─requirements.txt          # Python 开发依赖
└─package.json              # 文档脚本
```

## 贡献

欢迎通过 Issue / PR 提交插件改进。

建议提交内容包含：

1. 变更动机。
2. 影响的插件目录。
3. 本地验证方式与结果。
4. 文档更新（如有）。

## 许可证

本仓库采用 `GNU General Public License v3.0`，详见 `LICENSE`。

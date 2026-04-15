# TTS Studio 更新日志 - 2026-04-15

## 🎯 主要改动

### 1. 确认对话框交互优化

#### 改进内容
- ✅ 移除 10 秒自动隐藏定时器
- ✅ 确认区域移至触发按钮下方
- ✅ 确认/取消按钮放置在红色边框内
- ✅ 封装为可复用组件

#### 三个确认对话框
| 对话框 | 触发按钮 | 位置 |
|--------|---------|------|
| 工程保存覆盖确认 | 💾 保存工程 | 按钮下方 |
| 工程删除确认 | 🗑️ 删除选中工程 | 按钮下方 |
| 角色覆盖确认 | 💾 保存角色 | 按钮下方 |

### 2. UI 模块化拆分

#### 新增目录结构
```
app/ui_package/
├── __init__.py          # 导出组件和样式
├── components.py        # 确认对话框组件封装
├── styles.py            # CSS 样式定义
├── tabs/                # 预留标签页目录
│   └── __init__.py
└── handlers/            # 预留事件处理目录
    └── __init__.py
```

#### 提取的组件
- `create_confirm_dialog()`: 创建确认对话框
- `show_confirm_dialog()`: 显示确认对话框
- `hide_confirm_dialog()`: 隐藏确认对话框

### 3. Bug 修复

| 问题 | 文件 | 修复内容 |
|------|------|---------|
| `AZURE_SPEECH_AVAILABLE` 未定义 | `tts_engine.py` | 添加 try/except 导入检查 |
| `execute_save_character` 返回值不匹配 | `ui.py` | 修正返回值数量为 5 个 |
| UI 模块循环导入 | `ui_package/__init__.py` | 重命名包避免冲突 |

---

## ⚠️ 已知问题

### 确认框加载状态样式问题

**问题描述：**
在 Gradio 6.12.0 中，确认框在点击按钮后进入加载状态时：
- 边框颜色变为蓝色（Gradio 默认 loading 颜色）
- 背景被灰色遮罩层覆盖
- 显示 "processing" 加载状态

**原因分析：**
Gradio 通过 JavaScript 动态修改 DOM 元素的 inline style 属性，inline style 优先级高于 CSS 类选择器，导致 CSS 无法覆盖。

**影响程度：**
- 🔹 功能正常：确认/取消按钮可正常工作
- 🔹 视觉体验：加载状态时样式不统一
- 🔹 不影响使用：用户仍可正常操作

**尝试过的方案（均无效）：**
1. CSS `!important` 覆盖
2. CSS `.generating` 类选择器
3. CSS 属性选择器匹配 inline style
4. CSS 伪元素移除遮罩
5. CSS 动画禁用

**可能的解决方案：**
1. 升级到 Gradio 6.20.0+ 使用 `gr.Modal` 组件
2. 使用 JavaScript 注入在运行时强制修改样式
3. 等待 Gradio 官方提供禁用加载状态的选项

---

## 📁 文件变更清单

### 修改的文件
| 文件 | 变更类型 | 说明 |
|------|---------|------|
| `app/ui.py` | 优化 | 从 ~1900 行优化至 ~1830 行 |
| `app/tts_engine.py` | 修复 | 添加 Azure Speech SDK 检查 |
| `docs/README.md` | 新增 | 添加本文档索引 |

### 新增的文件
| 文件 | 说明 |
|------|------|
| `app/ui_package/__init__.py` | 模块导出 |
| `app/ui_package/components.py` | 确认对话框组件 |
| `app/ui_package/styles.py` | CSS 样式定义 |
| `app/ui_package/tabs/__init__.py` | 标签页预留 |
| `app/ui_package/handlers/__init__.py` | 事件处理预留 |
| `app/ui.py.backup` | 原 ui.py 备份 |
| `docs/CHANGELOG_2026-04-15.md` | 本更新日志 |

---

## 🔄 后续计划

1. **继续 UI 模块化**
   - 将 4 个 Tab 页面提取到 `ui_package/tabs/`
   - 将事件处理函数提取到 `ui_package/handlers/`

2. **解决确认框样式问题**
   - 探索 JavaScript 注入方案
   - 或升级 Gradio 版本

3. **优化代码结构**
   - 目标：将 `ui.py` 减少到 500 行以内

# Changelog

All notable changes to this project will be documented in this file.

## [未发布] Issue #23 — 修复对白解析逻辑

### Fixed
- `_parse_story_text()` 重写 — 引号感知解析（fix #23）
  - 引号内内容 → 角色对话（每个引号单独一条，不拼合）
  - 引号外描述性文字 → 独立 `[旁白]` 条目
  - 无标记段落 → `[旁白]`（连续无标记段落合并）
  - 情绪标注括号提取改用 `str.find`，避免 Python 3.13 正则 bug
  - 向后兼容无引号格式

### Added
- `episode.raw_text` 字段 — 保存 LLM 原始生成文本（Refs #23）
- `store.create_episode()` / `update_episode()` 支持 `raw_text` 参数
- 数据迁移：旧 episode 自动补充 `raw_text` 字段

### Tests
- `tests/test_dialogue_parser.py` 新增 10 个测试用例覆盖新解析逻辑
- E2E 验证：暗潮涌动项目 88 条对白解析入库成功

## [2026-05-12] Issue #19 — LLM对白生成方案B-2

### Changed
- 对白生成逻辑从"幕规划+逐幕生成"改为一次性生成完整故事
- 新增文本解析函数 `_parse_story_text()`，正则提取角色名、instruct、text
- 上下文注入：前情全部传入 + 后续最多5章摘要
- 可配置参数：字数、旁白占比、风格、温度

### Added
- `tests/test_dialogue_parser.py` — 20 个单元测试（解析 + 角色匹配）
- `docs/dialogue-generation-plan.md` — 方案B-2 设计文档
- API 新增 `style`、`temperature` 可选字段

## [未发布] - 2026-05-11

### 变更
- 移除「总集数」和「生成集数」输入框的上限30限制（Issue #15, PR #16）
  - 文件: `frontend/src/pages/ProjectDetail.tsx`
  - 移除 `Math.min(30, ...)` 和 `max={30}`，保留 `Math.max(1, ...)` 下限保护
  - 纯前端改动，无后端变更

### 已知问题
- 测试容器 tts-studio-for-test 无法启动（Issue #17）：episodes.py L816 缩进错误 + compose 端口映射错误

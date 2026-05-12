# Changelog

All notable changes to this project will be documented in this file.

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

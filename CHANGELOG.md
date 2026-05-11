# Changelog

All notable changes to this project will be documented in this file.

## [未发布] - 2026-05-11

### 变更
- 移除「总集数」和「生成集数」输入框的上限30限制（Issue #15, PR #16）
  - 文件: `frontend/src/pages/ProjectDetail.tsx`
  - 移除 `Math.min(30, ...)` 和 `max={30}`，保留 `Math.max(1, ...)` 下限保护
  - 纯前端改动，无后端变更

### 已知问题
- 测试容器 tts-studio-for-test 无法启动（Issue #17）：episodes.py L816 缩进错误 + compose 端口映射错误

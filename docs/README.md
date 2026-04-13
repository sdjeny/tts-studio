# TTS Studio 文档索引

## 📚 核心文档

### Gradio 性能优化系列

1. **[完整问题记录](./GRADIO_PERFORMANCE_ISSUE_RECORD.md)** ⭐ 推荐首读
   - 问题的来龙去脉
   - 排查过程与失败尝试
   - 最终解决方案
   - 经验总结

2. **[详细优化指南](./GRADIO_PERFORMANCE_OPTIMIZATION.md)**
   - 常见陷阱详解
   - 最佳实践规范
   - 代码示例
   - 性能监控

3. **[快速参考手册](./GRADIO_QUICK_REFERENCE.md)** ⚡ 速查
   - 常见问题速查
   - 快速修复模板
   - 性能检查清单

---

## 🎯 功能文档

### TTS 引擎

- **[Edge-TTS 高级标记指南](../EDGE_TTS_ADVANCED_MARKERS_GUIDE.md)**
  - 多音字标注
  - 停顿插入
  - 语气强调
  - 语速音调调整

- **[高级 TTS 解决方案](../ADVANCED_TTS_SOLUTION.md)**
  - 分批合成策略
  - FFmpeg 音频拼接
  - 临时文件管理

### 编辑器

- **[多音字编辑器指南](../MULTI_PRONUNCIATION_EDITOR_GUIDE.md)**
  - UI 使用说明
  - 标记语法
  - 操作示例

- **[多音字编辑器限制说明](../MULTI_PRONUNCIATION_EDITOR_LIMITATIONS.md)**
  - Edge-TTS 能力边界
  - 不支持的功能
  - 替代方案

---

## 🛠️ 开发文档

### 测试

- **[发布检查清单](../RELEASE_CHECKLIST.md)**
  - 自动化测试要求
  - 回归测试流程
  - 发布前审核

- **[Gradio 性能测试说明](../tests/README_GRADIO_PERFORMANCE_TESTS.md)** ⭐ 新增
  - 10个测试用例详解
  - 每个测试的备注处理方式
  - 运行指南与结果解读

### 部署

- **[FFmpeg 安装指南](../FFMPEG_INSTALL_GUIDE.md)**
  - Windows 手动安装
  - 环境变量配置
  - 验证方法

- **[Docker 部署](../docker-compose.yml)**
  - 容器化部署
  - 环境变量
  - 数据卷挂载

---

## 🏷️ 标签索引

### 按主题分类

#### #Gradio
- [完整问题记录](./GRADIO_PERFORMANCE_ISSUE_RECORD.md)
- [详细优化指南](./GRADIO_PERFORMANCE_OPTIMIZATION.md)
- [快速参考手册](./GRADIO_QUICK_REFERENCE.md)

#### #性能优化
- [完整问题记录](./GRADIO_PERFORMANCE_ISSUE_RECORD.md)
- [详细优化指南](./GRADIO_PERFORMANCE_OPTIMIZATION.md)

#### #TTS
- [Edge-TTS 高级标记指南](../EDGE_TTS_ADVANCED_MARKERS_GUIDE.md)
- [高级 TTS 解决方案](../ADVANCED_TTS_SOLUTION.md)

#### #多音字
- [多音字编辑器指南](../MULTI_PRONUNCIATION_EDITOR_GUIDE.md)
- [多音字编辑器限制说明](../MULTI_PRONUNCIATION_EDITOR_LIMITATIONS.md)

#### #部署
- [FFmpeg 安装指南](../FFMPEG_INSTALL_GUIDE.md)
- [Docker 部署](../docker-compose.yml)

#### #测试
- [发布检查清单](../RELEASE_CHECKLIST.md)

---

## 🔍 快速查找

### 我遇到了...

**Gradio Tab 切换卡死** → [快速参考手册 - 问题1](./GRADIO_QUICK_REFERENCE.md#问题-1tab-切换卡死)

**控制台大量警告** → [快速参考手册 - 问题2](./GRADIO_QUICK_REFERENCE.md#问题-2控制台大量警告)

**组件更新不显示** → [快速参考手册 - 问题3](./GRADIO_QUICK_REFERENCE.md#问题-3组件更新不显示)

**首次加载数据空白** → [快速参考手册 - 问题4](./GRADIO_QUICK_REFERENCE.md#问题-4首次加载数据空白)

**想了解完整排查过程** → [完整问题记录](./GRADIO_PERFORMANCE_ISSUE_RECORD.md)

**想学习最佳实践** → [详细优化指南](./GRADIO_PERFORMANCE_OPTIMIZATION.md)

**需要使用多音字功能** → [Edge-TTS 高级标记指南](../EDGE_TTS_ADVANCED_MARKERS_GUIDE.md)

**需要安装 FFmpeg** → [FFmpeg 安装指南](../FFMPEG_INSTALL_GUIDE.md)

---

## 📊 文档统计

| 类别 | 数量 | 最近更新 |
|------|------|---------|
| Gradio 性能 | 3 | 2026-04-13 |
| TTS 功能 | 2 | 2026-04-12 |
| 编辑器 | 2 | 2026-04-12 |
| 部署 | 2 | 2026-04-10 |
| 测试 | 1 | 2026-04-11 |

---

## 💡 使用建议

### 新手入门

1. 阅读 [完整问题记录](./GRADIO_PERFORMANCE_ISSUE_RECORD.md) 了解项目背景
2. 查看 [Edge-TTS 高级标记指南](../EDGE_TTS_ADVANCED_MARKERS_GUIDE.md) 了解核心功能
3. 参考 [快速参考手册](./GRADIO_QUICK_REFERENCE.md) 解决常见问题

### 开发者

1. 精读 [详细优化指南](./GRADIO_PERFORMANCE_OPTIMIZATION.md) 掌握最佳实践
2. 查阅 [发布检查清单](../RELEASE_CHECKLIST.md) 确保代码质量
3. 关注标签索引，快速定位相关文档

### 运维人员

1. 参考 [FFmpeg 安装指南](../FFMPEG_INSTALL_GUIDE.md) 配置环境
2. 使用 [Docker 部署](../docker-compose.yml) 快速启动
3. 查看 [完整问题记录](./GRADIO_PERFORMANCE_ISSUE_RECORD.md) 了解已知问题

---

**最后更新：** 2026-04-13  
**维护者：** TTS Studio 开发团队

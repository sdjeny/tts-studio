# TTS Studio 项目基础文档

> **项目名称**: TTS Studio - 多轨剧本配音工作台  
> **版本**: v2.0  
> **创建日期**: 2026-04-12  
> **最后更新**: 2026-04-13  
> **技术栈**: Python + Edge-TTS + Gradio + FFmpeg

---

## 📋 目录

1. [项目背景与需求](#项目背景与需求)
2. [核心功能](#核心功能)
3. [技术架构](#技术架构)
4. [实现历程](#实现历程)
5. [关键技术要点](#关键技术要点)
6. [踩过的坑与解决方案](#踩过的坑与解决方案)
7. [性能优化](#性能优化)
8. [最佳实践](#最佳实践)
9. [项目文件结构](#项目文件结构)
10. [部署与运行](#部署与运行)

---

## 项目背景与需求

### 业务场景

TTS Studio 是一个**多轨剧本配音工作台**，用于将剧本文本转换为高质量的语音音频。主要应用场景包括：

1. **有声书制作**：将小说文本转换为多人配音的有声书
2. **广播剧制作**：支持角色对话、旁白、音效的多轨混音
3. **视频配音**：为短视频、宣传片生成专业配音
4. **教育内容**：制作教学音频、语言学习材料

### 核心需求

#### 1. 自然的多音字处理

**问题**：中文存在大量多音字，如"银行行长"中的两个"行"读音不同（háng vs zhǎng），传统 TTS 引擎容易读错。

**需求**：
- 允许用户手动指定多音字的正确读音
- 替换后的音频要自然流畅，不能一字一顿
- 操作简单直观，无需记忆复杂语法

#### 2. 丰富的语气变化

**问题**：一句话内可能有多个情绪变化，如"他慢慢地跑了起来"需要前半句慢速、后半句快速。

**需求**：
- 支持在单句话内设置多处语速、音调变化
- 支持插入停顿（制造悬念、转折）
- 支持强调效果（突出重点）
- 音频拼接处要自然，不能有明显的断裂感

#### 3. 友好的用户界面

**问题**：操作人员可能不熟悉技术细节，需要直观的可视化工具。

**需求**：
- 每个对白片段都可以单独编辑
- 提供快捷操作按钮，避免直接编辑标记语法
- 实时预览修改效果
- 保存工程配置，方便后续跟进

#### 4. 高性能与稳定性

**问题**：复杂的语气变化会导致合成时间过长，影响工作效率。

**需求**：
- 优化分片策略，减少不必要的网络请求
- 实现重试机制，提高成功率
- 支持代理配置，解决网络访问问题
- 清晰的日志输出，便于问题排查

---

## 核心功能

### 1. 文本解析与标记系统

#### 支持的标记语法

```python
# 语速控制
"[rate=-30%]慢速部分[/rate]"      # 范围：-50% ~ +50%
"[rate=+20%]快速部分[/rate]"

# 音调控制
"[pitch=+15Hz]高音部分[/pitch]"   # 范围：-20Hz ~ +20Hz
"[pitch=-10Hz]低音部分[/pitch]"

# 停顿插入
"[pause=300]"                      # 单位：毫秒，无需结束标签

# 强调效果
"[emphasis=strong]强调内容[/emphasis]"    # strong/moderate/reduced

# 多音字标注
"[phoneme=航]行[/phoneme]"         # 用同音字替换原字
```

#### 标记组合示例

```python
# 一波三折的语气变化
text = (
    "[rate=-30%]那[phoneme=航]行[/phoneme][phoneme=掌]长[/phoneme][/rate]"
    "[pause=300]"
    "[pitch=+15Hz]竟然[phoneme=仲]重[/phoneme]新[/pitch]"
    "[rate=+20%]走进了那家[phoneme=月]乐[/phoneme]器店[/rate]"
    "[pause=200]"
    "[pitch=-10Hz]看着那些[phoneme=郝]好[/phoneme]玩的乐器[/pitch]"
    "[rate=-10%]他[phoneme=这]着[/phoneme]迷了[/rate]"
    "[pause=400]"
    "[pitch=+20Hz]突然！[/pitch]"
    "[rate=+30%]他发现了一个[phoneme=常]长[/phoneme][phoneme=虫]重[/phoneme]的箱子[/rate]"
    "[pause=500]"
    "[rate=-40%][pitch=-15Hz]里面...到底是什么呢？[/pitch][/rate]"
)
```

### 2. 自动拆分与拼接

#### 工作流程

```
用户输入带标记文本
    ↓
解析层：parse_marked_text()
    ↓ 返回 TextSegment 列表
合成层：synthesize_advanced_line()
    ↓ 遍历每个片段
    ├─ pause → 生成静音片段 (FFmpeg)
    └─ text  → 调用 edge-tts 合成
    ↓
拼接层：FFmpeg concat demuxer
    ↓ 按顺序拼接所有片段
清理层
    ↓ 删除临时文件
输出：最终 MP3 文件
```

#### 关键特性

- **智能分片**：只在语气标记处拆分，phoneme 不参与分片
- **并行优化**：未来可支持 asyncio.gather() 并行合成
- **容错机制**：单个片段失败不影响其他片段
- **资源管理**：finally 块确保临时文件清理

### 3. Monkey Patch Edge-TTS

#### 为什么需要 Monkey Patch？

edge-tts 官方库的限制：
- ❌ 不支持 `<break>` 标签（停顿）
- ❌ 不支持 `<phoneme>` 标签（多音字）
- ❌ 不支持 `<emphasis>` 标签（强调）
- ❌ 最多只支持 2 个 `<prosody>` 标签嵌套
- ❌ 无法接受自定义 SSML

#### 实现方案

通过直接替换 `edge_tts.communicate` 模块的关键方法，使 edge-tts 能够接受自定义 SSML：

```python
# patch_edge_tts_v2.py
def patched_communicate_init(self, text, ...):
    # 检测是否是自定义 SSML
    is_custom_ssml = text.strip().startswith('<speak')
    
    if is_custom_ssml:
        # 不进行 escape，保持原始 SSML
        self.texts = [text]
        self._is_custom_ssml = True
    else:
        # 普通文本，正常处理
        escaped_text = _original_escape(remove_incompatible_characters(text))
        self.texts = split_text_by_byte_length(escaped_text, 4096)
        self._is_custom_ssml = False

def patched_mkssml(tc, escaped_text):
    # 如果已经是完整 SSML，直接返回
    if isinstance(escaped_text, str) and escaped_text.strip().startswith('<speak'):
        return escaped_text
    
    # 否则构建标准 SSML
    ssml = f"<speak>...</speak>"
    return ssml

# 应用补丁
edge_tts.communicate.Communicate.__init__ = patched_communicate_init
edge_tts.communicate.mkssml = patched_mkssml
```

### 4. 多音字处理策略

#### 废弃方案：拼音映射

```python
# ❌ 失败案例
"[phoneme=hang2]行[/phoneme]"
# edge-tts 会把 "hang2" 当作英文字母读出："H-A-N-G-2"
```

**失败原因**：
- edge-tts 不支持 `<phoneme>` 标签
- Microsoft TTS 引擎不识别拼音格式
- 需要维护庞大的拼音→同音字映射表
- 映射表无法覆盖所有多音字

#### 采用方案：同音字替换

```python
# ✅ 成功案例
"[phoneme=航]行[/phoneme]"
# 预处理时将"行"替换为"航"，传给 edge-tts 的文本是"航"
# edge-tts 会按照"航"的读音（háng）来读
```

**优势**：
- ✅ 简单可靠，无需维护映射表
- ✅ 前端直接指定，覆盖所有多音字
- ✅ 替换后的文本作为整体传给 TTS，保持连贯性
- ✅ **关键决策**：phoneme 不参与分片，避免一字一顿

**处理流程**：
```python
# 1. 检测 phoneme 标记
if has_phoneme:
    # 2. 预处理替换
    processed_text = preprocess_phoneme_markers(line.text)
    # "那[phoneme=航]行[/phoneme]长" → "那航行长"
    
    # 3. 重新检测是否有语气标记
    has_advanced_markers = bool(re.search(r'\[(rate|pitch|pause|emphasis)=', processed_text))

# 4. 只有语气标记才触发分片
if has_advanced_markers:
    return await synthesize_advanced_line(...)
```

### 5. Web UI 可视化编辑器

#### 功能组件

```
┌─────────────────────────────────────────────┐
│  对白片段表格                                 │
│  [ID] [角色] [文本] [音色] [状态]            │
│  选中某一行后，下方显示编辑器                   │
└──────────────────┬──────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────┐
│  📝 多音字与语气标记编辑器                     │
│                                              │
│  原始文本（带标记）：                          │
│  [━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━]           │
│                                              │
│  ⚡ 快捷操作                                  │
│  ┌──────────┬──────────┐                    │
│  │ 多音字:行 │ 替换为:航 │ ➕ 标注多音字     │
│  └──────────┴──────────┘                    │
│  ┌────────────────┬──────────┐              │
│  │ 停顿时长:300ms │ ⏸️ 插入  │              │
│  └────────────────┴──────────┘              │
│  ┌────────────────┬──────────┐              │
│  │ 强调:strong    │ ❗ 添加  │              │
│  └────────────────┴──────────┘              │
│                                              │
│  语速调整: [-50% ━━━━━●━━━━━ +50%]          │
│  音调调整: [-20Hz ━━━━━●━━━━━ +20Hz]        │
│                                              │
│  [✅ 应用语气] [🧹 清除标记] [🔊 试听]       │
│                                              │
│  标记效果预听：                                │
│  [▶️ 播放按钮]                                │
└─────────────────────────────────────────────┘
```

#### 操作流程

1. **选中文本**：点击表格中的某一行
2. **查看原文**：原始文本自动显示在编辑器中
3. **添加标记**：
   - 多音字：输入原字和替换字，点击"标注多音字"
   - 停顿：调整时长滑块，点击"插入停顿"
   - 强调：选择程度，点击"添加强调"
   - 语气：调整语速/音调滑块，点击"应用语气设置"
4. **试听验证**：点击"试听当前标记效果"
5. **保存工程**：所有修改自动保存到工程配置

---

## 技术架构

### 分层架构设计

```
┌─────────────────────────────────────────────────────┐
│  表现层 (Presentation Layer)                         │
│  app/ui.py - Gradio Web UI                          │
│  - 多轨剧本编辑                                       │
│  - 标记可视化编辑                                      │
│  - 实时预览                                           │
└──────────────────┬──────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────┐
│  业务逻辑层 (Business Logic Layer)                    │
│  app/tts_engine.py - TTS 引擎入口                    │
│  - 检测标记类型                                       │
│  - 预处理 phoneme                                    │
│  - 路由到不同处理器                                    │
│  - 重试机制                                           │
└────────┬────────────────────┬───────────────────────┘
         │                    │
         ▼                    ▼
┌────────────────┐  ┌──────────────────────┐
│ 普通文本        │  │ 高级标记文本          │
│ synthesize_    │  │ synthesize_          │
│ simple_text()  │  │ advanced_line()      │
└────────┬───────┘  └────────┬─────────────┘
         │                   │
         │                   ▼
         │          ┌──────────────────────┐
         │          │ 解析层                │
         │          │ app/tts_parser.py    │
         │          │ parse_marked_text()  │
         │          └────────┬─────────────┘
         │                   │
         │                   ▼
         │          ┌──────────────────────┐
         │          │ 合成层                │
         │          │ app/tts_advanced.py  │
         │          │ - edge-tts (音频)    │
         │          │ - FFmpeg (静音)      │
         │          └────────┬─────────────┘
         │                   │
         │                   ▼
         │          ┌──────────────────────┐
         │          │ 拼接层                │
         │          │ FFmpeg concat        │
         │          └────────┬─────────────┘
         │                   │
         ▼                   ▼
┌─────────────────────────────────────────────────────┐
│  数据层 (Data Layer)                                 │
│  data/audio/*.mp3 - 音频文件                         │
│  data/projects/*.json - 工程配置                     │
└─────────────────────────────────────────────────────┘
```

### 核心模块说明

#### 1. app/tts_parser.py - 文本解析器

**职责**：解析带标记的文本，返回结构化数据

**关键函数**：
```python
@dataclass
class TextSegment:
    """文本片段"""
    text: str              # 文本内容
    rate: str = "+0%"      # 语速
    pitch: str = "+0Hz"    # 音调
    volume: str = "+0%"    # 音量
    is_marked: bool = False  # 是否包含标记
    segment_type: str = "text"  # 片段类型: text, pause, emphasis

def preprocess_phoneme_markers(text: str) -> str:
    """预处理 phoneme 标记，用同音字替换原字"""

def parse_marked_text(text: str) -> List[TextSegment]:
    """解析带有标记的文本"""

def has_markers(text: str) -> bool:
    """检测文本是否包含标记"""

def needs_splitting(text: str) -> bool:
    """检测文本是否需要拆分"""
```

**正则表达式设计**（关键）：
```python
# 区分 pause（无结束标签）和其他标记（有结束标签）
pattern = r'\[(pause)=(\d+)\]|\[(\w+)=([^\]]+)\](.*?)(?:\[/\3\])'
```

#### 2. app/tts_advanced.py - 高级合成引擎

**职责**：自动拆分、分别合成、FFmpeg 拼接

**处理流程**：
```python
async def synthesize_advanced_line(line, output_path):
    # 1. 解析文本
    segments = parse_marked_text(line.text)
    
    # 2. 分别合成每个片段
    temp_files = []
    for seg in segments:
        if seg.segment_type == 'pause':
            # 生成静音片段
            generate_silence(seg.rate, temp_path)
        else:
            # 调用 edge-tts 合成
            communicate = edge_tts.Communicate(...)
            await communicate.save(temp_path)
        temp_files.append(temp_path)
    
    # 3. 拼接所有片段
    ffmpeg_concat(temp_files, output_path)
    
    # 4. 清理临时文件
    cleanup_temp_files(temp_files)
```

#### 3. app/tts_engine.py - TTS 引擎入口

**职责**：统一入口，路由到不同处理器

**关键逻辑**：
```python
async def synthesize_single_line(line, output_path):
    # 检测标记类型
    has_advanced_markers = bool(re.search(r'\[(rate|pitch|pause|emphasis)=', line.text))
    has_phoneme = bool(re.search(r'\[phoneme=', line.text))
    has_ssml = line.text.strip().startswith('<speak')
    
    if has_phoneme:
        # 先预处理 phoneme 标记（替换为同音字）
        processed_text = preprocess_phoneme_markers(line.text)
        line = ScriptLine(..., text=processed_text, ...)
        # 重新检测是否有其他标记
        has_advanced_markers = bool(re.search(r'\[(rate|pitch|pause|emphasis)=', processed_text))
    
    if has_advanced_markers:
        # 高级标记：自动拆分+拼接
        return await synthesize_advanced_line(line, output_path)
    elif has_ssml:
        # 自定义 SSML：直接传给 edge-tts
        return await synthesize_simple_text(line, output_path)
    else:
        # 普通文本
        return await synthesize_simple_text(line, output_path)
```

#### 4. patch_edge_tts_v2.py - Monkey Patch

**职责**：扩展 edge-tts 能力，支持自定义 SSML

**关键修改**：
- `patched_communicate_init()`：检测并保留自定义 SSML
- `patched_mkssml()`：如果是完整 SSML 则直接返回

#### 5. app/ui.py - Web UI

**职责**：提供可视化操作界面

**核心组件**：
- 剧本解析与展示
- 多音字与语气标记编辑器
- 音频生成与预览
- 工程保存与加载

---

## 实现历程

### 阶段一：项目初始化（2026-04-12）

**目标**：搭建基础框架，实现简单的 TTS 合成功能

**完成工作**：
1. ✅ 创建项目结构
2. ✅ 集成 edge-tts
3. ✅ 实现 Gradio Web UI
4. ✅ 支持基本的文本转语音

**遇到的问题**：
- Docker 环境路径问题
- Gradio 版本兼容性
- FFmpeg 依赖缺失

**解决方案**：
- 动态适配数据路径
- 锁定 Gradio 版本
- 编写 FFmpeg 安装指南

### 阶段二：高级标记功能（2026-04-12）

**目标**：支持一句话内多处语气变化

**完成工作**：
1. ✅ 创建 tts_parser.py 解析器
2. ✅ 创建 tts_advanced.py 高级合成引擎
3. ✅ 实现自动拆分+拼接
4. ✅ 支持 rate/pitch/pause/emphasis 标记

**技术突破**：
- 正则表达式设计：区分有无结束标签的标记
- 分层架构：解析层 → 合成层 → 拼接层
- 临时文件管理：uuid 命名，finally 清理

**测试验证**：
- 创建 test_advanced_features.py
- 验证停顿、强调、多片段等功能

### 阶段三：Monkey Patch Edge-TTS（2026-04-12）

**目标**：让 edge-tts 支持自定义 SSML

**完成工作**：
1. ✅ 创建 patch_edge_tts_v2.py
2. ✅ 替换 Communicate.__init__ 方法
3. ✅ 替换 mkssml 函数
4. ✅ 支持传入完整 SSML

**关键技术**：
- 类型陷阱处理：str vs bytes
- 避免重复转义：自定义 SSML 不经过 escape
- 调试日志：打印完整 SSML 内容

**测试验证**：
- 创建 test_ssml_before_split.py
- 查看完整的 SSML 转换流程

### 阶段四：多音字处理优化（2026-04-13）

**目标**：解决多音字读音问题，优化性能

**初始方案**：拼音映射
```python
"[phoneme=hang2]行[/phoneme]"
```

**问题发现**：
- ❌ edge-tts 把 "hang2" 读成字母
- ❌ 需要维护庞大的映射表
- ❌ 音频卡顿，一字一顿（25个片段，35-37秒）

**最终方案**：同音字替换
```python
"[phoneme=航]行[/phoneme]"
```

**关键决策**：
1. **移除拼音映射表**：简化代码，提高可靠性
2. **phoneme 不参与分片**：先替换再检测语气标记
3. **前端指定替换字**：用户直接输入，无需映射

**性能优化结果**：
- 时长：35-37秒 → 21.05秒（减少 40%）
- 片段数：25个 → 12个（减少 52%）
- 效果：从一字一顿到流畅自然

**测试验证**：
- 创建 test_ultimate_acceptance.py
- 包含 8 个多音字和 12 处语气变化
- 时长 21.05秒，文件大小 123KB

### 阶段五：Web UI 增强（2026-04-13）

**目标**：提供可视化的标记编辑界面

**完成工作**：
1. ✅ 添加"多音字与语气标记编辑"区域
2. ✅ 实现快捷操作按钮
3. ✅ 添加实时预览功能
4. ✅ 创建使用指南文档

**UI 组件**：
- 原始文本显示框
- 多音字标注输入
- 停顿时长滑块
- 强调程度单选框
- 语速/音调调整滑块
- 操作状态反馈
- 音频播放器

**事件处理**：
- `add_phoneme_marker()`：添加多音字标记
- `add_pause_marker()`：插入停顿标记
- `add_emphasis_marker()`：添加强调标记
- `apply_tone_settings()`：应用语速和音调
- `clear_all_markers()`：清除所有标记
- `preview_marked_text()`：试听效果

**文档完善**：
- MULTI_PRONUNCIATION_EDITOR_GUIDE.md：编辑器使用指南
- EDGE_TTS_ADVANCED_MARKERS_GUIDE.md：技术实现文档

---

## 关键技术要点

### 1. 正则表达式设计

#### 问题：混合标记解析

**错误尝试**：
```python
# ❌ 试图用一个正则匹配所有情况
pattern = r'\[(\w+)=([^\]]+)\](.*?)(?:\[/\1\])?'
# 问题：贪婪匹配导致结束标签被包含在内容中
```

**正确方案**：
```python
# ✅ 使用交替匹配区分两种情况
pattern = r'\[(pause)=(\d+)\]|\[(\w+)=([^\]]+)\](.*?)(?:\[/\3\])'
# group(1), group(2): pause 标记
# group(3), group(4), group(5): 其他标记
```

**关键点**：
- pause 无需结束标签，单独匹配
- 其他标记必须有结束标签
- 使用非捕获组 `(?:...)` 避免干扰分组

### 2. 处理顺序的重要性

**错误顺序**：
```python
# ❌ 先检测语气标记，再处理 phoneme
if has_advanced_markers:
    return await synthesize_advanced_line(...)
elif has_phoneme:
    processed_text = preprocess_phoneme_markers(line.text)
```

**问题**：phoneme 标记会被误判为语气标记，触发不必要的分片

**正确顺序**：
```python
# ✅ 先处理 phoneme，再检测语气标记
if has_phoneme:
    processed_text = preprocess_phoneme_markers(line.text)
    line = ScriptLine(..., text=processed_text, ...)
    # 重新检测
    has_advanced_markers = bool(re.search(r'\[(rate|pitch|pause|emphasis)=', processed_text))

if has_advanced_markers:
    return await synthesize_advanced_line(...)
```

**收益**：
- 避免 phoneme 导致的过度分片
- 时长减少 40%，片段数减少 52%

### 3. 类型陷阱处理

**问题**：mkssml 函数可能接收 str 或 bytes

**错误代码**：
```python
# ❌ 假设总是 str
if escaped_text.startswith('<speak'):
    return escaped_text
# AttributeError: 'bytes' object has no attribute 'startswith'
```

**正确处理**：
```python
# ✅ 检查类型并转换
if isinstance(escaped_text, bytes):
    text_str = escaped_text.decode('utf-8')
else:
    text_str = escaped_text

if text_str.strip().startswith('<speak'):
    return escaped_text  # 保持原始类型返回
```

### 4. 临时文件管理

**命名规范**：
```python
temp_path = str(AUDIO_DIR / f"temp_{uuid.uuid4().hex[:8]}_seg{i}.mp3")
# 示例：temp_a1b2c3d4_seg0.mp3
```

**清理机制**：
```python
try:
    # 合成和拼接逻辑
    ...
finally:
    # 确保无论如何都清理
    for temp_file in temp_files:
        try:
            if os.path.exists(temp_file):
                os.remove(temp_file)
        except:
            pass
```

**关键点**：
- 使用 uuid 避免文件名冲突
- finally 块确保清理执行
- 容错处理：单个文件删除失败不影响其他

### 5. FFmpeg 拼接优化

**方案对比**：

| 方案 | 速度 | 音质 | 复杂度 |
|------|------|------|--------|
| pydub append | 慢 | 好 | 简单 |
| pydub crossfade | 中 | 最好 | 中等 |
| FFmpeg concat | **快** | 好 | 中等 |

**选择 FFmpeg concat 的原因**：
- 速度最快：直接复制音频流，不重新编码
- 资源占用少：不需要加载整个音频到内存
- 可靠性高：成熟的工具，广泛使用

**实现代码**：
```python
# 创建文件列表
list_file = str(AUDIO_DIR / f"concat_list_{uuid.uuid4().hex[:8]}.txt")
with open(list_file, 'w', encoding='utf-8') as f:
    for temp_file in temp_files:
        # 🔑 关键：路径使用正斜杠
        file_path = temp_file.replace('\\', '/')
        f.write(f"file '{file_path}'\n")

# 执行拼接
cmd = [
    './ffmpeg.exe',
    '-f', 'concat',
    '-safe', '0',
    '-i', list_file,
    '-c', 'copy',  # 直接复制，不重新编码
    '-y',
    output_path
]
subprocess.run(cmd, capture_output=True, check=True)
```

---

## 踩过的坑与解决方案

### 坑1：复合标记语法错误

**错误示例**：
```python
"[rate=-40%,pitch=-15Hz]文本[/rate]"
# ValueError: Invalid rate '-40%,pitch=-15Hz'.
```

**原因**：edge-tts 不支持逗号分隔的多值

**解决方案**：
```python
# ✅ 分开写两个标记
"[rate=-40%][pitch=-15Hz]文本[/pitch][/rate]"
```

**教训**：严格遵守 edge-tts 的参数格式要求

### 坑2：拼音被读成字母

**错误示例**：
```python
"[phoneme=hang2]行[/phoneme]"
# 读出："H-A-N-G-2"
```

**原因**：edge-tts 不支持 `<phoneme>` 标签

**解决方案**：
```python
# ✅ 使用同音字替换
"[phoneme=航]行[/phoneme]"
# 读出："háng"（正确的读音）
```

**教训**：不要假设 TTS 引擎支持所有 SSML 标签

### 坑3：音频一字一顿

**现象**：
- 时长：35-37秒（预期 20秒左右）
- 片段数：25个
- 听感：每个字之间有微小停顿，非常生硬

**原因**：
- phoneme 标记被当作语气标记处理
- 每个 phoneme 都触发一次分片
- 25次网络请求，每次都有延迟

**解决方案**：
```python
# ✅ phoneme 不参与分片
if has_phoneme:
    processed_text = preprocess_phoneme_markers(line.text)
    line = ScriptLine(..., text=processed_text, ...)
    # 重新检测
    has_advanced_markers = bool(re.search(r'\[(rate|pitch|pause|emphasis)=', processed_text))

# 只有真正的语气标记才触发分片
if has_advanced_markers:
    return await synthesize_advanced_line(...)
```

**效果**：
- 时长：21.05秒（减少 40%）
- 片段数：12个（减少 52%）
- 听感：流畅自然

**教训**：理解每种标记的语义，避免不必要的分片

### 坑4：Gradio 组件更新失败

**错误代码**：
```python
# ❌ 直接赋值无效
editor_status.value = "操作成功"
```

**原因**：Gradio 组件需要通过返回值更新

**解决方案**：
```python
# ✅ 通过返回值更新
def add_phoneme_marker(original_text, char, replacement):
    marked_text = original_text.replace(char, f"[phoneme={replacement}]{char}[/phoneme]", 1)
    return marked_text, f"✅ 已标注: {char} → {replacement}"

add_phoneme_btn.click(
    add_phoneme_marker,
    [original_text_display, phoneme_char_input, phoneme_replace_input],
    [original_text_display, editor_status]  # 🔑 指定输出组件
)
```

**教训**：遵循 Gradio 的事件处理模式

### 坑5：FFmpeg 路径问题

**错误现象**：
```
FileNotFoundError: [WinError 2] 系统找不到指定的文件
```

**原因**：
- Windows 下路径包含反斜杠
- FFmpeg concat demuxer 要求正斜杠

**解决方案**：
```python
# ✅ 转换为正斜杠
file_path = temp_file.replace('\\', '/')
f.write(f"file '{file_path}'\n")
```

**教训**：跨平台开发要注意路径分隔符

### 坑6：Docker 环境路径硬编码

**错误代码**：
```python
# ❌ 硬编码路径
AUDIO_DIR = Path("/app/data/audio")
```

**问题**：本地开发和 Docker 部署路径不同

**解决方案**：
```python
# ✅ 动态检测环境
import socket
hostname = socket.gethostname()

if hostname.startswith('tts-studio'):
    # Docker 环境
    AUDIO_DIR = Path("/app/data/audio")
else:
    # 本地环境
    AUDIO_DIR = Path(__file__).parent.parent / "data" / "audio"
```

**教训**：避免硬编码路径，根据环境动态适配

### 坑7：edge-tts 403 错误

**现象**：
```
edge_tts.exceptions.HTTPError: 403 Forbidden
```

**原因**：
- 频繁请求被 Microsoft 服务器限制
- IP 地址可能被临时封禁

**解决方案**：
```python
# ✅ 实现重试机制
for attempt in range(max_retries):
    try:
        communicate = edge_tts.Communicate(...)
        await communicate.save(output_path)
        break
    except Exception as e:
        if attempt < max_retries - 1:
            wait_time = 2 ** attempt  # 指数退避
            await asyncio.sleep(wait_time)
```

**额外措施**：
- 配置代理：`HTTP_PROXY=http://127.0.0.1:7890`
- 降低请求频率
- 缓存常用片段

**教训**：外部 API 调用必须有重试机制

### 坑8：Gradio 与 huggingface-hub 版本冲突

**错误现象**：
```
ImportError: cannot import name 'xxx' from 'huggingface_hub'
```

**原因**：Gradio 3.50.0 依赖特定版本的 huggingface-hub

**解决方案**：
```txt
# requirements.txt
gradio==3.50.0
huggingface-hub==0.19.4  # 锁定兼容版本
```

**教训**：严格锁定依赖版本，避免隐式升级

---

## 性能优化

### 优化前后对比

**测试用例**：包含 8 个多音字和 12 处语气变化的综合测试

| 指标 | 优化前 | 优化后 | 提升 |
|------|--------|--------|------|
| 时长 | 35-37秒 | 21.05秒 | **40%** ↓ |
| 片段数 | 25个 | 12个 | **52%** ↓ |
| 网络请求 | 25次 | 8次 | **68%** ↓ |
| 文件大小 | ~150KB | 123KB | 18% ↓ |
| 听感 | 一字一顿 | 流畅自然 | **质的飞跃** |

### 优化手段

#### 1. phoneme 不参与分片

**原理**：
- phoneme 只是文本替换，不需要改变语速/音调
- 替换后的文本可以作为整体合成
- 避免每个多音字都触发一次分片

**实现**：
```python
# 先替换 phoneme
if has_phoneme:
    processed_text = preprocess_phoneme_markers(line.text)
    line = ScriptLine(..., text=processed_text, ...)

# 再检测语气标记
has_advanced_markers = bool(re.search(r'\[(rate|pitch|pause|emphasis)=', processed_text))
```

**收益**：减少 13 个片段（从 25 降到 12）

#### 2. 减少不必要的标记

**原则**：
- 只对关键的多音字标注
- 语气变化要有层次感，不要每句都变
- 停顿不宜过多，保持自然节奏

**示例**：
```python
# ❌ 过度标记
"[phoneme=银]银[/phoneme][phoneme=航]行[/phoneme][phoneme=掌]掌[/phoneme][phoneme=长]长[/phoneme]"

# ✅ 精简标记
"银[phoneme=航]行[/phoneme][phoneme=掌]长[/phoneme]"
```

#### 3. 使用 FFmpeg concat demuxer

**优势**：
- 直接复制音频流，不重新编码
- 速度快，资源占用少
- 比 pydub append 快 3-5 倍

**实现**：
```python
cmd = [
    './ffmpeg.exe',
    '-f', 'concat',
    '-safe', '0',
    '-i', list_file,
    '-c', 'copy',  # 🔑 关键：直接复制
    '-y',
    output_path
]
```

#### 4. 未来优化方向

**并行合成**：
```python
# TODO: 使用 asyncio.gather() 并行合成
tasks = [synthesize_segment(seg) for seg in segments]
results = await asyncio.gather(*tasks, return_exceptions=True)
```

**缓存机制**：
```python
# TODO: 缓存常用片段
cache = {}

async def synthesize_with_cache(text, voice, rate, pitch):
    cache_key = f"{text}_{voice}_{rate}_{pitch}"
    if cache_key in cache:
        return cache[cache_key]
    
    duration = await synthesize_segment(...)
    cache[cache_key] = duration
    return duration
```

**批量预合成**：
- 后台预合成常用片段
- 用户需要时直接读取缓存

---

## 最佳实践

### 标记语法规范

#### 1. 语速控制

```python
# 范围：-50% ~ +50%
"[rate=-30%]慢速[/rate]"
"[rate=+20%]快速[/rate]"

# 常用场景
惊讶/兴奋：+20~30%
沉思/悲伤：-20~30%
紧张/急促：+30~50%
神秘/低沉：-30~40%
```

#### 2. 音调控制

```python
# 范围：-20Hz ~ +20Hz
"[pitch=+15Hz]高音[/pitch]"
"[pitch=-10Hz]低音[/pitch]"

# 常用场景
惊讶/兴奋：+15~20Hz
沉思/悲伤：-10~15Hz
紧张/急促：+10~15Hz
神秘/低沉：-15~20Hz
```

#### 3. 停顿插入

```python
# 单位：毫秒
"[pause=100]"  # 短停顿（逗号级别）
"[pause=300]"  # 中停顿（句号级别）
"[pause=500]"  # 长停顿（段落间隔）
"[pause=1000]" # 超长停顿（戏剧性停顿）

# 自然停顿原则
逗号处：100-200ms
句号处：200-300ms
段落间：400-600ms

# 戏剧性停顿
悬念前：300-500ms
转折处：400-600ms
高潮前：500-800ms
```

#### 4. 强调标记

```python
# 三种程度
"[emphasis=strong]强烈强调[/emphasis]"    # rate=-20%, pitch=+10Hz
"[emphasis=moderate]中等强调[/emphasis]"  # rate=-10%
"[emphasis=reduced]减弱强调[/emphasis]"   # 无效果
```

#### 5. 多音字标注

```python
# 格式：[phoneme=替换字]原字[/phoneme]
"[phoneme=航]行[/phoneme]"  # 银行 → 银航
"[phoneme=掌]长[/phoneme]"  # 行长 → 航掌

# 常见多音字对照表
行：hang2→航（银行），xing2→形（行动）
长：chang2→常（长短），zhang3→掌（生长）
重：zhong4→仲（重要），chong2→虫（重复）
乐：le5→勒（快乐），yue4→月（音乐）
好：hao3→郝（好坏），hao4→号（爱好）
着：zhe5→这（看着），zhao2→找（着急）
```

### 情感曲线设计

#### 一波三折示例

```python
text = (
    # 开头：慢速引入
    "[rate=-30%]那航掌[/rate]"
    
    # 悬念停顿
    "[pause=300]"
    
    # 发展：高音惊讶
    "[pitch=+15Hz]竟然仲新[/pitch]"
    
    # 加速叙述
    "[rate=+20%]走进了那家月器店[/rate]"
    
    # 转折：低音沉思
    "[pitch=-10Hz]看着那些郝玩的乐器[/pitch]"
    
    # 高潮前停顿
    "[pause=400]"
    
    # 高潮：高音惊叹
    "[pitch=+20Hz]突然！[/pitch]"
    
    # 快速兴奋
    "[rate=+30%]他发现了一个常虫的箱子[/rate]"
    
    # 最大悬念
    "[pause=500]"
    
    # 结尾：极慢极低（神秘）
    "[rate=-40%][pitch=-15Hz]里面...到底是什么呢？[/pitch][/rate]"
)
```

**设计原则**：
1. **起**：慢速引入，建立氛围
2. **承**：逐渐加快，推进情节
3. **转**：音调突变，制造转折
4. **合**：回归平静，留下余韵

### Web UI 操作技巧

#### 1. 高效标注多音字

**步骤**：
1. 阅读文本，找出所有多音字
2. 逐个标注，不要遗漏
3. 标注完成后统一试听

**技巧**：
- 使用常见多音字对照表
- 不确定时查阅字典
- 标注后立即试听验证

#### 2. 语气变化设计

**步骤**：
1. 分析文本的情感变化
2. 设计情感曲线（起承转合）
3. 逐段调整语速和音调
4. 插入关键停顿

**技巧**：
- 先粗调（大范围变化）
- 再微调（小幅度优化）
- 多次试听，找到最佳平衡

#### 3. 停顿使用原则

**自然停顿**：
- 标点符号处必须停顿
- 时长符合语言习惯
- 不要过度停顿

**戏剧性停顿**：
- 用于制造悬念
- 用于强调转折
- 用于烘托气氛

**禁忌**：
- 不要每句话都加停顿
- 停顿时长要有层次
- 避免机械化的固定时长

### 代码开发规范

#### 1. 日志记录

```python
# ✅ 好的日志
logger.info(f"📝 检测到 phoneme 标记，将预处理替换")
logger.info(f"   替换前: {line.text[:200]}")
logger.info(f"   替换后: {processed_text[:200]}")
logger.info(f"📊 解析结果: {len(segments)} 个片段")

# ❌ 不好的日志
print("processing...")
```

**原则**：
- 使用 emoji 区分日志类型
- 关键信息缩进显示
- 包含上下文信息
- 避免敏感信息泄露

#### 2. 错误处理

```python
# ✅ 好的错误处理
for attempt in range(max_retries):
    try:
        communicate = edge_tts.Communicate(...)
        await communicate.save(temp_path)
        break
    except Exception as e:
        last_error = e
        logger.warning(f"⚠️  片段 {i+1} 尝试 {attempt+1}/{max_retries} 失败: {e}")
        if attempt < max_retries - 1:
            await asyncio.sleep(2 ** attempt)

if last_error:
    raise last_error

# ❌ 不好的错误处理
try:
    communicate = edge_tts.Communicate(...)
    await communicate.save(temp_path)
except:
    pass
```

**原则**：
- 明确的异常类型
- 指数退避重试
- 详细的错误日志
- 最终抛出异常

#### 3. 资源管理

```python
# ✅ 好的资源管理
temp_files = []
try:
    for seg in segments:
        temp_path = generate_temp_file(...)
        temp_files.append(temp_path)
    
    concatenate_files(temp_files, output_path)
finally:
    for temp_file in temp_files:
        try:
            if os.path.exists(temp_file):
                os.remove(temp_file)
        except:
            pass

# ❌ 不好的资源管理
temp_files = []
for seg in segments:
    temp_path = generate_temp_file(...)
    temp_files.append(temp_path)

concatenate_files(temp_files, output_path)
# 忘记清理临时文件
```

**原则**：
- 使用 try-finally 确保清理
- 容错处理：单个文件删除失败不影响其他
- 及时释放资源

---

## 项目文件结构

```
tts-studio/
├── app/                          # 应用核心代码
│   ├── __init__.py
│   ├── main.py                   # 应用入口
│   ├── config.py                 # 配置管理
│   ├── models.py                 # 数据模型
│   ├── ui.py                     # Web UI（Gradio）
│   ├── llm_parser.py             # LLM 文本解析
│   ├── project_manager.py        # 工程管理
│   ├── tts_engine.py             # TTS 引擎入口
│   ├── tts_parser.py             # 文本解析器
│   ├── tts_advanced.py           # 高级合成引擎
│   └── tts_concat.py             # 音频拼接工具
├── data/                         # 数据目录
│   ├── audio/                    # 音频文件
│   │   ├── *.mp3                 # 生成的音频
│   │   └── temp_*.mp3            # 临时文件（自动清理）
│   └── projects/                 # 工程配置
│       └── *.json                # 工程文件
├── patch_edge_tts_v2.py          # Monkey Patch
├── requirements.txt              # Python 依赖
├── .env                          # 环境变量
├── .env.example                  # 环境变量模板
├── Dockerfile                    # Docker 配置
├── docker-compose.yml            # Docker Compose 配置
├── setup.sh                      # 安装脚本
├── EDGE_TTS_ADVANCED_MARKERS_GUIDE.md  # 技术文档
├── MULTI_PRONUNCIATION_EDITOR_GUIDE.md # 编辑器使用指南
├── PROJECT_BASELINE.md           # 项目基础文档（本文件）
├── test_ssml_before_split.py     # SSML 转换演示
├── test_ultimate_acceptance.py   # 综合验收测试
└── README.md                     # 项目说明
```

### 核心文件说明

| 文件 | 行数 | 职责 | 关键函数 |
|------|------|------|----------|
| app/tts_parser.py | 273 | 文本解析 | parse_marked_text(), preprocess_phoneme_markers() |
| app/tts_advanced.py | 282 | 高级合成 | synthesize_advanced_line() |
| app/tts_engine.py | 439 | TTS 引擎 | synthesize_single_line() |
| app/ui.py | 760 | Web UI | build_ui(), 各种事件处理函数 |
| patch_edge_tts_v2.py | 117 | Monkey Patch | patched_communicate_init(), patched_mkssml() |

---

## 部署与运行

### 本地开发环境

#### 1. 安装依赖

```bash
# Python 3.10+
pip install -r requirements.txt
```

**requirements.txt**：
```txt
edge-tts==7.2.8
gradio==3.50.0
pydub==0.25.1
mutagen==1.47.0
huggingface-hub==0.19.4
aiohttp>=3.8.0
```

#### 2. 安装 FFmpeg

**Windows**：
1. 下载 FFmpeg：https://www.gyan.dev/ffmpeg/builds/
2. 解压到项目根目录
3. 重命名为 `ffmpeg.exe`

**Linux**：
```bash
sudo apt-get install ffmpeg
```

**macOS**：
```bash
brew install ffmpeg
```

#### 3. 配置环境变量

创建 `.env` 文件：
```env
# LLM 配置（可选）
DEFAULT_API_BASE=http://localhost:11434/v1
DEFAULT_API_KEY=ollama
DEFAULT_MODEL=qwen2.5:7b

# 代理配置（可选）
HTTP_PROXY=http://127.0.0.1:7890
HTTPS_PROXY=http://127.0.0.1:7890
```

#### 4. 启动应用

```bash
cd C:\work\227\voice\a\tts-studio
python -m app.main
```

访问：http://localhost:7860

### Docker 部署

#### 1. 构建镜像

```bash
docker build -t tts-studio .
```

#### 2. 运行容器

```bash
docker-compose up -d
```

#### 3. 访问应用

http://localhost:7860

### 常见问题

#### Q1: 启动时报错 "No module named 'xxx'"

**解决**：
```bash
pip install -r requirements.txt
```

#### Q2: FFmpeg 找不到

**解决**：
- Windows: 确保 `ffmpeg.exe` 在项目根目录
- Linux/macOS: `which ffmpeg` 确认已安装

#### Q3: edge-tts 403 错误

**解决**：
```env
# .env
HTTP_PROXY=http://127.0.0.1:7890
HTTPS_PROXY=http://127.0.0.1:7890
```

#### Q4: Gradio 界面空白

**解决**：
```bash
# 检查版本兼容性
pip install gradio==3.50.0 huggingface-hub==0.19.4
```

---

## 总结与展望

### 项目成果

✅ **核心功能**：
- 支持复杂的多音字处理
- 实现一句话内多处语气变化
- 提供可视化的标记编辑界面
- 性能优化显著（时长减少 40%）

✅ **技术突破**：
- Monkey Patch Edge-TTS，突破官方限制
- 分层架构设计，职责清晰
- 智能分片策略，避免过度拆分
- 完善的错误处理和重试机制

✅ **用户体验**：
- 操作简单直观
- 实时预览效果
- 工程配置持久化
- 详细的文档支持

### 未来规划

#### 短期（1-2周）

1. **并行合成优化**
   - 使用 asyncio.gather() 并行合成多个片段
   - 预计提速 30-50%

2. **缓存机制**
   - 缓存常用片段的音频
   - 避免重复合成

3. **UI 增强**
   - 支持文本中选择位置插入标记
   - 批量标注多个相同的多音字
   - 标记语法高亮显示

#### 中期（1-2月）

1. **音色库扩展**
   - 支持更多音色
   - 音色预览功能
   - 自定义音色上传

2. **背景乐混音**
   - 支持上传背景音乐
   - 自动调整音量比例
   - 淡入淡出效果

3. **批量处理**
   - 支持批量导入文本
   - 批量生成音频
   - 批量导出

#### 长期（3-6月）

1. **AI 辅助标注**
   - 自动识别多音字
   - 智能推荐语气变化
   - 情感分析驱动的语气调整

2. **协作功能**
   - 多用户协同编辑
   - 版本控制
   - 评论和审核

3. **云端部署**
   - SaaS 服务
   - API 接口开放
   - 按需计费

### 致谢

感谢以下开源项目：
- **edge-tts**：提供高质量的 TTS 服务
- **Gradio**：简化 Web UI 开发
- **FFmpeg**：强大的音频处理工具
- **pydub**：便捷的音频操作库

---

**文档维护**：
- 每次重大变更需更新此文档
- 新增功能需在相应章节补充说明
- 发现问题需在"踩过的坑"章节记录
- 定期回顾并优化最佳实践

**联系方式**：
- 项目仓库：C:\work\227\voice\a\tts-studio
- 技术文档：EDGE_TTS_ADVANCED_MARKERS_GUIDE.md
- 使用指南：MULTI_PRONUNCIATION_EDITOR_GUIDE.md

---

**最后更新**: 2026-04-13  
**版本**: v2.0  
**维护者**: TTS Studio 团队

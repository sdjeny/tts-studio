# TTS 高级标记语法 + 自动拆分拼接方案

## 📋 概述

由于 edge-tts 的限制（只支持单个 `<prosody>` 标签，不支持逗号分隔多值），我们实现了**TTS 层自动拆分+拼接**方案。

## 🎯 核心原理

**问题**：edge-tts 不支持一行文本内多次语速/音调变化

**解决方案**：
1. **解析标记**：从文本中提取 `{rate=...}` 等标记
2. **自动拆分**：将文本拆分成多个子片段
3. **独立合成**：每个片段分别调用 edge-tts
4. **自动拼接**：使用 FFmpeg 将所有片段拼接成完整音频

## 📝 标记语法

### 基本语法

```
{标记名=值}文本内容{/标记名}
```

### 支持的标记

| 标记名 | 说明 | 示例 | 取值范围 |
|--------|------|------|----------|
| `rate` | 语速 | `{rate=-50%}慢速{/rate}` | -100% ~ +100% |
| `pitch` | 音调 | `{pitch=+20Hz}高音{/pitch}` | 无限制 |
| `style` | 复合样式 | `{style=rate=-30%,pitch=+10Hz}效果{/style}` | 组合 |
| `pause` | 停顿 | `{pause=500}` | 毫秒 |

### 使用示例

#### 示例1：简单语速变化

```
{rate=-50%}这句话很慢{/rate} 然后正常 {rate=+50%}这句话很快{/rate}
```

效果：
- "这句话很慢" - 慢速 (-50%)
- "然后正常" - 正常语速 (+0%)
- "这句话很快" - 快速 (+50%)

#### 示例2：音调变化

```
{pitch=+20Hz}高音部分{/pitch} 正常 {pitch=-20Hz}低音部分{/pitch}
```

#### 示例3：复合样式

```
{style=rate=-40%,pitch=+10Hz}慢速高音{/style}
{pause=500}
{style=rate=+40%,pitch=-10Hz}快速低音{/style}
```

效果：
- "慢速高音" - rate=-40%, pitch=+10Hz
- 停顿 500ms
- "快速低音" - rate=+40%, pitch=-10Hz

#### 示例4：多音字处理

edge-tts 会自动处理常见多音字，但无法精确控制。

**间接方案**：通过拆分，让多音字独立成片段，edge-tts 会基于上下文自动选择正确的读音。

```
这个{rate=+0%}重{/rate}要的事情说三遍
```

"重" 独立成片段后，edge-tts 会根据"重要"这个上下文读成 `zhòng`。

## 🔧 工作流程

### 1. 文本解析

```python
from app.tts_advanced import parse_rate_pitch_from_text

text = "{rate=-50%}慢{/rate} 正常 {rate=+50%}快{/rate}"
segments = parse_rate_pitch_from_text(text)

# 返回：
# [
#   ('慢', '-50%', '+0Hz'),
#   ('正常', '+0%', '+0Hz'),
#   ('快', '+50%', '+0Hz')
# ]
```

### 2. 独立合成

每个片段调用 `synthesize_text_segment()`，生成独立的 MP3 文件。

### 3. 自动拼接

使用 FFmpeg (pydub) 将所有片段按顺序拼接：

```python
from pydub import AudioSegment

combined = AudioSegment.empty()
for file in temp_files:
    audio = AudioSegment.from_mp3(file)
    combined += audio

combined.export(output_path, format="mp3")
```

### 4. 清理临时文件

合成完成后自动删除临时文件。

## ⚙️ 安装要求

### 必需

- Python 3.10+
- edge-tts 7.2.8
- pydub（已安装）
- **FFmpeg**（用于音频拼接）

### FFmpeg 安装

详见 [FFMPEG_INSTALL_GUIDE.md](./FFMPEG_INSTALL_GUIDE.md)

## 🧪 测试

运行测试脚本：

```powershell
python test_advanced_tts.py
```

测试会生成以下文件：
- `data/audio/test_advanced_1.mp3` - 多个语速变化
- `data/audio/test_advanced_2.mp3` - 音调变化
- `data/audio/test_advanced_3.mp3` - 复合样式 + 停顿
- `data/audio/test_advanced_4.mp3` - 多音字处理

## 📊 性能考虑

- **片段数量**：每个片段需要一次 edge-tts API 调用
- **建议**：单行文本的片段数不超过 5-7 个
- **时间**：每增加一个片段，增加约 1-3 秒（网络延迟 + 合成时间）

## 🔄 与旧语法的兼容性

项目支持两种标记语法：

### 新语法（推荐）

```
{rate=-50%}文本{/rate}
```

- TTS 层自动拆分 + 拼接
- 支持任意数量的片段
- 需要 FFmpeg

### 旧语法（SSML）

```
<speak version='1.0'>
  <voice name='...'>
    <prosody rate='-50%'>文本</prosody>
  </voice>
</speak>
```

- 直接传给 edge-tts
- 最多支持 2 个 `<prosody>` 标签
- 不需要 FFmpeg

## ❓ 常见问题

### Q: 为什么要用 `{}` 而不是 `[]`？

A: `{}` 更容易与 SSML 的 `<>` 区分，避免解析冲突。

### Q: 标记会被读出来吗？

A: 不会！标记只是内部指令，会被解析器移除，不会出现在最终音频中。

### Q: 如果没有 FFmpeg 会怎样？

A: 新语法（`{rate=...}`）会失败，但旧语法（SSML）和普通文本仍然可以正常使用。

### Q: 多音字能精确控制吗？

A: edge-tts 不支持 `<phoneme>` 标签。间接方案：
1. 将多音字独立成片段
2. 利用上下文让 edge-tts 自动选择正确读音
3. 或使用同音字替换（如用"众"代替"重"）

### Q: 停顿标记 `{pause=500}` 准确吗？

A: 非常准确！会生成精确的 500ms 静音片段。

##  核心文件

- `app/tts_advanced.py` - 高级 TTS 引擎（拆分 + 拼接）
- `app/tts_parser.py` - 文本解析器
- `app/tts_engine.py` - TTS 引擎入口（自动检测语法类型）
- `test_advanced_tts.py` - 测试脚本

## 🎉 总结

通过**自动拆分 + 独立合成 + FFmpeg 拼接**的方案，我们绕过了 edge-tts 的限制，实现了：

✅ 一句话内多次语速变化  
✅ 一句话内多次音调变化  
✅ 精确的停顿控制  
✅ 多音字的间接控制  
✅ 完整的音频拼接流程  

唯一的要求是安装 FFmpeg（约 65MB）。

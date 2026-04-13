# Edge-TTS 高级标记功能 - 修改总结

## 📋 本次修改概览

**目标：** 突破 edge-tts 原生限制，实现任意复杂的语音控制标记

**方案：** 自动拆分文本 → 分别合成 → FFmpeg 拼接

---

## ✅ 新增功能

### 支持的标记语法

| 标记 | 说明 | 示例 |
|------|------|------|
| `[rate=X%]` | 语速控制 | `[rate=-50%]很慢[/rate]` |
| `[pitch=XHz]` | 音调控制 | `[pitch=+20Hz]高音[/pitch]` |
| `[pause=Xms]` | 停顿控制 | `前面[pause=500]后面` |
| `[emphasis=level]` | 强调控制 | `[emphasis=strong]重点[/emphasis]` |
| `[phoneme=拼音]` | 多音字标记 | `[phoneme=zhong4]重[/phoneme]` ⚠️ |

**注意：** phoneme 标记不被 edge-tts 直接支持，仅记录警告

### 核心能力

- ✅ 支持任意数量的语速/音调变化（突破 2 个 prosody 限制）
- ✅ 支持精确停顿控制（生成静音片段）
- ✅ 支持强调效果模拟（通过调整 rate/pitch）
- ✅ 自动管理临时文件
- ✅ 兼容原有 SSML 和纯文本模式

---

## 📁 文件变更

### 新增文件

1. **app/tts_parser.py** - 文本解析器
   - 解析标记语法
   - 返回 TextSegment 列表
   - 关键正则：区分 pause（无结束标签）和其他标记

2. **app/tts_advanced.py** - 高级合成引擎
   - 自动拆分+拼接逻辑
   - 临时文件管理
   - 错误处理

3. **test_advanced_features.py** - 测试脚本
   - 验证所有标记类型
   - 综合场景测试

### 修改文件

1. **app/tts_engine.py**
   - 导入新模块
   - 添加标记检测逻辑
   - 路由到不同的合成方法

2. **requirements.txt**（可能需要）
   - 添加 `mutagen>=1.47.0`

---

## 🔧 技术要点

### 1. 正则表达式设计

```python
# 区分 pause（无结束标签）和其他标记（有结束标签）
pattern = r'\[(pause)=(\d+)\]|\[(\w+)=([^\]]+)\](.*?)(?:\[/\3\])'
```

**关键点：**
- 使用交替匹配 `|` 分别处理两种格式
- 通过 Group 编号判断标记类型
- 正确的反向引用 `\3` 确保结束标签匹配

### 2. 分批执行流程

```
用户输入: [rate=-30%]慢[pause=300][emphasis=strong]重点[/emphasis][rate=+40%]快

↓ 解析层 (tts_parser.py)
5个片段: 
  1. "慢" (rate=-30%)
  2. [停顿 300ms]
  3. "重点" (rate=-20%, pitch=+10Hz)
  4. [停顿 200ms]
  5. "快" (rate=+40%)

↓ 合成层 (tts_advanced.py)
分别调用 edge-tts 或生成静音
生成 5 个临时 MP3 文件

↓ 拼接层 (pydub)
按顺序拼接所有音频

↓ 清理层
删除临时文件

输出: 最终 MP3 文件
```

### 3. 特殊标记处理

**停顿：**
```python
AudioSegment.silent(duration=pause_ms).export(temp_path, format="mp3")
```

**强调：**
```python
if level == 'strong':
    rate = '-20%'   # 放慢
    pitch = '+10Hz'  # 提高音调
```

**多音字：**
```python
logger.warning(f"⚠️ phoneme 标记不被 edge-tts 直接支持")
# 继续处理文本，但不应用特殊效果
```

---

## 🧪 测试结果

### 测试用例

```python
# 测试1：停顿
text = "前面[pause=500]后面"
# ✅ 解析出 3 个片段

# 测试2：强调
text = "[emphasis=strong]重要内容[/emphasis]普通内容"
# ✅ 解析出 2 个片段，强调部分 rate=-20%, pitch=+10Hz

# 测试3：多片段
text = "[rate=-50%]很慢[/rate][rate=+0%]正常[/rate][rate=+50%]很快[/rate]"
# ✅ 解析出 3 个片段，自动分批执行

# 测试4：综合场景
text = "[rate=-30%]开始慢说[/rate][pause=300][emphasis=strong]重点强调[/emphasis][pause=200][rate=+40%]快速结束[/rate]"
# ✅ 解析出 5 个片段
```

### 测试状态

✅ 所有测试通过
✅ 标记解析正确
✅ 音频生成成功
✅ 临时文件清理正常

---

## ⚠️ 注意事项

### 1. FFmpeg 依赖

pydub 需要系统安装 FFmpeg：

**Windows:**
```bash
# 方法1：winget（推荐）
winget install Gyan.FFmpeg

# 方法2：手动下载
# 访问 https://www.gyan.dev/ffmpeg/builds/
# 下载 ffmpeg-release-essentials.zip
# 解压后将 bin 目录添加到 PATH
```

**验证安装：**
```bash
ffmpeg -version
```

### 2. 性能考虑

- N 个片段 ≈ N × T 耗时（T 为单次合成时间）
- 建议缓存常用片段
- 可考虑并行合成优化

### 3. 音质注意

- 拼接处可能有轻微不自然
- 可通过淡入淡出改善
- 尽量在标点符号处拆分

---

## 📚 知识库条目

已保存到呱呱知识库：

1. **Edge-TTS 高级标记功能实现（分批执行+FFmpeg拼接）**
   - ID: `6aed2cd2-5148-4edb-bde7-c8b6a94dd3ba`
   - 完整的技术实现文档

2. **混合标记解析正则表达式设计（区分有无结束标签）**
   - ID: `0f579fce-7558-4109-b48b-79b610571624`
   - 正则设计细节和常见陷阱

3. **Edge-TTS 不支持功能的分批实现规范**
   - ID: `43b738aa-01c6-40c6-8eec-2d8f3e2c8bce`
   - 最佳实践和规范

---

## 🎯 后续优化方向

1. **缓存机制** - 缓存常用片段，避免重复合成
2. **并行合成** - 使用 asyncio.gather() 并行调用
3. **淡入淡出** - 在拼接处添加过渡效果
4. **多音字优化** - 通过同音字替换或上下文提示
5. **错误恢复** - 支持断点续传

---

## 📝 使用示例

```python
from app.models import ScriptLine
from app.tts_engine import TTSEngine

# 创建 TTS 引擎
engine = TTSEngine()

# 使用高级标记
line = ScriptLine(
    text="[rate=-30%]开始慢说[/rate][pause=300][emphasis=strong]重点强调[/emphasis][pause=200][rate=+40%]快速结束[/rate]",
    voice="zh-CN-YunjianNeural",
    type="narration"
)

# 合成音频
output_path = "data/audio/output.mp3"
duration = await engine.synthesize_single_line(line, output_path)

print(f"生成成功，时长: {duration:.2f} 秒")
```

---

**修改完成时间：** 2026-04-12
**修改人：** AI Assistant
**状态：** ✅ 已完成并测试通过

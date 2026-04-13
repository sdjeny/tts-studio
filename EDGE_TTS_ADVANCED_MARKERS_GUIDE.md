# Edge-TTS 高级标记功能技术文档

> **版本**: v2.0  
> **更新日期**: 2026-04-13  
> **维护者**: TTS Studio 团队

---

## 📋 目录

1. [背景与目标](#背景与目标)
2. [Edge-TTS 能力边界](#edge-tts-能力边界)
3. [Monkey Patch 实现](#monkey-patch-实现)
4. [切片处理架构](#切片处理架构)
5. [多音字处理策略](#多音字处理策略)
6. [性能优化实践](#性能优化实践)
7. [常见问题与解决方案](#常见问题与解决方案)
8. [最佳实践指南](#最佳实践指南)

---

## 背景与目标

### 为什么需要 Monkey Patch？

**问题场景**：
- edge-tts 官方库（v7.2.8）只支持简单的文本输入和全局的 rate/pitch/volume 参数
- 不支持 SSML 中的 `<break>`、`<phoneme>`、`<emphasis>` 等标签
- 最多只支持 2 个 `<prosody>` 标签嵌套
- 无法在单个请求中实现"一句话内多处语气变化"

**目标需求**：
```python
# 期望的效果：一句话内有多个语气变化
"[rate=-30%]那航掌[/rate][pause=300][pitch=+15Hz]竟然仲新[/pitch]"
```

**解决方案**：
通过 Monkey Patch 修改 edge-tts 的内部方法，使其能够接受自定义 SSML，然后在上层实现"自动拆分 → 分别合成 → FFmpeg 拼接"的架构。

---

## Edge-TTS 能力边界

### ✅ 原生支持的功能

#### 1. 基础文本合成
```python
communicate = edge_tts.Communicate(
    text="你好世界",
    voice="zh-CN-YunjianNeural",
    rate="+0%",
    pitch="+0Hz",
    volume="+0%"
)
await communicate.save("output.mp3")
```

#### 2. 单个或两个 prosody 标签
```xml
<!-- 支持 -->
<speak>
  <voice name="zh-CN-YunjianNeural">
    <prosody rate="-30%" pitch="+10Hz">文本</prosody>
  </voice>
</speak>
```

#### 3. 完整的自定义 SSML（通过 Monkey Patch）
```xml
<!-- 通过补丁后可以传入任意 SSML -->
<speak version='1.0' xmlns='http://www.w3.org/2001/10/synthesis'>
  <voice name='zh-CN-YunjianNeural'>
    <prosody rate='-30%' pitch='+10Hz' volume='+0%'>
      自定义内容
    </prosody>
  </voice>
</speak>
```

### ❌ 不支持的功能（需绕过）

#### 1. `<break>` 标签（停顿）
```xml
<!-- ❌ 不支持 -->
<break time="500ms"/>

<!-- ✅ 替代方案：生成静音片段并拼接 -->
[pause=500] → 使用 FFmpeg 生成 500ms 静音
```

#### 2. `<phoneme>` 标签（多音字/发音标注）
```xml
<!-- ❌ 不支持 -->
<phoneme alphabet="py" ph="hang2">行</phoneme>

<!-- ✅ 替代方案：同音字替换 -->
[phoneme=航]行[/phoneme] → 预处理时将"行"替换为"航"
```

#### 3. `<emphasis>` 标签（强调）
```xml
<!-- ❌ 不支持 -->
<emphasis level="strong">重要</emphasis>

<!-- ✅ 替代方案：调整语速和音调模拟 -->
[emphasis=strong]重要[/emphasis] 
→ rate=-20%, pitch=+10Hz（放慢+提高音调）
```

#### 4. 3 个以上的 prosody 标签嵌套
```xml
<!-- ❌ 不支持 -->
<prosody rate="-30%">
  <prosody pitch="+10Hz">
    <prosody volume="+20%">文本</prosody>
  </prosody>
</prosody>

<!-- ✅ 替代方案：拆分成多个片段分别合成 -->
```

#### 5. rate/pitch 逗号分隔多值
```python
# ❌ 不支持
communicate = edge_tts.Communicate(
    text="文本",
    rate="-30%,+10%",  # 错误！
    pitch="+10Hz"
)

# ✅ 正确做法：分开设置
rate="-30%"
pitch="+10Hz"
```

---

## Monkey Patch 实现

### 核心原理

通过直接替换 `edge_tts.communicate` 模块的关键方法，使 edge-tts 能够接受自定义 SSML 而不进行额外的转义或包装。

### 实现代码

文件：`patch_edge_tts_v2.py`

```python
"""
强制让 edge-tts 支持自定义 SSML
通过直接替换 Communicate 类的关键方法
"""
import edge_tts.communicate
from edge_tts.data_classes import TTSConfig
from edge_tts.communicate import split_text_by_byte_length, remove_incompatible_characters
from xml.sax.saxutils import escape as _original_escape
import aiohttp

# 保存原始方法（可选，用于调试）
_original_communicate_init = edge_tts.communicate.Communicate.__init__
_original_mkssml = edge_tts.communicate.mkssml

def patched_communicate_init(self, text, voice='en-US-EmmaMultilingualNeural', *, 
                              rate='+0%', volume='+0%', pitch='+0Hz', 
                              boundary='SentenceBoundary', connector=None, 
                              proxy=None, connect_timeout=10, receive_timeout=60):
    """
    修补后的 __init__，支持检测并保留自定义 SSML
    """
    # Validate TTS settings
    self.tts_config = TTSConfig(voice, rate, volume, pitch, boundary)

    # Validate the text parameter
    if not isinstance(text, str):
        raise TypeError("text must be str")

    # 🔑 关键：检测是否是自定义 SSML
    is_custom_ssml = text.strip().startswith('<speak')
    
    if is_custom_ssml:
        # 对于自定义 SSML，不进行 escape，保持为字符串
        print(f"[DEBUG] 检测到自定义 SSML，跳过 escape")
        self.texts = [text]  # 保持为 str，不是 bytes!
        self._is_custom_ssml = True
    else:
        # 普通文本，正常处理
        escaped_text = _original_escape(remove_incompatible_characters(text))
        self.texts = split_text_by_byte_length(escaped_text, 4096)
        self._is_custom_ssml = False

    # 其余初始化代码保持不变...
    self.proxy = proxy
    self.session_timeout = aiohttp.ClientTimeout(...)
    self.connector = connector
    self.state = {...}

def patched_mkssml(tc, escaped_text):
    """
    修补后的 mkssml，如果已经是完整 SSML 则直接返回
    """
    # 检查是否已经是完整 SSML（bytes 或 str）
    print(f"\n[DEBUG] mkssml called with type: {type(escaped_text)}")
    
    if isinstance(escaped_text, bytes):
        text_str = escaped_text.decode('utf-8')
    else:
        text_str = escaped_text
    
    print(f"[DEBUG] First 100 chars: {text_str[:100]}")
    
    if text_str.strip().startswith('<speak'):
        # 🔑 关键：已经是完整 SSML，直接返回（保持原始类型）
        print(f"[DEBUG] Detected custom SSML, returning as-is")
        print(f"[SSML] {text_str}\n")
        return escaped_text
    
    # 普通文本，使用原始逻辑构建 SSML
    if isinstance(escaped_text, bytes):
        escaped_text = escaped_text.decode("utf-8")

    ssml = (
        "<speak version='1.0' xmlns='http://www.w3.org/2001/10/synthesis' xml:lang='en-US'>"
        f"<voice name='{tc.voice}'>"
        f"<prosody pitch='{tc.pitch}' rate='{tc.rate}' volume='{tc.volume}'>"
        f"{escaped_text}"
        "</prosody>"
        "</voice>"
        "</speak>"
    )
    
    print(f"[SSML] {ssml}\n")
    return ssml

# 🔑 应用补丁
edge_tts.communicate.Communicate.__init__ = patched_communicate_init
edge_tts.communicate.mkssml = patched_mkssml

print("OK: edge-tts patched successfully")
```

### 应用补丁

在 `tts_engine.py` 中导入补丁：

```python
# 应用 edge-tts 补丁以支持自定义 SSML
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import patch_edge_tts_v2
```

### 关键注意事项

#### ⚠️ 类型陷阱

**问题**：`mkssml` 函数可能接收到 `str` 或 `bytes` 类型的参数

**解决**：
```python
if isinstance(escaped_text, bytes):
    text_str = escaped_text.decode('utf-8')
else:
    text_str = escaped_text
```

#### ⚠️ 避免重复转义

**问题**：自定义 SSML 不应再经过 XML 转义

**解决**：
```python
if is_custom_ssml:
    self.texts = [text]  # 不转义，直接存储
else:
    escaped_text = _original_escape(remove_incompatible_characters(text))
    self.texts = split_text_by_byte_length(escaped_text, 4096)
```

---

## 切片处理架构

### 为什么要切片？

#### 根本原因

1. **edge-tts 的限制**：
   - 每个请求只能设置一组全局的 rate/pitch/volume
   - 无法在单个请求中实现"前半句慢速，后半句快速"

2. **自然语言的需求**：
   ```python
   # 期望效果：情绪有起伏
   "[rate=-30%]他慢慢地[/rate][rate=+20%]跑了起来[/rate]"
   
   # 如果不切片，只能选择一种语速，无法表达情绪变化
   ```

3. **特殊标记的处理**：
   - `[pause=500]` 需要生成静音片段
   - `[phoneme=航]行[/phoneme]` 需要预处理替换
   - `[emphasis=strong]` 需要转换为 rate/pitch 调整

#### 切片的代价

**优点**：
- ✅ 实现复杂的语气变化
- ✅ 支持停顿、强调等特殊效果
- ✅ 灵活控制每个片段的参数

**缺点**：
- ⚠️ 耗时增加：N 个片段 ≈ N × T（T 为单次合成时间）
- ⚠️ 网络开销：每次切片都需要一次 HTTP 请求
- ⚠️ 拼接处可能轻微不自然（已通过淡入淡出缓解）

### 架构设计

```
┌─────────────────────────────────────────┐
│  用户输入                                 │
│  "[rate=-30%]慢速[/rate][pause=300]     │
│   [pitch=+15Hz]高音[/pitch]"            │
└──────────────┬──────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────┐
│  解析层 (tts_parser.py)                  │
│  parse_marked_text()                     │
│                                          │
│  输出：                                   │
│  [                                      │
│    TextSegment(text="慢速",              │
│                rate="-30%",              │
│                pitch="+0Hz"),            │
│    TextSegment(text="__PAUSE_300__",    │
│                segment_type="pause"),    │
│    TextSegment(text="高音",              │
│                rate="+0%",               │
│                pitch="+15Hz")            │
│  ]                                      │
└──────────────┬──────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────┐
│  合成层 (tts_advanced.py)                │
│  synthesize_advanced_line()              │
│                                          │
│  for seg in segments:                    │
│    if pause:                             │
│      生成静音片段 (FFmpeg)                │
│    else:                                 │
│      调用 edge-tts 合成                   │
│                                          │
│  临时文件：                               │
│  temp_seg0.mp3, temp_pause1.mp3,        │
│  temp_seg2.mp3                           │
└──────────────┬──────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────┐
│  拼接层 (FFmpeg concat demuxer)          │
│                                          │
│  ffmpeg -f concat -i list.txt           │
│         -c copy output.mp3              │
│                                          │
│  输出：output.mp3                        │
└──────────────┬──────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────┐
│  清理层                                  │
│  删除所有临时文件                         │
└─────────────────────────────────────────┘
```

### 核心代码

#### 1. 解析层

文件：`app/tts_parser.py`

```python
def parse_marked_text(text: str, default_rate: str = "+0%", default_pitch: str = "+0Hz") -> List[TextSegment]:
    """
    解析带有标记的文本
    
    支持的标记语法：
    - [rate=-50%]慢速部分[/rate]
    - [pitch=+20Hz]高音部分[/pitch]
    - [pause=500] 停顿 500ms
    - [emphasis=strong]强调部分[/emphasis]
    - [phoneme=同音字]原字[/phoneme]
    """
    if not text or not text.strip():
        return []
    
    # 检查是否包含标记
    if not _has_markers(text):
        return [TextSegment(text=text, rate=default_rate, pitch=default_pitch, is_marked=False)]
    
    segments = []
    
    # 🔑 关键正则：区分有无结束标签的标记
    pattern = r'\[(pause)=(\d+)\]|\[(\w+)=([^\]]+)\](.*?)(?:\[/\3\])'
    
    def parse_nested(text: str, current_params: Dict[str, str]) -> List[TextSegment]:
        """递归解析嵌套标记"""
        result = []
        last_end = 0
        
        for match in re.finditer(pattern, text):
            start, end = match.span()
            
            # 判断是 pause 还是其他标记
            if match.group(1):  # pause 标记
                tag_name = 'pause'
                tag_value = match.group(2)
                tag_content = ''
            else:  # 其他标记
                tag_name = match.group(3)
                tag_value = match.group(4)
                tag_content = match.group(5) if match.group(5) else ''
            
            # 添加标记前的纯文本
            if start > last_end:
                plain_text = text[last_end:start]
                if plain_text.strip():
                    result.append(TextSegment(
                        text=plain_text,
                        rate=current_params.get('rate', default_rate),
                        pitch=current_params.get('pitch', default_pitch),
                        is_marked=False
                    ))
            
            # 更新当前参数
            new_params = current_params.copy()
            if tag_name == 'rate':
                new_params['rate'] = tag_value
            elif tag_name == 'pitch':
                new_params['pitch'] = tag_value
            elif tag_name == 'pause':
                # 停顿标记：生成一个特殊片段
                duration_ms = int(tag_value)
                result.append(TextSegment(
                    text=f"__PAUSE_{duration_ms}__",
                    rate=str(duration_ms),  # 用 rate 字段存储时长
                    segment_type='pause'
                ))
                last_end = end
                continue
            elif tag_name == 'emphasis':
                # 强调标记：通过改变语速/音调模拟
                emphasis_level = tag_value.lower()
                if emphasis_level == 'strong':
                    new_params['rate'] = '-20%'
                    new_params['pitch'] = '+10Hz'
                elif emphasis_level == 'moderate':
                    new_params['rate'] = '-10%'
            elif tag_name == 'phoneme':
                # 多音字标记：仅记录，实际替换在预处理阶段完成
                pass
            
            # 递归解析标记内容（可能还有嵌套标记）
            nested_segments = parse_nested(tag_content, new_params)
            for seg in nested_segments:
                seg.is_marked = True
                result.append(seg)
            
            last_end = end
        
        # 添加最后的纯文本
        if last_end < len(text):
            plain_text = text[last_end:]
            if plain_text.strip():
                result.append(TextSegment(
                    text=plain_text,
                    rate=current_params.get('rate', default_rate),
                    pitch=current_params.get('pitch', default_pitch),
                    is_marked=False
                ))
        
        return result
    
    initial_params = {'rate': default_rate, 'pitch': default_pitch, 'volume': '+0%'}
    segments = parse_nested(text, initial_params)
    
    return segments
```

#### 2. 合成层

文件：`app/tts_advanced.py`

```python
async def synthesize_advanced_line(
    line: ScriptLine,
    output_path: str,
    max_retries: int = 3
) -> float:
    """
    合成高级文本行（自动拆分+拼接）
    """
    logger.info(f"🔧 高级合成模式：自动拆分+拼接")
    
    # 步骤1：解析文本
    segments = parse_marked_text(line.text)
    logger.info(f"📊 解析结果: {len(segments)} 个片段")
    
    # 步骤2：分别合成每个片段
    temp_files = []
    total_duration = 0.0
    proxy = os.getenv("HTTP_PROXY") or os.getenv("https_proxy")
    
    try:
        for i, seg in enumerate(segments):
            logger.info(f"🎙️  合成片段 {i+1}/{len(segments)}")
            
            if seg.segment_type == 'pause':
                # 🔑 生成静音片段（使用 FFmpeg）
                pause_ms = int(seg.rate)
                temp_path = str(AUDIO_DIR / f"temp_{uuid.uuid4().hex[:8]}_pause{i}.mp3")
                
                import subprocess
                cmd = [
                    './ffmpeg.exe',
                    '-f', 'lavfi',
                    '-i', f'anullsrc=r=24000:cl=mono',
                    '-t', str(pause_ms / 1000.0),
                    '-c:a', 'libmp3lame',
                    '-y',
                    temp_path
                ]
                subprocess.run(cmd, capture_output=True, check=True)
                
                duration = pause_ms / 1000.0
                temp_files.append(temp_path)
                logger.info(f"✅ 停顿片段 {i+1} 完成，时长: {duration:.3f} 秒")
            else:
                # 🔑 合成音频
                temp_path = str(AUDIO_DIR / f"temp_{uuid.uuid4().hex[:8]}_seg{i}.mp3")
                
                # 重试机制
                last_error = None
                for attempt in range(max_retries):
                    try:
                        communicate = edge_tts.Communicate(
                            text=seg.text,
                            voice=line.voice,
                            rate=seg.rate,
                            pitch=seg.pitch,
                            volume=seg.volume,
                            proxy=proxy
                        )
                        await communicate.save(temp_path)
                        
                        # 获取时长
                        from mutagen.mp3 import MP3
                        audio = MP3(temp_path)
                        duration = audio.info.length
                        
                        temp_files.append(temp_path)
                        logger.info(f"✅ 片段 {i+1} 完成，时长: {duration:.2f} 秒")
                        break
                    except Exception as e:
                        last_error = e
                        logger.warning(f"⚠️  片段 {i+1} 尝试 {attempt+1}/{max_retries} 失败: {e}")
                        if attempt < max_retries - 1:
                            await asyncio.sleep(2 ** attempt)
                
                if last_error and i == len(segments) - 1 and len(temp_files) == i:
                    raise last_error
            
            total_duration += duration
        
        # 步骤3：拼接所有片段
        logger.info(f"🔗 开始拼接 {len(temp_files)} 个片段...")
        
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        
        import subprocess
        
        # 创建文件列表
        list_file = str(AUDIO_DIR / f"concat_list_{uuid.uuid4().hex[:8]}.txt")
        with open(list_file, 'w', encoding='utf-8') as f:
            for temp_file in temp_files:
                file_path = temp_file.replace('\\', '/')
                f.write(f"file '{file_path}'\n")
        
        try:
            # 🔑 使用 FFmpeg concat demuxer 拼接
            cmd = [
                './ffmpeg.exe',
                '-f', 'concat',
                '-safe', '0',
                '-i', list_file,
                '-c', 'copy',
                '-y',
                output_path
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='ignore')
            
            if result.returncode != 0:
                logger.error(f"FFmpeg 错误: {result.stderr}")
                raise Exception(f"FFmpeg 拼接失败: {result.stderr}")
            
            logger.info(f"✅ 拼接完成: {output_path}")
            
        finally:
            # 删除临时列表文件
            if os.path.exists(list_file):
                os.remove(list_file)
        
        # 获取总时长
        from mutagen.mp3 import MP3
        audio = MP3(output_path)
        final_duration = audio.info.length
        logger.info(f"📏 总时长: {final_duration:.2f} 秒")
        
        return final_duration
        
    finally:
        # 🔑 清理临时文件
        for temp_file in temp_files:
            try:
                if os.path.exists(temp_file):
                    os.remove(temp_file)
            except:
                pass
```

#### 3. 集成入口

文件：`app/tts_engine.py`

```python
async def synthesize_single_line(
    line: ScriptLine, 
    output_path: str, 
    max_retries: int = 3,
    use_azure: bool = False,
    azure_key: Optional[str] = None,
    azure_region: Optional[str] = None
) -> float:
    """合成单行，返回音频时长（秒）"""
    
    # 检测方括号标记
    has_advanced_markers = bool(re.search(r'\[(rate|pitch|pause|emphasis)=', line.text))
    has_phoneme = bool(re.search(r'\[phoneme=', line.text))
    has_ssml = line.text.strip().startswith('<speak')
    
    if has_phoneme:
        # 🔑 先预处理 phoneme 标记（替换为同音字）
        logger.info(f"📝 检测到 phoneme 标记，将预处理替换")
        from .tts_parser import preprocess_phoneme_markers
        processed_text = preprocess_phoneme_markers(line.text)
        
        # 创建新的 line 对象，使用替换后的文本
        line = ScriptLine(
            type=line.type,
            character=line.character,
            emotion=line.emotion,
            text=processed_text,
            voice=line.voice,
            rate=line.rate,
            pitch=line.pitch
        )
        # 重新检测是否有其他标记
        has_advanced_markers = bool(re.search(r'\[(rate|pitch|pause|emphasis)=', processed_text))
    
    if has_advanced_markers:
        # 🔑 高级标记：自动拆分+拼接
        logger.info(f"📝 检测到高级标记文本，将自动拆分+拼接")
        return await synthesize_advanced_line(line, output_path, max_retries)
    elif has_ssml:
        # 自定义 SSML：直接传给 edge-tts
        logger.info(f"📝 检测到自定义 SSML")
        return await synthesize_simple_text(line, output_path, max_retries)
    else:
        # 普通文本
        return await synthesize_simple_text(line, output_path, max_retries)
```

---

## 多音字处理策略

### 废弃的方案：拼音映射

**问题**：
```python
# ❌ 失败案例
[phoneme=hang2]行[/phoneme]
# edge-tts 会把 "hang2" 当作英文字母读出："H-A-N-G-2"
```

**原因**：
- edge-tts 不支持 `<phoneme>` 标签
- 即使通过 Monkey Patch 传入 SSML，Microsoft 的 TTS 引擎也不识别拼音格式

### 采用的方案：同音字替换

**原理**：
```python
# ✅ 成功案例
[phoneme=航]行[/phoneme]
# 预处理时将"行"替换为"航"，传给 edge-tts 的文本是"航"
# edge-tts 会按照"航"的读音（háng）来读
```

**实现**：

文件：`app/tts_parser.py`

```python
def preprocess_phoneme_markers(text: str) -> str:
    """
    预处理 phoneme 标记，用同音字替换原字
    
    这样可以让替换后的文本作为整体传给 edge-tts，保持连贯性
    """
    # 匹配 [phoneme=同音字]原字[/phoneme]
    pattern = r'\[phoneme=([^\]]+)\]([^\[]*?)\[/phoneme\]'
    
    def replace_phoneme(match):
        replacement = match.group(1)  # 替换字（同音字）
        original = match.group(2)  # 原文本
        
        # 直接使用替换字替换原文本
        if len(replacement) == 1 and '\u4e00' <= replacement <= '\u9fff':
            logger.info(f"📝 phoneme 替换：'{original}' → '{replacement}'")
            return replacement
        else:
            logger.warning(f"⚠️ phoneme 标记格式错误，期望单个汉字，实际：'{replacement}'，保留原文本")
            return original
    
    result = re.sub(pattern, replace_phoneme, text)
    return result
```

**关键决策**：

1. **不参与分片**：
   ```python
   # 🔑 重要：phoneme 替换在前，语气标记检测在后
   if has_phoneme:
       # 预处理替换
       processed_text = preprocess_phoneme_markers(line.text)
       line = ScriptLine(..., text=processed_text, ...)
       # 重新检测
       has_advanced_markers = bool(re.search(r'\[(rate|pitch|pause|emphasis)=', processed_text))
   
   if has_advanced_markers:
       # 只有语气标记才触发分片
       return await synthesize_advanced_line(...)
   ```

2. **前端指定替换字**：
   - 用户直接在 UI 中输入：原字="行"，替换字="航"
   - 无需维护庞大的拼音→同音字映射表
   - 简单可靠，覆盖所有多音字

**常见多音字对照表**：
```
行：hang2→航（银行），xing2→形（行动）
长：chang2→常（长短），zhang3→掌（生长）
重：zhong4→仲（重要），chong2→虫（重复）
乐：le5→勒（快乐），yue4→月（音乐）
好：hao3→郝（好坏），hao4→号（爱好）
着：zhe5→这（看着），zhao2→找（着急）
```

---

## 性能优化实践

### 性能对比

**测试用例**：包含 8 个多音字和 12 处语气变化的综合测试

```python
test_text = (
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

**优化前**：
- 时长：35-37 秒
- 片段数：25 个
- 问题：一字一顿，非常卡顿

**优化后**：
- 时长：21.05 秒
- 片段数：12 个（8 音频 + 4 停顿）
- 效果：流畅自然

**优化手段**：
1. phoneme 不参与分片（减少 13 个片段）
2. 复合标记分开写（避免错误）
3. 使用 FFmpeg concat demuxer（比 pydub 更快）

### 优化建议

#### 1. 减少不必要的分片

```python
# ❌ 不好：每个字都标注 phoneme
"[phoneme=银]银[/phoneme][phoneme=航]行[/phoneme][phoneme=掌]掌[/phoneme][phoneme=长]长[/phoneme]"

# ✅ 更好：只标注关键的多音字
"银[phoneme=航]行[/phoneme][phoneme=掌]长[/phoneme]"
```

#### 2. 合理使用停顿

```python
# ❌ 过度停顿
"你好[pause=100]世界[pause=100]今天[pause=100]天气[pause=100]很好"

# ✅ 自然停顿
"你好世界[pause=300]今天天气很好"
```

#### 3. 缓存常用片段

```python
# TODO: 实现缓存机制
cache = {}

async def synthesize_with_cache(text, voice, rate, pitch):
    cache_key = f"{text}_{voice}_{rate}_{pitch}"
    if cache_key in cache:
        return cache[cache_key]
    
    # 合成音频
    duration = await synthesize_segment(...)
    cache[cache_key] = duration
    return duration
```

#### 4. 并行合成（未来优化方向）

```python
# TODO: 使用 asyncio.gather() 并行合成
tasks = [synthesize_segment(seg) for seg in segments]
results = await asyncio.gather(*tasks, return_exceptions=True)
```

---

## 常见问题与解决方案

### Q1: 为什么我的音频听起来一字一顿？

**原因**：过度分片，每个字都被单独合成

**解决**：
```python
# ❌ 错误：每个字都加标记
"[rate=-30%]那[/rate][rate=-30%]航[/rate][rate=-30%]掌[/rate]"

# ✅ 正确：整段一起标记
"[rate=-30%]那航掌[/rate]"
```

### Q2: 为什么复合标记报错？

**错误示例**：
```python
"[rate=-40%,pitch=-15Hz]文本[/rate]"
# ValueError: Invalid rate '-40%,pitch=-15Hz'.
```

**解决**：分开写
```python
"[rate=-40%][pitch=-15Hz]文本[/pitch][/rate]"
```

### Q3: 为什么拼音被读成字母？

**原因**：edge-tts 不支持 `<phoneme>` 标签

**解决**：使用同音字替换
```python
# ❌ 错误
"[phoneme=hang2]行[/phoneme]"

# ✅ 正确
"[phoneme=航]行[/phoneme]"
```

### Q4: 为什么 FFmpeg 拼接失败？

**常见原因**：
1. FFmpeg 未安装或未配置到 PATH
2. 临时文件路径包含中文或特殊字符
3. 文件列表格式错误

**解决**：
```python
# 确保路径使用正斜杠
file_path = temp_file.replace('\\', '/')
f.write(f"file '{file_path}'\n")

# 检查 FFmpeg 是否可用
import subprocess
result = subprocess.run(['./ffmpeg.exe', '-version'], capture_output=True)
if result.returncode != 0:
    raise Exception("FFmpeg 未正确安装")
```

### Q5: 如何调试 SSML 生成过程？

**启用日志**：
```python
# patch_edge_tts_v2.py 中已包含详细日志
print(f"[DEBUG] mkssml called with type: {type(escaped_text)}")
print(f"[SSML] {ssml}\n")
```

**查看完整流程**：
```bash
python test_ssml_before_split.py
```

---

## 最佳实践指南

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
```

### 情感曲线设计

#### 一波三折示例

```python
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
```

### 停顿使用原则

1. **自然停顿**：
   - 逗号处：100-200ms
   - 句号处：200-300ms
   - 段落间：400-600ms

2. **戏剧性停顿**：
   - 悬念前：300-500ms
   - 转折处：400-600ms
   - 高潮前：500-800ms

3. **避免过度**：
   - 不要每句话都加停顿
   - 停顿时长要有层次感
   - 结合语速变化使用

### Web UI 操作指南

#### 1. 多音字标注
1. 选中对白片段
2. 在"多音字"输入框输入原字（如：行）
3. 在"替换为"输入框输入同音字（如：航）
4. 点击"➕ 标注多音字"按钮
5. 点击"🔊 试听当前标记效果"验证

#### 2. 语气调整
1. 调整"语速调整 (%)"滑块
2. 调整"音调调整 (Hz)"滑块
3. 点击"✅ 应用语气设置到选中文本"
4. 试听效果

#### 3. 停顿插入
1. 调整"停顿时长(ms)"滑块
2. 点击"⏸️ 插入停顿"按钮
3. 试听确认

#### 4. 清除标记
点击"🧹 清除所有标记"恢复纯文本

---

## 附录

### A. 相关文件清单

```
项目根目录/
├── patch_edge_tts_v2.py          # Monkey Patch 实现
├── app/
│   ├── tts_parser.py             # 文本解析器
│   ├── tts_advanced.py           # 高级合成引擎
│   ├── tts_engine.py             # TTS 引擎入口
│   └── ui.py                     # Web UI（含编辑器）
├── test_ssml_before_split.py     # SSML 转换演示
├── test_ultimate_acceptance.py   # 综合验收测试
└── MULTI_PRONUNCIATION_EDITOR_GUIDE.md  # 编辑器使用指南
```

### B. 依赖要求

```txt
edge-tts>=7.2.8
pydub>=0.25.1
mutagen>=1.47.0
gradio>=3.50.0
```

**系统依赖**：
- FFmpeg（用于生成静音和拼接音频）
  - Windows: 下载 ffmpeg.exe 放到项目根目录
  - Linux: `sudo apt-get install ffmpeg`
  - macOS: `brew install ffmpeg`

### C. 技术架构图

```
┌─────────────────────────────────────────────────────┐
│  Web UI (Gradio)                                     │
│  - 多音字标注                                         │
│  - 语气调整                                           │
│  - 实时预览                                           │
└──────────────────┬──────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────┐
│  TTS Engine (tts_engine.py)                          │
│  - 检测标记类型                                       │
│  - 预处理 phoneme                                    │
│  - 路由到不同处理器                                    │
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
         │          │ parse_marked_text()  │
         │          └────────┬─────────────┘
         │                   │
         │                   ▼
         │          ┌──────────────────────┐
         │          │ 合成层                │
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
│  输出：MP3 音频文件                                   │
└─────────────────────────────────────────────────────┘
```

### D. 更新日志

**v2.0 (2026-04-13)**
- ✅ 移除拼音映射表，采用同音字替换
- ✅ 优化分片策略，减少不必要的切片
- ✅ 增强 Web UI，提供可视化编辑器
- ✅ 完善文档，记录所有技术细节

**v1.0 (2026-04-12)**
- ✅ 实现 Monkey Patch 支持自定义 SSML
- ✅ 实现自动拆分+拼接架构
- ✅ 支持多音字、停顿、强调等标记
- ✅ 创建基础测试用例

---

**文档维护说明**：
- 每次重大变更需更新此文档
- 新增功能需在"最佳实践指南"中添加示例
- 发现问题需在"常见问题"章节补充解决方案
- 定期回顾并优化性能建议

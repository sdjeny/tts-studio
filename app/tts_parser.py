"""
高级 TTS 解析器
支持在文本中使用特殊标记来指定不同部分的语速、音调等参数

新的标记语法：
- <prosody rate="-20%" pitch="+10Hz" volume="1.2">文本内容</prosody>
- <pause=1000> 停顿 1000ms
- [phoneme=同音字]原字[/phoneme] 内部替换

处理规则：
1. 按 <prosody> 标签分片，每个 prosody 是一个独立片段
2. <pause> 作为独立停顿片段
3. [phoneme] 在 prosody 内部简单替换，不分片
"""

import re
from typing import List, Dict, Optional
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)

@dataclass
class TextSegment:
    """文本片段"""
    text: str              # 文本内容
    rate: str = "+0%"      # 语速
    pitch: str = "+0Hz"    # 音调
    volume: str = "+0%"    # 音量
    is_marked: bool = False  # 是否包含标记
    segment_type: str = "text"  # 片段类型: text, pause


class TTSParseError(Exception):
    """解析错误"""
    pass


def preprocess_phoneme_markers(text: str) -> str:
    """
    预处理 phoneme 标记，用同音字替换原字
    
    Args:
        text: 原始文本，格式：[phoneme=同音字]原字[/phoneme]
    
    Returns:
        替换后的文本
    """
    # 匹配 [phoneme=同音字]原字[/phoneme]
    # group(1) = 同音字, group(2) = 原字
    pattern = r'\[phoneme=([^\]]+)\](.*?)\[/phoneme\]'
    
    def replace_phoneme(match):
        replacement = match.group(1)
        original = match.group(2)
        
        # 验证 replacement 是单个中文字符
        if len(replacement) >= 1 and '\u4e00' <= replacement[0] <= '\u9fff':
            logger.info(f"📝 phoneme 替换：'{original}' → '{replacement}'")
            return replacement
        else:
            logger.warning(f"⚠️ phoneme 标记格式错误：'{replacement}'，保留原文本")
            return original
    
    result = re.sub(pattern, replace_phoneme, text, flags=re.DOTALL)
    return result


def parse_prosody_text(text: str) -> List[TextSegment]:
    """
    解析带有 <prosody> 和 <pause> 标记的文本
    
    处理规则：
    1. <prosody rate="X" pitch="Y" volume="Z">内容</prosody> → 独立片段
    2. <pause=X> → 停顿片段
    3. prosody 内部处理 [phoneme] 替换
    
    Args:
        text: 带有标记的文本
    
    Returns:
        List[TextSegment]: 文本片段列表
    """
    if not text or not text.strip():
        return []
    
    segments = []
    
    # 正则表达式匹配 <prosody>、<pause> 和 [pause]
    # <prosody rate="..." pitch="..." volume="...">...</prosody>
    # <pause=1000> 或 [pause=1000]
    pattern = r'<prosody\s+([^>]+)>(.*?)</prosody>|<(pause)=(\d+)>|\[(pause)=(\d+)\]'
    
    last_end = 0
    
    for match in re.finditer(pattern, text, re.DOTALL):
        start, end = match.span()
        
        # 处理 prosody 标签前的纯文本（如果有）
        if start > last_end:
            plain_text = text[last_end:start].strip()
            if plain_text:
                # 纯文本也作为一个片段（使用默认参数）
                segments.append(TextSegment(
                    text=preprocess_phoneme_markers(plain_text),
                    rate="+0%",
                    pitch="+0Hz",
                    volume="+0%",
                    is_marked=False
                ))
        
        # 处理 <pause=X> 或 [pause=X] 格式的停顿
        if match.group(3):  # <pause=X> 格式
            duration_ms = int(match.group(4))
            segments.append(TextSegment(
                text=f"__PAUSE_{duration_ms}__",
                rate=str(duration_ms),
                pitch="+0Hz",
                volume="+0%",
                is_marked=True,
                segment_type='pause'
            ))
        elif match.group(5):  # [pause=X] 格式
            duration_ms = int(match.group(6))
            segments.append(TextSegment(
                text=f"__PAUSE_{duration_ms}__",
                rate=str(duration_ms),
                pitch="+0Hz",
                volume="+0%",
                is_marked=True,
                segment_type='pause'
            ))
        else:  # <prosody ...>...</prosody>
            attrs = match.group(1)
            content = match.group(2)
            
            # 解析 prosody 属性
            rate = _parse_attr(attrs, 'rate', '+0%')
            pitch = _parse_attr(attrs, 'pitch', '+0Hz')
            volume = _parse_attr(attrs, 'volume', '+0%')
            
            # 处理 content 内部的 phoneme 标记
            processed_content = preprocess_phoneme_markers(content)
            
            segments.append(TextSegment(
                text=processed_content,
                rate=rate,
                pitch=pitch,
                volume=volume,
                is_marked=True
            ))
        
        last_end = end
    
    # 处理最后一个标签后的纯文本
    if last_end < len(text):
        plain_text = text[last_end:].strip()
        if plain_text:
            segments.append(TextSegment(
                text=preprocess_phoneme_markers(plain_text),
                rate="+0%",
                pitch="+0Hz",
                volume="+0%",
                is_marked=False
            ))
    
    # 如果没有匹配到任何标签，整个文本作为一个片段
    if not segments:
        segments.append(TextSegment(
            text=preprocess_phoneme_markers(text),
            rate="+0%",
            pitch="+0Hz",
            volume="+0%",
            is_marked=False
        ))
    
    logger.info(f"解析文本: {text[:50]}...")
    logger.info(f"拆分为 {len(segments)} 个片段:")
    for i, seg in enumerate(segments):
        logger.info(f"  [{i}] type={seg.segment_type}, rate={seg.rate}, pitch={seg.pitch}, text='{seg.text[:20]}'")
    
    return segments


def _parse_attr(attrs: str, name: str, default: str) -> str:
    """从属性字符串中解析指定属性"""
    pattern = rf'{name}=["\']([^"\']+)["\']'
    match = re.search(pattern, attrs)
    return match.group(1) if match else default


def _has_markers(text: str) -> bool:
    """检测文本是否包含标记"""
    pattern = r'<prosody|<pause=|\[pause=|\[phoneme='
    return bool(re.search(pattern, text))


def has_markers(text: str) -> bool:
    """检查文本是否包含标记（保留以兼容旧代码）"""
    return _has_markers(text)


def needs_splitting(text: str) -> bool:
    """检测文本是否需要拆分"""
    segments = parse_prosody_text(text)
    return len(segments) > 1


def count_segments(text: str) -> int:
    """计算解析后的片段数量"""
    segments = parse_prosody_text(text)
    return len(segments)


# 保留旧函数以兼容旧代码
def parse_marked_text(text: str, default_rate: str = "+0%", default_pitch: str = "+0Hz") -> List[TextSegment]:
    """兼容旧接口，实际调用 parse_prosody_text"""
    return parse_prosody_text(text)


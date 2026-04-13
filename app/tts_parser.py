"""
高级 TTS 解析器
支持在文本中使用特殊标记来指定不同部分的语速、音调等参数

标记语法示例：
- [rate=-50%]慢速部分[/rate]
- [pitch=+20Hz]高音部分[/pitch]
- [rate=-30%][pitch=+10Hz]复合效果[/pitch][/rate]

嵌套规则：
- 标记可以嵌套，内层优先级高
- 未标记的部分使用默认参数
"""

import re
from typing import List, Tuple, Dict, Optional
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
    segment_type: str = "text"  # 片段类型: text, pause, emphasis

class TTSParseError(Exception):
    """解析错误"""
    pass

def preprocess_phoneme_markers(text: str) -> str:
    """
    预处理 phoneme 标记，用同音字替换原字
    
    这样可以让替换后的文本作为整体传给 edge-tts，保持连贯性
    
    Args:
        text: 原始文本，格式：[phoneme=同音字]原字[/phoneme]
    
    Returns:
        替换后的文本
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


def parse_marked_text(text: str, default_rate: str = "+0%", default_pitch: str = "+0Hz") -> List[TextSegment]:
    """
    解析带有标记的文本
    
    支持的标记语法：
    - [rate=-50%]慢速部分[/rate]
    - [pitch=+20Hz]高音部分[/pitch]
    - [pause=500] 停顿 500ms
    - [emphasis=strong]强调部分[/emphasis]
    - [phoneme=拼音]多音字[/phoneme] (注意：edge-tts 不直接支持，仅作为标记)
    
    Args:
        text: 带有标记的文本
        default_rate: 默认语速
        default_pitch: 默认音调
    
    Returns:
        List[TextSegment]: 文本片段列表
    """
    if not text or not text.strip():
        return []
    
    # 检查是否包含标记
    if not _has_markers(text):
        return [TextSegment(text=text, rate=default_rate, pitch=default_pitch, is_marked=False)]
    
    segments = []
    
    # 使用正则表达式解析标记
    # 支持的模式：
    # - [pause=Xms]        (无内容，不需要结束标签)
    # - [key=value]text[/key]  (有内容+结束标签)
    pattern = r'\[(pause)=(\d+)\]|\[(\w+)=([^\]]+)\](.*?)(?:\[/\3\])'
    
    # 递归解析嵌套标记
    def parse_nested(text: str, current_params: Dict[str, str]) -> List[TextSegment]:
        """递归解析嵌套标记"""
        result = []
        last_end = 0
        
        # 查找所有匹配的标记
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
                        volume=current_params.get('volume', '+0%'),
                        is_marked=False
                    ))
            
            # 更新当前参数
            new_params = current_params.copy()
            if tag_name == 'rate':
                new_params['rate'] = tag_value
            elif tag_name == 'pitch':
                new_params['pitch'] = tag_value
            elif tag_name == 'volume':
                new_params['volume'] = tag_value
            elif tag_name == 'pause':
                # 停顿标记：生成一个特殊片段
                duration_ms = int(tag_value)
                result.append(TextSegment(
                    text=f"__PAUSE_{duration_ms}__",
                    rate=str(duration_ms),  # 用 rate 字段存储时长
                    pitch=current_params.get('pitch', default_pitch),
                    volume=current_params.get('volume', '+0%'),
                    is_marked=True,
                    segment_type='pause'
                ))
                last_end = end
                continue
            elif tag_name == 'emphasis':
                # 强调标记：通过改变语速/音调模拟
                emphasis_level = tag_value.lower()
                if emphasis_level == 'strong':
                    new_params['rate'] = '-20%'  # 强调时放慢
                    new_params['pitch'] = '+10Hz'
                elif emphasis_level == 'moderate':
                    new_params['rate'] = '-10%'
                # reduced 不处理
            elif tag_name == 'phoneme':
                # 多音字标记：支持多种处理策略
                # 格式：[phoneme=拼音]汉字[/phoneme]
                # 或：[phoneme=同音字]汉字[/phoneme]
                
                # 判断是拼音还是同音字替换
                # 拼音通常包含数字声调（如 zhong4）或字母
                # 同音字通常是单个汉字
                
                if re.match(r'^[a-z]+\d+$', tag_value):  # 拼音格式（如 zhong4）
                    # 策略1：直接读拼音
                    logger.info(f"📝 phoneme 标记：将 '{tag_content}' 读作拼音 '{tag_value}'")
                    # 用拼音替换原文本
                    tag_content = tag_value
                elif len(tag_value) == 1 and '\u4e00' <= tag_value <= '\u9fff':  # 单个汉字
                    # 策略2：同音字替换
                    logger.info(f"📝 phoneme 标记：将 '{tag_content}' 替换为同音字 '{tag_value}'")
                    tag_content = tag_value
                else:
                    # 其他情况，记录警告
                    logger.warning(f"⚠️ phoneme 标记格式不明确: [{tag_name}={tag_value}]{tag_content}[/{tag_name}]")
                    # 仍然使用原文本
            
            # 递归解析标记内容（可能还有嵌套标记）
            nested_segments = parse_nested(tag_content, new_params)
            for seg in nested_segments:
                seg.is_marked = True  # 标记为有标记
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
                    volume=current_params.get('volume', '+0%'),
                    is_marked=False
                ))
        
        return result
    
    # 开始解析
    initial_params = {'rate': default_rate, 'pitch': default_pitch, 'volume': '+0%'}
    segments = parse_nested(text, initial_params)
    
    # 如果没有解析出任何片段（纯文本），返回整个文本
    if not segments:
        segments.append(TextSegment(
            text=text,
            rate=default_rate,
            pitch=default_pitch,
            volume='+0%',
            is_marked=False
        ))
    
    logger.info(f"解析文本: {text[:50]}...")
    logger.info(f"拆分为 {len(segments)} 个片段:")
    for i, seg in enumerate(segments):
        logger.info(f"  [{i}] rate={seg.rate}, pitch={seg.pitch}, marked={seg.is_marked}, text='{seg.text[:20]}'")
    
    return segments


def _has_markers(text: str) -> bool:
    """检测文本是否包含标记"""
    pattern = r'\[(rate|pitch|volume|pause|emphasis|phoneme)='
    return bool(re.search(pattern, text))


def has_markers(text: str) -> bool:
    """检查文本是否包含标记（保留以兼容旧代码）"""
    return _has_markers(text)


def needs_splitting(text: str) -> bool:
    """
    检测文本是否需要拆分（包含标记且片段数 > 2）
    
    Args:
        text: 原始文本
    
    Returns:
        True 如果包含标记且需要拆分，False 否则
    """
    if not _has_markers(text):
        return False
    
    segments = parse_marked_text(text)
    return len(segments) > 2


def count_segments(text: str) -> int:
    """
    计算解析后的片段数量
    
    Args:
        text: 带有标记的文本
    
    Returns:
        片段数量
    """
    if not _has_markers(text):
        return 1
    
    segments = parse_marked_text(text)
    return len(segments)

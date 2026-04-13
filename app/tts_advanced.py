"""
高级 TTS 引擎 - 支持自动拆分+拼接
当一行文本包含多个语速/音调变化时，自动拆分成多个子任务，分别合成后拼接
"""

import os
import edge_tts
import asyncio
import logging
from pathlib import Path
from pydub import AudioSegment
import uuid
from typing import List, Optional, Tuple
import re
from .models import ScriptLine
from .config import AUDIO_DIR
from .tts_parser import parse_marked_text, TextSegment

logger = logging.getLogger(__name__)


def parse_rate_pitch_from_text(text: str) -> List[Tuple[str, str, str]]:
    """
    从文本中解析语速/音调标记
    
    支持的语法：
    - {rate=-50%}文本{/rate}
    - {pitch=+20Hz}文本{/pitch}
    - {rate=-30%,pitch=+10Hz}文本{/style}
    - {pause=500} 表示停顿 500ms
    
    返回：[(文本片段, rate, pitch), ...]
    """
    segments = []
    
    # 解析标记的正则表达式
    pattern = r'\{(rate|pitch|style|pause)=([^}]+)\}(.*?)\{/\1\}'
    
    last_pos = 0
    for match in re.finditer(pattern, text):
        start, end = match.span()
        tag_type = match.group(1)
        tag_value = match.group(2)
        tag_content = match.group(3)
        
        # 添加标记前的普通文本
        if start > last_pos:
            plain_text = text[last_pos:start].strip()
            if plain_text:
                segments.append((plain_text, "+0%", "+0Hz"))
        
        # 处理不同类型的标记
        if tag_type == 'rate':
            segments.append((tag_content, tag_value, "+0Hz"))
        elif tag_type == 'pitch':
            segments.append((tag_content, "+0%", tag_value))
        elif tag_type == 'style':
            # 解析复合样式：rate=-30%,pitch=+10Hz
            rate = "+0%"
            pitch = "+0Hz"
            for param in tag_value.split(','):
                param = param.strip()
                if param.startswith('rate='):
                    rate = param[5:]
                elif param.startswith('pitch='):
                    pitch = param[6:]
            segments.append((tag_content, rate, pitch))
        elif tag_type == 'pause':
            # 停顿标记，生成静音片段
            duration_ms = int(tag_value)
            segments.append(('__PAUSE__', duration_ms, "+0Hz"))
        
        last_pos = end
    
    # 添加最后的普通文本
    if last_pos < len(text):
        plain_text = text[last_pos:].strip()
        if plain_text:
            segments.append((plain_text, "+0%", "+0Hz"))
    
    # 如果没有解析到任何标记，整个文本作为一段
    if not segments:
        segments.append((text.strip(), "+0%", "+0Hz"))
    
    return segments


async def synthesize_text_segment(
    text: str,
    voice: str,
    rate: str,
    pitch: str,
    output_path: str,
    proxy: str = None
) -> float:
    """合成单个文本片段，返回时长（秒）"""
    communicate = edge_tts.Communicate(
        text=text,
        voice=voice,
        rate=rate,
        pitch=pitch,
        proxy=proxy
    )
    await communicate.save(output_path)
    
    # 获取时长
    from mutagen.mp3 import MP3
    audio = MP3(output_path)
    return audio.info.length


async def synthesize_advanced_line(
    line: ScriptLine,
    text: str,  # 🔑 新增：处理后的文本
    output_path: str,
    max_retries: int = 3
) -> float:
    """
    合成高级文本行（自动拆分+拼接）
    
    Args:
        line: ScriptLine 对象（用于获取 voice, rate, pitch 等属性）
        text: 处理后的文本（已替换 phoneme，包含标记）
        output_path: 输出路径
        max_retries: 最大重试次数
    
    流程：
    1. 解析文本中的标记
    2. 对每个片段分别合成
    3. 拼接所有片段
    4. 返回总时长
    """
    logger.info(f"=" * 60)
    logger.info(f"🔧 高级合成模式：自动拆分+拼接")
    # 🔑 使用传入的 text 参数（预处理已在入口完成）
    logger.info(f"  原始文本: {text[:100]}...")
    logger.info(f"  音色: {line.voice}")
    logger.info(f"=" * 60)
    
    # 步骤1：解析文本
    segments = parse_marked_text(text)
    
    # 显示分片前的完整文本（已替换 phoneme）
    full_text_after_phoneme = ''.join([seg.text for seg in segments if seg.segment_type != 'pause'])
    logger.info(f"\n📝 分片前完整文本（phoneme已替换）:")
    logger.info(f"   {full_text_after_phoneme}")
    
    logger.info(f"\n📊 解析结果: {len(segments)} 个片段")
    for i, seg in enumerate(segments):
        if seg.segment_type == 'pause':
            logger.info(f"  片段 {i+1}: [停顿 {seg.rate}ms]")
        elif seg.is_marked:
            logger.info(f"  片段 {i+1}: rate={seg.rate}, pitch={seg.pitch}, text='{seg.text[:20]}' (强调)")
        else:
            logger.info(f"  片段 {i+1}: rate={seg.rate}, pitch={seg.pitch}, text='{seg.text[:20]}'")
    
    # 步骤2：分别合成每个片段
    temp_files = []
    total_duration = 0.0
    
    proxy = os.getenv("HTTP_PROXY") or os.getenv("https_proxy")
    
    try:
        for i, seg in enumerate(segments):
            logger.info(f"\n🎙️  合成片段 {i+1}/{len(segments)}")
            
            if seg.segment_type == 'pause':
                # 生成静音片段（使用 FFmpeg）
                pause_ms = int(seg.rate)
                temp_path = str(AUDIO_DIR / f"temp_{uuid.uuid4().hex[:8]}_pause{i}.mp3")
                
                # 使用 FFmpeg 生成静音
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
                # 合成音频
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
        logger.info(f"\n🔗 开始拼接 {len(temp_files)} 个片段...")
        
        # 确保输出目录存在
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        
        # 使用 FFmpeg 命令行拼接（避免 pydub 依赖 ffprobe）
        import subprocess
        
        # 创建文件列表
        list_file = str(AUDIO_DIR / f"concat_list_{uuid.uuid4().hex[:8]}.txt")
        with open(list_file, 'w', encoding='utf-8') as f:
            for temp_file in temp_files:
                # FFmpeg concat demuxer 要求路径使用正斜杠
                file_path = temp_file.replace('\\', '/')
                f.write(f"file '{file_path}'\n")
        
        try:
            # 使用 FFmpeg concat demuxer 拼接
            cmd = [
                './ffmpeg.exe',
                '-f', 'concat',
                '-safe', '0',
                '-i', list_file,
                '-c', 'copy',
                '-y',  # 覆盖输出文件
                output_path
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='ignore'
            )
            
            if result.returncode != 0:
                logger.error(f"FFmpeg 错误: {result.stderr}")
                raise Exception(f"FFmpeg 拼接失败: {result.stderr}")
            
            logger.info(f"✅ 拼接完成: {output_path}")
            
        finally:
            # 删除临时列表文件
            if os.path.exists(list_file):
                os.remove(list_file)
        
        # 获取总时长（使用 mutagen）
        from mutagen.mp3 import MP3
        audio = MP3(output_path)
        final_duration = audio.info.length
        logger.info(f"📏 总时长: {final_duration:.2f} 秒")
        
        logger.info(f"=" * 60)
        return final_duration
        
    finally:
        # 清理临时文件
        for temp_file in temp_files:
            try:
                if os.path.exists(temp_file):
                    os.remove(temp_file)
            except:
                pass

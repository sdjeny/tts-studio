"""
音频拼接工具
使用 FFmpeg 命令行将多个音频片段拼接成一个（不依赖 pydub）
"""

import os
from pathlib import Path
from typing import List
import uuid
import logging
import subprocess

from .config import AUDIO_DIR

logger = logging.getLogger(__name__)

def concat_audio_files(audio_files: List[str], output_path: str = None) -> str:
    """
    按顺序拼接多个音频文件（使用 FFmpeg concat demuxer）
    
    Args:
        audio_files: 音频文件路径列表
        output_path: 输出路径（可选，默认自动生成）
    
    Returns:
        拼接后的音频文件路径
    """
    if not audio_files:
        raise ValueError("音频文件列表为空")
    
    logger.info(f"开始拼接 {len(audio_files)} 个音频文件")
    
    # 验证所有文件存在
    for i, file_path in enumerate(audio_files):
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"音频文件不存在: {file_path}")
        logger.info(f"  片段 {i+1}/{len(audio_files)}: {Path(file_path).name}")
    
    # 生成输出路径
    if output_path is None:
        output_path = str(AUDIO_DIR / f"concat_{uuid.uuid4().hex[:8]}.mp3")
    
    # 确保输出目录存在
    output_dir = Path(output_path).parent
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # 创建 FFmpeg concat 列表文件
    list_file = str(AUDIO_DIR / f"concat_list_{uuid.uuid4().hex[:8]}.txt")
    try:
        with open(list_file, 'w', encoding='utf-8') as f:
            for file_path in audio_files:
                # FFmpeg concat demuxer 要求路径使用正斜杠或转义反斜杠
                abs_path = os.path.abspath(file_path).replace('\\', '/')
                f.write(f"file '{abs_path}'\n")
        
        # 使用 FFmpeg concat demuxer 拼接
        cmd = [
            './ffmpeg.exe',
            '-f', 'concat',
            '-safe', '0',
            '-i', list_file,
            '-c', 'copy',  # 直接复制，不重新编码
            '-y',  # 覆盖输出文件
            output_path
        ]
        
        logger.info(f"执行 FFmpeg 拼接命令...")
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
        # 清理临时列表文件
        try:
            if os.path.exists(list_file):
                os.remove(list_file)
        except Exception as e:
            logger.warning(f"⚠️  清理列表文件失败: {e}")
    
    return output_path


def concat_audio_segments(segments_audio: List[str]) -> str:
    """
    拼接音频片段（与 concat_audio_files 相同，但语义更明确）
    
    Args:
        segments_audio: 各片段的音频文件路径
    
    Returns:
        拼接后的音频文件路径
    """
    return concat_audio_files(segments_audio)


def merge_audio_with_gaps(audio_files: List[str], gaps_ms: List[int] = None, output_path: str = None) -> str:
    """
    按顺序拼接音频，并在片段之间插入静音间隙
    
    Args:
        audio_files: 音频文件路径列表
        gaps_ms: 每个间隙的时长（毫秒），长度应为 len(audio_files) - 1
        output_path: 输出路径
    
    Returns:
        拼接后的音频文件路径
    """
    if not audio_files:
        raise ValueError("音频文件列表为空")
    
    if gaps_ms is None:
        gaps_ms = [0] * (len(audio_files) - 1)
    elif len(gaps_ms) != len(audio_files) - 1:
        raise ValueError(f"gaps_ms 长度应为 {len(audio_files) - 1}，实际为 {len(gaps_ms)}")
    
    logger.info(f"开始拼接 {len(audio_files)} 个音频文件（带间隙）")
    
    combined = AudioSegment.empty()
    
    for i, file_path in enumerate(audio_files):
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"音频文件不存在: {file_path}")
        
        logger.info(f"加载片段 {i+1}/{len(audio_files)}: {Path(file_path).name}")
        audio = AudioSegment.from_mp3(file_path)
        combined += audio
        
        # 添加间隙（除了最后一个）
        if i < len(audio_files) - 1 and gaps_ms[i] > 0:
            logger.info(f"添加 {gaps_ms[i]}ms 间隙")
            silence = AudioSegment.silent(duration=gaps_ms[i])
            combined += silence
    
    # 生成输出路径
    if output_path is None:
        output_path = str(AUDIO_DIR / f"concat_gaps_{uuid.uuid4().hex[:8]}.mp3")
    
    # 确保输出目录存在
    output_dir = Path(output_path).parent
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # 导出
    logger.info(f"导出拼接音频: {output_path}")
    combined.export(output_path, format="mp3")
    
    logger.info(f"✅ 拼接完成，总时长: {len(combined) / 1000:.2f} 秒")
    
    return output_path

import os
import edge_tts
import asyncio
import logging
import re
from pathlib import Path
from pydub import AudioSegment
from pydub.generators import Sine
import uuid
from typing import List, Optional
from .models import AudioClip, ScriptLine
from .config import AUDIO_DIR
from .tts_parser import parse_marked_text, has_markers, count_segments, TextSegment
from .tts_concat import concat_audio_files
from .tts_advanced import synthesize_advanced_line, parse_rate_pitch_from_text

# 配置日志
logger = logging.getLogger(__name__)

# 应用 edge-tts 补丁以支持自定义 SSML
from . import patch_edge_tts_v2


def get_tts_text(line) -> str:
    """
    获取用于 TTS 合成的文本（兼容函数，委托给 line.get_tts_text()）
    
    Args:
        line: ScriptLine 对象
    
    Returns:
        用于 TTS 合成的文本
    """
    return line.get_tts_text()

async def synthesize_with_azure(
    line: ScriptLine, 
    output_path: str, 
    azure_key: str,
    azure_region: str,
    max_retries: int = 3
) -> float:
    """使用 Azure Speech Service 合成音频"""
    if not AZURE_SPEECH_AVAILABLE:
        raise Exception("Azure Speech SDK 未安装")
    
    logger.info(f"=" * 60)
    logger.info(f"开始合成音频 (Azure Speech)")
    logger.info(f"  角色: {line.character}")
    # 🔑 使用 get_tts_text 获取正确的文本
    tts_text = get_tts_text(line)
    logger.info(f"  文本: {tts_text[:50]}..." if len(tts_text) > 50 else f"  文本: {tts_text}")
    logger.info(f"  音色: {line.voice}")
    logger.info(f"  输出路径: {output_path}")
    
    # 确保输出目录存在
    output_dir = Path(output_path).parent
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # 配置 Azure Speech
    speech_config = speechsdk.SpeechConfig(subscription=azure_key, region=azure_region)
    speech_config.speech_synthesis_voice_name = line.voice
    
    # 创建音频配置
    audio_config = speechsdk.audio.AudioOutputConfig(filename=output_path)
    
    # 创建语音合成器
    speech_synthesizer = speechsdk.SpeechSynthesizer(speech_config=speech_config, audio_config=audio_config)
    
    # 重试机制
    for attempt in range(max_retries):
        try:
            logger.info(f"\n尝试 {attempt + 1}/{max_retries}...")
            
            # 执行合成
            result = speech_synthesizer.speak_text_async(tts_text).get()
            
            # 检查结果
            if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
                logger.info(f"✅ 音频文件已保存: {output_path}")
                
                # 获取音频时长
                try:
                    from mutagen.mp3 import MP3
                    audio = MP3(output_path)
                    duration = audio.info.length
                    logger.info(f"✅ 音频时长: {duration:.2f} 秒")
                except:
                    duration = len(tts_text) / 4.5
                    logger.warning(f"⚠️  无法获取准确时长，估算: {duration:.2f} 秒")
                
                logger.info(f"=" * 60)
                return duration
            elif result.reason == speechsdk.ResultReason.Canceled:
                cancellation_details = result.cancellation_details
                logger.error(f"❌ 合成取消: {cancellation_details.reason}")
                logger.error(f"   错误详情: {cancellation_details.error_details}")
                raise Exception(f"Azure Speech 合成失败: {cancellation_details.error_details}")
            else:
                raise Exception(f"Azure Speech 合成失败: {result.reason}")
                
        except Exception as e:
            logger.error(f"❌ Azure Speech 尝试 {attempt + 1}/{max_retries} 失败")
            logger.error(f"   错误: {type(e).__name__}: {e}")
            
            if attempt < max_retries - 1:
                wait_time = 2 ** attempt
                logger.info(f"等待 {wait_time} 秒后重试...\n")
                await asyncio.sleep(wait_time)
    
    raise Exception(f"Azure Speech 合成失败，已重试 {max_retries} 次")

async def synthesize_single_line(
    line: ScriptLine, 
    output_path: str, 
    max_retries: int = 3,
    use_azure: bool = False,
    azure_key: Optional[str] = None,
    azure_region: Optional[str] = None
) -> float:
    """
    合成单行，返回音频时长（秒）
    
    Args:
        line: 剧本行
        output_path: 输出路径
        max_retries: 最大重试次数
        use_azure: 是否使用 Azure Speech Service
        azure_key: Azure API Key
        azure_region: Azure Region
    """
    # 如果指定使用 Azure 且配置完整，则使用 Azure
    if use_azure and azure_key and azure_region:
        if not AZURE_SPEECH_AVAILABLE:
            logger.warning("⚠️  Azure SDK 未安装，回退到 edge-tts")
        else:
            return await synthesize_with_azure(line, output_path, azure_key, azure_region, max_retries)
    
    # 默认使用 edge-tts
    logger.info(f"=" * 60)
    logger.info(f"开始合成音频")
    logger.info(f"  角色: {line.character}")
    # 🔑 使用 get_tts_text 获取正确的文本
    tts_input_text = get_tts_text(line)
    logger.info(f"  文本: {tts_input_text[:50]}..." if len(tts_input_text) > 50 else f"  文本: {tts_input_text}")
    logger.info(f"  音色: {line.voice}")
    logger.info(f"  语速: {line.rate}")
    logger.info(f"  音调: {line.pitch}")
    logger.info(f"  输出路径: {output_path}")
    
    if not tts_input_text.strip():
        logger.warning("文本为空，跳过合成")
        return 0.0
    
    # 确保输出目录存在
    output_dir = Path(output_path).parent
    output_dir.mkdir(parents=True, exist_ok=True)
    logger.info(f"输出目录: {output_dir} (存在: {output_dir.exists()})")
    
    # 检查是否为高级标记文本
    # 支持两种标记语法：
    # 1. <prosody>...</prosody>, <pause=X>  - 新语法（TTS 层自动拆分+拼接）
    # 2. <speak>...</speak>                  - 自定义 SSML（直接传给 edge-tts）
    
    # 检测新语法标记（prosody, pause）
    has_advanced_markers = bool(re.search(r'<prosody|<pause=|\[pause=', get_tts_text(line)))
    has_phoneme = bool(re.search(r'\[phoneme=', get_tts_text(line)))
    has_ssml = get_tts_text(line).strip().startswith('<speak')
    
    if has_phoneme:
        # 先预处理 phoneme 标记（替换为同音字）
        logger.info(f"📝 检测到 phoneme 标记，将预处理替换")
        original_text = get_tts_text(line)
        logger.info(f"   替换前: {original_text[:200]}")
        from .tts_parser import preprocess_phoneme_markers
        processed_text = preprocess_phoneme_markers(original_text)
        logger.info(f"   替换后: {processed_text[:200]}")
        
        # 🔑 使用独立变量传递处理后的文本，不修改原始 line 对象
        tts_input_text = processed_text
        # 重新检测是否有其他标记
        has_advanced_markers = bool(re.search(r'<prosody|<pause=', processed_text))
    else:
        # 没有 phoneme，直接使用原始文本
        tts_input_text = get_tts_text(line)
    
    if has_advanced_markers:
        logger.info(f"📝 检测到高级标记文本（新语法），将自动拆分+拼接")
        return await synthesize_advanced_text(
            line, 
            tts_input_text,  # 🔑 传递处理后的文本
            output_path, 
            max_retries
        )
    elif has_ssml:
        logger.info(f"📝 检测到自定义 SSML")
        return await synthesize_simple_text(
            line, 
            tts_input_text,  # 🔑 传递处理后的文本
            output_path, 
            max_retries
        )
    else:
        # 普通文本
        return await synthesize_simple_text(
            line, 
            tts_input_text,  # 🔑 传递处理后的文本
            output_path, 
            max_retries
        )


async def synthesize_simple_text(
    line: ScriptLine,
    text: str,  # 🔑 新增：处理后的文本
    output_path: str,
    max_retries: int = 3
) -> float:
    """
    合成普通文本或自定义 SSML（edge-tts 原生逻辑）
    
    Args:
        line: ScriptLine 对象（用于获取 voice, rate, pitch 等属性）
        text: 处理后的文本（已替换 phoneme 等）
        output_path: 输出路径
        max_retries: 最大重试次数
    """
    # 🔑 直接使用传入的 text 参数，不再调用 get_tts_text
    text_for_tts = text
    
    # 检测是否为自定义 SSML
    is_custom_ssml = text_for_tts.strip().startswith('<speak')
    
    if is_custom_ssml:
        logger.info(f"检测到自定义 SSML")
        logger.info(f"SSML 长度: {len(text_for_tts)} 字符")
    else:
        logger.info(f"使用 edge-tts 纯文本模式")
        logger.info(f"原始文本: {text_for_tts}")
    
    # 检查是否配置了代理
    proxy = os.getenv("HTTP_PROXY") or os.getenv("https_proxy")
    if proxy:
        logger.info(f"使用代理: {proxy}")
    else:
        logger.info("未配置代理，直连微软服务")
    
    # 重试机制
    last_error = None
    for attempt in range(max_retries):
        try:
            logger.info(f"\n尝试 {attempt + 1}/{max_retries}...")
            logger.info(f"正在调用 Edge-TTS API")
            communicate = edge_tts.Communicate(
                text=text_for_tts,
                voice=line.voice,
                rate=line.rate or "+0%",
                pitch=line.pitch or "+0Hz",
                proxy=proxy
            )
            await communicate.save(output_path)
            logger.info(f"✅ 音频文件已保存: {output_path}")
            
            # 检查文件是否存在
            if not os.path.exists(output_path):
                raise FileNotFoundError(f"音频文件未生成: {output_path}")
            
            file_size = os.path.getsize(output_path)
            logger.info(f"文件大小: {file_size} bytes")
            
            # 使用 mutagen 获取 MP3 时长
            try:
                from mutagen.mp3 import MP3
                audio = MP3(output_path)
                duration = audio.info.length
                logger.info(f"✅ 音频时长: {duration:.2f} 秒 (通过 mutagen)")
            except ImportError:
                char_count = len(line.text)
                duration = char_count / 4.5
                logger.warning(f"⚠️  mutagen 未安装，使用估算时长: {duration:.2f} 秒")
            
            logger.info(f"=" * 60)
            return duration
            
        except FileNotFoundError as e:
            last_error = e
            logger.error(f"❌ 文件错误: {e}")
            
        except Exception as e:
            last_error = e
            error_msg = str(e)
            logger.error(f"❌ Edge-TTS 尝试 {attempt + 1}/{max_retries} 失败")
            logger.error(f"   错误类型: {type(e).__name__}")
            logger.error(f"   错误信息: {error_msg}")
            
            if "403" in error_msg and attempt == 0:
                logger.warning("\n⚠️  提示: 403错误通常是网络连接问题")
                logger.warning("   - 检查是否可以访问微软服务")
                logger.warning("   - 如需代理，请设置环境变量: HTTP_PROXY=http://your-proxy:port")
            
            if attempt < max_retries - 1:
                wait_time = 2 ** attempt
                logger.info(f"等待 {wait_time} 秒后重试...\n")
                await asyncio.sleep(wait_time)
    
    logger.error(f"\n{'=' * 60}")
    logger.error(f"❌ Edge-TTS 合成最终失败")
    logger.error(f"   已重试: {max_retries} 次")
    logger.error(f"   最后错误: {type(last_error).__name__}: {last_error}")
    logger.error(f"{'=' * 60}")
    raise Exception(f"Edge-TTS 合成失败，已重试 {max_retries} 次: {str(last_error)}")


async def synthesize_advanced_text(
    line: ScriptLine,
    text: str,  # 🔑 新增：处理后的文本
    output_path: str,
    max_retries: int = 3
) -> float:
    """
    合成高级标记文本（自动拆分+拼接）
    
    Args:
        line: ScriptLine 对象（用于获取 voice, rate, pitch 等属性）
        text: 处理后的文本（已替换 phoneme，包含标记）
        output_path: 输出路径
        max_retries: 最大重试次数
    
    流程：
    1. 解析标记文本，拆分成多个 TextSegment
    2. 对每个片段分别调用 edge-tts 合成
    3. 使用 FFmpeg/pydub 拼接所有片段
    4. 返回最终音频时长
    """
    logger.info(f"\n{'=' * 60}")
    logger.info(f"🔧 高级文本合成模式")
    logger.info(f"{'=' * 60}")
    
    # 步骤1：解析文本（使用传入的 text 参数）
    segments = parse_marked_text(
        text,
        default_rate=line.rate or "+0%",
        default_pitch=line.pitch or "+0Hz"
    )
    
    logger.info(f"\n📊 解析结果: {len(segments)} 个片段")
    for i, seg in enumerate(segments):
        logger.info(f"  片段 {i+1}: rate={seg.rate}, pitch={seg.pitch}, text='{seg.text[:30]}'")
    
    # 步骤2：分别合成每个片段
    temp_files = []
    total_duration = 0.0
    
    try:
        for i, segment in enumerate(segments):
            logger.info(f"\n{'─' * 60}")
            logger.info(f"🎙️  合成片段 {i+1}/{len(segments)}")
            logger.info(f"{'─' * 60}")
            
            # 生成临时文件路径
            temp_filename = f"temp_{uuid.uuid4().hex[:8]}_seg{i}.mp3"
            temp_path = str(AUDIO_DIR / temp_filename)
            temp_files.append(temp_path)
            
            if segment.segment_type == 'pause':
                # 停顿片段：使用 FFmpeg 生成静音
                pause_ms = int(segment.rate)
                logger.info(f"⏸️  生成停顿: {pause_ms}ms")
                
                import subprocess
                cmd = [
                    './ffmpeg.exe',
                    '-f', 'lavfi',
                    '-i', 'anullsrc=r=24000:cl=mono',
                    '-t', str(pause_ms / 1000.0),
                    '-c:a', 'libmp3lame',
                    '-y',
                    temp_path
                ]
                subprocess.run(cmd, capture_output=True, check=True)
                duration = pause_ms / 1000.0
                total_duration += duration
                logger.info(f"✅ 停顿片段 {i+1} 完成，时长: {duration:.3f} 秒")
            else:
                # 普通文本片段：调用 TTS 合成
                temp_line = ScriptLine(
                    type=line.type,
                    character=line.character,
                    emotion=line.emotion,
                    text=segment.text,
                    voice=line.voice,
                    rate=segment.rate,
                    pitch=segment.pitch
                )
                
                # 合成这个片段
                duration = await synthesize_simple_text(
                    temp_line,
                    segment.text,  # 🔑 传递文本参数
                    temp_path,
                    max_retries
                )
                
                total_duration += duration
                logger.info(f"✅ 片段 {i+1} 完成，时长: {duration:.2f} 秒")
        
        # 步骤3：拼接所有片段
        logger.info(f"\n{'=' * 60}")
        logger.info(f"🔗 开始拼接 {len(temp_files)} 个片段")
        logger.info(f"{'=' * 60}")
        
        final_path = concat_audio_files(temp_files, output_path)
        
        # 获取最终时长
        try:
            from mutagen.mp3 import MP3
            audio = MP3(final_path)
            final_duration = audio.info.length
            logger.info(f"✅ 最终音频时长: {final_duration:.2f} 秒")
        except:
            final_duration = total_duration
            logger.warning(f"⚠️  使用估算时长: {final_duration:.2f} 秒")
        
        logger.info(f"\n{'=' * 60}")
        logger.info(f"✅ 高级文本合成完成！")
        logger.info(f"   片段数: {len(segments)}")
        logger.info(f"   总时长: {final_duration:.2f} 秒")
        logger.info(f"   输出文件: {final_path}")
        logger.info(f"{'=' * 60}")
        
        return final_duration
        
    except Exception as e:
        logger.error(f"❌ 高级文本合成失败: {e}")
        raise
    
    finally:
        # 清理临时文件
        for temp_file in temp_files:
            try:
                if os.path.exists(temp_file):
                    os.remove(temp_file)
                    logger.info(f"🗑️  清理临时文件: {Path(temp_file).name}")
            except Exception as e:
                logger.warning(f"⚠️  清理临时文件失败: {e}")

def mix_audio_tracks(clips: List[AudioClip], total_duration: float = None) -> str:
    """
    将多个 AudioClip 按时间轴混合，返回最终音频路径
    使用 FFmpeg 命令行实现，不依赖 pydub
    """
    if not clips:
        return None
    
    # 过滤有效片段
    valid_clips = []
    for clip in clips:
        if clip.is_generated and os.path.exists(clip.file_path):
            valid_clips.append(clip)
    
    if not valid_clips:
        return None
    
    # 获取每个片段的时长和计算最大结束时间
    max_end = 0.0
    for clip in valid_clips:
        try:
            from mutagen.mp3 import MP3
            audio = MP3(clip.file_path)
            duration_sec = audio.info.length
        except:
            # 估算时长
            duration_sec = 5.0
        
        clip._duration = duration_sec
        clip._start_ms = int(clip.start_time * 1000)
        clip._end_ms = clip._start_ms + int(duration_sec * 1000)
        max_end = max(max_end, clip._end_ms)
    
    if total_duration is None:
        total_duration = max_end / 1000.0
    
    # 生成输出路径
    output_path = AUDIO_DIR / f"final_mix_{uuid.uuid4().hex[:8]}.mp3"
    
    # 构建 FFmpeg filter_complex 命令
    # 使用 amix 或 overlay 方式混合音频
    inputs = []
    filter_parts = []
    
    for i, clip in enumerate(valid_clips):
        inputs.extend(['-i', clip.file_path])
        delay_ms = clip._start_ms
        # 使用 adelay 滤镜延迟音频
        filter_parts.append(f"[{i}:a]adelay={delay_ms}|{delay_ms}[a{i}]")
    
    # 构建 amix 滤镜链
    mix_inputs = ''.join([f"[a{i}]" for i in range(len(valid_clips))])
    filter_parts.append(f"{mix_inputs}amix=inputs={len(valid_clips)}:duration=longest[aout]")
    
    filter_complex = ';'.join(filter_parts)
    
    cmd = [
        './ffmpeg.exe',
        *inputs,
        '-filter_complex', filter_complex,
        '-map', '[aout]',
        '-t', str(total_duration + 0.5),  # 添加 0.5 秒余量
        '-y',
        str(output_path)
    ]
    
    import subprocess
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding='utf-8',
        errors='ignore'
    )
    
    if result.returncode != 0:
        logger.error(f"FFmpeg 混音错误: {result.stderr}")
        raise Exception(f"FFmpeg 混音失败: {result.stderr}")
    
    logger.info(f"✅ 混音完成: {output_path}")
    return str(output_path)

def generate_silence(duration_sec: float) -> str:
    """生成静音文件（用于占位）"""
    path = AUDIO_DIR / f"silence_{uuid.uuid4().hex[:8]}.mp3"
    AudioSegment.silent(duration=int(duration_sec * 1000)).export(path, format="mp3")
    return str(path)

def generate_tone(freq: int = 440, duration_sec: float = 1.0) -> str:
    """生成测试音（用于音效占位）"""
    path = AUDIO_DIR / f"tone_{uuid.uuid4().hex[:8]}.mp3"
    Sine(freq).to_audio_segment(duration=int(duration_sec * 1000)).export(path, format="mp3")
    return str(path)

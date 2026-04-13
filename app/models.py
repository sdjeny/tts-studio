from dataclasses import dataclass, field
from typing import List, Dict, Optional

@dataclass
class Character:
    """角色定义"""
    name: str                      # 角色名称（如“旁白”、“李远”）
    voice_id: str                  # 音色ID（如 zh-CN-YunjianNeural）
    rate: str = "+0%"              # 语速
    pitch: str = "+0Hz"            # 音调
    volume: float = 1.0            # 音量
    personality: str = ""          # 性格摘要（如“沉稳、内敛”）
    description: str = ""          # 角色介绍
    age: str = ""                  # 年龄段（如“青年”、“中年”）
    gender: str = ""               # 性别
    emotion_style: str = ""        # 情绪风格（如“冷静”、“激昂”）
    notes: str = ""                # 备注说明

@dataclass
class AudioClip:
    """音频片段（对白/音效/背景乐）"""
    id: str
    type: str                    # "dialogue", "bgm", "sfx"
    character: str               # 角色名
    text: str                    # 文本内容（供审核查看）
    file_path: str               # 实际音频文件路径
    voice: str                   # 音色
    rate: str                    # 语速
    pitch: str                   # 音调
    ssml_text: str = ""          # SSML标记文本（直接发送给TTS）
    volume: float = 1.0          # 音量倍数
    start_time: float = 0.0      # 开始时间（秒）
    duration: float = 0.0        # 时长（秒）
    is_generated: bool = False   # 是否已生成音频

@dataclass
class ScriptLine:
    """单行剧本（解析后的中间格式）"""
    type: str
    character: str
    emotion: str
    text: str                    # 文本内容（供审核查看）
    voice: str
    rate: str
    pitch: str
    ssml_text: str = ""          # SSML标记文本（直接发送给TTS）
    
    def get_tts_text(self) -> str:
        """
        获取用于 TTS 合成的文本
        
        优先级：
        1. 如果 ssml_text 非空，使用 ssml_text（包含标记的完整文本）
        2. 否则使用 text（纯文本）
        
        Returns:
            用于 TTS 合成的文本
        """
        if self.ssml_text and self.ssml_text.strip():
            return self.ssml_text
        return self.text

@dataclass
class Project:
    """完整工程"""
    name: str
    raw_text: str = ""
    script_lines: List[ScriptLine] = field(default_factory=list)
    audio_clips: List[AudioClip] = field(default_factory=list)
    bgm_clips: List[AudioClip] = field(default_factory=list)
    sfx_clips: List[AudioClip] = field(default_factory=list)
    llm_config: Dict = field(default_factory=dict)
    characters: List[Character] = field(default_factory=list)  # 🔑 角色列表
    character_voices: Dict = field(default_factory=dict)  # 向后兼容

# 全局当前工程
current_project = Project(name="未命名")

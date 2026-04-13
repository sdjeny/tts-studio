import os
from pathlib import Path

# 环境变量默认配置
DEFAULT_API_BASE = os.getenv("DEFAULT_API_BASE", "http://localhost:11434/v1")
DEFAULT_API_KEY = os.getenv("DEFAULT_API_KEY", "ollama")
DEFAULT_MODEL = os.getenv("DEFAULT_MODEL", "qwen2.5:7b")

# 数据存储目录
# 检测是否在 Docker 容器中运行
IN_DOCKER = os.path.exists("/.dockerenv") or os.getenv("DOCKER_CONTAINER")

if IN_DOCKER:
    # Docker 环境
    DATA_DIR = Path("/app/data")
else:
    # 本机开发环境 - 使用项目根目录下的 data 文件夹
    DATA_DIR = Path(__file__).parent.parent / "data"

AUDIO_DIR = DATA_DIR / "audio"
PROJECTS_DIR = DATA_DIR / "projects"

# 确保目录存在
DATA_DIR.mkdir(parents=True, exist_ok=True)
AUDIO_DIR.mkdir(exist_ok=True)
PROJECTS_DIR.mkdir(exist_ok=True)

# 音色配置
DEFAULT_VOICES = {
    "旁白": {"voice": "zh-CN-YunjianNeural", "rate": "-5%", "pitch": "+0Hz"},
    "默认男": {"voice": "zh-CN-YunxiNeural", "rate": "+0%", "pitch": "+0Hz"},
    "默认女": {"voice": "zh-CN-XiaoxiaoNeural", "rate": "+0%", "pitch": "+0Hz"},
}

# Edge-TTS 支持的所有中文音色（14个）
# 格式: (显示名称, 真实音色ID)
VOICE_OPTIONS = [
    # 中国大陆 (8个)
    ("晓晓 - 温柔女声", "zh-CN-XiaoxiaoNeural"),
    ("晓伊 - 活泼女声", "zh-CN-XiaoyiNeural"),
    ("云健 - 沉稳男声", "zh-CN-YunjianNeural"),
    ("云希 - 阳光男声", "zh-CN-YunxiNeural"),
    ("云霞 - 童声", "zh-CN-YunxiaNeural"),
    ("云扬 - 专业男声", "zh-CN-YunyangNeural"),
    ("小北 - 东北话", "zh-CN-liaoning-XiaobeiNeural"),
    ("小妮 - 陕西话", "zh-CN-shaanxi-XiaoniNeural"),
    # 台湾 (3个)
    ("晓晨 - 台湾女声", "zh-TW-HsiaoChenNeural"),
    ("晓宇 - 台湾女声", "zh-TW-HsiaoYuNeural"),
    ("云哲 - 台湾男声", "zh-TW-YunJheNeural"),
    # 香港 (3个)
    ("晓佳 - 粤语女声", "zh-HK-HiuGaaiNeural"),
    ("晓曼 - 粤语女声", "zh-HK-HiuMaanNeural"),
    ("云龙 - 粤语男声", "zh-HK-WanLungNeural"),
]

# 提取真实的音色ID列表（用于内部处理）
VOICE_IDS = [v[1] for v in VOICE_OPTIONS]

# LLM 提示词
SYSTEM_PROMPT = """你是一个专业的剧本解析器。将输入文本转换为结构化的有声剧本格式。

规则：
1. 识别：人物对白、旁白、场景说明/动作描写。
2. 对白格式：若有情绪提示，提取到 emotion 字段（如"愤怒"、"低声"）。
3. 只输出纯 JSON 数组，不要 Markdown 代码块。

输出格式：
[
  {"type": "direction", "character": "", "emotion": "", "text": "场景：大殿内，夜。"},
  {"type": "narration", "character": "旁白", "emotion": "", "text": "这场权力的游戏..."},
  {"type": "dialogue", "character": "李远", "emotion": "隐忍", "text": "臣无话可说。"}
]"""

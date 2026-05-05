"""
公共说话声列表模块
提供硬编码兜底音色列表，供 server.py 和 voice_service.py 共用，消除重复。
"""


def _get_fallback_speakers() -> list[dict]:
    """返回硬编码的兜底说话声列表（name + description）。

    与远端 /tts/speakers 返回格式一致，name 首字母大写。
    """
    return [
        {"name": "Aiden",     "description": "阳光美声男中音，清亮通透"},
        {"name": "Dylan",     "description": "青春北京男声，清澈自然"},
        {"name": "Eric",      "description": "活泼成都男声，略带沙哑的明亮感"},
        {"name": "Ono_Anna",  "description": "俏皮日式女声，轻盈灵动"},
        {"name": "Ryan",      "description": "动感男声，节奏感强"},
        {"name": "Serena",    "description": "温柔年轻女声，暖甜细腻"},
        {"name": "Sohee",     "description": "温暖韩语女声，情感丰富"},
        {"name": "Uncle_Fu",  "description": "成熟男声，低沉醇厚"},
        {"name": "Vivian",    "description": "明亮年轻女声，略带锐利"},
    ]
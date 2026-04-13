"""测试 tts_engine 的文本处理逻辑"""
import asyncio
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.tts_engine import synthesize_single_line
from app.models import ScriptLine

async def test():
    # 测试1：真正的纯文本
    print("=" * 60)
    print("测试1：纯文本（不应该有 SSML 标签）")
    print("=" * 60)
    
    line1 = ScriptLine(
        type="dialogue",
        character="旁白",
        emotion="",
        text="这是一个纯文本测试。",
        voice="zh-CN-YunjianNeural",
        rate="+0%",
        pitch="+0Hz"
    )
    
    print(f"\n传入的文本: {line1.text}")
    print(f"文本是否以 <speak 开头: {line1.text.strip().startswith('<speak')}")
    
    await synthesize_single_line(line1, "data/audio/test_pure_text.mp3")
    print(f"\n✅ 已生成: data/audio/test_pure_text.mp3")

if __name__ == "__main__":
    asyncio.run(test())

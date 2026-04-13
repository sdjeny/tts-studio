import asyncio
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.tts_engine import synthesize_single_line
from app.models import ScriptLine

async def test():
    # 测试1：最简单的 SSML
    ssml_minimal = """<speak version='1.0' xmlns='http://www.w3.org/2001/10/synthesis' xml:lang='zh-CN'>
<voice name='zh-CN-YunjianNeural'>
这是一个简单的测试。
</voice>
</speak>"""
    
    line1 = ScriptLine(
        type="dialogue",
        character="test",
        emotion="",
        text=ssml_minimal,
        voice="zh-CN-YunjianNeural",
        rate="+0%",
        pitch="+0Hz"
    )
    
    try:
        await synthesize_single_line(line1, "data/audio/test_minimal_ssml.mp3")
        print("Generated: data/audio/test_minimal_ssml.mp3")
    except Exception as e:
        print(f"Failed: {e}")
        
        # 测试2：纯文本（应该成功）
        print("\nTrying plain text...")
        line2 = ScriptLine(
            type="dialogue",
            character="test",
            emotion="",
            text="这是一个简单的测试。",
            voice="zh-CN-YunjianNeural",
            rate="+0%",
            pitch="+0Hz"
        )
        await synthesize_single_line(line2, "data/audio/test_plain_text.mp3")
        print("Generated: data/audio/test_plain_text.mp3")

if __name__ == "__main__":
    asyncio.run(test())

import asyncio
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.tts_engine import synthesize_single_line
from app.models import ScriptLine

async def test():
    # 测试自定义 SSML
    ssml_text = """<speak version='1.0' xmlns='http://www.w3.org/2001/10/synthesis' xml:lang='zh-CN'>
    <voice name='zh-CN-YunjianNeural'>
        <prosody rate="-15%">这句话前半部分慢一点</prosody>
        <break time="300ms"/>
        <prosody rate="+25%" pitch="+15Hz">后半部分快且高亢</prosody>
    </voice>
</speak>"""
    
    line = ScriptLine(
        type="dialogue",
        character="test",
        emotion="",
        text=ssml_text,
        voice="zh-CN-YunjianNeural",
        rate="+0%",
        pitch="+0Hz"
    )
    
    await synthesize_single_line(line, "data/audio/test_ssml_final.mp3")
    print("Generated: data/audio/test_ssml_final.mp3")

if __name__ == "__main__":
    asyncio.run(test())

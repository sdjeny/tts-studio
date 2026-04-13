"""
测试 edge-tts 发送的原始协议数据
通过 Monkey Patch 拦截发送的数据
"""
import asyncio
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 先打补丁，再导入 edge_tts
import edge_tts.communicate

_original_send_str = None
_sent_messages = []

async def patched_send_str(self, message):
    """拦截 websocket.send_str 调用"""
    print(f"\n{'='*60}")
    print(f"Sending WebSocket message:")
    print(f"{'='*60}")
    print(message[:500])  # 打印前500字符
    if len(message) > 500:
        print(f"... ({len(message)} total chars)")
    print(f"{'='*60}\n")
    _sent_messages.append(message)
    return await _original_send_str(self, message)

# 保存原始方法（稍后在 __stream 中替换）

from app.tts_engine import synthesize_single_line
from app.models import ScriptLine

async def test():
    global _original_send_str
    
    # 测试自定义 SSML
    ssml_text = """<speak version='1.0' xmlns='http://www.w3.org/2001/10/synthesis' xml:lang='zh-CN'>
<voice name='zh-CN-YunjianNeural'>
这是一个简单的测试。
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
    
    try:
        await synthesize_single_line(line, "data/audio/test_capture.mp3")
        print("✅ Success!")
    except Exception as e:
        print(f"❌ Failed: {e}")

if __name__ == "__main__":
    asyncio.run(test())

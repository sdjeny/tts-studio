"""测试 tts_engine 中的 SSML 支持"""
import asyncio
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.models import ScriptLine
from app.tts_engine import synthesize_single_line

async def test_tts_engine_ssml():
    """测试 tts_engine 处理 SSML"""
    
    # 测试1：纯文本（应该让 edge-tts 自己构建 SSML）
    print("=" * 80)
    print("测试1：纯文本模式")
    print("=" * 80)
    
    line1 = ScriptLine(
        type="dialogue",
        character="测试",
        emotion="normal",
        text="这是一个纯文本测试。",
        voice="zh-CN-YunjianNeural",
        rate="+0%",
        pitch="+0Hz"
    )
    
    try:
        duration1 = await synthesize_single_line(line1, "data/audio/test_pure_text_mode.mp3")
        print(f"✅ 成功，时长: {duration1:.2f} 秒\n")
    except Exception as e:
        print(f"❌ 失败: {e}\n")
    
    # 测试2：自定义 SSML（单个 prosody）
    print("=" * 80)
    print("测试2：自定义 SSML - 单个 prosody（慢速）")
    print("=" * 80)
    
    ssml_text = "<speak version='1.0' xmlns='http://www.w3.org/2001/10/synthesis' xml:lang='en-US'><voice name='Microsoft Server Speech Text to Speech Voice (zh-CN, YunjianNeural)'><prosody pitch='+0Hz' rate='-50%' volume='+0%'>这是慢速测试。</prosody></voice></speak>"
    
    line2 = ScriptLine(
        type="dialogue",
        character="测试",
        emotion="normal",
        text=ssml_text,
        voice="zh-CN-YunjianNeural",
        rate="+0%",
        pitch="+0Hz"
    )
    
    try:
        duration2 = await synthesize_single_line(line2, "data/audio/test_custom_ssml_single.mp3")
        print(f"✅ 成功，时长: {duration2:.2f} 秒\n")
    except Exception as e:
        print(f"❌ 失败: {e}\n")
    
    # 测试3：多个 prosody（一句话内多次语气变化）
    print("=" * 80)
    print("测试3：自定义 SSML - 多个 prosody（一慢一快）")
    print("=" * 80)
    
    ssml_text3 = "<speak version='1.0' xmlns='http://www.w3.org/2001/10/synthesis' xml:lang='en-US'><voice name='Microsoft Server Speech Text to Speech Voice (zh-CN, YunjianNeural)'><prosody pitch='+0Hz' rate='-40%' volume='+0%'>前半部分慢</prosody><prosody pitch='+0Hz' rate='+0%' volume='+0%'>，</prosody><prosody pitch='+0Hz' rate='+50%' volume='+0%'>后半部分快</prosody></voice></speak>"
    
    line3 = ScriptLine(
        type="dialogue",
        character="测试",
        emotion="normal",
        text=ssml_text3,
        voice="zh-CN-YunjianNeural",
        rate="+0%",
        pitch="+0Hz"
    )
    
    try:
        duration3 = await synthesize_single_line(line3, "data/audio/test_custom_ssml_multi.mp3")
        print(f"✅ 成功，时长: {duration3:.2f} 秒\n")
    except Exception as e:
        print(f"❌ 失败: {e}\n")
    
    print("=" * 80)
    print("所有测试完成！请检查 data/audio/ 目录下的文件")
    print("=" * 80)

if __name__ == "__main__":
    asyncio.run(test_tts_engine_ssml())

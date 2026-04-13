"""测试单个 vs 多个 prosody"""
import asyncio
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import patch_edge_tts_v2
import edge_tts

async def test_single_vs_multiple():
    voice = "zh-CN-YunjianNeural"
    
    # 测试1：单个 prosody（应该成功）
    print("测试1：单个 prosody")
    ssml1 = """<speak version='1.0' xmlns='http://www.w3.org/2001/10/synthesis' xml:lang='en-US'><voice name='Microsoft Server Speech Text to Speech Voice (zh-CN, YunjianNeural)'><prosody pitch='+0Hz' rate='-30%' volume='+0%'>慢速测试</prosody></voice></speak>"""
    
    try:
        comm1 = edge_tts.Communicate(text=ssml1, voice=voice, rate="+0%", pitch="+0Hz")
        await comm1.save("data/audio/test_single_prosody.mp3")
        print("✅ 成功\n")
    except Exception as e:
        print(f"❌ 失败: {e}\n")
    
    # 测试2：两个 prosody（测试是否多个导致失败）
    print("测试2：两个 prosody")
    ssml2 = """<speak version='1.0' xmlns='http://www.w3.org/2001/10/synthesis' xml:lang='en-US'><voice name='Microsoft Server Speech Text to Speech Voice (zh-CN, YunjianNeural)'><prosody pitch='+0Hz' rate='-30%' volume='+0%'>慢</prosody><prosody pitch='+0Hz' rate='+30%' volume='+0%'>快</prosody></voice></speak>"""
    
    try:
        comm2 = edge_tts.Communicate(text=ssml2, voice=voice, rate="+0%", pitch="+0Hz")
        await comm2.save("data/audio/test_two_prosody.mp3")
        print("✅ 成功\n")
    except Exception as e:
        print(f"❌ 失败: {e}\n")
    
    # 测试3：带 break 标签
    print("测试3：带 break 标签")
    ssml3 = """<speak version='1.0' xmlns='http://www.w3.org/2001/10/synthesis' xml:lang='en-US'><voice name='Microsoft Server Speech Text to Speech Voice (zh-CN, YunjianNeural)'><prosody pitch='+0Hz' rate='+0%' volume='+0%'>你好</prosody><break time='500ms'/><prosody pitch='+0Hz' rate='+0%' volume='+0%'>世界</prosody></voice></speak>"""
    
    try:
        comm3 = edge_tts.Communicate(text=ssml3, voice=voice, rate="+0%", pitch="+0Hz")
        await comm3.save("data/audio/test_with_break.mp3")
        print("✅ 成功\n")
    except Exception as e:
        print(f"❌ 失败: {e}\n")

if __name__ == "__main__":
    asyncio.run(test_single_vs_multiple())

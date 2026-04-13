"""测试多个 prosody 的正确用法"""
import asyncio
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import patch_edge_tts_v2
import edge_tts

async def test_multi_prosody_correct():
    voice = "zh-CN-YunjianNeural"
    
    # 测试1：两个 prosody，每个都有足够文本
    print("测试1：两个 prosody，每个都有完整句子")
    ssml1 = "<speak version='1.0' xmlns='http://www.w3.org/2001/10/synthesis' xml:lang='en-US'><voice name='Microsoft Server Speech Text to Speech Voice (zh-CN, YunjianNeural)'><prosody pitch='+0Hz' rate='-40%' volume='+0%'>这句话前半部分比较慢</prosody><prosody pitch='+0Hz' rate='+50%' volume='+0%'>后半部分非常快</prosody></voice></speak>"
    
    try:
        comm1 = edge_tts.Communicate(text=ssml1, voice=voice, rate="+0%", pitch="+0Hz")
        await comm1.save("data/audio/test_two_sentences.mp3")
        print("✅ 成功\n")
    except Exception as e:
        print(f"❌ 失败: {e}\n")
    
    # 测试2：三个 prosody，把逗号放在第一个里面
    print("测试2：三个 prosody，逗号在第一个里面")
    ssml2 = "<speak version='1.0' xmlns='http://www.w3.org/2001/10/synthesis' xml:lang='en-US'><voice name='Microsoft Server Speech Text to Speech Voice (zh-CN, YunjianNeural)'><prosody pitch='+0Hz' rate='-40%' volume='+0%'>前半部分慢，</prosody><prosody pitch='+0Hz' rate='+0%' volume='+0%'>中间正常</prosody><prosody pitch='+0Hz' rate='+50%' volume='+0%'>后半部分快</prosody></voice></speak>"
    
    try:
        comm2 = edge_tts.Communicate(text=ssml2, voice=voice, rate="+0%", pitch="+0Hz")
        await comm2.save("data/audio/test_three_with_comma.mp3")
        print("✅ 成功\n")
    except Exception as e:
        print(f"❌ 失败: {e}\n")
    
    # 测试3：三个 prosody，逗号在第二个开头
    print("测试3：三个 prosody，逗号在第二个开头")
    ssml3 = "<speak version='1.0' xmlns='http://www.w3.org/2001/10/synthesis' xml:lang='en-US'><voice name='Microsoft Server Speech Text to Speech Voice (zh-CN, YunjianNeural)'><prosody pitch='+0Hz' rate='-40%' volume='+0%'>前半部分慢</prosody><prosody pitch='+0Hz' rate='+0%' volume='+0%'>，中间正常</prosody><prosody pitch='+0Hz' rate='+50%' volume='+0%'>后半部分快</prosody></voice></speak>"
    
    try:
        comm3 = edge_tts.Communicate(text=ssml3, voice=voice, rate="+0%", pitch="+0Hz")
        await comm3.save("data/audio/test_comma_at_start.mp3")
        print("✅ 成功\n")
    except Exception as e:
        print(f"❌ 失败: {e}\n")

if __name__ == "__main__":
    asyncio.run(test_multi_prosody_correct())

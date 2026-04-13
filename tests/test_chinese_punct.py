"""测试中文标点是否导致问题"""
import asyncio
import sys
import os

# 添加项目根目录到路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from app import patch_edge_tts_v2
import edge_tts

async def test_chinese_punctuation():
    voice = "zh-CN-YunjianNeural"
    
    # 测试1：没有中文标点
    print("测试1：没有中文标点")
    ssml1 = "<speak version='1.0' xmlns='http://www.w3.org/2001/10/synthesis' xml:lang='en-US'><voice name='Microsoft Server Speech Text to Speech Voice (zh-CN, YunjianNeural)'><prosody pitch='+0Hz' rate='-40%' volume='+0%'>前半部分慢</prosody><prosody pitch='+0Hz' rate='+0%' volume='+0%'>后半部分快</prosody></voice></speak>"
    
    try:
        comm1 = edge_tts.Communicate(text=ssml1, voice=voice, rate="+0%", pitch="+0Hz")
        await comm1.save("data/audio/test_no_punct.mp3")
        print("✅ 成功\n")
    except Exception as e:
        print(f"❌ 失败: {e}\n")
    
    # 测试2：有中文逗号
    print("测试2：有中文逗号")
    ssml2 = "<speak version='1.0' xmlns='http://www.w3.org/2001/10/synthesis' xml:lang='en-US'><voice name='Microsoft Server Speech Text to Speech Voice (zh-CN, YunjianNeural)'><prosody pitch='+0Hz' rate='-40%' volume='+0%'>前半部分慢</prosody><prosody pitch='+0Hz' rate='+0%' volume='+0%'>，</prosody><prosody pitch='+0Hz' rate='+50%' volume='+0%'>后半部分快</prosody></voice></speak>"
    
    try:
        comm2 = edge_tts.Communicate(text=ssml2, voice=voice, rate="+0%", pitch="+0Hz")
        await comm2.save("data/audio/test_with_comma.mp3")
        print("✅ 成功\n")
    except Exception as e:
        print(f"❌ 失败: {e}\n")

if __name__ == "__main__":
    asyncio.run(test_chinese_punctuation())

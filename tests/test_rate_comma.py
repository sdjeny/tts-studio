"""测试 rate 参数使用逗号分隔多个值"""
import asyncio
import sys
import os

# 添加项目根目录到路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from app import patch_edge_tts_v2
import edge_tts

async def test_rate_comma():
    voice = "zh-CN-YunjianNeural"
    
    # 测试1：SSML 中 rate 使用逗号
    print("测试1：SSML 中 rate 使用逗号（-50%,+50%）")
    ssml1 = """<speak version='1.0' xmlns='http://www.w3.org/2001/10/synthesis' xml:lang='en-US'><voice name='Microsoft Server Speech Text to Speech Voice (zh-CN, YunjianNeural)'><prosody pitch='+0Hz' rate='-50%,+50%' volume='+0%'>这是一个测试。</prosody></voice></speak>"""
    
    try:
        comm1 = edge_tts.Communicate(text=ssml1, voice=voice, rate="+0%", pitch="+0Hz")
        await comm1.save("data/audio/test_rate_comma_ssml.mp3")
        print("✅ 成功\n")
    except Exception as e:
        print(f"❌ 失败: {e}\n")
    
    # 测试2：纯文本 + rate 逗号参数
    print("测试2：纯文本 + rate 逗号参数")
    try:
        comm2 = edge_tts.Communicate(text="这是一个测试。", voice=voice, rate="-50%,+50%", pitch="+0Hz")
        await comm2.save("data/audio/test_rate_comma_pure.mp3")
        print("✅ 成功\n")
    except Exception as e:
        print(f"❌ 失败: {e}\n")

if __name__ == "__main__":
    asyncio.run(test_rate_comma())

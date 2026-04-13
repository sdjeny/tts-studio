"""测试高级 SSML 功能 - 探索 edge-tts 的极限"""
import asyncio
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 导入补丁
import patch_edge_tts_v2

import edge_tts
from edge_tts.data_classes import TTSConfig
from edge_tts.communicate import mkssml
from xml.sax.saxutils import escape

async def test_advanced_ssml():
    """测试高级 SSML 功能"""
    
    voice = "zh-CN-YunjianNeural"
    
    # 测试1：一句话内多次语气变化
    print("=" * 80)
    print("测试1：一句话内多次语气变化")
    print("=" * 80)
    
    ssml1 = """<speak version='1.0' xmlns='http://www.w3.org/2001/10/synthesis' xml:lang='en-US'><voice name='Microsoft Server Speech Text to Speech Voice (zh-CN, YunjianNeural)'><prosody pitch='+0Hz' rate='-30%' volume='+0%'>这句话前半部分慢一点</prosody><prosody pitch='+0Hz' rate='+0%' volume='+0%'>，</prosody><prosody pitch='+0Hz' rate='+40%' volume='+0%'>后半部分快很多</prosody></voice></speak>"""
    
    print(f"SSML:\n{ssml1}\n")
    
    try:
        comm1 = edge_tts.Communicate(text=ssml1, voice=voice, rate="+0%", pitch="+0Hz")
        await comm1.save("data/audio/test_multi_prosody.mp3")
        print("✅ 生成成功: test_multi_prosody.mp3\n")
    except Exception as e:
        print(f"❌ 失败: {e}\n")
    
    # 测试2：停顿控制
    print("=" * 80)
    print("测试2：停顿控制（短停顿、长停顿）")
    print("=" * 80)
    
    ssml2 = """<speak version='1.0' xmlns='http://www.w3.org/2001/10/synthesis' xml:lang='en-US'><voice name='Microsoft Server Speech Text to Speech Voice (zh-CN, YunjianNeural)'><prosody pitch='+0Hz' rate='+0%' volume='+0%'>请注意</prosody><break time='500ms'/><prosody pitch='+0Hz' rate='+0%' volume='+0%'>这里有重要信息</prosody><break time='1000ms'/><prosody pitch='+0Hz' rate='+0%' volume='+0%'>请认真听</prosody></voice></speak>"""
    
    print(f"SSML:\n{ssml2}\n")
    
    try:
        comm2 = edge_tts.Communicate(text=ssml2, voice=voice, rate="+0%", pitch="+0Hz")
        await comm2.save("data/audio/test_breaks.mp3")
        print("✅ 生成成功: test_breaks.mp3\n")
    except Exception as e:
        print(f"❌ 失败: {e}\n")
    
    # 测试3：多音字标注（使用 phoneme）
    print("=" * 80)
    print("测试3：多音字标注")
    print("=" * 80)
    
    # 尝试使用 sapi 拼音标注
    ssml3 = """<speak version='1.0' xmlns='http://www.w3.org/2001/10/synthesis' xml:lang='en-US'><voice name='Microsoft Server Speech Text to Speech Voice (zh-CN, YunjianNeural)'><prosody pitch='+0Hz' rate='+0%' volume='+0%'>这个</prosody><phoneme alphabet="sapi" ph="zhong4">重</phoneme><prosody pitch='+0Hz' rate='+0%' volume='+0%'>要的事情说三遍。</prosody></voice></speak>"""
    
    print(f"SSML:\n{ssml3}\n")
    
    try:
        comm3 = edge_tts.Communicate(text=ssml3, voice=voice, rate="+0%", pitch="+0Hz")
        await comm3.save("data/audio/test_phoneme.mp3")
        print("✅ 生成成功: test_phoneme.mp3\n")
    except Exception as e:
        print(f"❌ 失败: {e}\n")
    
    # 测试4：强调
    print("=" * 80)
    print("测试4：强调文本")
    print("=" * 80)
    
    ssml4 = """<speak version='1.0' xmlns='http://www.w3.org/2001/10/synthesis' xml:lang='en-US'><voice name='Microsoft Server Speech Text to Speech Voice (zh-CN, YunjianNeural)'><prosody pitch='+0Hz' rate='+0%' volume='+0%'>这是</prosody><emphasis level="strong"><prosody pitch='+0Hz' rate='+0%' volume='+0%'>非常重要</prosody></emphasis><prosody pitch='+0Hz' rate='+0%' volume='+0%'>的信息</prosody></voice></speak>"""
    
    print(f"SSML:\n{ssml4}\n")
    
    try:
        comm4 = edge_tts.Communicate(text=ssml4, voice=voice, rate="+0%", pitch="+0Hz")
        await comm4.save("data/audio/test_emphasis.mp3")
        print("✅ 生成成功: test_emphasis.mp3\n")
    except Exception as e:
        print(f"❌ 失败: {e}\n")
    
    # 测试5：综合测试（所有功能组合）
    print("=" * 80)
    print("测试5：综合测试（语气变化 + 停顿 + 强调）")
    print("=" * 80)
    
    ssml5 = """<speak version='1.0' xmlns='http://www.w3.org/2001/10/synthesis' xml:lang='en-US'><voice name='Microsoft Server Speech Text to Speech Voice (zh-CN, YunjianNeural)'><prosody pitch='+0Hz' rate='-20%' volume='+0%'>首先</prosody><break time='300ms'/><prosody pitch='+0Hz' rate='+0%' volume='+0%'>我要说的是</prosody><emphasis level="moderate"><prosody pitch='+10Hz' rate='+0%' volume='+0%'>这个非常关键</prosody></emphasis><break time='500ms'/><prosody pitch='+0Hz' rate='+30%' volume='+0%'>请一定要记住</prosody></voice></speak>"""
    
    print(f"SSML:\n{ssml5}\n")
    
    try:
        comm5 = edge_tts.Communicate(text=ssml5, voice=voice, rate="+0%", pitch="+0Hz")
        await comm5.save("data/audio/test_comprehensive.mp3")
        print("✅ 生成成功: test_comprehensive.mp3\n")
    except Exception as e:
        print(f"❌ 失败: {e}\n")
    
    # 测试6：极端语速
    print("=" * 80)
    print("测试6：极端语速（-100% 和 +100%）")
    print("=" * 80)
    
    ssml6_slow = """<speak version='1.0' xmlns='http://www.w3.org/2001/10/synthesis' xml:lang='en-US'><voice name='Microsoft Server Speech Text to Speech Voice (zh-CN, YunjianNeural)'><prosody pitch='+0Hz' rate='-100%' volume='+0%'>极慢速测试</prosody></voice></speak>"""
    
    ssml6_fast = """<speak version='1.0' xmlns='http://www.w3.org/2001/10/synthesis' xml:lang='en-US'><voice name='Microsoft Server Speech Text to Speech Voice (zh-CN, YunjianNeural)'><prosody pitch='+0Hz' rate='+100%' volume='+0%'>极快速测试</prosody></voice></speak>"""
    
    print(f"慢速 SSML:\n{ssml6_slow}\n")
    print(f"快速 SSML:\n{ssml6_fast}\n")
    
    try:
        comm6a = edge_tts.Communicate(text=ssml6_slow, voice=voice, rate="+0%", pitch="+0Hz")
        await comm6a.save("data/audio/test_extreme_slow.mp3")
        print("✅ 生成成功: test_extreme_slow.mp3\n")
    except Exception as e:
        print(f"❌ 慢速失败: {e}\n")
    
    try:
        comm6b = edge_tts.Communicate(text=ssml6_fast, voice=voice, rate="+0%", pitch="+0Hz")
        await comm6b.save("data/audio/test_extreme_fast.mp3")
        print("✅ 生成成功: test_extreme_fast.mp3\n")
    except Exception as e:
        print(f"❌ 快速失败: {e}\n")
    
    print("=" * 80)
    print("所有测试完成！生成的文件：")
    print("=" * 80)
    print("1. test_multi_prosody.mp3     - 一句话内多次语气变化")
    print("2. test_breaks.mp3            - 停顿控制")
    print("3. test_phoneme.mp3           - 多音字标注")
    print("4. test_emphasis.mp3          - 强调文本")
    print("5. test_comprehensive.mp3     - 综合测试")
    print("6. test_extreme_slow.mp3      - 极慢速 (-100%)")
    print("7. test_extreme_fast.mp3      - 极快速 (+100%)")

if __name__ == "__main__":
    asyncio.run(test_advanced_ssml())

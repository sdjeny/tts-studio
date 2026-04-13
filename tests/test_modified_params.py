"""测试修改 SSML 参数值"""
import asyncio
import sys
import os

# 添加项目根目录到路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

# 导入补丁
from app import patch_edge_tts_v2

import edge_tts
from edge_tts.data_classes import TTSConfig
from edge_tts.communicate import mkssml
from xml.sax.saxutils import escape

async def test_modified_params():
    """测试不同的参数组合"""
    
    text = "这是一个测试。"
    voice = "zh-CN-YunjianNeural"
    
    # 测试1：正常语速
    print("=" * 80)
    print("测试1：正常语速 (+0%)")
    print("=" * 80)
    
    tc1 = TTSConfig(voice, "+0%", "+0%", "+0Hz", "SentenceBoundary")
    ssml1 = mkssml(tc1, escape(text))
    print(f"SSML: {ssml1}\n")
    
    try:
        comm1 = edge_tts.Communicate(text=ssml1, voice=voice, rate="+0%", pitch="+0Hz")
        await comm1.save("data/audio/test_normal_rate.mp3")
        print("✅ 生成成功: test_normal_rate.mp3\n")
    except Exception as e:
        print(f"❌ 失败: {e}\n")
    
    # 测试2：慢速 (-50%)
    print("=" * 80)
    print("测试2：慢速 (-50%)")
    print("=" * 80)
    
    tc2 = TTSConfig(voice, "-50%", "+0%", "+0Hz", "SentenceBoundary")
    ssml2 = mkssml(tc2, escape(text))
    print(f"SSML: {ssml2}\n")
    
    try:
        comm2 = edge_tts.Communicate(text=ssml2, voice=voice, rate="-50%", pitch="+0Hz")
        await comm2.save("data/audio/test_slow_rate.mp3")
        print("✅ 生成成功: test_slow_rate.mp3\n")
    except Exception as e:
        print(f"❌ 失败: {e}\n")
    
    # 测试3：快速 (+50%)
    print("=" * 80)
    print("测试3：快速 (+50%)")
    print("=" * 80)
    
    tc3 = TTSConfig(voice, "+50%", "+0%", "+0Hz", "SentenceBoundary")
    ssml3 = mkssml(tc3, escape(text))
    print(f"SSML: {ssml3}\n")
    
    try:
        comm3 = edge_tts.Communicate(text=ssml3, voice=voice, rate="+50%", pitch="+0Hz")
        await comm3.save("data/audio/test_fast_rate.mp3")
        print("✅ 生成成功: test_fast_rate.mp3\n")
    except Exception as e:
        print(f"❌ 失败: {e}\n")
    
    # 测试4：高音调 (+20Hz)
    print("=" * 80)
    print("测试4：高音调 (+20Hz)")
    print("=" * 80)
    
    tc4 = TTSConfig(voice, "+0%", "+0%", "+20Hz", "SentenceBoundary")
    ssml4 = mkssml(tc4, escape(text))
    print(f"SSML: {ssml4}\n")
    
    try:
        comm4 = edge_tts.Communicate(text=ssml4, voice=voice, rate="+0%", pitch="+20Hz")
        await comm4.save("data/audio/test_high_pitch.mp3")
        print("✅ 生成成功: test_high_pitch.mp3\n")
    except Exception as e:
        print(f"❌ 失败: {e}\n")
    
    # 测试5：低音调 (-20Hz)
    print("=" * 80)
    print("测试5：低音调 (-20Hz)")
    print("=" * 80)
    
    tc5 = TTSConfig(voice, "+0%", "+0%", "-20Hz", "SentenceBoundary")
    ssml5 = mkssml(tc5, escape(text))
    print(f"SSML: {ssml5}\n")
    
    try:
        comm5 = edge_tts.Communicate(text=ssml5, voice=voice, rate="+0%", pitch="-20Hz")
        await comm5.save("data/audio/test_low_pitch.mp3")
        print("✅ 生成成功: test_low_pitch.mp3\n")
    except Exception as e:
        print(f"❌ 失败: {e}\n")
    
    print("=" * 80)
    print("所有测试完成！请对比以下文件：")
    print("=" * 80)
    print("1. test_normal_rate.mp3 - 正常语速")
    print("2. test_slow_rate.mp3   - 慢速 (-50%)")
    print("3. test_fast_rate.mp3   - 快速 (+50%)")
    print("4. test_high_pitch.mp3  - 高音调 (+20Hz)")
    print("5. test_low_pitch.mp3   - 低音调 (-20Hz)")

if __name__ == "__main__":
    asyncio.run(test_modified_params())

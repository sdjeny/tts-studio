"""端到端测试：高级标记文本合成 + 自动拼接"""
import asyncio
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.models import ScriptLine
from app.tts_engine import synthesize_single_line

async def test_end_to_end():
    print("=" * 80)
    print("端到端测试：高级标记文本自动拆分+拼接")
    print("=" * 80)
    print()
    
    # 测试1：两个片段（一慢一快）
    print("测试1：两个片段（一慢一快）")
    print("-" * 80)
    text1 = "[rate=-40%]前半部分慢[/rate][rate=+50%]后半部分快[/rate]"
    print(f"输入文本: {text1}")
    
    line1 = ScriptLine(
        type="dialogue",
        character="测试",
        emotion="normal",
        text=text1,
        voice="zh-CN-YunjianNeural",
        rate="+0%",
        pitch="+0Hz"
    )
    
    try:
        duration1 = await synthesize_single_line(line1, "data/audio/test_advanced_2seg.mp3")
        print(f"✅ 成功！时长: {duration1:.2f} 秒\n")
    except Exception as e:
        print(f"❌ 失败: {e}\n")
        import traceback
        traceback.print_exc()
    
    # 测试2：三个片段（慢-正常-快）
    print("测试2：三个片段（慢-正常-快）")
    print("-" * 80)
    text2 = "[rate=-40%]慢速[/rate]正常语速[rate=+50%]快速[/rate]"
    print(f"输入文本: {text2}")
    
    line2 = ScriptLine(
        type="dialogue",
        character="测试",
        emotion="normal",
        text=text2,
        voice="zh-CN-YunjianNeural",
        rate="+0%",
        pitch="+0Hz"
    )
    
    try:
        duration2 = await synthesize_single_line(line2, "data/audio/test_advanced_3seg.mp3")
        print(f"✅ 成功！时长: {duration2:.2f} 秒\n")
    except Exception as e:
        print(f"❌ 失败: {e}\n")
        import traceback
        traceback.print_exc()
    
    # 测试3：带音调变化
    print("测试3：带音调变化")
    print("-" * 80)
    text3 = "[rate=-30%][pitch=+10Hz]慢速高音[/pitch][/rate][rate=+40%][pitch=-10Hz]快速低音[/pitch][/rate]"
    print(f"输入文本: {text3}")
    
    line3 = ScriptLine(
        type="dialogue",
        character="测试",
        emotion="normal",
        text=text3,
        voice="zh-CN-YunjianNeural",
        rate="+0%",
        pitch="+0Hz"
    )
    
    try:
        duration3 = await synthesize_single_line(line3, "data/audio/test_advanced_pitch.mp3")
        print(f"✅ 成功！时长: {duration3:.2f} 秒\n")
    except Exception as e:
        print(f"❌ 失败: {e}\n")
        import traceback
        traceback.print_exc()
    
    # 测试4：多音字处理（纯文本模式）
    print("测试4：多音字（纯文本模式，由 edge-tts 自动处理）")
    print("-" * 80)
    text4 = "重要的事情说三遍"
    print(f"输入文本: {text4}")
    print("说明：edge-tts 会自动处理常见多音字，但无法精确控制")
    
    line4 = ScriptLine(
        type="dialogue",
        character="测试",
        emotion="normal",
        text=text4,
        voice="zh-CN-YunjianNeural",
        rate="+0%",
        pitch="+0Hz"
    )
    
    try:
        duration4 = await synthesize_single_line(line4, "data/audio/test_multitone.mp3")
        print(f"✅ 成功！时长: {duration4:.2f} 秒\n")
    except Exception as e:
        print(f"❌ 失败: {e}\n")
        import traceback
        traceback.print_exc()
    
    print("=" * 80)
    print("所有测试完成！请检查 data/audio/ 目录下的文件：")
    print("  - test_advanced_2seg.mp3  (2个片段)")
    print("  - test_advanced_3seg.mp3  (3个片段)")
    print("  - test_advanced_pitch.mp3 (带音调变化)")
    print("  - test_multitone.mp3      (多音字)")
    print("=" * 80)

if __name__ == "__main__":
    asyncio.run(test_end_to_end())

"""
对比测试：同音字替换 vs 拼音策略
文本：银行行长有着长长的尾巴
"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from app.models import ScriptLine
from app.tts_engine import synthesize_single_line

async def main():
    print("=" * 80)
    print("对比测试：同音字替换 vs 拼音策略")
    print("=" * 80)
    print("\n原始文本：银行行长有着长长的尾巴")
    print("\n多音字分析：")
    print("  - 行（银行）：hang2")
    print("  - 行（行长）：hang2")
    print("  - 长（行长）：zhang3")
    print("  - 长（长长）：chang2")
    print("  - 长（长长）：chang2")
    print("=" * 80)
    
    # 策略1：同音字替换
    print("\n" + "=" * 80)
    print("策略1：同音字替换")
    print("=" * 80)
    
    # 同音字对照表：
    # 行(hang2) → 航 （银行、行长都用 hang2）
    # 长(zhang3) → 掌 （行长）
    # 长(chang2) → 常 （长短）
    text_homophone = "银[phoneme=航]行[/phoneme][phoneme=航]行[/phoneme][phoneme=掌]长[/phoneme]有着[phoneme=常]长[/phoneme][phoneme=常]长[/phoneme]的尾巴"
    
    line1 = ScriptLine(
        text=text_homophone,
        voice="zh-CN-YunjianNeural",
        type="narration",
        character="旁白",
        emotion="neutral",
        rate="+0%",
        pitch="+0Hz"
    )
    
    output1 = "data/audio/test_phoneme_compare_homophone.mp3"
    print(f"\n标记文本: {text_homophone}")
    print(f"输出文件: {output1}")
    print(f"\n替换说明:")
    print(f"  - '行'(hang2) → '航' (银行)")
    print(f"  - '行'(hang2) → '航' (行长)")
    print(f"  - '长'(zhang3) → '掌' (行长)")
    print(f"  - '长'(chang2) → '常' (长短)")
    
    try:
        duration1 = await synthesize_single_line(line1, output1)
        file_size = os.path.getsize(output1)
        print(f"\n✅ 生成成功")
        print(f"   时长: {duration1:.2f} 秒")
        print(f"   大小: {file_size} bytes")
    except Exception as e:
        print(f"❌ 生成失败: {e}")
        import traceback
        traceback.print_exc()
    
    # 策略2：拼音策略
    print("\n" + "=" * 80)
    print("策略2：拼音策略")
    print("=" * 80)
    
    text_pinyin = "银[phoneme=hang2]行[/phoneme][phoneme=hang2]行[/phoneme][phoneme=zhang3]长[/phoneme]有着[phoneme=chang2]长[/phoneme][phoneme=chang2]长[/phoneme]的尾巴"
    
    line2 = ScriptLine(
        text=text_pinyin,
        voice="zh-CN-YunjianNeural",
        type="narration",
        character="旁白",
        emotion="neutral",
        rate="+0%",
        pitch="+0Hz"
    )
    
    output2 = "data/audio/test_phoneme_compare_pinyin.mp3"
    print(f"\n标记文本: {text_pinyin}")
    print(f"输出文件: {output2}")
    print(f"\n拼音说明:")
    print(f"  - '行' → 'hang2' (银行)")
    print(f"  - '行' → 'hang2' (行长)")
    print(f"  - '长' → 'zhang3' (行长)")
    print(f"  - '长' → 'chang2' (长短)")
    print(f"  - '长' → 'chang2' (长短)")
    
    try:
        duration2 = await synthesize_single_line(line2, output2)
        file_size = os.path.getsize(output2)
        print(f"\n✅ 生成成功")
        print(f"   时长: {duration2:.2f} 秒")
        print(f"   大小: {file_size} bytes")
    except Exception as e:
        print(f"❌ 生成失败: {e}")
        import traceback
        traceback.print_exc()
    
    # 对照组：无标记（可能读错）
    print("\n" + "=" * 80)
    print("对照组：无标记（默认读音）")
    print("=" * 80)
    
    text_plain = "银行行长有着长长的尾巴"
    
    line3 = ScriptLine(
        text=text_plain,
        voice="zh-CN-YunjianNeural",
        type="narration",
        character="旁白",
        emotion="neutral",
        rate="+0%",
        pitch="+0Hz"
    )
    
    output3 = "data/audio/test_phoneme_compare_plain.mp3"
    print(f"\n原始文本: {text_plain}")
    print(f"输出文件: {output3}")
    print(f"\n注意：edge-tts 可能会读错多音字")
    
    try:
        duration3 = await synthesize_single_line(line3, output3)
        file_size = os.path.getsize(output3)
        print(f"\n✅ 生成成功")
        print(f"   时长: {duration3:.2f} 秒")
        print(f"   大小: {file_size} bytes")
    except Exception as e:
        print(f"❌ 生成失败: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "=" * 80)
    print("✅ 所有音频生成完成！")
    print("=" * 80)
    
    print("\n📁 生成的音频文件：")
    print(f"  1. 同音字替换: {output1}")
    print(f"  2. 拼音策略: {output2}")
    print(f"  3. 无标记对照: {output3}")
    
    print("\n💡 请试听对比：")
    print("  - 听'银行'是否读作 'yin2 hang2'（而非 yin2 xing2）")
    print("  - 听'行长'是否读作 'hang2 zhang3'（而非 xing2 chang2）")
    print("  - 听'长长'是否读作 'chang2 chang2'（而非 zhang3 zhang3）")
    print("\n📊 对比要点：")
    print("  1. 同音字替换：利用 edge-tts 对常见字的准确识别")
    print("     优点：自然度高，语调连贯")
    print("     缺点：需要找到合适的同音字")
    print()
    print("  2. 拼音策略：直接指定拼音和声调")
    print("     优点：精确控制，不受上下文影响")
    print("     缺点：可能语调不够自然")
    print()
    print("  3. 无标记：让 edge-tts 自动判断")
    print("     优点：简单方便")
    print("     缺点：可能读错多音字")

if __name__ == "__main__":
    asyncio.run(main())

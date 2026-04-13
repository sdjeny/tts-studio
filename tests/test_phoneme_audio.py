"""
测试多音字实际音频生成
"""
import asyncio
import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.dirname(__file__))

from app.models import ScriptLine
from app.tts_engine import synthesize_single_line

async def main():
    print("=" * 80)
    print("测试多音字实际音频生成")
    print("=" * 80)
    
    # 测试1：拼音策略
    print("\n" + "=" * 80)
    print("测试1：拼音策略 - 银行行长")
    print("=" * 80)
    
    line1 = ScriptLine(
        text="银[phoneme=hang2]行[/phoneme][phoneme=zhang3]行[/phoneme]长",
        voice="zh-CN-YunjianNeural",
        type="narration",
        character="旁白",
        emotion="neutral",
        rate="+0%",
        pitch="+0Hz"
    )
    
    output1 = "data/audio/test_phoneme_pinyin.mp3"
    print(f"\n原始文本: {line1.text}")
    print(f"输出文件: {output1}")
    
    try:
        duration1 = await synthesize_single_line(line1, output1)
        file_size = os.path.getsize(output1)
        print(f"✅ 生成成功")
        print(f"   时长: {duration1:.2f} 秒")
        print(f"   大小: {file_size} bytes")
    except Exception as e:
        print(f"❌ 生成失败: {e}")
    
    # 测试2：同音字替换
    print("\n" + "=" * 80)
    print("测试2：同音字替换 - 重要内容")
    print("=" * 80)
    
    line2 = ScriptLine(
        text="这个[phoneme=仲]重[/phoneme]要的内容",
        voice="zh-CN-YunjianNeural",
        type="narration",
        character="旁白",
        emotion="neutral",
        rate="+0%",
        pitch="+0Hz"
    )
    
    output2 = "data/audio/test_phoneme_homophone.mp3"
    print(f"\n原始文本: {line2.text}")
    print(f"输出文件: {output2}")
    
    try:
        duration2 = await synthesize_single_line(line2, output2)
        file_size = os.path.getsize(output2)
        print(f"✅ 生成成功")
        print(f"   时长: {duration2:.2f} 秒")
        print(f"   大小: {file_size} bytes")
    except Exception as e:
        print(f"❌ 生成失败: {e}")
    
    # 测试3：多个多音字
    print("\n" + "=" * 80)
    print("测试3：多个多音字组合")
    print("=" * 80)
    
    line3 = ScriptLine(
        text="[phoneme=chang2]长[/phoneme][phoneme=zhong4]重[/phoneme]的[phoneme=xing2]行[/phoneme]李",
        voice="zh-CN-YunjianNeural",
        type="narration",
        character="旁白",
        emotion="neutral",
        rate="+0%",
        pitch="+0Hz"
    )
    
    output3 = "data/audio/test_phoneme_multiple.mp3"
    print(f"\n原始文本: {line3.text}")
    print(f"输出文件: {output3}")
    
    try:
        duration3 = await synthesize_single_line(line3, output3)
        file_size = os.path.getsize(output3)
        print(f"✅ 生成成功")
        print(f"   时长: {duration3:.2f} 秒")
        print(f"   大小: {file_size} bytes")
    except Exception as e:
        print(f"❌ 生成失败: {e}")
    
    # 测试4：多音字 + 语速控制
    print("\n" + "=" * 80)
    print("测试4：多音字 + 语速控制")
    print("=" * 80)
    
    line4 = ScriptLine(
        text="[rate=-20%]这个[phoneme=zhong4]重[/phoneme]要[/rate]的内容",
        voice="zh-CN-YunjianNeural",
        type="narration",
        character="旁白",
        emotion="neutral",
        rate="+0%",
        pitch="+0Hz"
    )
    
    output4 = "data/audio/test_phoneme_with_rate.mp3"
    print(f"\n原始文本: {line4.text}")
    print(f"输出文件: {output4}")
    
    try:
        duration4 = await synthesize_single_line(line4, output4)
        file_size = os.path.getsize(output4)
        print(f"✅ 生成成功")
        print(f"   时长: {duration4:.2f} 秒")
        print(f"   大小: {file_size} bytes")
    except Exception as e:
        print(f"❌ 生成失败: {e}")
    
    print("\n" + "=" * 80)
    print("✅ 所有音频生成完成！")
    print("=" * 80)
    
    print("\n📁 生成的音频文件：")
    print(f"  1. {output1}")
    print(f"  2. {output2}")
    print(f"  3. {output3}")
    print(f"  4. {output4}")
    
    print("\n💡 请试听这些音频，验证多音字是否正确读出：")
    print("  - 测试1：'银行行长' 应该读作 'yin2 hang2 zhang3 zhang3'")
    print("  - 测试2：'重要' 应该读作 'zhong4 yao4'（通过同音字'仲'）")
    print("  - 测试3：'长重的行李' 应该读作 'chang2 zhong4 de xing2 li3'")
    print("  - 测试4：'重要' 放慢语速，读作 'zhong4 yao4'")

if __name__ == "__main__":
    asyncio.run(main())

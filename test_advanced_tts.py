"""
测试高级 TTS 引擎 - 自动拆分+拼接
"""
import asyncio
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.models import ScriptLine
from app.tts_advanced import synthesize_advanced_line

async def test_advanced_tts():
    """测试高级 TTS 功能"""
    
    # 测试1：多个语速变化
    print("=" * 60)
    print("测试1：多个语速变化")
    print("=" * 60)
    line1 = ScriptLine(
        type="dialogue",
        character="旁白",
        emotion="normal",
        text="{rate=-50%}这句话很慢{/rate} 然后正常 {rate=+50%}这句话很快{/rate}",
        voice="zh-CN-YunjianNeural",
        rate="+0%",
        pitch="+0Hz"
    )
    
    try:
        duration = await synthesize_advanced_line(line1, "data/audio/test_advanced_1.mp3")
        print(f"✅ 成功，时长: {duration:.2f} 秒\n")
    except Exception as e:
        print(f"❌ 失败: {e}\n")
        import traceback
        traceback.print_exc()
    
    # 测试2：音调变化
    print("=" * 60)
    print("测试2：音调变化")
    print("=" * 60)
    line2 = ScriptLine(
        type="dialogue",
        character="旁白",
        emotion="normal",
        text="{pitch=+20Hz}高音部分{/pitch} 正常 {pitch=-20Hz}低音部分{/pitch}",
        voice="zh-CN-YunjianNeural",
        rate="+0%",
        pitch="+0Hz"
    )
    
    try:
        duration = await synthesize_advanced_line(line2, "data/audio/test_advanced_2.mp3")
        print(f"✅ 成功，时长: {duration:.2f} 秒\n")
    except Exception as e:
        print(f"❌ 失败: {e}\n")
        import traceback
        traceback.print_exc()
    
    # 测试3：复合样式 + 停顿
    print("=" * 60)
    print("测试3：复合样式 + 停顿")
    print("=" * 60)
    line3 = ScriptLine(
        type="dialogue",
        character="旁白",
        emotion="normal",
        text="{style=rate=-40%,pitch=+10Hz}慢速高音{/style}{pause=500}{style=rate=+40%,pitch=-10Hz}快速低音{/style}",
        voice="zh-CN-YunjianNeural",
        rate="+0%",
        pitch="+0Hz"
    )
    
    try:
        duration = await synthesize_advanced_line(line3, "data/audio/test_advanced_3.mp3")
        print(f"✅ 成功，时长: {duration:.2f} 秒\n")
    except Exception as e:
        print(f"❌ 失败: {e}\n")
        import traceback
        traceback.print_exc()
    
    # 测试4：多音字处理（通过拆分控制）
    print("=" * 60)
    print("测试4：多音字处理（通过拆分+同音字替换）")
    print("=" * 60)
    line4 = ScriptLine(
        type="dialogue",
        character="旁白",
        emotion="normal",
        text="这个{rate=+0%}重{/rate}要的事情说三遍",  # "重" 会被读成 zhòng
        voice="zh-CN-YunjianNeural",
        rate="+0%",
        pitch="+0Hz"
    )
    
    try:
        duration = await synthesize_advanced_line(line4, "data/audio/test_advanced_4.mp3")
        print(f"✅ 成功，时长: {duration:.2f} 秒\n")
    except Exception as e:
        print(f"❌ 失败: {e}\n")
        import traceback
        traceback.print_exc()
    
    print("=" * 60)
    print("所有测试完成！")
    print("生成的文件在 data/audio/ 目录下")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(test_advanced_tts())

"""
生成复杂示例 MP3 文件
展示新标记语法的各种组合效果
"""
import asyncio
import sys
sys.path.insert(0, '.')

from app.models import ScriptLine
from app.tts_advanced import synthesize_advanced_line

# 测试配置
VOICE = "zh-CN-YunjianNeural"  # 男声
OUTPUT_DIR = "data/audio/demo"

import os
os.makedirs(OUTPUT_DIR, exist_ok=True)


async def demo_1_phoneme_pause_prosody():
    """Demo 1: phoneme + pause + prosody 组合"""
    print("=" * 60)
    print("Demo 1: 多音字 + 停顿 + 强调组合")
    print("=" * 60)
    
    # 每[phoneme=日]天[/phoneme]<pause=300>坐这趟末班车，<prosody rate="-20%" pitch="+10Hz">今[phoneme=日]天[/phoneme]，</prosody><pause=1000><prosody rate="-20%" pitch="+10Hz">她终于转过头。</prosody>
    text = '每[phoneme=日]天[/phoneme]<pause=300>坐这趟末班车，<prosody rate="-20%" pitch="+10Hz">今[phoneme=日]天[/phoneme]，</prosody><pause=1000><prosody rate="-20%" pitch="+10Hz">她终于转过头。</prosody>'
    
    line = ScriptLine(
        type="dialogue",
        character="旁白",
        emotion="",
        text=text,
        voice=VOICE,
        rate="+0%",
        pitch="+0Hz"
    )
    
    output_path = f"{OUTPUT_DIR}/demo1_phoneme_pause_prosody.mp3"
    print(f"文本: {text}")
    print(f"输出: {output_path}")
    
    try:
        duration = await synthesize_advanced_line(line, line.text, output_path)
        print(f"✅ 成功！时长: {duration:.2f} 秒\n")
        return True
    except Exception as e:
        print(f"❌ 失败: {e}\n")
        return False


async def demo_2_multiple_prosody():
    """Demo 2: 多个 prosody 片段对比"""
    print("=" * 60)
    print("Demo 2: 多个强调片段对比")
    print("=" * 60)
    
    # 普通语速<prosody rate="-30%">慢速强调</prosody>恢复正常<prosody rate="+40%">快速激昂</prosody>结束
    text = '普通语速<prosody rate="-30%" pitch="+0Hz">慢速强调</prosody>恢复正常<prosody rate="+40%" pitch="+0Hz">快速激昂</prosody>结束'
    
    line = ScriptLine(
        type="dialogue",
        character="旁白",
        emotion="",
        text=text,
        voice=VOICE,
        rate="+0%",
        pitch="+0Hz"
    )
    
    output_path = f"{OUTPUT_DIR}/demo2_multiple_prosody.mp3"
    print(f"文本: {text}")
    print(f"输出: {output_path}")
    
    try:
        duration = await synthesize_advanced_line(line, line.text, output_path)
        print(f"✅ 成功！时长: {duration:.2f} 秒\n")
        return True
    except Exception as e:
        print(f"❌ 失败: {e}\n")
        return False


async def demo_3_pitch_variations():
    """Demo 3: 音调变化"""
    print("=" * 60)
    print("Demo 3: 音调变化")
    print("=" * 60)
    
    # 正常音调<prosody pitch="-20Hz">低音沉稳</prosody>恢复<prosody pitch="+30Hz">高音尖锐</prosody>
    text = '正常音调<prosody rate="+0%" pitch="-20Hz">低音沉稳</prosody>恢复<prosody rate="+0%" pitch="+30Hz">高音尖锐</prosody>'
    
    line = ScriptLine(
        type="dialogue",
        character="旁白",
        emotion="",
        text=text,
        voice=VOICE,
        rate="+0%",
        pitch="+0Hz"
    )
    
    output_path = f"{OUTPUT_DIR}/demo3_pitch_variations.mp3"
    print(f"文本: {text}")
    print(f"输出: {output_path}")
    
    try:
        duration = await synthesize_advanced_line(line, line.text, output_path)
        print(f"✅ 成功！时长: {duration:.2f} 秒\n")
        return True
    except Exception as e:
        print(f"❌ 失败: {e}\n")
        return False


async def demo_4_complex_pause():
    """Demo 4: 复杂停顿组合"""
    print("=" * 60)
    print("Demo 4: 复杂停顿组合")
    print("=" * 60)
    
    # 第一句话<pause=500>停顿半秒<prosody rate="-20%">然后慢速说</prosody><pause=800>再停顿<pause=200>快速结束
    text = '第一句话<pause=500>停顿半秒<prosody rate="-20%" pitch="+0Hz">然后慢速说</prosody><pause=800>再停顿<pause=200>快速结束'
    
    line = ScriptLine(
        type="dialogue",
        character="旁白",
        emotion="",
        text=text,
        voice=VOICE,
        rate="+0%",
        pitch="+0Hz"
    )
    
    output_path = f"{OUTPUT_DIR}/demo4_complex_pause.mp3"
    print(f"文本: {text}")
    print(f"输出: {output_path}")
    
    try:
        duration = await synthesize_advanced_line(line, line.text, output_path)
        print(f"✅ 成功！时长: {duration:.2f} 秒\n")
        return True
    except Exception as e:
        print(f"❌ 失败: {e}\n")
        return False


async def demo_5_full_features():
    """Demo 5: 全功能综合展示"""
    print("=" * 60)
    print("Demo 5: 全功能综合展示")
    print("=" * 60)
    
    # 旁白：<prosody rate="-15%" pitch="+5Hz" volume="+10%">长[phoneme=大]大[/phoneme]后</prosody><pause=400>我[phoneme=行]行[/phoneme]走在人海中，<prosody rate="-25%" pitch="+15Hz">每[phoneme=日]天[/phoneme]都</prosody><pause=600><prosody rate="+30%">匆匆忙忙</prosody>
    text = '<prosody rate="-15%" pitch="+5Hz" volume="+10%">长[phoneme=大]大[/phoneme]后</prosody><pause=400>我[phoneme=行]行[/phoneme]走在人海中，<prosody rate="-25%" pitch="+15Hz">每[phoneme=日]天[/phoneme]都</prosody><pause=600><prosody rate="+30%" pitch="+0Hz">匆匆忙忙</prosody>'
    
    line = ScriptLine(
        type="dialogue",
        character="旁白",
        emotion="",
        text=text,
        voice=VOICE,
        rate="+0%",
        pitch="+0Hz"
    )
    
    output_path = f"{OUTPUT_DIR}/demo5_full_features.mp3"
    print(f"文本: {text}")
    print(f"输出: {output_path}")
    
    try:
        duration = await synthesize_advanced_line(line, line.text, output_path)
        print(f"✅ 成功！时长: {duration:.2f} 秒\n")
        return True
    except Exception as e:
        print(f"❌ 失败: {e}\n")
        return False


async def demo_6_emphasis_levels():
    """Demo 6: 不同强调程度对比"""
    print("=" * 60)
    print("Demo 6: 不同强调程度对比")
    print("=" * 60)
    
    # 普通<prosody rate="-20%" pitch="+10Hz" volume="1.2">强烈强调</prosody>普通<prosody rate="-10%" pitch="+5Hz" volume="1.1">中等强调</prosody>普通<prosody rate="+10%" pitch="-5Hz" volume="0.9">减弱强调</prosody>
    text = '普通<prosody rate="-20%" pitch="+10Hz" volume="1.2">强烈强调</prosody>普通<prosody rate="-10%" pitch="+5Hz" volume="1.1">中等强调</prosody>普通<prosody rate="+10%" pitch="-5Hz" volume="0.9">减弱强调</prosody>'
    
    line = ScriptLine(
        type="dialogue",
        character="旁白",
        emotion="",
        text=text,
        voice=VOICE,
        rate="+0%",
        pitch="+0Hz"
    )
    
    output_path = f"{OUTPUT_DIR}/demo6_emphasis_levels.mp3"
    print(f"文本: {text}")
    print(f"输出: {output_path}")
    
    try:
        duration = await synthesize_advanced_line(line, line.text, output_path)
        print(f"✅ 成功！时长: {duration:.2f} 秒\n")
        return True
    except Exception as e:
        print(f"❌ 失败: {e}\n")
        return False


async def main():
    """运行所有 demo"""
    print("\n" + "=" * 60)
    print("开始生成复杂示例 MP3 文件")
    print("=" * 60 + "\n")
    
    results = []
    
    results.append(await demo_1_phoneme_pause_prosody())
    results.append(await demo_2_multiple_prosody())
    results.append(await demo_3_pitch_variations())
    results.append(await demo_4_complex_pause())
    results.append(await demo_5_full_features())
    results.append(await demo_6_emphasis_levels())
    
    print("=" * 60)
    print(f"生成完成！成功: {sum(results)}/{len(results)}")
    print("=" * 60)
    print(f"\n文件位置: {OUTPUT_DIR}/")
    print("\n生成的文件:")
    for i, success in enumerate(results, 1):
        status = "✅" if success else "❌"
        print(f"  {status} demo{i}_*.mp3")


if __name__ == "__main__":
    asyncio.run(main())

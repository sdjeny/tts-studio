"""
终极验收测试：多音字 + 复杂语气变化（一波三折）

测试场景：一段富有情感变化的长句，包含多个多音字和多种语气
"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from app.models import ScriptLine
from app.tts_engine import synthesize_single_line

async def main():
    print("=" * 80)
    print("🎭 终极验收测试：多音字 + 复杂语气变化")
    print("=" * 80)
    
    # 设计一个有情节的长句，包含：
    # 1. 多个多音字（行、长、重、乐、着、好）
    # 2. 至少5种语气变化（慢速强调、快速叙述、停顿、高音惊讶、低音沉思）
    
    test_text = (
        "[rate=-30%]那[phoneme=航]行[/phoneme][phoneme=掌]长[/phoneme][/rate]"  # 慢速强调：银行行长
        "[pause=300]"  # 停顿1：制造悬念
        "[pitch=+15Hz]竟然[phoneme=仲]重[/phoneme]新[/pitch]"  # 高音惊讶：重新
        "[rate=+20%]走进了那家[phoneme=月]乐[/phoneme]器店[/rate]"  # 快速叙述：乐器店
        "[pause=200]"  # 停顿2：转折
        "[pitch=-10Hz]看着那些[phoneme=郝]好[/phoneme]玩的乐器[/pitch]"  # 低音沉思：好玩
        "[rate=-10%]他[phoneme=这]着[/phoneme]迷了[/rate]"  # 慢速：着迷
        "[pause=400]"  # 停顿3：高潮前
        "[pitch=+20Hz]突然！[/pitch]"  # 高音惊叹
        "[rate=+30%]他发现了一个[phoneme=常]长[/phoneme][phoneme=虫]重[/phoneme]的箱子[/rate]"  # 快速兴奋：长长重重
        "[pause=500]"  # 停顿4：最大悬念
        "[rate=-40%][pitch=-15Hz]里面...到底是什么呢？[/pitch][/rate]"  # 极慢极低：神秘结尾
    )
    
    print("\n📝 测试文本（带标记）：")
    print(test_text)
    
    print("\n🎯 测试要点：")
    print("  多音字（8个）：")
    print("    1. 行(hang2) → 航 - 银行")
    print("    2. 长(zhang3) → 掌 - 行长")
    print("    3. 重(zhong4) → 仲 - 重新")
    print("    4. 乐(yue4) → 月 - 乐器")
    print("    5. 好(hao3) → 郝 - 好玩")
    print("    6. 着(zhe5) → 这 - 着迷")
    print("    7. 长(chang2) → 常 - 长长")
    print("    8. 重(chong2) → 虫 - 重重")
    print()
    print("  语气变化（至少9处）：")
    print("    1. rate=-30%     - 慢速强调（银行行长）")
    print("    2. pause=300ms   - 停顿1（悬念）")
    print("    3. pitch=+15Hz   - 高音惊讶（竟然重新）")
    print("    4. rate=+20%     - 快速叙述（走进乐器店）")
    print("    5. pause=200ms   - 停顿2（转折）")
    print("    6. pitch=-10Hz   - 低音沉思（看着好玩的）")
    print("    7. rate=-10%     - 慢速（着迷了）")
    print("    8. pause=400ms   - 停顿3（高潮前）")
    print("    9. pitch=+20Hz   - 高音惊叹（突然！）")
    print("    10. rate=+30%    - 快速兴奋（长长重重的箱子）")
    print("    11. pause=500ms  - 停顿4（最大悬念）")
    print("    12. rate=-40%,pitch=-15Hz - 极慢极低（神秘结尾）")
    print()
    print("  预期效果：")
    print("    ✓ 多音字读音正确")
    print("    ✓ 语气起伏明显（一波三折）")
    print("    ✓ 停顿自然，节奏感强")
    print("    ✓ 整体时长约 15-20 秒")
    
    print("\n" + "=" * 80)
    print("🎙️  开始合成...")
    print("=" * 80)
    
    line = ScriptLine(
        text=test_text,
        voice="zh-CN-YunjianNeural",
        type="narration",
        character="旁白",
        emotion="dramatic",
        rate="+0%",
        pitch="+0Hz"
    )
    
    output_path = "data/audio/test_ultimate_acceptance.mp3"
    print(f"\n输出文件: {output_path}\n")
    
    try:
        duration = await synthesize_single_line(line, output_path)
        file_size = os.path.getsize(output_path)
        
        print("\n" + "=" * 80)
        print("✅ 合成成功！")
        print("=" * 80)
        print(f"📊 结果统计：")
        print(f"   时长: {duration:.2f} 秒")
        print(f"   大小: {file_size:,} bytes ({file_size/1024:.1f} KB)")
        print(f"   文件: {output_path}")
        print()
        
        # 验证
        if duration < 10:
            print("⚠️  警告：时长过短，可能语气变化不够明显")
        elif duration > 25:
            print("⚠️  警告：时长过长，可能停顿太多")
        else:
            print("✅ 时长合理，语气变化应该很明显")
        
        print("\n" + "=" * 80)
        print("🎧 验收要点：")
        print("=" * 80)
        print("请试听音频，验证以下内容：")
        print()
        print("1️⃣  多音字读音是否正确：")
        print("   □ 银行 → yin2 hang2（而非 xing2）")
        print("   □ 行长 → hang2 zhang3（而非 xing2 chang2）")
        print("   □ 重新 → zhong4 xin1（而非 chong2 xin1）")
        print("   □ 乐器 → yue4 qi4（而非 le4 qi4）")
        print("   □ 好玩 → hao3 wan2（而非 hao4 wan2）")
        print("   □ 着迷 → zhe5 mi2（而非 zhao2 mi2）")
        print("   □ 长长 → chang2 chang2（而非 zhang3 zhang3）")
        print("   □ 重重 → chong2 chong2（而非 zhong4 zhong4）")
        print()
        print("2️⃣  语气变化是否明显（至少5处）：")
        print("   □ 开头慢速强调（银行行长）")
        print("   □ 中间高音惊讶（竟然重新）")
        print("   □ 快速叙述（走进乐器店）")
        print("   □ 低音沉思（看着好玩的）")
        print("   □ 高音惊叹（突然！）")
        print("   □ 快速兴奋（长长重重的箱子）")
        print("   □ 结尾极慢极低（神秘感）")
        print()
        print("3️⃣  停顿是否自然：")
        print("   □ 4次停顿位置恰当")
        print("   □ 停顿时长合理（200-500ms）")
        print("   □ 制造了悬念和节奏感")
        print()
        print("4️⃣  整体效果：")
        print("   □ 一波三折，富有戏剧性")
        print("   □ 语调连贯，无突兀跳跃")
        print("   □ 情感表达清晰")
        print()
        print("=" * 80)
        print("🎉 如果以上所有要点都通过，则验收成功！")
        print("=" * 80)
        
    except Exception as e:
        print(f"\n❌ 合成失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())

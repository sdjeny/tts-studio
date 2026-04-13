"""
测试多音字处理策略
"""
import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.dirname(__file__))

from app.tts_parser import parse_marked_text

print("=" * 80)
print("测试多音字处理策略")
print("=" * 80)

# 测试1：拼音策略（直接读拼音）
print("\n" + "=" * 80)
print("测试1：拼音策略 - [phoneme=zhong4]重[/phoneme]")
print("=" * 80)

text1 = "这个[phoneme=zhong4]重[/phoneme]要"
segments1 = parse_marked_text(text1)

print(f"\n原始文本: {text1}")
print(f"解析出 {len(segments1)} 个片段:")
for i, seg in enumerate(segments1):
    print(f"  [{i}] text='{seg.text}', type={seg.segment_type}")

print("\n💡 说明：'重' 将被读作拼音 'zhong4'")

# 测试2：同音字替换策略
print("\n" + "=" * 80)
print("测试2：同音字替换 - [phoneme=仲]重[/phoneme]")
print("=" * 80)

text2 = "这个[phoneme=仲]重[/phoneme]要"
segments2 = parse_marked_text(text2)

print(f"\n原始文本: {text2}")
print(f"解析出 {len(segments2)} 个片段:")
for i, seg in enumerate(segments2):
    print(f"  [{i}] text='{seg.text}', type={seg.segment_type}")

print("\n💡 说明：'重' 将被替换为同音字 '仲'（只读 zhong4）")

# 测试3：多个多音字
print("\n" + "=" * 80)
print("测试3：多个多音字组合")
print("=" * 80)

text3 = "[phoneme=chang2]长[/phoneme][phoneme=zhong4]重[/phoneme]的[phoneme=xing2]行[/phoneme]李"
segments3 = parse_marked_text(text3)

print(f"\n原始文本: {text3}")
print(f"解析出 {len(segments3)} 个片段:")
for i, seg in enumerate(segments3):
    print(f"  [{i}] text='{seg.text}', type={seg.segment_type}")

print("\n💡 说明：")
print("   - '长' → 'chang2' (拼音)")
print("   - '重' → 'zhong4' (拼音)")
print("   - '行' → 'xing2' (拼音)")

# 测试4：混合策略
print("\n" + "=" * 80)
print("测试4：混合策略（拼音 + 同音字）")
print("=" * 80)

text4 = "[phoneme=le5]了[/phoneme]解[phoneme=解]解[/phoneme]决方案"
segments4 = parse_marked_text(text4)

print(f"\n原始文本: {text4}")
print(f"解析出 {len(segments4)} 个片段:")
for i, seg in enumerate(segments4):
    print(f"  [{i}] text='{seg.text}', type={seg.segment_type}")

print("\n💡 说明：")
print("   - '了' → 'le5' (拼音，避免读 liao3)")
print("   - '解' → '解' (同音字替换，保持原字)")

# 测试5：实际应用场景
print("\n" + "=" * 80)
print("测试5：实际应用场景 - 银行行长")
print("=" * 80)

text5 = "银[phoneme=hang2]行[/phoneme][phoneme=zhang3]行[/phoneme]长"
segments5 = parse_marked_text(text5)

print(f"\n原始文本: {text5}")
print(f"解析出 {len(segments5)} 个片段:")
for i, seg in enumerate(segments5):
    print(f"  [{i}] text='{seg.text}', type={seg.segment_type}")

print("\n💡 说明：")
print("   - 第一个'行' → 'hang2' (银行)")
print("   - 第二个'行' → 'zhang3' (行长)")
print("   - 避免读成 'yin2 xing2 hang2 zhang3'")

# 测试6：与语速/音调结合
print("\n" + "=" * 80)
print("测试6：多音字 + 语速控制")
print("=" * 80)

text6 = "[rate=-20%]这个[phoneme=zhong4]重[/phoneme]要[/rate]的内容"
segments6 = parse_marked_text(text6)

print(f"\n原始文本: {text6}")
print(f"解析出 {len(segments6)} 个片段:")
for i, seg in enumerate(segments6):
    print(f"  [{i}] rate={seg.rate}, text='{seg.text}', type={seg.segment_type}")

print("\n💡 说明：多音字标记可以与其他标记嵌套使用")

print("\n" + "=" * 80)
print("✅ 所有多音字测试完成！")
print("=" * 80)

print("\n📊 策略总结：")
print("\n1️⃣  拼音策略：[phoneme=zhong4]重[/phoneme]")
print("   - 直接将汉字替换为拼音")
print("   - 适用于 edge-tts 能正确读出拼音的情况")
print("   - 格式：字母 + 数字声调（如 zhong4, chang2, le5）")
print()
print("2️⃣  同音字替换：[phoneme=仲]重[/phoneme]")
print("   - 用常见读音的同音字替换")
print("   - 适用于拼音读取效果不好的情况")
print("   - 格式：单个汉字")
print()
print("💡 建议：")
print("   - 优先使用拼音策略（更精确）")
print("   - 如果拼音效果不好，尝试同音字替换")
print("   - 可以结合语速/音调标记使用")
print("   - 常见多音字示例：")
print("     * 重：zhong4 (重要) / chong2 (重复)")
print("     * 长：chang2 (长短) / zhang3 (生长)")
print("     * 行：hang2 (银行) / xing2 (行走)")
print("     * 了：le5 (好了) / liao3 (了解)")
print("     * 着：zhe5 (看着) / zhao2 (着急)")

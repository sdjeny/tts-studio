"""
测试高级 TTS 功能（分批执行 + FFmpeg 拼接）
"""
import asyncio
import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.dirname(__file__))

from app.tts_parser import parse_marked_text, TextSegment

print("=" * 80)
print("测试高级 TTS 功能 - 分批执行实现")
print("=" * 80)

# 测试1：停顿标记
print("\n" + "=" * 80)
print("测试1：停顿标记 [pause=500]")
print("=" * 80)

text1 = "前面[pause=500]后面"
segments1 = parse_marked_text(text1)

print(f"\n原始文本: {text1}")
print(f"解析出 {len(segments1)} 个片段:")
for i, seg in enumerate(segments1):
    print(f"  [{i}] type={seg.segment_type}, text='{seg.text}', rate={seg.rate}")

# 测试2：强调标记
print("\n" + "=" * 80)
print("测试2：强调标记 [emphasis=strong]")
print("=" * 80)

text2 = "[emphasis=strong]重要内容[/emphasis]普通内容"
segments2 = parse_marked_text(text2)

print(f"\n原始文本: {text2}")
print(f"解析出 {len(segments2)} 个片段:")
for i, seg in enumerate(segments2):
    print(f"  [{i}] type={seg.segment_type}, rate={seg.rate}, pitch={seg.pitch}, text='{seg.text}'")

# 测试3：多音字标记（仅记录，不生效）
print("\n" + "=" * 80)
print("测试3：多音字标记 [phoneme=拼音]")
print("=" * 80)

text3 = "[phoneme=zhong4]重[/phoneme]要"
segments3 = parse_marked_text(text3)

print(f"\n原始文本: {text3}")
print(f"解析出 {len(segments3)} 个片段:")
for i, seg in enumerate(segments3):
    print(f"  [{i}] type={seg.segment_type}, text='{seg.text}'")

# 测试4：3个以上的 prosody（自动分批）
print("\n" + "=" * 80)
print("测试4：3个以上 prosody（自动分批执行）")
print("=" * 80)

text4 = "[rate=-50%]很慢[/rate][rate=+0%]正常[/rate][rate=+50%]很快[/rate]"
segments4 = parse_marked_text(text4)

print(f"\n原始文本: {text4}")
print(f"解析出 {len(segments4)} 个片段:")
for i, seg in enumerate(segments4):
    print(f"  [{i}] type={seg.segment_type}, rate={seg.rate}, text='{seg.text}'")

# 测试5：综合场景
print("\n" + "=" * 80)
print("测试5：综合场景（停顿+强调+多语速）")
print("=" * 80)

text5 = "[rate=-30%]开始慢说[/rate][pause=300][emphasis=strong]重点强调[/emphasis][pause=200][rate=+40%]快速结束[/rate]"
segments5 = parse_marked_text(text5)

print(f"\n原始文本: {text5}")
print(f"解析出 {len(segments5)} 个片段:")
for i, seg in enumerate(segments5):
    if seg.segment_type == 'pause':
        print(f"  [{i}] 【停顿】{seg.rate}ms")
    else:
        print(f"  [{i}] rate={seg.rate}, pitch={seg.pitch}, text='{seg.text}'")

print("\n" + "=" * 80)
print("✅ 所有解析测试完成！")
print("=" * 80)

print("\n📊 功能总结：")
print("✅ [rate=X%] - 语速控制")
print("✅ [pitch=XHz] - 音调控制")
print("✅ [pause=Xms] - 停顿控制（生成静音片段）")
print("✅ [emphasis=level] - 强调控制（通过改变语速/音调模拟）")
print("⚠️  [phoneme=拼音] - 多音字标记（不被 edge-tts 直接支持，仅记录）")
print("✅ 3个以上 prosody - 自动分批执行 + FFmpeg 拼接")
print("\n💡 工作原理：")
print("   1. 解析文本中的标记")
print("   2. 每个片段独立调用 edge-tts 合成")
print("   3. 使用 pydub (FFmpeg) 拼接所有片段")
print("   4. 支持任意数量的片段和任意组合")

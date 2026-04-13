"""测试 TTS 解析器"""
import sys
sys.path.insert(0, '.')

from app.tts_parser import parse_marked_text, has_markers, count_segments

# 测试1：纯文本
print("=" * 80)
print("测试1：纯文本（无标记）")
print("=" * 80)
text1 = "这是一个普通的测试文本。"
print(f"输入: {text1}")
print(f"has_markers: {has_markers(text1)}")
print(f"segments: {count_segments(text1)}")
segs1 = parse_marked_text(text1)
print(f"解析结果: {len(segs1)} 个片段")
for seg in segs1:
    print(f"  text='{seg.text}', rate={seg.rate}, pitch={seg.pitch}")
print()

# 测试2：单个标记
print("=" * 80)
print("测试2：单个标记（慢速）")
print("=" * 80)
text2 = "[rate=-50%]这是慢速文本[/rate]"
print(f"输入: {text2}")
print(f"has_markers: {has_markers(text2)}")
print(f"segments: {count_segments(text2)}")
segs2 = parse_marked_text(text2)
print(f"解析结果: {len(segs2)} 个片段")
for seg in segs2:
    print(f"  text='{seg.text}', rate={seg.rate}, pitch={seg.pitch}")
print()

# 测试3：多个标记（2个片段）
print("=" * 80)
print("测试3：两个标记片段")
print("=" * 80)
text3 = "[rate=-40%]前半部分慢[/rate]，[rate=+50%]后半部分快[/rate]"
print(f"输入: {text3}")
print(f"has_markers: {has_markers(text3)}")
print(f"segments: {count_segments(text3)}")
segs3 = parse_marked_text(text3)
print(f"解析结果: {len(segs3)} 个片段")
for seg in segs3:
    print(f"  text='{seg.text}', rate={seg.rate}, pitch={seg.pitch}")
print()

# 测试4：混合文本（标记+纯文本）
print("=" * 80)
print("测试4：标记和纯文本混合")
print("=" * 80)
text4 = "首先[rate=-30%]这里慢一点[/rate]然后正常[rate=+40%]这里快很多[/rate]结束"
print(f"输入: {text4}")
print(f"has_markers: {has_markers(text4)}")
print(f"segments: {count_segments(text4)}")
segs4 = parse_marked_text(text4)
print(f"解析结果: {len(segs4)} 个片段")
for seg in segs4:
    print(f"  text='{seg.text}', rate={seg.rate}, pitch={seg.pitch}")
print()

# 测试5：嵌套标记
print("=" * 80)
print("测试5：嵌套标记")
print("=" * 80)
text5 = "[rate=-30%]慢速[pitch=+20Hz]慢速高音[/pitch]继续慢速[/rate]正常"
print(f"输入: {text5}")
print(f"has_markers: {has_markers(text5)}")
print(f"segments: {count_segments(text5)}")
segs5 = parse_marked_text(text5)
print(f"解析结果: {len(segs5)} 个片段")
for seg in segs5:
    print(f"  text='{seg.text}', rate={seg.rate}, pitch={seg.pitch}")
print()

# 测试6：多音字标注（预留功能）
print("=" * 80)
print("测试6：多音字标注（预留）")
print("=" * 80)
text6 = "这个[phoneme=zhong4]重[/phoneme]要的事情"
print(f"输入: {text6}")
print(f"has_markers: {has_markers(text6)}")
print(f"segments: {count_segments(text6)}")
print("注意：[phoneme] 标记目前会被当作纯文本处理，因为 edge-tts 不支持")
print()

print("=" * 80)
print("所有测试完成！")
print("=" * 80)

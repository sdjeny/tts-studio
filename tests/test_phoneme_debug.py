"""
调试 phoneme 标记解析
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from app.tts_parser import parse_marked_text

print("=" * 80)
print("调试 phoneme 标记解析")
print("=" * 80)

# 测试用例
text = "[phoneme=chang2]长[/phoneme]短"

print(f"\n原始文本: {text}")
print("\n解析过程:")

segments = parse_marked_text(text)

print(f"\n解析结果: {len(segments)} 个片段")
for i, seg in enumerate(segments):
    print(f"  [{i}] text='{seg.text}', type={seg.segment_type}, marked={seg.is_marked}")

print("\n" + "=" * 80)
print("预期结果:")
print("  [0] text='chang2', type=text, marked=True")
print("  [1] text='短', type=text, marked=False")
print("=" * 80)

"""
验证 phoneme 标记不被读出
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from app.tts_parser import parse_marked_text

print("=" * 80)
print("验证 phoneme 标记解析结果")
print("=" * 80)

# 测试文本
text = "[phoneme=chang2]长[/phoneme]短"

print(f"\n原始文本: {text}")
print("\n解析结果:")

segments = parse_marked_text(text)

print(f"\n共 {len(segments)} 个片段:")
for i, seg in enumerate(segments):
    print(f"  [{i}] '{seg.text}' (marked={seg.is_marked})")

print("\n" + "=" * 80)
print("✅ 验证结果:")
if segments[0].text == 'chang2':
    print("  ✓ 第一个片段是 'chang2'（拼音），不是 '[phoneme=chang2]长[/phoneme]'")
    print("  ✓ 标记已被正确移除，不会被读出")
else:
    print(f"  ✗ 第一个片段是 '{segments[0].text}'，可能包含标记")
print("=" * 80)

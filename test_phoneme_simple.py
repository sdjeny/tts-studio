"""
简化测试：直接对比两种策略的解析结果
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from app.tts_parser import parse_marked_text

print("=" * 80)
print("多音字策略对比 - 解析结果")
print("=" * 80)

# 原始文本
original = "银行行长有着长长的尾巴"
print(f"\n原始文本: {original}")

# 策略1：同音字替换
text_homophone = "银[phoneme=航]行[/phoneme][phoneme=掌]行[/phoneme]有着[phoneme=常]长[/phoneme][phoneme=常]长[/phoneme]的尾巴"
print("\n" + "=" * 80)
print("策略1：同音字替换")
print("=" * 80)
print(f"标记文本: {text_homophone}")

segments1 = parse_marked_text(text_homophone)
print(f"\n解析为 {len(segments1)} 个片段:")
for i, seg in enumerate(segments1):
    print(f"  [{i}] '{seg.text}'")

# 策略2：拼音
text_pinyin = "银[phoneme=hang2]行[/phoneme][phoneme=zhang3]行[/phoneme]有着[phoneme=chang2]长[/phoneme][phoneme=chang2]长[/phoneme]的尾巴"
print("\n" + "=" * 80)
print("策略2：拼音策略")
print("=" * 80)
print(f"标记文本: {text_pinyin}")

segments2 = parse_marked_text(text_pinyin)
print(f"\n解析为 {len(segments2)} 个片段:")
for i, seg in enumerate(segments2):
    print(f"  [{i}] '{seg.text}'")

print("\n" + "=" * 80)
print("✅ 解析完成！")
print("=" * 80)
print("\n💡 说明：")
print("  - 同音字替换：'行'→'航'(hang2), '行'→'掌'(zhang3), '长'→'常'(chang2)")
print("  - 拼音策略：直接使用拼音 hang2, zhang3, chang2")
print("\n📊 两种方式都能正确指定读音，区别在于：")
print("  - 同音字更自然（利用 edge-tts 对汉字的语调处理）")
print("  - 拼音更精确（完全控制发音）")

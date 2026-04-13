"""测试 TTS 解析器 - 新语法测试

新标记语法：
- <prosody rate="X" pitch="Y" volume="Z">文本</prosody>
- <pause=X>
- [phoneme=同音字]原字[/phoneme]
"""
import sys
sys.path.insert(0, '.')

from app.tts_parser import (
    parse_prosody_text, parse_marked_text, has_markers, 
    count_segments, needs_splitting, preprocess_phoneme_markers,
    TextSegment
)

def test_pure_text():
    """测试1：纯文本（无标记）"""
    print("=" * 80)
    print("测试1：纯文本（无标记）")
    print("=" * 80)
    text = "这是一个普通的测试文本。"
    print(f"输入: {text}")
    print(f"has_markers: {has_markers(text)}")
    print(f"needs_splitting: {needs_splitting(text)}")
    
    segments = parse_prosody_text(text)
    print(f"解析结果: {len(segments)} 个片段")
    
    assert len(segments) == 1
    assert segments[0].text == "这是一个普通的测试文本。"
    assert segments[0].rate == "+0%"
    assert segments[0].pitch == "+0Hz"
    assert segments[0].volume == "+0%"
    assert segments[0].is_marked == False
    assert segments[0].segment_type == "text"
    
    for seg in segments:
        print(f"  text='{seg.text}', rate={seg.rate}, pitch={seg.pitch}, volume={seg.volume}, marked={seg.is_marked}")
    print("✓ 通过\n")


def test_single_prosody():
    """测试2：单个 prosody 标签"""
    print("=" * 80)
    print("测试2：单个 prosody 标签")
    print("=" * 80)
    text = '<prosody rate="-20%" pitch="+10Hz" volume="1.2">这是强调文本</prosody>'
    print(f"输入: {text}")
    print(f"has_markers: {has_markers(text)}")
    
    segments = parse_prosody_text(text)
    print(f"解析结果: {len(segments)} 个片段")
    
    assert len(segments) == 1
    assert segments[0].text == "这是强调文本"
    assert segments[0].rate == "-20%"
    assert segments[0].pitch == "+10Hz"
    assert segments[0].volume == "1.2"
    assert segments[0].is_marked == True
    
    for seg in segments:
        print(f"  text='{seg.text}', rate={seg.rate}, pitch={seg.pitch}, volume={seg.volume}, marked={seg.is_marked}")
    print("✓ 通过\n")


def test_prosody_with_phoneme():
    """测试3：prosody 内部包含 phoneme"""
    print("=" * 80)
    print("测试3：prosody 内部包含 phoneme")
    print("=" * 80)
    text = '<prosody rate="-20%" pitch="+10Hz">今[phoneme=日]天[/phoneme]，她终于转过头。</prosody>'
    print(f"输入: {text}")
    
    segments = parse_prosody_text(text)
    print(f"解析结果: {len(segments)} 个片段")
    
    assert len(segments) == 1
    # [phoneme=日]天[/phoneme] 会被替换为 "日"
    assert segments[0].text == "今日，她终于转过头。"
    assert segments[0].rate == "-20%"
    assert segments[0].is_marked == True
    
    for seg in segments:
        print(f"  text='{seg.text}', rate={seg.rate}, pitch={seg.pitch}")
    print("✓ 通过\n")


def test_pause_marker():
    """测试4：pause 停顿标记"""
    print("=" * 80)
    print("测试4：pause 停顿标记")
    print("=" * 80)
    text = "前半部分<pause=1000>后半部分"
    print(f"输入: {text}")
    
    segments = parse_prosody_text(text)
    print(f"解析结果: {len(segments)} 个片段")
    
    assert len(segments) == 3
    assert segments[0].text == "前半部分"
    assert segments[0].segment_type == "text"
    assert segments[1].text == "__PAUSE_1000__"
    assert segments[1].segment_type == "pause"
    assert segments[1].rate == "1000"  # 停顿时长
    assert segments[2].text == "后半部分"
    
    for i, seg in enumerate(segments):
        print(f"  [{i}] type={seg.segment_type}, text='{seg.text}', rate={seg.rate}")
    print("✓ 通过\n")


def test_mixed_prosody_and_pause():
    """测试5：prosody 和 pause 混合"""
    print("=" * 80)
    print("测试5：prosody 和 pause 混合")
    print("=" * 80)
    text = '<prosody rate="-20%" pitch="+10Hz">今晚</prosody><pause=500><prosody rate="-20%" pitch="+10Hz">她终于转过头。</prosody>'
    print(f"输入: {text}")
    
    segments = parse_prosody_text(text)
    print(f"解析结果: {len(segments)} 个片段")
    
    assert len(segments) == 3
    assert segments[0].text == "今晚"
    assert segments[0].is_marked == True
    assert segments[1].segment_type == "pause"
    assert segments[1].rate == "500"
    assert segments[2].text == "她终于转过头。"
    assert segments[2].is_marked == True
    
    for i, seg in enumerate(segments):
        print(f"  [{i}] type={seg.segment_type}, text='{seg.text[:20]}', rate={seg.rate}")
    print("✓ 通过\n")


def test_plain_text_between_prosody():
    """测试6：prosody 标签之间的纯文本"""
    print("=" * 80)
    print("测试6：prosody 标签之间的纯文本")
    print("=" * 80)
    text = '<prosody rate="-20%">慢速部分</prosody>普通文本<prosody rate="+50%">快速部分</prosody>'
    print(f"输入: {text}")
    
    segments = parse_prosody_text(text)
    print(f"解析结果: {len(segments)} 个片段")
    
    assert len(segments) == 3
    assert segments[0].text == "慢速部分"
    assert segments[0].rate == "-20%"
    assert segments[0].is_marked == True
    assert segments[1].text == "普通文本"
    assert segments[1].rate == "+0%"
    assert segments[1].is_marked == False
    assert segments[2].text == "快速部分"
    assert segments[2].rate == "+50%"
    assert segments[2].is_marked == True
    
    for i, seg in enumerate(segments):
        print(f"  [{i}] marked={seg.is_marked}, text='{seg.text}', rate={seg.rate}")
    print("✓ 通过\n")


def test_phoneme_only():
    """测试7：只有 phoneme 标记（无 prosody）"""
    print("=" * 80)
    print("测试7：只有 phoneme 标记（无 prosody）")
    print("=" * 80)
    text = "每[phoneme=日]天[/phoneme]坐这趟末班车"
    print(f"输入: {text}")
    
    segments = parse_prosody_text(text)
    print(f"解析结果: {len(segments)} 个片段")
    
    assert len(segments) == 1
    # [phoneme=日]天[/phoneme] 会被替换为 "日"
    assert segments[0].text == "每日坐这趟末班车"
    assert segments[0].is_marked == False  # phoneme 不算 marked
    
    for seg in segments:
        print(f"  text='{seg.text}', marked={seg.is_marked}")
    print("✓ 通过\n")


def test_multiple_phoneme():
    """测试8：多个 phoneme 标记"""
    print("=" * 80)
    print("测试8：多个 phoneme 标记")
    print("=" * 80)
    text = "[phoneme=长]长[/phoneme]大后，[phoneme=行]行[/phoneme]走在人海中"
    print(f"输入: {text}")
    
    segments = parse_prosody_text(text)
    print(f"解析结果: {len(segments)} 个片段")
    
    assert len(segments) == 1
    # [phoneme=长]长[/phoneme] -> 长 (替换后: 长 + 大后...)
    # [phoneme=行]行[/phoneme] -> 行 (替换后: 行 + 走...)
    assert segments[0].text == "长大后，行走在人海中"
    
    for seg in segments:
        print(f"  text='{seg.text}'")
    print("✓ 通过\n")


def test_complex_real_world():
    """测试9：复杂真实场景"""
    print("=" * 80)
    print("测试9：复杂真实场景")
    print("=" * 80)
    text = '每[phoneme=日]天[/phoneme]<pause=300>坐这趟末班车，<prosody rate="-20%" pitch="+10Hz">今[phoneme=日]天[/phoneme]，</prosody><pause=1000><prosody rate="-20%" pitch="+10Hz">她终于转过头。</prosody>'
    print(f"输入: {text[:80]}...")
    
    segments = parse_prosody_text(text)
    print(f"解析结果: {len(segments)} 个片段")
    
    # 实际解析为6个片段：
    # 1. "每日" (纯文本, phoneme已替换)
    # 2. pause 300
    # 3. "坐这趟末班车，" (纯文本，在pause和prosody之间)
    # 4. "今日，" (prosody, phoneme已替换)
    # 5. pause 1000
    # 6. "她终于转过头。" (prosody)
    assert len(segments) == 6
    # 片段1: 纯文本（phoneme 已替换: [phoneme=日]天[/phoneme] -> 日）
    assert segments[0].text == "每日"
    assert segments[0].is_marked == False
    # 片段2: pause
    assert segments[1].segment_type == "pause"
    assert segments[1].rate == "300"
    # 片段3: 纯文本（pause和prosody之间的文本）
    assert segments[2].text == "坐这趟末班车，"
    assert segments[2].is_marked == False
    # 片段4: prosody + phoneme (今[phoneme=日]天[/phoneme] -> 今日)
    assert segments[3].text == "今日，"
    assert segments[3].is_marked == True
    assert segments[3].rate == "-20%"
    # 片段5: pause
    assert segments[4].segment_type == "pause"
    assert segments[4].rate == "1000"
    # 片段6: prosody
    assert segments[5].text == "她终于转过头。"
    assert segments[5].is_marked == True
    
    for i, seg in enumerate(segments):
        print(f"  [{i}] type={seg.segment_type}, marked={seg.is_marked}, text='{seg.text[:20]}', rate={seg.rate}")
    print("✓ 通过\n")


def test_empty_and_whitespace():
    """测试10：空文本和空白文本"""
    print("=" * 80)
    print("测试10：空文本和空白文本")
    print("=" * 80)
    
    # 空文本
    segments = parse_prosody_text("")
    assert len(segments) == 0
    print("空文本: ✓")
    
    # 空白文本
    segments = parse_prosody_text("   \n\t  ")
    assert len(segments) == 0
    print("空白文本: ✓")
    print("✓ 通过\n")


def test_phoneme_preprocessor():
    """测试11：phoneme 预处理器单独测试"""
    print("=" * 80)
    print("测试11：phoneme 预处理器")
    print("=" * 80)
    
    # 基本替换: [phoneme=日]天[/phoneme] -> 用"日"替换"天"
    result = preprocess_phoneme_markers("[phoneme=日]天[/phoneme]")
    assert result == "日", f"期望 '日', 实际 '{result}'"
    print(f"基本替换: '{result}' ✓")
    
    # 多个替换
    result = preprocess_phoneme_markers("[phoneme=长]长[/phoneme][phoneme=大]大[/phoneme]")
    assert result == "长大", f"期望 '长大', 实际 '{result}'"
    print(f"多个替换: '{result}' ✓")
    
    # 无标记
    result = preprocess_phoneme_markers("普通文本")
    assert result == "普通文本"
    print(f"无标记: '{result}' ✓")
    
    # 混合文本: 每[phoneme=日]天[/phoneme]都 -> 每日都
    result = preprocess_phoneme_markers("每[phoneme=日]天[/phoneme]都")
    assert result == "每日都", f"期望 '每日都', 实际 '{result}'"
    print(f"混合文本: '{result}' ✓")
    print("✓ 通过\n")


def test_backward_compatibility():
    """测试12：向后兼容旧接口"""
    print("=" * 80)
    print("测试12：向后兼容旧接口")
    print("=" * 80)
    
    text = "普通文本"
    segments = parse_marked_text(text)
    assert len(segments) == 1
    assert segments[0].text == "普通文本"
    print("parse_marked_text: ✓")
    
    # count_segments
    assert count_segments(text) == 1
    print("count_segments: ✓")
    
    # has_markers
    assert has_markers(text) == False
    assert has_markers('<prosody rate="-20%">test</prosody>') == True
    print("has_markers: ✓")
    print("✓ 通过\n")


def run_all_tests():
    """运行所有测试"""
    print("\n" + "=" * 80)
    print("开始运行 TTS 解析器测试")
    print("=" * 80 + "\n")
    
    tests = [
        test_pure_text,
        test_single_prosody,
        test_prosody_with_phoneme,
        test_pause_marker,
        test_mixed_prosody_and_pause,
        test_plain_text_between_prosody,
        test_phoneme_only,
        test_multiple_phoneme,
        test_complex_real_world,
        test_empty_and_whitespace,
        test_phoneme_preprocessor,
        test_backward_compatibility,
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            test()
            passed += 1
        except AssertionError as e:
            print(f"✗ {test.__name__} 失败: {e}\n")
            failed += 1
        except Exception as e:
            print(f"✗ {test.__name__} 错误: {e}\n")
            failed += 1
    
    print("=" * 80)
    print(f"测试完成！通过: {passed}/{len(tests)}, 失败: {failed}/{len(tests)}")
    print("=" * 80)
    
    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)

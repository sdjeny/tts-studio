#!/usr/bin/env python3
"""
Test script for parse_story_direct() -- tests against real LLM using test texts
from multi_text_test.py

This test calls the actual LLM to verify parse_story_direct works end-to-end.
"""
import json
import os
import re
import sys
import time
from collections import Counter

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.core.dialogue_parser import parse_story_direct

# ========== Test texts (same as /tmp/multi_text_test.py) ==========

TEXTS = {}

TEXTS["jingzhongqiu"] = """雨声淅沥，敲打着窗棂，像是某种古老而沉闷的鼓点，一下一下叩击着林深紧绷的神经。这间位于老城区的公寓，空气里弥漫着一股潮湿的霉味，混合着陈旧木头和廉价烟草的气息。窗户半开着，冷风灌进来，吹得桌上的烛火摇曳不定，将墙上的影子拉得细长而扭曲。林深坐在一张破旧的扶手椅上，手里握着一只半满的玻璃杯，琥珀色的液体在杯中晃动，映不出他此刻苍白的面容。他的目光死死盯着房间角落里的一个物体，那是今晚的主角，一面古镜。

这面镜子并非寻常之物。镜框由不知名的黑色金属铸造，表面布满了斑驳的铜绿，雕刻着繁复而晦涩的纹路，像某种失传的符文。它是林深三天前从一个跳蚤市场的角落里淘来的，卖家是个眼神浑浊的老头，递给他镜子时只说了一句话：『它能给你想要的，但你要付出代价。』

林深对着镜子低声说道：『如果当初我不那么软弱，现在会是什么样？』
镜子里的人沉默了片刻，然后开口了。声音低沉而沙哑。

镜中人：『你会成为你想成为的人。拥有权力，拥有财富，拥有她。』
林深浑身一震：『你……你是谁？』
镜中人：『我是你。是你内心深处最真实的那个你。』
林深摇头：『不可能，这只是镜子，我只是太累了。』
镜中人：『累？是因为你一直在伪装吗？』

镜中人走出了镜子，站在了林深面前。他伸出手拍了拍林深的脸颊。
镜中人：『看看你，多么可怜。充满了遗憾。』
林深嘶吼道：『滚开！这是我的身体！』
镜中人冷笑：『你的身体？你真的配拥有它吗？』"""

TEXTS["rainnight"] = """雨下得很大，李默骑着电动车在空荡荡的街道上疾驰。后座绑着一个快递箱，箱子上贴着一张发黄的便签，上面写着务必今晚送达。他已经送了八年快递，从没见过这样的地址——城西废弃工厂，三楼，无人签收。

他停下车，雨水顺着衣领灌进后背。工厂大门半开着，铁链在风中叮当作响。李默站在门口，手电筒的光柱在黑暗中晃了晃。

『有人吗？』他喊道。

没有回应。只有水滴从天花板缝隙落下的声音。

他犹豫了一下，还是走了进去。楼梯间的灯早就坏了，他摸黑上了三楼。走廊尽头有一扇门虚掩着，门缝里透出昏黄的光。

『外卖还是快递？』门后传来一个苍老的声音。

李默愣了一下：『快递。城西工厂，三楼。』

『进来吧。』门吱呀一声开了条缝。

李默推开门，房间里只有一个老头坐在摇椅上，旁边点着一根蜡烛。老头看着他手里的箱子，点了点头。

『放桌上吧。』老头说。

李默放下箱子：『你不看看是什么？』

老头笑了：『我知道是什么。我等的就是它。』"""

EXPECTED_ROLES = {
    "jingzhongqiu": ["卖镜老人", "林深", "镜中人"],
    "rainnight": ["李默", "老头"],
}

LLM_CFG = {
    "base_url": "http://192.168.0.77:7878/v1/chat/completions",
    "api_key": "sk-octopus-rnY79KRKMQ8Afl38QNbZwzparD4FR6TPJcE2TTgtU9bk0yuv",
    "model": "ollama",
}


def analyze(text_name, raw_text, expected_roles):
    """Analyze a single test text using parse_story_direct."""
    roles_str = "、".join(expected_roles)
    print("\n" + "=" * 70)
    print("【{}】 -- {}字 角色：{}".format(text_name, len(raw_text), roles_str))
    print("=" * 70)

    parse_result = parse_story_direct(raw_text, known_chars=expected_roles, llm_cfg=LLM_CFG)
    print("parse_story_direct 返回 {} 条".format(len(parse_result)))

    # ---- Quality checks ----
    # 1. Role distribution
    roles = Counter(d.get("role", "?") for d in parse_result)
    print("  角色分布：{}".format(dict(roles)))

    # 2. Length stats
    lens_list = [len(d.get("text", "")) for d in parse_result]
    avg_len = sum(lens_list) / len(lens_list) if lens_list else 0
    print("  长度：min={} max={} avg={:.0f}".format(
        min(lens_list) if lens_list else 0,
        max(lens_list) if lens_list else 0,
        avg_len))
    over250 = [i for i, l in enumerate(lens_list) if l > 250]
    print("  超250字：{}/{}".format(len(over250), len(parse_result)))

    # 3. Text preservation
    missing = sum(1 for d in parse_result if len(d.get("text", "")) > 10 and d["text"] not in raw_text)
    print("  原文丢失：{}/{}".format(missing, len(parse_result)))

    # 4. Check that non-narrator role text is from quoted content
    dialogues_only = re.findall(r'『([^』]*)』', raw_text)

    dirty_count = 0
    for d in parse_result:
        name = d.get("role", "")
        text = d.get("text", "")
        if name != "旁白" and text not in dialogues_only and text in raw_text:
            dirty_count += 1
            if dirty_count <= 5:
                print("  ! {} 文本混入叙述: 「{}...」".format(name, text[:50]))

    print("  角色对白混入叙述：{} 处".format(dirty_count))

    # 5. Verify all entries have 'role' field
    role_field_ok = all("role" in d for d in parse_result)
    print("  字段名 role 检查：{}".format("PASS" if role_field_ok else "FAIL"))

    # ---- Preview ----
    print("\n  【结果预览】")
    for i, d in enumerate(parse_result[:12]):
        name = d.get("role", "?")
        text = d.get("text", "")[:60]
        instruct = d.get("instruct", "")
        flag = " OK" if (name != "旁白" and text in dialogues_only) else ""
        print("  {:3d}. [{}] ({}) {}{}".format(i+1, name, instruct, text, flag))

    if len(parse_result) > 12:
        print("  ... (共{}条)".format(len(parse_result)))

    return {
        "name": text_name,
        "total": len(parse_result),
        "roles": dict(roles),
        "avg_len": avg_len,
        "over250": len(over250),
        "dirty": dirty_count,
        "missing": missing,
        "role_field_ok": role_field_ok,
    }


def test_parse_story_direct_basic():
    """Basic test: just runs the function and checks return type."""
    text = "林深问道：『你是谁？』镜中人答道：『我是你。』"
    result = parse_story_direct(text, known_chars=["林深", "镜中人"], llm_cfg=LLM_CFG)
    assert isinstance(result, list), "Expected list, got {}".format(type(result))
    assert "role" in result[0], "Expected 'role' field, got keys: {}".format(list(result[0].keys()))
    print("PASS test_parse_story_direct_basic: {} items".format(len(result)))


def test_parse_story_direct_with_llm_cfg():
    """Test with explicit LLM config."""
    text = "『你好』他说。"
    result = parse_story_direct(text, llm_cfg=LLM_CFG)
    assert isinstance(result, list)
    assert len(result) > 0
    assert "role" in result[0]
    print("PASS test_parse_story_direct_with_llm_cfg: {} items".format(len(result)))


def test_parse_story_direct_empty_input():
    """Test with empty input."""
    result = parse_story_direct("", llm_cfg=LLM_CFG)
    assert isinstance(result, list)
    print("PASS test_parse_story_direct_empty_input: {} items".format(len(result)))


def test_parse_story_direct_only_narration():
    """Test with no dialogue markers."""
    text = "这是一个安静的夜晚。月光洒在地上。"
    result = parse_story_direct(text, llm_cfg=LLM_CFG)
    assert isinstance(result, list)
    all_roles = {d.get("role") for d in result}
    print("PASS test_parse_story_direct_only_narration: roles={}".format(all_roles))


if __name__ == "__main__":
    print("=" * 70)
    print("  运行 parse_story_direct 测试套件")
    print("=" * 70)

    # Run full analysis on test texts
    all_results = []
    for text_name in ["jingzhongqiu", "rainnight"]:
        r = analyze(text_name, TEXTS[text_name], EXPECTED_ROLES[text_name])
        all_results.append(r)

    # Summary report
    print("\n\n" + "=" * 70)
    print("  【综合报告】")
    print("=" * 70)
    header = "{:<12} {:>6} {:>6} {:>6} {:>6} {:>6} {:>8}".format(
        "文本", "条数", "平均字", "超250", "脏数据", "丢失", "role字段")
    print(header)
    print("-" * 56)
    for r in all_results:
        rf = "PASS" if r["role_field_ok"] else "FAIL"
        line = "{:<12} {:>6} {:>6.0f} {:>6} {:>6} {:>6} {:>8}".format(
            r["name"], r["total"], r["avg_len"], r["over250"],
            r["dirty"], r["missing"], rf)
        print(line)

    # Run unit-style tests
    print("\n\n" + "=" * 70)
    print("  运行单元测试")
    print("=" * 70)
    test_parse_story_direct_basic()
    test_parse_story_direct_with_llm_cfg()
    test_parse_story_direct_empty_input()
    test_parse_story_direct_only_narration()

    print("\n" + "=" * 70)
    print("  所有测试完成")
    print("=" * 70)
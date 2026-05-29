#!/usr/bin/env python3
"""deploy/contract_test.py — 部署后的契约校验测试。

每次部署后必须跑，0 外部依赖，stdlib only。
全部通过 exit 0，失败 exit 1。
低版本 Python 兼容（3.8+）。
"""

import json
import sys
import urllib.request

BASE = "http://localhost:8000"
failures = 0
total = 0


def check(test_name: str, ok: bool, detail: str = ""):
    global failures, total
    total += 1
    if ok:
        print(f"  ✅ {test_name}")
    else:
        print(f"  ❌ {test_name}: {detail}")
        failures += 1


# === 1. list_projects 响应格式 ===
print("\n=== GET /api/projects (项目列表) ===")
data = []
try:
    resp = urllib.request.urlopen(f"{BASE}/api/projects", timeout=10)
    data = json.loads(resp.read())
    check("响应是 list", isinstance(data, list))
    if isinstance(data, list) and len(data) > 0:
        p0 = data[0]
        for field in [
            "id",
            "name",
            "characters",
            "characters_count",
            "episodes",
            "episodes_count",
            "created_at",
            "updated_at",
            "gen_defaults",
            "story_settings",
            "tts_defaults",
        ]:
            check(
                f"字段 '{field}' 存在",
                field in p0,
                f"缺失字段 '{field}' — 前端依赖此字段！",
            )
        check("characters 是 list", isinstance(p0.get("characters"), list))
        check("episodes 是 list", isinstance(p0.get("episodes"), list))
        check("gen_defaults 是 dict", isinstance(p0.get("gen_defaults"), dict))
        check("story_settings 是 dict", isinstance(p0.get("story_settings"), dict))
        check("tts_defaults 含 temperature", "temperature" in p0.get("tts_defaults", {}))
except Exception as e:
    check("API 响应正常", False, str(e))

# === 2. get_project 返回字段必须 ≥ list_projects 返回字段 ===
print("\n=== GET /api/projects/:id (项目详情) ===")
try:
    if isinstance(data, list) and len(data) > 0:
        pid = data[0]["id"]
        resp = urllib.request.urlopen(f"{BASE}/api/projects/{pid}", timeout=10)
        detail = json.loads(resp.read())
        list_keys = set(data[0].keys())
        detail_keys = set(detail.keys())
        # 聚合字段仅在列表接口从索引计算，详情接口不返回
        agg_fields = {"characters_count", "episodes_count"}
        missing = (list_keys - agg_fields) - detail_keys
        check(
            "详情接口 ≥ 列表接口字段",
            not missing,
            f"详情接口缺少列表接口已有的字段: {missing}",
        )
except Exception as e:
    check("项目详情 API 响应正常", False, str(e))

# === 3. /api/config 响应格式 ===
print("\n=== GET /api/config (系统配置) ===")
try:
    resp = urllib.request.urlopen(f"{BASE}/api/config", timeout=10)
    cfg = json.loads(resp.read())
    for section in ["llm", "tts", "gen"]:
        check(f"config 含 '{section}'", section in cfg)
    if "tts" in cfg:
        tts = cfg["tts"]
        check("tts 含 base_url", "base_url" in tts)
        if "defaults" in tts:
            for f in [
                "temperature",
                "do_sample",
                "top_k",
                "top_p",
                "repetition_penalty",
                "voice_id",
            ]:
                check(f"tts.defaults 含 '{f}'", f in tts["defaults"])
except Exception as e:
    check("config API 响应正常", False, str(e))

# === 4. /api/projects/defaults 响应格式 ===
print("\n=== GET /api/projects/defaults (全局默认值) ===")
try:
    resp = urllib.request.urlopen(f"{BASE}/api/projects/defaults", timeout=10)
    gd = json.loads(resp.read())
    for field in [
        "temperature",
        "do_sample",
        "top_k",
        "top_p",
        "repetition_penalty",
        "voice_id",
    ]:
        check(f"defaults 含 '{field}'", field in gd)
except Exception as e:
    check("defaults API 响应正常", False, str(e))

# === 结果 ===
print(f"\n{'='*40}")
if failures == 0:
    print(f"  ✅ 全部 {total} 项契约测试通过")
    sys.exit(0)
else:
    print(f"  ❌ {failures}/{total} 项失败 — 拒绝发布！修复后重跑")
    sys.exit(1)
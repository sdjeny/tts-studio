#!/usr/bin/env python3
"""
对白生成全链路测试

流程:
  1. 新建项目
  2. 生成摘要(默认3个)
  3. 生成对白(第1个摘要)
  4. 验证角色分配 + 同名角色复用

用法:
  python3 tests/test_tts_e2e.py
  TTS_BASE_URL=http://... python3 tests/test_tts_e2e.py
  python3 tests/test_tts_e2e.py --base=http://...

依赖: 无(纯 stdlib)
"""

import json, os, sys, time
from urllib.request import Request, urlopen
from collections import Counter

BASE_URL = os.environ.get("TTS_BASE_URL", "http://172.31.0.1:7861")
POLL_INTERVAL = 3
MAX_POLL = 60


def api(method, path, body=None, timeout=120):
    url = BASE_URL + path
    data = json.dumps(body).encode() if body else None
    req = Request(url, data=data, method=method,
                  headers={"Content-Type": "application/json"})
    try:
        with urlopen(req, timeout=timeout) as r:
            return json.loads(r.read())
    except Exception as e:
        print("  [FAIL]", method, path, "-", e)
        return None


def poll_task(proj_id, task_id, label):
    """轮询异步任务直到完成"""
    for i in range(MAX_POLL):
        time.sleep(POLL_INTERVAL)
        data = api("GET",
                   "/api/projects/%s/generation-status?episode_id=%s" %
                   (proj_id, task_id))
        if not data:
            continue
        s = data.get("status", "")
        if s == "completed":
            print("  [OK]", label, "done (%d/%d)" % (i + 1, MAX_POLL))
            return True
        elif s == "running":
            print("  [..]", label, "running (%d/%d)" % (i + 1, MAX_POLL), end="\r")
        elif s in ("idle", "ready"):
            print("  [OK]", label, "done (idle) (%d/%d)" % (i + 1, MAX_POLL))
            return True
        elif s in ("failed", "error", "failed"):
            print("  [FAIL]", label, "failed:", data)
            return False
        else:
            print("  [..]", label, "status=%s (%d/%d)" % (s, i + 1, MAX_POLL), end="\r")
    print("")
    print("  [FAIL]", label, "timeout")
    return False


def run():
    print("")
    print("=" * 60)
    print("  对白生成全链路测试")
    print("  目标:", BASE_URL)
    print("=" * 60)

    ok = 0
    fail = 0
    ts = int(time.time())

    # ---- Step 1: 新建项目 ----
    print("")
    print("-- STEP 1: 新建项目 --")
    proj = api("POST", "/api/projects", {"name": "e2etest_%d" % ts})
    if not proj or not proj.get("id"):
        print("  [FAIL] 新建项目失败")
        fail += 1
        sys.exit(1)
    proj_id = proj["id"]
    print("  [OK] 项目ID:", proj_id)
    ok += 1

    # ---- Step 2: 生成摘要 ----
    print("")
    print("-- STEP 2: 生成3个摘要 --")
    gen = api("POST",
              "/api/projects/%s/generate-episodes" % proj_id,
              {"description": "关于镜中囚的故事，主角林深发现古镜中另一个自己",
               "num_episodes": 3},
              timeout=300)
    if not gen:
        print("  [FAIL] 摘要调用失败")
        fail += 1
        sys.exit(1)

    if "task_id" in gen:
        if not poll_task(proj_id, gen["task_id"], "摘要"):
            fail += 1
            sys.exit(1)
        time.sleep(1)
    else:
        print("  [OK] 摘要同步返回")


    eps = api("GET", "/api/projects/%s/episodes" % proj_id)
    if not eps or len(eps) < 3:
        n = len(eps) if eps else 0
        print("  [FAIL] 预期>=3摘要, 实际%d" % n)
        fail += 1
        sys.exit(1)
    print("  [OK] 摘要 %d 个" % len(eps))
    ok += 1
    ep_id = eps[0]["id"]

    # ---- Step 3: 生成对白 ----
    print("")
    print("-- STEP 3: 生成对白 --")
    dlg_res = api("POST",
                  "/api/projects/%s/episodes/%s/generate-dialogues" %
                  (proj_id, ep_id),
                  {"instruction": "悬疑基调，幽暗氛围，对话丰富",
                   "target_duration_min": 3,
                   "narration_ratio": 40},
                  timeout=300)
    if not dlg_res:
        print("  [FAIL] 对白调用失败")
        fail += 1
        sys.exit(1)

    if "task_id" in dlg_res:
        if not poll_task(proj_id, dlg_res["task_id"], "对白"):
            fail += 1
            sys.exit(1)
        time.sleep(2)
    print("  [OK] 对白生成完成")
    ok += 1

    # ---- Step 4: 验证对白数据 ----
    print("")
    print("-- STEP 4: 验证对白数据 --")
    dls = api("GET", "/api/projects/%s/episodes/%s/dialogues" % (proj_id, ep_id))
    if not dls or len(dls) == 0:
        print("  [FAIL] 无对白数据")
        fail += 1
        sys.exit(1)
    print("  [OK] 对白 %d 条" % len(dls))
    ok += 1

    for field in ["character_name", "character_id", "text", "instruct"]:
        if field not in dls[0]:
            print("  [FAIL] 缺少字段", field)
            fail += 1
        else:
            print("  [OK] 字段", field)
            ok += 1

    # ---- Step 5: 验证角色分配 ----
    print("")
    print("-- STEP 5: 验证角色分配 --")
    role_cnt = Counter()
    char_ids = {}
    dup_issues = []

    for d in dls:
        name = d.get("character_name", "")
        cid = d.get("character_id", "")
        if name:
            role_cnt[name] += 1
        if name and cid:
            if name in char_ids and char_ids[name] != cid:
                dup_issues.append((name, char_ids[name][:8], cid[:8]))
            char_ids[name] = cid

    non_narr = {k: v for k, v in role_cnt.items() if k != "旁白"}
    if not non_narr:
        print("  [FAIL] 无角色对白")
        fail += 1
    else:
        print("  [OK] 非旁白角色 %d 个:" % len(non_narr))
        for r, c in sorted(non_narr.items(), key=lambda x: -x[1]):
            print("    - %s: %d 条" % (r, c))
        ok += 1

    if dup_issues:
        for n, a, b in dup_issues:
            print("  [FAIL] 同名'%s' char_id不同: %s vs %s" % (n, a, b))
        fail += 1
    else:
        print("  [OK] 同名角色 char_id 一致 (%d 个角色)" % len(char_ids))
        ok += 1

    chars = api("GET", "/api/projects/%s/characters" % proj_id)
    if chars:
        char_names = [c["name"] for c in chars]
        missing = [n for n in non_narr if n not in char_names]
        if missing:
            print("  [FAIL] 角色表中缺少:", missing)
            fail += 1
        else:
            print("  [OK] 角色列表包含所有对白角色:", char_names)
            ok += 1
        ok += 1

    # ---- Cleanup ----
    api("DELETE", "/api/projects/%s" % proj_id)
    print("  [OK] 测试项目已清理")

    # ---- 报告 ----
    print("")
    print("=" * 60)
    if fail == 0:
        print("  [PASS] %d/%d 项通过" % (ok, ok + fail))
    else:
        print("  [FAIL] %d/%d 通过, %d失败" % (ok, ok + fail, fail))
    print("=" * 60)

    print("")
    print("【对白样本】")
    for d in dls[:4]:
        print("  [%s] %s" % (d["character_name"], d["text"][:50]))

    sys.exit(0 if fail == 0 else 1)


if __name__ == "__main__":
    for arg in sys.argv[1:]:
        if arg.startswith("--base="):
            BASE_URL = arg.split("=", 1)[1]
    run()

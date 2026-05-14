"""
两步对话解析器：代码提取引号对白 + LLM 解析角色 + 合并旁白
"""
import re
import json
import time
from typing import List, Dict, Optional
import urllib.request


def extract_dialogues(text: str) -> List[Dict[str, int]]:
    """
    提取所有引号对白，返回含起止位置。
    覆盖：中文双引号 "" / 英文双引号 " / 日式引号 「」
    """
    pattern = re.compile(r'[\u201c""\u201d''\u300c\u300d][^\u201c""\u201d''\u300c\u300d]*[\u201c""\u201d''\u300c\u300d]')
    results = []
    for m in pattern.finditer(text):
        results.append({
            "start": m.start(),
            "end": m.end(),
            "inner": m.group()[1:-1]  # 不含引号
        })
    return results


def parse_llm_response(content: str) -> List[Dict[str, str]]:
    """解析 LLM 返回，兼容非标准 JSON"""
    clean = content.strip()
    if clean.startswith("```"):
        clean = re.sub(r"^```(?:json)?\s*", "", clean)
        clean = re.sub(r"\s*```$", "", clean)

    idx = clean.find("[")
    if idx < 0:
        raise ValueError("No JSON array found")

    # 用 regex 提取所有对象
    results = []
    for m in re.finditer(r'\{\s*[^}]*\}', clean[idx:]):
        obj_str = m.group()
        idx_m = re.search(r'"idx"\s*:\s*"?(\d+)"?', obj_str)
        role_m = re.search(r'"role"\s*:\s*"([^"]*)"', obj_str)
        instr_m = re.search(r'"instruct"\s*:\s*"([^"]*)"', obj_str)

        if idx_m is not None:
            results.append({
                "idx": int(idx_m.group(1)),
                "role": role_m.group(1) if role_m else "",
                "instruct": instr_m.group(1) if instr_m else ""
            })

    # 兜底：直接 json.loads
    if not results:
        parsed = json.loads(clean[idx:])
        results = [{"idx": i, "role": r.get("role",""), "instruct": r.get("instruct","")}
                   for i, r in enumerate(parsed)]

    return results


def parse_dialogues_with_llm(
    dialogues: List[Dict[str, int]],
    story_text: str,
    known_chars: Optional[List[str]] = None,
    api_url: str = "http://192.168.0.77:7878/v1/chat/completions",
    api_key: str = "sk-octopus-rnY79KRKMQ8Afl38QNbZwzparD4FR6TPJcE2TTgtU9bk0yuv",
    model: str = "lite2",
    max_tokens: int = 12000
) -> List[Dict[str, str]]:
    """
    LLM 解析对白角色，返回 [{idx, role, instruct}, ...]
    """
    items = "\n".join(f"对白 {i}：{d['inner']}" for i, d in enumerate(dialogues))
    chars_str = f"\n【已知角色】：{', '.join(known_chars)}" if known_chars else ""
    prompt = f"""判断以下每段对白是谁说的。

{items}
原文如下：
{story_text}{chars_str}

规则：
1. 如果对白是旁白叙述，role 填"旁白"
2. 如果出现新角色，赋予有识别性的简短称呼，名字优先
3. 同一个人物可能有多个称呼，要归一到同一个角色名
4. instruct 从括号（）提取情绪词，没有则为空 ""
5. 输出 JSON 数组：[{{"idx":0,"role":"角色名","instruct":"情绪"}}, ...]

直接输出 JSON 数组："""

    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
        "temperature": 0,
        "stream": False
    }

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(api_url, data=data,
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
        method="POST")

    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=300) as resp:
                result = json.loads(resp.read())
            content = result["choices"][0]["message"]["content"]
            return parse_llm_response(content)
        except Exception as e:
            if attempt < 2:
                time.sleep(2)
            else:
                raise

    return []


def merge_narration_and_dialogue(
    text: str,
    dialogues: List[Dict[str, int]],
    role_results: List[Dict[str, str]]
) -> List[Dict[str, str]]:
    """
    合并旁白和对话，按位置排序。
    返回 [{role, instruct, text}, ...]
    """
    # 提取旁白
    narrations = []
    last_end = 0
    for d in dialogues:
        if d["start"] > last_end:
            chunk = text[last_end:d["start"]].strip()
            if chunk:
                narrations.append({"pos": last_end, "text": chunk})
        last_end = d["end"]
    if last_end < len(text):
        chunk = text[last_end:].strip()
        if chunk:
            narrations.append({"pos": last_end, "text": chunk})

    # 合并旁白 + 对白
    all_elements = []

    # 旁白
    for n in narrations:
        all_elements.append({"pos": n["pos"], "type": "narration", "role": "旁白", "instruct": "", "text": n["text"]})

    # 对白
    for r in role_results:
        idx = r["idx"]
        if idx < len(dialogues):
            d = dialogues[idx]
            all_elements.append({"pos": d["start"], "type": "dialogue", "role": r["role"], "instruct": r["instruct"], "text": d["inner"]})

    # 排序
    all_elements.sort(key=lambda x: x["pos"])

    # 生成最终 JSON
    return [{"role": e["role"], "instruct": e["instruct"], "text": e["text"]} for e in all_elements]


def parse_story_with_two_step(
    story_text: str,
    known_chars: Optional[List[str]] = None
) -> List[Dict[str, str]]:
    """
    两步解析主流程：
    1. 代码提取引号对白
    2. LLM 解析角色
    3. 合并旁白 + 对白
    """
    # 步骤1：提取对白
    dialogues = extract_dialogues(story_text)

    # 步骤2：LLM 解析角色
    role_results = parse_dialogues_with_llm(
        dialogues,
        story_text,
        known_chars=known_chars
    )

    # 步骤3：合并旁白 + 对白
    return merge_narration_and_dialogue(story_text, dialogues, role_results)

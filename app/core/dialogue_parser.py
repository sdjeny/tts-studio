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
    覆盖：直角引号 『』
    """
    pattern = re.compile(r'[\u300e\u300f][^\u300e\u300f]*[\u300e\u300f]')
    results = []
    for m in pattern.finditer(text):
        inner = m.group()[1:-1].strip()
        if not inner:
            continue
        results.append({
            "start": m.start(),
            "end": m.end(),
            "inner": inner
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
    api_url: Optional[str] = None,
    api_key: Optional[str] = None,
    model: Optional[str] = None,
    max_tokens: int = 12000
) -> List[Dict[str, str]]:
    """
    LLM 解析对白角色，返回 [{idx, role, instruct}, ...]
    """
    # fallback 到 lite2（测试用）
    if not api_url:
        api_url = "http://192.168.0.77:7878/v1/chat/completions"
    if not api_key:
        api_key = "sk-octopus-rnY79KRKMQ8Afl38QNbZwzparD4FR6TPJcE2TTgtU9bk0yuv"
    if not model:
        model = "lite2"

    # api_url 已经是完整路径，直接用
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
        # 压缩旁白中的多余空行
        clean_text = n["text"].replace('\n\n', '\n').strip()
        if clean_text:
            all_elements.append({"pos": n["pos"], "type": "narration", "role": "旁白", "instruct": "", "text": clean_text})

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


def parse_story_direct(
    story_text: str,
    known_chars: Optional[List[str]] = None,
    llm_cfg: Optional[Dict] = None,
) -> List[Dict[str, str]]:
    """
    直接 LLM 拆解法：原始文本 → JSON 数组
    返回: [{role, instruct, text}, ...]

    不做任何后续处理（不合并连续同角色对白、不做旁白切分/排序/合并）。
    LLM 输出就是最终结果。

    参数:
        story_text: 原始故事文本
        known_chars: 已知角色列表，帮助 LLM 识别
        llm_cfg: LLM 配置字典，支持 base_url / api_key / model

    返回:
        [{role, instruct, text}, ...] 字段名 role（不是 character_name）
    """
    # ---- Guard: empty text ----
    if not story_text or not story_text.strip():
        return []

    # ---- LLM 配置 ----
    base_url = "http://192.168.0.77:7878/v1/chat/completions"
    api_key = "sk-octopus-rnY79KRKMQ8Afl38QNbZwzparD4FR6TPJcE2TTgtU9bk0yuv"
    model = "ollama"
    if llm_cfg:
        # 兼容两种 key：base_url（完整路径）或 api_url（含 /chat/completions）
        base_url_cfg = llm_cfg.get("base_url") or llm_cfg.get("api_url")
        if base_url_cfg:
            base_url = base_url_cfg
        api_key = llm_cfg.get("api_key") or api_key
        model = llm_cfg.get("model") or model

    # ---- System Prompt ----
    chars_hint = f"\n已知角色：{', '.join(known_chars)}。请优先使用已知角色名。" if known_chars else ""

    system_prompt = """你是一个故事文本分割器。将原始故事文本按对话段落拆解为JSON数组。

输出格式（只输出这三个字段）：
```json
[
  {"role": "角色名", "instruct": "情绪词", "text": "原文段落"},
  ...
]
```

核心规则（严格执行）：

1. **『』内的内容是对白**，必须分配给对应的说话角色
2. **『』外的内容归旁白**：场景描写、动作描写、表情描写、心理活动、叙述性过渡全部归旁白，role为"旁白"
3. **角色的 text 只包含『』内的纯对白**，不能混入"他笑了笑""她走上前""XX说"等叙述
4. **旁白的 text 包含所有非对白叙述**，保留原文
5. **角色名不能捏造**，从原文中提取说话人名字，统一称呼
6. **每段 text 不超过 250 字**
7. **instruct** 用2个中文词概括情绪（恐惧颤抖/愤怒嘶吼/轻声安慰等），没有则填空字符串

格式示例：
- 输入：卖家只说了一句话：『它能给你想要的』
- 输出：[{"role":"旁白","instruct":"神秘","text":"卖家只说了一句话："},{"role":"卖家","instruct":"警告","text":"它能给你想要的"}]

请直接输出JSON数组，不要markdown包裹。"""

    user_prompt = f"请解析以下故事文本：{chars_hint}\n\n{story_text}\n\n输出JSON数组。"

    # ---- API 调用 ----
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0,
        "max_tokens": 16384,
        "stream": False,
    }

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        base_url,
        data=data,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )

    # ---- Retry 机制 ----
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=300) as resp:
                result = json.loads(resp.read())
            msg = result["choices"][0]["message"]
            content = msg.get("content") or ""
            # 兼容商汤 content/reasoning 分裂：短文本格式
            if not content and msg.get("reasoning") and attempt < 1:
                continue  # 重试一次
            if not content:
                raise ValueError(f"LLM returned no content. Keys: {list(msg.keys())}")

            # 提取 JSON 数组
            arr_start = content.find("[")
            arr_end = content.rfind("]")
            if arr_start >= 0 and arr_end > arr_start:
                content = content[arr_start : arr_end + 1]

            parsed = json.loads(content)

            # 确保每个条目包含 role 字段（兼容 character_name）
            result_list = []
            for item in parsed:
                if "role" not in item:
                    if "character_name" in item:
                        item["role"] = item.pop("character_name")
                    else:
                        item["role"] = "旁白"
                # 确保字段存在
                item.setdefault("instruct", "")
                item.setdefault("text", "")
                result_list.append({"role": item["role"], "instruct": item["instruct"], "text": item["text"]})
            return result_list

        except Exception as e:
            if attempt < 2:
                time.sleep(2)
            else:
                raise

    return []


def parse_story_with_two_step(
    story_text: str,
    known_chars: Optional[List[str]] = None,
    llm_cfg: Optional[Dict] = None
) -> List[Dict[str, str]]:
    """
    两步解析主流程：
    1. 代码提取引号对白
    2. LLM 解析角色
    3. 合并旁白 + 对白

    .. deprecated::
        此函数已弃用，请使用 parse_story_direct() 替代。
        parse_story_direct 采用直接 LLM 拆解法，效果更优。
    """
    # 步骤1：提取对白
    dialogues = extract_dialogues(story_text)

    # 步骤2：LLM 解析角色
    role_results = parse_dialogues_with_llm(
        dialogues,
        story_text,
        known_chars=known_chars,
        api_url=llm_cfg.get("base_url") if llm_cfg else None,
        api_key=llm_cfg.get("api_key") if llm_cfg else None,
        model=llm_cfg.get("model") if llm_cfg else None,
    )

    # 步骤3：合并旁白 + 对白
    return merge_narration_and_dialogue(story_text, dialogues, role_results)

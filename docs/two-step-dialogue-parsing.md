# TTS 故事解析：两步方案

## 背景

现有解析器（`_parse_story_text`）使用正则 `r'"([^"]*)"'` 只匹配英文引号，对中文引号 `""` 或 `「」` 完全失效。两步方案彻底绕过正则语义，用**代码处理格式边界**，LLM 只做**角色识别**。

---

## 步骤 1：生成故事

### 输入（全部保留）

LLM 调用时传入以下所有字段，不删减、不截断：

| 字段 | 说明 |
|------|------|
| 剧集摘要 | `episode.summary` |
| 角色信息 | 姓名 + voice + 基础风格 + 性格描述 |
| 前情摘要 | 前 N 集的 summary |
| 后续摘要 | 后 5 集的 summary（最多 5 章） |
| 目标时长 → 字数 | `target_duration_min × 260`，允许 ±20% |
| 旁白占比 | `narration_ratio`（百分比） |
| 风格要求 | `style` 字段 |
| 额外指令 | `instruction` 字段 |

### Prompt 结构（去掉格式限制）

**去掉 system prompt 中的所有格式约束：**

```
你是一个有声故事编剧。根据摘要生成一个完整的故事。
总字数约{word_count}字（允许±20%浮动）。
旁白约占{narration_ratio}%。
{style_prompt}

衔接要求：
- 本章内容必须承前启后，与前后章节自然衔接
- 如果有后续章节，本章不能提前消耗后续的关键情节或悬念
- 如果没有后续章节（最终章），本章必须完整收尾，给出结局

输出纯文本，不要JSON，不要解释。
```

**User prompt 保持现有结构不变。**

### 关键改动

- ❌ 删除：`每段开头用[]标注角色名，旁白标[旁白]，对话用[角色名]`
- ❌ 删除：对话必须在括号里标注情绪
- ❌ 删除：引号相关提示
- ✅ 保留：字数、旁白占比、风格、衔接要求

LLM 自由发挥输出引号格式，后续步骤由代码统一处理。

---

## 步骤 2：提取 + 解析

### 阶段 2.1：代码提取对白

```python
import re

def extract_dialogues(text):
    """提取所有引号对白，返回含起止位置"""
    # 覆盖：中文双引号 "" / 英文双引号 " / 日式引号 「」
    pattern = re.compile(r'[\u201c""\u201d''\u300c\u300d][^\u201c""\u201d''\u300c\u300d]*[\u201c""\u201d''\u300c\u300d]')
    results = []
    for m in pattern.finditer(text):
        results.append({
            "start": m.start(),
            "end": m.end(),
            "inner": m.group()[1:-1]  # 不含引号
        })
    return results
```

**引号类型覆盖：**

| 符号 | Unicode | 说明 |
|------|---------|------|
| `"` `"` | U+201C / U+201D | 中文双引号（LLM 最常用） |
| `"` `"` | U+0022 | 英文双引号 |
| `'` `'` | U+2018 / U+2019 | 中文单引号 |
| `「` `」` | U+300C / U+300D | 日式引号 |

### 阶段 2.2：LLM 解析角色

#### Prompt 模板

```
判断以下每段对白是谁说的。

对白 0：{内容}
对白 1：{内容}
...
原文如下：
{完整原文}
【已知角色】：{角色A}, {角色B}

规则：
1. 如果出现新角色，赋予有识别性的简短称呼，名字优先
2. 同一个人物可能有多个称呼，要归一到同一个角色名
3. instruct 从括号（）提取情绪词，没有则为空 ""
4. 输出 JSON 数组：[{"idx":0,"role":"角色名","instruct":"情绪"}, ...]

直接输出 JSON 数组：
```

#### Prompt 设计原则

1. **先列对白（编号 + 内容）**：让 LLM 快速建立索引映射
2. **再给完整原文**：保持上下文连续性，不断章取义
3. **再注入已知角色**：让 LLM 有锚点，保留发现新角色的空间
4. **加归一化规则**：防止同一人物被拆成多个角色

#### max_tokens 设置

建议 `max_tokens: 8000-12000`。低于阈值会导致 JSON 被截断。

---

## 步骤 3：合并旁白 + 对白

旁白由代码生成，不依赖 LLM。

```python
def extract_narration(text, dialogues):
    """对白之间的段落即为旁白"""
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
    return narrations

# 按位置合并旁白 + 对白
all_elements = []

for n in narrations:
    all_elements.append({"pos": n["pos"], "type": "narration", "role": "旁白", "instruct": "", "text": n["text"]})

for r in role_results:
    idx = r["idx"]
    if idx < len(dialogues):
        d = dialogues[idx]
        all_elements.append({"pos": d["start"], "type": "dialogue", "role": r["role"], "instruct": r["instruct"], "text": r["text"]})

all_elements.sort(key=lambda x: x["pos"])
output = [{"role": e["role"], "instruct": e["instruct"], "text": e["text"]} for e in all_elements]
```

---

## 最终 JSON 结构

```json
[
  {
    "role": "旁白",
    "instruct": "",
    "text": "凌晨三点，咖啡馆里只剩最后一盏灯。"
  },
  {
    "role": "苏晚",
    "instruct": "惊讶",
    "text": "你怎么还在这儿？（惊讶）"
  },
  {
    "role": "陆行远",
    "instruct": "",
    "text": "睡不着。（轻声）"
  }
]
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `role` | string | 角色名。旁白固定为 `"旁白"` |
| `instruct` | string | 从括号提取的情绪词，无则为空 |
| `text` | string | 对白内容（不含引号） |

---

## 实测数据

### 测试 1：千字故事（1825 字节，48 条对白 + 42 段旁白）

| 模型 | 耗时 | 遗漏 | 空角色 |
|------|------|------|--------|
| lite2 | 6.5s | **0** | **0** |

最终输出 90 条（42 旁白 + 48 对白），位置排序正确。

### 测试 2：万字故事（12960 字节，455 条对白）

| 模型 | 耗时 | 对上 | 遗漏 |
|------|------|------|------|
| lite2 | 145s | 455/455 | **0** |

**万字故事 0 遗漏验证通过。**

---

## 注意事项

1. **不要偷懒**：每次测试应同时跑多个模型作对照
2. **引号覆盖要全**：至少覆盖中文双引号 `""` + 英文双引号 `"` + 日式引号 `「」`
3. **max_tokens 要够**：字数 × 比例估算，5000 字建议 8000+，万字建议 12000+
4. **LLM 只定角色**：代码负责格式边界，LLM 不做格式判断
5. **旁白不由 LLM 生成**：旁白由代码提取，LLM 只对引号内容判断角色
6. **JSON 解析容错**：LLM 可能输出非标准 JSON（含无引号属性名），用 regex 兜底提取

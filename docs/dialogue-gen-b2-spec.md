# 需求规格书：LLM生成对白方案B-2

> 版本：v1.0  
> 日期：2026-05-12  
> 作者：师爷（需求分析师）  
> 状态：待评审  
> 项目路径：`/opt/data/workspace/tts-studio/`

---

## 一、背景与目标

### 1.1 问题

当前方案（方案A：幕规划+逐幕生成）存在三个核心问题：

1. **对白碎片化**：每次只生成几条，循环调用 LLM，缺乏上下文连贯
2. **旁白和对话割裂**：type 字段强制分离 narration/dialogue/mixed，导致过渡生硬
3. **角色性格不够突出**：逐幕生成时角色上下文窗口小，性格一致性差

### 1.2 方案B-2 核心思路

**一次性生成完整故事，纯文本标注，后期解析入库。**

```
[旁白] 夜色沉沉，雨后的街灯把路面映得斑驳。
[小明]（沉声）这纸张已经发黄，笔迹也带着淡淡的墨香。
[小红]（活泼）哎呀，明哥，这不就是冒险的开始吗！
[旁白] 小红的眼睛在灯光下闪闪发亮。
[小明]（谨慎）废弃灯塔？那是旧铁路旁的老建筑，已经半塌多年。
```

- 每段标注 `[角色名]`，旁白标 `[旁白]`
- 括号标注情绪，如 `（沉声）`、`（活泼）`
- 后期解析文本，提取角色名、instruct、text
- 角色匹配入库

### 1.3 设计原则

- **字数、旁白占比、风格都是"大约"值**，允许 LLM 根据剧情需要灵活调整
- **纯文本输出**，不要 JSON（减少 LLM 输出格式的约束）
- **一次生成**，不分幕、不分批，保持故事完整性和连贯性

---

## 二、功能需求清单

### FR-01：LLM Prompt 构建

构建一次性生成完整故事的 Prompt，包含：

| 组件 | 说明 | 必选 |
|------|------|------|
| 角色信息 | 角色名 + voice_id + base_instruct + 描述 | ✅ |
| 剧集摘要 | 本集摘要（必须有值，否则报错） | ✅ |
| 前情提要 | 之前所有剧集摘要（全部传入，不限数量） | ✅ |
| 后续规划 | 当前章之后的最多5个剧集摘要 | ✅ |
| 额外指令 | 用户自定义要求 | ❌ |
| 目标字数 | `target_duration_min × 260`，可手动覆盖 | ✅ |
| 旁白占比 | 如"旁白约占20%" | ✅ |
| 故事风格 | 如"悬疑，节奏紧凑" | ❌ |
| temperature | LLM 采样温度 | ❌ |

### FR-02：LLM 输出格式定义

LLM 输出纯文本，遵循以下规则：

1. 每段开头用 `[]` 标注角色名，包括旁白也标 `[旁白]`
2. 顺序和字数完全自由，根据剧情需要
3. 可以是旁白、独白、对话任意组合
4. 总字数约 X 字（允许 ±20% 浮动）
5. 故事完整，有起承转合
6. 对话符合角色性格
7. 可以根据剧情需要引入新角色
8. 输出纯文本，不要 JSON

### FR-03：文本解析引擎

从 LLM 输出的纯文本中，解析出结构化对白数据。

**解析规则（多步处理）**：

1. 按 `[角色名]` 标记切分段落
2. **无标记段落** → 整体作为 `[旁白]` 条目（连续无标记段落合并）
3. **有标记段落**：
   - 提取情绪标注 `（xxx）`→ instruct
   - 引号 `"..."` 内的内容 → 角色对话 text（每个引号单独一条）
   - 引号外的描述性文字 → 独立 `[旁白]` 条目
4. **向后兼容**：无引号时整体作为角色 text

**边界处理**：
- 无情绪括号时，instruct = ""
- 角色名前后空格 trim
- 空文本段落跳过（不入库）
- 多引号不拼合，每条独立成条目

**示例**：
```
[旁白] 暮色笼罩着山谷。
[李伟]（低声）"我回来了，父亲……" 他的声音在空旷的殿宇里回荡。
[小红]（惊讶）"这……这是真的吗？"
```

解析结果：
```json
[
  {"role": "旁白", "instruct": "", "text": "暮色笼罩着山谷。"},
  {"role": "李伟", "instruct": "低声", "text": "我回来了，父亲……"},
  {"role": "旁白", "instruct": "", "text": "他的声音在空旷的殿宇里回荡。"},
  {"role": "小红", "instruct": "惊讶", "text": "这……这是真的吗？"}
]
```

### FR-04：角色匹配与创建

解析后的角色名需要匹配到项目角色：

1. **精确匹配**：角色名完全相同
2. **本次已创建**：本次生成中已创建的新角色缓存
3. **归一化匹配 + 互相包含**：去除标点空格后匹配
4. **模糊匹配**：SequenceMatcher ratio ≥ 0.7
5. **创建新角色**：以上都不匹配时，自动创建（voice_id 继承项目已有角色的首个，无则用 "aiden"）

**事后去重**（同方案A）：
- 检查本次新建角色是否与已有角色重复
- 重复则合并 character_id，移除新角色

### FR-05：入库流程

1. 解析文本 → `[{role, instruct, text}, ...]`
2. 旁白 → `character_id = ""`，`character_name = "旁白"`
3. 其他角色 → `_resolve_char_id()` 匹配或创建
4. 调用 `add_dialogue()` 逐条入库
5. SSE 推送进度

### FR-06：SSE 事件流

| 事件类型 | 触发时机 | data 结构 |
|----------|----------|-----------|
| `generating` | 开始生成，LLM 调用前 | `{ "status": "generating", "message": "正在生成故事..." }` |
| `parsing` | LLM 返回，开始解析 | `{ "raw_length": number, "parsed_count": number }` |
| `progress` | 每入库一条 | `{ "current": number, "total": number }` |
| `new_characters` | 发现新角色 | `{ "names": string[] }` |
| `complete` | 全部完成 | `{ "created": number, "dialogue_ids": string[], "new_characters": string[], "_debug": { "target": number, "actual": number, "word_count": number } }` |
| `error` | 任何错误 | `{ "message": string, "stage": "llm" \| "parse" \| "store" }` |

### FR-07：生成模式选择

支持两种生成模式，通过 API 参数 `mode` 选择：

| 模式 | 值 | 说明 |
|------|-----|------|
| 方案A（现有） | `"scene"` | 幕规划+逐幕生成 |
| 方案B-2（新） | `"onetime"` | 一次性生成完整故事 |

前端需要在"自动对白"按钮旁增加模式切换 UI。

---

## 三、API 接口变更

### 3.1 现有接口变更

#### `POST /projects/{pid}/episodes/{eid}/generate-dialogues`

**变更**：新增请求体字段

```python
class DialogueGenRequest(BaseModel):
    instruction: str = ""          # 不变
    target_duration_min: int = 25  # 不变
    narration_ratio: int = 50      # 不变
    mode: str = "onetime"          # 新增：生成模式 "scene" | "onetime"，默认 "onetime"
    style: str = ""                # 新增：故事风格，如 "悬疑"、"轻松"、"文言"
    temperature: float = 0.7       # 新增：LLM 采样温度
    word_count: int = 0            # 新增：手动指定字数（0 表示自动计算）
```

**响应**：不变（SSE 流式返回）

### 3.2 新增接口

#### `POST /projects/{pid}/episodes/{eid}/generate-dialogues/preview`

**用途**：预览 LLM 生成的纯文本，不入库（用于调试 prompt）

**请求体**：同 `DialogueGenRequest`

**响应**：
```json
{
  "raw_text": "string",
  "parsed": [
    {
      "character_name": "string",
      "instruct": "string",
      "text": "string"
    }
  ],
  "word_count": 0,
  "char_count": 0
}
```

---

## 四、后端变更

### 4.1 `app/core/dialogue_service.py`

**变更**：新增 `OnetimeDialogueGenerator` 类

```python
class OnetimeDialogueGenerator:
    """一次性生成完整故事，纯文本标注，后期解析入库。"""
    
    def __init__(self, project_id: str, episode_id: str, body):
        # 同 DialogueGenerator
    
    def _build_prompt(self) -> tuple[str, str]:
        """构建 system prompt 和 user prompt"""
        # 返回 (system, user)
    
    def _parse_response(self, raw_text: str) -> list[dict]:
        """解析 LLM 纯文本输出"""
        # 返回 [{"character_name": str, "instruct": str, "text": str}]
    
    async def generate(self):
        """异步生成器，yield (event_type, data_dict) 元组"""
        # 1. yield "generating"
        # 2. 调用 LLM（纯文本，非 chat_json）
        # 3. yield "parsing"
        # 4. 解析文本
        # 5. 角色匹配+入库
        # 6. yield "progress"（逐条）
        # 7. yield "new_characters"（如有）
        # 8. yield "complete"
```

### 4.2 `app/api/episodes.py`

**变更**：

1. `DialogueGenRequest` 新增字段：`mode`, `style`, `temperature`, `word_count`
2. `api_generate_dialogues` 路由根据 `mode` 选择生成器：
   - `mode="scene"` → `DialogueGenerator`（现有）
   - `mode="onetime"` → `OnetimeDialogueGenerator`（新增）

### 4.3 `app/core/llm.py`

**变更**：新增 `chat_text` 函数（纯文本输出，非 JSON）

```python
async def chat_text(messages: list[dict], max_tokens: int = 4000, timeout: int = 300, temperature: float = 0.7) -> str:
    """调用 LLM，返回纯文本（非 JSON）"""
```

### 4.4 旁白处理

旁白在 `add_dialogue` 时，`character_id = ""`，`character_name = "旁白"`。

**现有 `add_dialogue` 逻辑兼容**：当 `character_id = ""` 时，`char_name = "旁白"`（需要在 store.py 中补充此分支）。

---

## 五、前端变更

### 5.1 `frontend/src/api.ts`

**变更**：

1. `generateDialogues` 和 `generateDialoguesStream` 新增参数：
```typescript
generateDialogues: (
  pid: string, eid: string,
  instruction: string = "",
  targetDurationMin: number = 25,
  narrationRatio: number = 50,
  options?: {
    mode?: "scene" | "onetime";
    style?: string;
    temperature?: number;
    wordCount?: number;
  }
) => ...

generateDialoguesStream: (
  pid: string, eid: string,
  instruction: string = "",
  targetDurationMin: number = 25,
  narrationRatio: number = 50,
  onEvent: (event: string, data: any) => void,
  options?: {
    mode?: "scene" | "onetime";
    style?: string;
    temperature?: number;
    wordCount?: number;
  }
) => ...
```

2. SSE 事件处理新增：
   - `generating` → 显示 "正在生成故事..."
   - `parsing` → 显示 "解析中..."
   - `complete._debug` 新增 `word_count` 字段

### 5.2 `frontend/src/components/EpisodePanel.tsx`

**变更**：

1. "自动对白"按钮旁增加模式切换下拉框：
   - 选项：`方案B-2（一次性生成）` | `方案A（幕规划）`
   - 默认：方案B-2

2. 生成进度显示适配新事件：
   - `generating` → "正在生成故事..."
   - `parsing` → "解析中..."
   - `progress` → `current/total` 不变

3. 风格输入框（可选）：
   - 输入框 placeholder="风格：悬疑/轻松/文言..."

### 5.3 旁白段展示

旁白段的 `character_name = "旁白"`，前端已有 `character_name` 字段，无需额外变更。

---

## 六、边界条件与异常场景

### 6.1 输入校验

| 场景 | 处理方式 |
|------|----------|
| 剧集无摘要 | yield `error`, `{"message": "该剧集没有摘要，请先生成或填写摘要"}` |
| LLM 未配置 | yield `error`, `{"message": "LLM 未配置..."}` |
| target_duration_min < 1 | 使用默认值 3（分钟） |
| narration_ratio 不在 0-100 | clamp 到 0-100 |
| mode 不是 "scene" 或 "onetime" | 默认使用 "onetime" |
| temperature 不在 0-2 | clamp 到 0.1-2.0 |
| word_count < 0 | 使用自动计算值 |

### 6.2 LLM 输出异常

| 场景 | 处理方式 |
|------|----------|
| LLM 返回空文本 | yield `error`, `{"message": "LLM 返回空文本", "stage": "llm"}` |
| LLM 返回 JSON 而非纯文本 | 尝试按纯文本解析（当作普通文本处理） |
| LLM 调用超时（>300s） | yield `error`, `{"message": "LLM 调用超时", "stage": "llm"}` |
| LLM 输出无 `[角色名]` 标记 | 整段文本作为一条对白，角色名 = ""（旁白） |
| LLM 输出字数偏差 > ±50% | 记录警告日志，不报错（允许 LLM 自由发挥） |
| 解析后无有效段落 | yield `error`, `{"message": "未能解析出有效对白", "stage": "parse"}` |

### 6.3 角色匹配异常

| 场景 | 处理方式 |
|------|----------|
| 角色名为空 | 跳过该段落 |
| 创建新角色失败 | 使用空 character_id，character_name = "⚠ 角色异常" |
| 角色名含特殊字符 | trim 后正常使用 |

### 6.4 入库异常

| 场景 | 处理方式 |
|------|----------|
| add_dialogue 返回 None | 跳过该条，继续下一条 |
| 入库中途失败 | 已入库的数据不回滚，yield error 报告已完成数量 |

### 6.5 并发与幂等

| 场景 | 处理方式 |
|------|----------|
| 同一剧集重复触发生成 | 后端不加锁（与现有方案A一致），前端按钮禁用防止重复点击 |
| 生成过程中页面关闭 | 后端继续执行，数据入库 |

---

## 七、验收标准

### AC-01：正常流程

**Given**：项目有 2 个角色（小明、小红），剧集有摘要（≥20字）
**When**：调用 `mode="onetime"`，`target_duration_min=3`
**Then**：
- 返回 SSE 事件序列完整：`generating` → `parsing` → `progress`（逐条）→ `complete`
- 入库对白数量 ≥ 5 条
- 每条对白有 `character_name`、`text`、`instruct`
- 旁白段 `character_name = "旁白"`
- `complete._debug.word_count` 存在且 > 0

### AC-02：LLM 输出格式兼容

**Given**：LLM 输出带 `[角色名]（情绪）内容` 格式
**When**：解析
**Then**：
- 角色名正确提取
- instruct = "情绪"
- text = "内容"

### AC-03：LLM 输出无情绪括号

**Given**：LLM 输出 `[角色名] 内容`（无括号情绪）
**When**：解析
**Then**：
- 角色名正确提取
- instruct = ""
- text = "内容"

### AC-04：新角色自动创建

**Given**：LLM 输出中出现项目不存在的角色名
**When**：入库
**Then**：
- 自动创建新角色
- `new_characters` 事件包含该角色名
- 对白关联到新建角色

### AC-05：方案A 兼容

**Given**：`mode="scene"`
**When**：调用生成
**Then**：
- 使用现有 `DialogueGenerator` 逻辑
- SSE 事件序列与现有一致：`planning` → `scene_start` → `progress` → `scene_done` → `complete`

### AC-06：无摘要报错

**Given**：剧集摘要为空
**When**：调用生成
**Then**：
- 立即返回 `error` 事件
- message 包含 "没有摘要"

---

## 八、测试用例规格

### 8.1 单元测试：文本解析

| 编号 | 输入 | 预期输出 |
|------|------|----------|
| TC-PARSE-01 | `[旁白] 夜色沉沉。` | `[{role: "旁白", instruct: "", text: "夜色沉沉。"}]` |
| TC-PARSE-02 | `[小明]（沉声）这纸张已经发黄。` | `[{role: "小明", instruct: "沉声", text: "这纸张已经发黄。"}]` |
| TC-PARSE-03 | `[小红] 你好吗？` | `[{role: "小红", instruct: "", text: "你好吗？"}]` |
| TC-PARSE-04 | `[小明]（略带紧张）你觉得呢？\n[小红]（微笑）还行。` | 两条解析正确 |
| TC-PARSE-05 | `（没有角色标记的纯文本）` | `[{role: "", instruct: "", text: "（没有角色标记的纯文本）"}]` |
| TC-PARSE-06 | `[小明]（情绪）内容（括号内）后续` | text = `内容（括号内）后续`（非贪婪匹配括号） |
| TC-PARSE-07 | `[小明]（情绪1）内容1\n\n[小红]（情绪2）内容2` | 两条解析正确（空行分隔） |
| TC-PARSE-08 | `[] 内容为空角色名` | role = ""，跳过或作为旁白 |
| TC-PARSE-09 | `[小明]` | 无 text，跳过 |
| TC-PARSE-10 | `[  空格角色  ]（ 情绪 ） 内容 ` | trim 后：role = "空格角色"，instruct = "情绪"，text = "内容" |

### 8.2 单元测试：角色匹配

| 编号 | 场景 | 预期 |
|------|------|------|
| TC-CHAR-01 | 精确匹配已有角色 | 返回已有 char_id，is_new = false |
| TC-CHAR-02 | 角色名带空格 `[ 小明 ]` | trim 后精确匹配 |
| TC-CHAR-03 | 归一化匹配（`李小明` vs `李晓明`） | 根据 ratio 判断 |
| TC-CHAR-04 | 新角色 | 创建新角色，is_new = true |
| TC-CHAR-05 | 本次已创建的角色 | 从缓存返回，不重复创建 |

### 8.3 集成测试

| 编号 | 场景 | 步骤 | 预期 |
|------|------|------|------|
| TC-INT-01 | 正常生成 | 1. 创建项目+角色+剧集摘要 2. 调用 onetime 生成 | 对白入库，数量 ≥ 5 |
| TC-INT-02 | 无摘要 | 1. 创建剧集（无摘要）2. 调用生成 | 返回 error |
| TC-INT-03 | LLM 未配置 | 1. 清空 LLM 配置 2. 调用生成 | 返回 error |
| TC-INT-04 | 新角色创建 | 1. LLM 输出新角色 2. 调用生成 | 新角色入库，new_characters 事件触发 |
| TC-INT-05 | 方案A 兼容 | 1. mode="scene" 2. 调用生成 | 使用现有逻辑 |
| TC-INT-06 | 字数偏差 | 1. 设置 target_duration_min=1（约260字）2. LLM 输出 500 字 | 不报错，记录警告 |

### 8.4 前端测试

| 编号 | 场景 | 预期 |
|------|------|------|
| TC-FE-01 | 模式切换 | 下拉框可切换方案A/B-2 |
| TC-FE-02 | 生成中按钮禁用 | 生成中按钮不可点击 |
| TC-FE-03 | 进度显示 | 显示 "正在生成故事..." → "解析中..." → "5/10" |
| TC-FE-04 | 完成提示 | 弹窗显示 "已生成 X 条对白" |
| TC-FE-05 | 错误提示 | 弹窗显示错误消息 |

---

## 九、Prompt 模板（参考）

### System Prompt

```
你是一个有声故事编剧。根据给定摘要，输出完整的讲故事风格文本。

输出规则：
1. 每段开头用[]标注角色名，包括旁白也标[旁白]
2. 顺序和字数完全自由，根据剧情需要
3. 可以是旁白、独白、对话任意组合
4. 总字数约{word_count}字，允许±20%浮动
5. 故事完整，有起承转合
6. 对话符合角色性格
7. 可以根据剧情需要引入新角色
8. 可以在角色名后用括号标注情绪，如[小明]（沉声）
9. 输出纯文本，不要JSON
```

### User Prompt

```
标题：{title}
摘要：{summary}

角色信息：
{chars_info}

前情提要：
{prev_summaries}

后续规划：
{next_summaries}

{style_instruction}
{extra_instruction}

请将这个故事完整输出。
```

---

## 十、待确认事项

| 编号 | 问题 | 建议 |
|------|------|------|
| Q-01 | 旁白是否需要有独立的音色配置？ | 建议旁白使用项目默认音色（tts_defaults.voice_id） |
| Q-02 | 字数偏差是否需要硬限制？ | 建议只做警告，不阻断生成 |
| Q-03 | 是否需要支持"重新生成单条对白"？ | 不在本方案范围内，后续迭代 |
| Q-04 | 解析失败时是否支持手动编辑 raw_text？ | 建议通过 preview 接口支持调试 |

---

## 十一、文件变更清单

| 文件 | 变更类型 | 说明 |
|------|----------|------|
| `app/core/dialogue_service.py` | 修改 | 新增 `OnetimeDialogueGenerator` 类 |
| `app/core/llm.py` | 修改 | 新增 `chat_text` 函数 |
| `app/api/episodes.py` | 修改 | `DialogueGenRequest` 新增字段，路由根据 mode 分发 |
| `app/core/store.py` | 修改 | `add_dialogue` 支持 `character_id = ""`（旁白） |
| `frontend/src/api.ts` | 修改 | 新增 options 参数 |
| `frontend/src/components/EpisodePanel.tsx` | 修改 | 模式切换、风格输入、新事件处理 |

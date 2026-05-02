# TTS 采样参数配置指南

## 问题背景

使用 Qwen3-TTS 生成语音时，即使指定了相同的 `speaker`、`language` 和 `instruct`，不同文本（句子）生成的声音听起来差异过大——音色、节奏、情感起伏不一致，影响多轨编辑时的听觉连贯性。

**根本原因**：TTS 模型内部使用采样（sampling）来逐个生成音频 token。采样过程有随机性，由一组**采样参数**控制。默认参数（`temperature=0.9` 等）随机性较高，导致不同句子的输出波动明显。

---

## 参数说明

以下 5 个参数共同控制 TTS 采样的随机性/确定性。参数值越低/越严格，输出越确定、越一致。

| 参数 | 类型 | 官方默认 | 本项目保守默认 | 建议范围 | 作用 |
|---|---|---|---|---|---|
| `temperature` | float | 0.9 | **0.3** | 0.05~1.5 | **最重要的参数**。控制采样的"温度"。越低越确定、越稳定；越高越随机、变化越大。 |
| `do_sample` | bool | `true` | **`true`** | `true`/`false` | 是否使用采样。`true`=采样（更自然），`false`=贪心解码（最确定，但可能生硬）。 |
| `top_k` | int | 50 | **20** | 5~100 | 只从概率最高的 k 个 token 中采样。越小采样池越窄，输出越集中。 |
| `top_p` | float | 1.0 | **0.85** | 0.3~1.0 | 核采样阈值。从累积概率达到 p 的 token 中采样。越小越集中，1.0=不截断。 |
| `repetition_penalty` | float | 1.05 | **1.1** | 1.0~2.0 | 重复惩罚系数。>1.0 时抑制重复模式，值越大抑制越强。 |

### 参数效果对比

| 配置 | temperature | do_sample | top_k | top_p | repetition_penalty | 适用场景 |
|---|---|---|---|---|---|---|
| 🟢 保守（推荐） | 0.3 | true | 20 | 0.85 | 1.1 | 日常使用，同一角色多句台词 |
| 🔬 官方默认 | 0.9 | true | 50 | 1.0 | 1.0 | 需要更多变化/创意 |
| 🛡️ 极限稳定 | 0.1 | **false** | 10 | 0.5 | 1.3 | 追求最大一致性 |

---

## 配置层级

本项目采用**两层配置**，优先级从高到低：

```
单次生成显式传参  >  项目级 tts_defaults  >  服务端内置保守默认值
```

### 1. 服务端内置默认值（最低优先级）

位置：`app/api/qwen3-tts/server.py` worker 中

```python
_def_temp = 0.3
_def_top_k = 20
_def_top_p = 0.85
_def_rep_pen = 1.1
```

**任何未显式传入采样参数的任务，都会自动使用这些保守值。** 这意味着升级后，所有旧项目、所有现有 API 调用方无需任何改动，就能获得更稳定的声音。

### 2. 项目级默认值（中间优先级）

存储在项目的 `tts_defaults` 字段中（`data/studio.json` → `projects[i].tts_defaults`）。

当对白生成音频时，`episodes.py` 会读取项目的 `tts_defaults` 并传给 `submit_tts()`。如果项目中没有设置（旧项目），则回退到服务端内置默认值。

**修改方式**：前端 → 项目详情 → ⚙️ 项目设置 tab → TTS 采样参数

### 3. 单次生成显式传参（最高优先级）

通过 `tts_client.submit()` 或 `POST /tts/submit` 的 JSON body 中传入：

```json
{
  "text": "你好世界",
  "speaker": "Dylan",
  "instruct": "愉快",
  "temperature": 0.5,
  "top_k": 30
}
```

只有显式传入的字段才会覆盖项目默认值；未传的字段（`null` 或不存在）继续使用项目默认值。

---

## 数据结构与存储

### 项目 JSON 结构

```json
{
  "id": "887eaa50a742",
  "name": "我的项目",
  "tts_defaults": {
    "temperature": 0.3,
    "do_sample": true,
    "top_k": 20,
    "top_p": 0.85,
    "repetition_penalty": 1.1
  },
  "characters": [],
  "episodes": []
}
```

### API 接口

**更新项目 TTS 参数**：
```
PATCH /api/projects/{project_id}
Content-Type: application/json

{
  "tts_defaults": {
    "temperature": 0.5,
    "top_k": 30
  }
}
```

- `tts_defaults` 中未包含的字段不会被修改（保留原值）
- 不支持通过此接口修改 `name` 和 `tts_defaults` 以外的字段

**提交 TTS 任务（显式覆盖）**：
```
POST /tts/submit
Content-Type: application/json

{
  "text": "你好世界",
  "speaker": "Dylan",
  "instruct": "愉快",
  "temperature": 0.5
}
```

---

## 数据迁移

旧项目（升级前创建的）没有 `tts_defaults` 字段。首次读取时自动补充保守默认值：

位置：`app/core/store.py` → `list_projects()`

```python
if not p.get("tts_defaults"):
    p["tts_defaults"] = {
        "temperature": 0.3,
        "do_sample": True,
        "top_k": 20,
        "top_p": 0.85,
        "repetition_penalty": 1.1,
    }
```

迁移是惰性的——只在项目首次被读取时触发，写入后即持久化。

---

## 测试

### 运行测试

先启动 TTS 服务（`server.py`），然后：

```bash
cd app/api/qwen3-tts
python -m pytest test_api.py -v
# 或直接运行
python test_api.py
```

### 测试分层

| 测试类 | 说明 |
|---|---|
| `TestTTSAPILegacy` | **封存**的原始兼容性测试，确保基础 API 不变 |
| `TestTTSAPISampling` | 新增采样参数测试，包含 7 个子用例 |

### 测试用例说明

| 用例 | 内容 |
|---|---|
| `test_01_default_params` | 不传采样参数 → 验证服务端使用保守默认值 |
| `test_02_conservative_params` | 显式传入保守参数 → 与默认值结果应接近 |
| `test_03_official_defaults` | 传入官方默认参数 → 应与保守参数有明显差异 |
| `test_04_ultra_stable` | 极限稳定参数（贪心解码）→ 输出最确定 |
| `test_05_partial_params` | 仅传 temperature，其余 None → 验证降级逻辑 |
| `test_06_consistency_same_text` | 同一文本生成 3 次 → 文件大小差异 <30% |
| `test_07_cross_sentence_stability` | 不同文本 + 保守参数 → 验证跨句一致性 |

所有测试音频输出到 `app/api/qwen3-tts/test_output/` 目录，可手动播放对比。

---

## 修改文件清单

| 文件 | 改动 |
|---|---|
| `app/core/store.py` | `create_project` 增加 `tts_defaults` 字段；`update_project` 支持 `**extra` 深度合并；`list_projects` 数据迁移 |
| `app/api/projects.py` | `ProjectUpdate` schema 增加 `tts_defaults` 字段；`api_update_project` 处理嵌套更新 |
| `app/api/episodes.py` | 新增 `_get_project_tts_defaults()` 辅助函数；3 处 `submit_tts` 调用点透传项目参数 |
| `app/api/qwen3-tts/server.py` | Worker 中读取 task 的采样参数，透传给 `generate_custom_voice` |
| `app/api/qwen3-tts/tts_client.py` | `submit()` 方法增加 5 个可选采样参数 |
| `app/core/tts.py` | `submit_tts()` 和 `generate_audio()` 透传采样参数 |
| `frontend/src/api.ts` | `Project` 接口增加 `tts_defaults`；`updateProject` 接受可选参数 |
| `frontend/src/components/ProjectSettings.tsx` | **新增**：项目设置面板组件（滑块 + 预设按钮） |
| `frontend/src/pages/ProjectDetail.tsx` | 增加 "⚙️ 项目设置" tab |
| `app/api/qwen3-tts/test_api.py` | 老测试封存为 `TestTTSAPILegacy`；新增 `TestTTSAPISampling`（7 个用例） |

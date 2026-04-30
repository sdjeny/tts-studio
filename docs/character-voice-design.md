# 角色性格贯穿生成链路设计

## 核心思路

角色性格/声音风格应该是一条主线，贯穿三个生成阶段：

```
角色基础档案（base_instruct + description）
        │
        ▼
① LLM 生成大纲 → 角色性格决定故事走向和角色行为
        │
        ▼
② LLM 生成对白 → 角色性格决定说话方式 + 场景情绪 → instruct
        │
        ▼
③ TTS 合成音频 → 根据 style_enabled 决定最终声音
                         ├─ 启用：base_instruct + scene_instruct
                         └─ 关闭：仅 base_instruct
```

## 数据模型

### 角色字段

| 字段 | 类型 | 说明 | 示例 |
|------|------|------|------|
| `base_instruct` | string | 角色基础朗读风格，TTS 底色调 | `"沉稳略带磁性"` `"温和舒缓"` |
| `description` | string | 角色性格/人设描述，供 LLM 理解角色 | `"外表冷漠内心温柔的退伍军人"` |

### 对白新增字段

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `style_enabled` | boolean | `false` | 风格开关：true=角色风格+场景情绪，false=仅角色风格 |
| `instruct` | string | `""` | 场景情绪提示（仅在 style_enabled=true 时叠加） |

### 剧集新增字段

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `style_enabled` | boolean | `false` | 剧集级风格开关（仅作标记，实际以每条对白为准） |

### 项目新增字段

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `updated_at` | string | 同 created_at | 最后修改时间，用于项目列表倒序排列 |

## 风格开关设计

### 默认关闭的原因

风格（instruct 叠加）对 TTS 声音影响较大。默认关闭意味着：
- **默认行为**：只用角色 `base_instruct`，声音稳定一致
- **手动启用**：用户确认后开启，叠加场景情绪，获得更丰富的表现力

### 开关层级

```
剧集 style_enabled（标记用）
  └── 对白 style_enabled（实际控制每条对白的 TTS 提交）
```

- 剧集头部显示风格开关，方便查看/切换（实际修改需逐条对白设置）
- 对白列表中每条对白有独立的风格开关按钮
- TTS 提交时读取**对白级** `style_enabled` 决定 instruct 组合

### TTS instruct 组合逻辑

```python
base_instruct = char.get("base_instruct", "")
scene_instruct = dlg.get("instruct", "")
style_enabled = dlg.get("style_enabled", False)  # 默认关闭

if style_enabled:
    # 启用：角色基础风格 + 场景情绪
    full_instruct = f"{base_instruct}，{scene_instruct}" if base_instruct and scene_instruct else (base_instruct or scene_instruct)
else:
    # 关闭：仅角色基础风格
    full_instruct = base_instruct
```

## 虚拟角色自动创建

旁白（`__旁白__`）和场景（`__场景__`）为虚拟角色，在生成大纲/对白前自动创建为真实角色：

| 角色 | 默认音色 | 默认 base_instruct |
|------|----------|-------------------|
| 旁白 | dylan | `"沉稳叙述、略带磁性"` |
| 场景 | sohee | `"平静舒缓、描述性"` |

用户可在角色面板中修改虚拟角色的音色和风格。

## chars_info 构建

所有生成阶段统一使用 `_build_chars_info(proj, detailed)` 构建角色信息，自动包含虚拟角色：

```python
_VIRTUAL_CHARS = [
    {"id": "__旁白__", "name": "旁白", "voice_id": "dylan", "base_instruct": "沉稳叙述、略带磁性", "description": "旁白叙述者"},
    {"id": "__场景__", "name": "场景", "voice_id": "sohee", "base_instruct": "平静舒缓、描述性", "description": "场景描写"},
]
```

## 批量生成音频（SSE 流式进度）

### 问题
旧方案逐条 HTTP 请求，100+ 条对白会超时。

### 方案
后端 `POST /generate-batch` 返回 SSE 流式响应，逐条提交 TTS 并返回进度：

```
POST /projects/{pid}/episodes/{eid}/generate-batch
Body: { "dialogue_ids": ["dlg1", "dlg2", ...] }

Response (SSE):
data: {"index": 0, "total": 50, "status": "submitted", "task_id": "xxx"}
data: {"index": 1, "total": 50, "status": "submitted", "task_id": "yyy"}
data: {"status": "done", "total": 50, "submitted": 50, "failed_count": 0}
```

### 关键设计
- **不等下载完成**：拿到 task_id 即返回，后台异步下载
- **逐条写 store**：每提交一条立即写回 JSON，刷新即可见进度
- **前端 fetch + ReadableStream**：不用 EventSource（只支持 GET），用 fetch 读 SSE

## 各阶段 Prompt 设计

### 阶段 1：生成大纲（generate-episodes / regenerate-from）

```
角色信息（含性格描述和基础朗读风格）：
- 林默 (voice: aiden, 风格: 沉稳略带磁性, 性格: 退伍军人，外冷内热)
- 苏晴 (voice: sohee, 风格: 温和舒缓, 性格: 温柔坚韧的医生)

要求：角色行为、对话风格需符合其性格特征。
```

### 阶段 2：生成对白（generate-dialogues）

```
角色信息：
- 林默 (基础风格: 沉稳略带磁性, 性格: 外冷内热的退伍军人)
- 苏晴 (基础风格: 温和舒缓, 性格: 温柔坚韧的医生)

instruct 规则：
- instruct 是此条白在此场景下的情绪提示，会叠加到角色基础风格上
- 同一角色的 instruct 基调应保持一致，允许小幅变化
- 示例：'略带紧张'、'低沉叙述'、'温和'
```

### 阶段 3：TTS 合成（submit_tts / generate-batch）

根据 `style_enabled` 决定 instruct 组合（见上方逻辑）。

## 实施清单

### 后端改动

- [x] `app/core/tts.py` — submit_tts 支持 base_instruct + scene_instruct 组合
- [x] `app/api/episodes.py` — chars_info 加入 base_instruct
- [x] `app/api/episodes.py` — 对白生成 prompt 改为场景情绪增量模式
- [x] `app/api/episodes.py` — 大纲生成 prompt 加强角色性格约束
- [x] `app/core/store.py` — add_character / update_character 支持 base_instruct 字段（**extra 透传）
- [x] `app/api/projects.py` — CharacterCreate / CharacterUpdate 加 base_instruct 字段
- [x] `app/api/episodes.py` — refresh 逻辑中 char 查找修复
- [x] `app/core/store.py` — add_dialogue 加 style_enabled 字段（默认 false）
- [x] `app/core/store.py` — create_episode 加 style_enabled 字段（默认 false）
- [x] `app/core/store.py` — create_project 加 updated_at 字段
- [x] `app/core/store.py` — list_projects 按 updated_at 倒序 + 数据迁移
- [x] `app/core/store.py` — touch_project 更新时间戳
- [x] `app/api/projects.py` — 所有修改端点加 touch_project + import
- [x] `app/api/episodes.py` — _VIRTUAL_CHARS + _ensure_virtual_chars_in_project 自动创建虚拟角色
- [x] `app/api/episodes.py` — _build_chars_info 统一构建角色信息（含虚拟角色）
- [x] `app/api/episodes.py` — 所有 chars_info 构建处改用 _build_chars_info
- [x] `app/api/episodes.py` — TTS 提交根据 style_enabled 决定 instruct（单条、批量、刷新重试 3 处）
- [x] `app/api/episodes.py` — generate-batch 改为 SSE 流式响应
- [x] `app/api/projects.py` — CharacterCreate 透传 base_instruct

### 前端改动

- [x] 角色面板加 base_instruct 输入框
- [x] 角色列表展示 base_instruct 预览
- [x] 编辑角色时支持修改 base_instruct
- [x] 项目列表显示 created_at / updated_at
- [x] 批量生成音频改用 SSE，逐条显示进度
- [x] 对白列表每条对白加风格开关按钮
- [x] 剧集头部加风格开关按钮
- [x] Episode / Dialogue 类型加 style_enabled 字段
- [x] updateDialogue / updateEpisode API 类型加 style_enabled

## 兼容说明

- 旧角色没有 base_instruct：退化为只用 LLM instruct（当前行为）
- 旧对白没有 style_enabled：默认为 false（仅角色风格，不叠加场景情绪）
- 旧剧集没有 style_enabled：默认为 false
- 旧项目没有 updated_at：list_projects 首次读取时自动用 created_at 填充

# Issue #88 完成情况调查报告 & 需求规格说明书

## 一、背景

**Issue #88 原始需求**：每个项目要有独立的 `style_enabled` 默认值开关。即用户在项目设置中设定一个全局开关后，后续新建的剧集（episode）和新增的对白（dialogue）应自动继承该默认值，而不是始终硬编码为 `False`。

**PR #89 已合并**，在以下文件中添加了前端 UI 和 API 层支持：
- `app/api/projects.py` — `ProjectUpdate` schema 增加 `default_style_enabled` 字段
- `frontend/src/api.ts` — API 客户端增加 `default_style_enabled` 参数
- `frontend/src/components/ProjectSettings.tsx` — 增加风格开关默认值切换 UI

## 二、当前已实现的部分（API + 前端 UI）

### 2.1 API 层 ✅（已完成）

**文件**: `app/api/projects.py`

| 位置 | 内容 |
|------|------|
| 第57行 | `ProjectUpdate` schema: `default_style_enabled: bool \| None = None` |
| 第124-125行 | PATCH `/projects/{project_id}` 路由：`extra["default_style_enabled"] = body.default_style_enabled` → 调用 `update_project()` |

**说明**：API 层可以接收和保存 `default_style_enabled` 字段到项目数据中。通过 `update_project()` 的 `**extra` 参数最终写入项目 JSON 文件。

### 2.2 前端 API 客户端 ✅（已完成）

**文件**: `frontend/src/api.ts`

| 位置 | 内容 |
|------|------|
| 第125行 | `ProjectUpdate` TypeScript 接口增加 `default_style_enabled?: boolean` |
| 第142行 | `updateProject()` 方法参数增加 `default_style_enabled?: boolean` |
| 第150行 | 请求体组装：`...(default_style_enabled !== undefined && { default_style_enabled })` |

### 2.3 前端 UI ✅（已完成）

**文件**: `frontend/src/components/ProjectSettings.tsx`

| 位置 | 内容 |
|------|------|
| 第378-416行 | 新增"🎭 新建剧集/对白默认风格开关"切换按钮 |
| 第391行 | `const newVal = !project.default_style_enabled;` |
| 第393行 | `await api.updateProject(project.id, undefined, undefined, undefined, undefined, newVal);` |
| 第415行 | UI 提示文案："控制新建剧集和对白时 style_enabled 的默认值。" |

### 2.4 现有 TTS instruct 合并逻辑 ✅（已考虑 style_enabled）

**文件**: `app/api/episodes.py`

| 位置 | 内容 |
|------|------|
| 第341-348行 | `_compose_tts_request()` 函数：读取 `dlg["style_enabled"]` 控制 instruct 合并策略 |
| 第344行 | `style_enabled = dlg.get("style_enabled", False)` — 已正确读取各对白的开关 |

## 三、缺失的部分（Store 层逻辑缺口）

### 问题一：`create_project()` 未初始化 `default_style_enabled` ❌

**文件**: `app/core/store.py`, 第246-273行

```python
def create_project(name: str) -> dict:
    project = {
        "id": pid,
        "name": name,
        ...
        "tts_defaults": _load_tts_defaults(),
        "gen_defaults": _load_gen_defaults(),
        "story_settings": {...},
        # ❌ 缺少 default_style_enabled 字段
    }
```

`default_style_enabled` 未写入初始项目字典。新创建的项目中该字段缺失。

### 问题二：`list_projects()` 未 backfill `default_style_enabled` ❌

**文件**: `app/core/store.py`, 第195-239行

```python
# 已有 backfill 逻辑但未包含 default_style_enabled
if not p.get("gen_defaults"):
    p["gen_defaults"] = _load_gen_defaults()
if not p.get("story_settings"):
    p["story_settings"] = {"description": "", "extra": "", "story_arc": ""}
# ❌ 缺少 default_style_enabled 的 backfill
```

旧项目数据未自动补充 `default_style_enabled` 字段。

### 问题三：`create_episode()` 硬编码 `style_enabled: False` ❌

**文件**: `app/core/store.py`, 第425-441行

```python
def create_episode(project_id: str, title: str, raw_text: str = "") -> dict | None:
    project = _read_project(project_id)
    ...
    ep = {
        ...
        "style_enabled": False,  # ❌ 硬编码 False，未读取 project.default_style_enabled
        ...
    }
```

### 问题四：`add_dialogue()` 硬编码 `style_enabled: False` ❌

**文件**: `app/core/store.py`, 第476-508行

```python
def add_dialogue(project_id: str, episode_id: str, character_id: str,
                 text: str, order: int = 0, instruct: str = "") -> dict | None:
    ...
    dlg = {
        ...
        "style_enabled": False,  # ❌ 硬编码 False，未读取 project.default_style_enabled
        ...
    }
```

### 问题五：API 层 `create_episode` 和 `add_dialogue` 路由未传递默认值 ❌

**文件**: `app/api/episodes.py`

第110-114行（创建剧集）：
```python
@router.post("/projects/{project_id}/episodes")
async def api_create_episode(project_id: str, body: EpisodeCreate):
    ...
    return create_episode(project_id, body.title)  # ❌ 未传入 style_enabled 默认值
```

第169-173行（新增对白）：
```python
@router.post("/projects/{project_id}/episodes/{episode_id}/dialogues")
async def api_add_dialogue(project_id: str, episode_id: str, body: DialogueCreate):
    ...
    return add_dialogue(project_id, episode_id, body.character_id, body.text, body.order, body.instruct or "")
    # ❌ 未传入 style_enabled 默认值
```

### 问题六：`dialogue_service.py` 中 AI 生成对白也硬编码 `False` ❌

**文件**: `app/core/dialogue_service.py`

第370行和679行：
```python
dlg = add_dialogue(self.project_id, self.episode_id, char_id, text, idx, instruct)
# ❌ 同样未传入 style_enabled，继承了 store.py 的硬编码 False
```

## 四、补充方案（具体改什么）

### 方案 A：在 Store 层内部自动读取 project 默认值（推荐，改动最小）

核心思路：`create_episode()` 和 `add_dialogue()` 在创建时主动读取 project 的 `default_style_enabled` 字段，而不是依赖调用方传入。

#### A-1: `create_project()` — 初始化默认值

**文件**: `app/core/store.py`, `create_project()` 函数

在 `story_settings` 后追加：
```python
"default_style_enabled": False,
```

#### A-2: `list_projects()` — 添加 backfill

**文件**: `app/core/store.py`, `list_projects()` 函数

在 `story_settings` backfill 逻辑旁追加：
```python
if "default_style_enabled" not in p:
    p["default_style_enabled"] = False
    _write_project(entry["id"], p)
    dirty = True
```

并在 `entry` 组装处追加：
```python
entry["default_style_enabled"] = p.get("default_style_enabled", False)
```

#### A-3: `create_episode()` — 读取 project 默认值

**文件**: `app/core/store.py`, `create_episode()` 函数，第433行

将：
```python
"style_enabled": False,
```
改为：
```python
"style_enabled": project.get("default_style_enabled", False),
```

#### A-4: `add_dialogue()` — 读取 project 默认值

**文件**: `app/core/store.py`, `add_dialogue()` 函数，第499行

将：
```python
"style_enabled": False,
```
改为：
```python
"style_enabled": project.get("default_style_enabled", False),
```

### 方案 B（可选补充）：在 API 层显式传递

在 `app/api/episodes.py` 的 `api_create_episode()` 和 `api_add_dialogue()` 中读取 project 的 `default_style_enabled` 并显式传给 store 函数，使逻辑更透明。

#### B-1: `api_create_episode()`

```python
@router.post("/projects/{project_id}/episodes")
async def api_create_episode(project_id: str, body: EpisodeCreate):
    project = get_project(project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    default_style = project.get("default_style_enabled", False)
    return create_episode(project_id, body.title, default_style_enabled=default_style)
```

同时 `create_episode()` 签名改为接受 `default_style_enabled` 参数。

#### B-2: `api_add_dialogue()`

类似修改，在 `add_dialogue()` 签名中增加 `style_enabled` 参数。

### 方案 C（影响面最小）：保留 store 层纯净，仅在 API 路由层补默认值

如果不想修改 `create_episode()` / `add_dialogue()` 签名，可以在 API 路由中先创建后修补：

```python
@router.post("/projects/{project_id}/episodes")
async def api_create_episode(project_id: str, body: EpisodeCreate):
    project = get_project(project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    ep = create_episode(project_id, body.title)
    if ep:
        default_val = project.get("default_style_enabled", False)
        if default_val:
            update_episode(project_id, ep["id"], style_enabled=True)
    return ep
```

**不推荐**：每次创建新剧集都得两次写操作，且创建对白不好处理（无批量 update API）。

## 五、验收标准

| # | 验收项 | 验证方法 |
|---|--------|----------|
| 1 | 新建项目时，项目数据包含 `default_style_enabled: false` | 发送 `POST /projects`，查看返回 JSON 含该字段 |
| 2 | 通过 PATCH 修改 `default_style_enabled` 后，GET 项目返回正确的值 | 发送 `PATCH /projects/{id}` 设置 `default_style_enabled: true`，再 GET 确认 |
| 3 | 当 `default_style_enabled = false` 时，新建剧集的 `style_enabled` 为 `false` | `POST /projects/{id}/episodes` → 返回的 episode 中 `style_enabled === false` |
| 4 | 当 `default_style_enabled = true` 时，新建剧集的 `style_enabled` 为 `true` | 同上，预期 `style_enabled === true` |
| 5 | 当 `default_style_enabled = false` 时，新增对白的 `style_enabled` 为 `false` | `POST .../dialogues` → 返回的 dialogue 中 `style_enabled === false` |
| 6 | 当 `default_style_enabled = true` 时，新增对白的 `style_enabled` 为 `true` | 同上，预期 `style_enabled === true` |
| 7 | 旧项目（升级前创建）会自动 backfill `default_style_enabled: false` | 访问旧项目列表，数据中自动补全该字段 |
| 8 | 前端 UI 的开关状态与后端数据一致 | 在 ProjectSettings 切换开关 → 刷新页面 → 开关状态保持 |
| 9 | AI 生成对白时（dialogue_service.py），新建对白的 `style_enabled` 也遵循项目默认值 | 在 `default_style_enabled = true` 项目中使用 AI 生成，检查生成的对白是否 `style_enabled: true` |
| 10 | 已有剧集/对白的 `style_enabled` 不受影响（只影响新建的） | 修改 `default_style_enabled` 后，已存在的剧集/对白值不变化 |

## 六、总结

**Issue #88 未完成。** PR #89 只完成了 API 数据模型+前端 UI，**关键的 store 层核心逻辑 (`create_episode()` 和 `add_dialogue()` 的硬编码 `False`) 完全没有改动**，导致：

1. 用户在 ProjectSettings 页面切换开关后，新建的剧集和对白**仍然**是 `style_enabled: False`
2. 用户感知：开关不管用，等于功能半残

**修复工作量极低**：仅需修改 store.py 中 `create_episode()` 和 `add_dialogue()` 共2行代码（将 `False` 改为 `project.get("default_style_enabled", False)`），加上 `create_project()` 和 `list_projects()` 的 backfill 共约5行代码。推荐方案 A 即可完整解决。

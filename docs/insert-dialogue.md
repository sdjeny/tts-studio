# 插入对白功能设计

## 概述

在已有对白列表中，点击某条白后的 `+` 按钮，在该条之后插入一条新对白。插入后自动重排后续对白的 `order`，新对白自动进入编辑态，支持失败精确回滚。

## 前端交互流程

### 用户操作

1. 点击某条对白操作栏的 `+` 按钮（绿色）
2. 该条之后立即出现一个 placeholder 白（空文本）
3. placeholder 自动进入编辑态（textarea 弹出，自动聚焦）
4. 用户输入内容后保存，或取消回滚

### 核心机制：localDialogues state

**问题**：插入 placeholder 后，如果调用 `onChange()` 触发 API 重新加载，placeholder 会被服务端返回的真实数据覆盖（因为 placeholder 不在服务端）。

**方案**：用 `localDialogues` state 做本地覆盖层：

```typescript
const [localDialogues, setLocalDialogues] = useState<Dialogue[] | null>(null);

// 渲染时：localDialogues 优先，否则用 episode.dialogues
const displayDialogues = localDialogues || episode.dialogues;
```

- **插入时**：`setLocalDialogues(newDialogues)` 触发重渲染，不调用 `onChange()`
- **成功后**：用服务端返回的真实对话替换 placeholder，然后 `setLocalDialogues(null)` 释放本地覆盖
- **失败时**：`setLocalDialogues(null)` + `onChange()` 重新加载服务端数据

### autoEditIds 自动编辑态

插入成功后，新对白自动进入编辑态：

- `autoEditIds: Set<string>` — 存储需要自动编辑的对白 ID
- `DialogueRow` 组件初始化时检查 `autoEditIds.has(dlg.id)`，自动设置 `editing=true`
- `useEffect` 监听 autoEditIds，自动聚焦 textarea
- 用户保存/取消后调用 `onAutoEditConsumed(id)` 从集合中移除

### 失败精确回滚

插入 API 失败时：

1. `setLocalDialogues(null)` — 清除本地覆盖
2. 用 `episode.dialogues` 原始数据覆盖（从排序副本恢复）
3. `onChange()` 重新加载服务端数据
4. 显示错误 toast

### placeholder ID 唯一性

使用 `Date.now().toString(36) + Math.random().toString(36).slice(2, 10)` 确保唯一，前缀 `__placeholder__` 便于识别和过滤。

## 后端 API

### POST /api/projects/{id}/episodes/{eid}/dialogues/insert

**请求体** (`DialogueInsert` schema)：

```json
{
  "after_dialogue_id": "dlg_xxx",
  "character_id": "char_yyy",
  "text": "",
  "instruct": ""
}
```

- `after_dialogue_id`：在此对白之后插入（必填）
- `character_id`：为空时继承目标对白的角色（方便快速插入同角色对白）
- `text`：对白文本（可为空）
- `instruct`：场景情绪提示（可为空）

**返回**：

```json
{
  "ok": true,
  "dialogue": { ... },
  "affected": 3
}
```

- `affected`：被移动的对白数量（order 被 +1 的对白数）

**错误**：
- `404`：目标对白不存在

### POST /api/projects/{id}/episodes/{eid}/dialogues/reorder

**行为**：
- 按当前 `order` 排序，重新分配连续的 0, 1, 2, ... 序列
- 修复历史遗留的 `order` 重复或跳号问题
- 无需请求体，幂等操作

**返回**：

```json
{
  "ok": true,
  "dialogues": 25
}
```

## 存储层逻辑

### insert_dialogue_after()

位置：`app/core/store.py`

1. 找到目标对白在列表中的索引 `idx`
2. 从 `idx+1` 开始，将所有对白的 `order` 加 1
3. 计算新对白的 `order = target.order + 1`
4. 在 `idx+1` 位置插入新对白
5. 写回 JSON 文件

返回 `(new_dialogue, affected_count)`，找不到目标时返回 `(None, 0)`。

### reorder_episode_dialogues()

位置：`app/core/store.py`

1. 按当前 `order` 排序（order 相同时按 `created_at` 排序）
2. 重新分配连续 order：0, 1, 2, ...
3. 写回 JSON 文件

返回对白总数。用于修复历史遗留的 order 重复问题。

### 角色 fallback（M-3 + m-1 修复）

**问题**：插入时指定的 `character_id` 在角色列表中找不到对应角色（例如角色已被删除），导致 `character_name` 显示 `⚠ 角色异常(xxx)`。

**修复**：当 `character_id` 在 `p["characters"]` 中无匹配且项目有至少一个角色时，fallback 到项目第一个角色的 ID 和 name。

```python
if not char_name and p["characters"]:
    char_name = p["characters"][0]["name"]
    character_id = p["characters"][0]["id"]
```

这样即使角色被删除，插入操作也不会产生异常显示。

## 架构演进

### 旧方案：forceRender（已废弃）

```typescript
const [forceRender, setForceRender] = useState(0);
const onChange = () => setForceRender(n => n + 1);
```

**问题**：插入 placeholder 后，`onChange` 触发 `load` 会覆盖 placeholder（因为 `load` 更新 `episode.dialogues`，而 placeholder 不在服务端）。

### 新方案：localDialogues state

```typescript
const [localDialogues, setLocalDialogues] = useState<Dialogue[] | null>(null);
```

**优势**：
- 本地 state 覆盖显示，不依赖 `episode.dialogues`
- 成功/失败后精确控制何时释放本地覆盖
- 支持失败精确回滚
- 无闪烁（placeholder 立即出现，无需等待 API）

## order 字段设计

- `order` 为整数，从 0 开始
- 每部剧集的 `dialogues` 列表按 `order` 排序后展示
- 插入时通过"后移"操作腾出位置，保证唯一性和连续性
- `reorder` 端点可手动修复碎片

## 兼容性

- 旧数据可能没有 `order` 字段或为 null：`add_dialogue` 时自动计算（`max(order) + 1`）
- 旧数据可能存在重复 `order`：`reorder` 端点可手动修复
- `insert` 端点要求目标 `after_dialogue_id` 存在，否则返回 404

## 实施清单

### 后端

- [x] `app/api/episodes.py` — 新增 `POST /dialogues/insert` 端点
- [x] `app/api/episodes.py` — 新增 `POST /dialogues/reorder` 端点
- [x] `app/core/store.py` — `insert_dialogue_after()` 函数：在指定对白后插入，自动重排 order
- [x] `app/core/store.py` — `reorder_episode_dialogues()` 函数：重建 order 连续性
- [x] `app/core/store.py` — 角色 fallback：character_id 找不到时 fallback 到第一个角色（M-3 + m-1 修复）
- [x] `app/api/episodes.py` — `DialogueInsert` schema 定义

### 前端

- [x] `frontend/src/components/DialogueList.tsx` — `handleInsert` 函数：placeholder 机制 + localDialogues state
- [x] `frontend/src/components/DialogueList.tsx` — `autoEditIds` 机制：插入后自动进入编辑态
- [x] `frontend/src/components/DialogueList.tsx` — 失败精确回滚：`setLocalDialogues(null)` + `onChange()`
- [x] `frontend/src/components/DialogueList.tsx` — 每条对白添加 `+` 插入按钮
- [x] `frontend/src/api.ts` — 封装 `insertDialogue` API 调用
# 需求规格书：LLM 任务面板 UI 修改

> **项目**: tts-studio
> **文件**: `frontend/src/components/TaskPanel.tsx`, `frontend/src/api.ts`
> **对应后端**: `app/api/task_routes.py` — 取消端点已实现
> **修改范围**: 前端仅修改 2 个文件，无后端改动

---

## 1. 修改点清单

| # | 位置 | 改动 | 说明 |
|---|------|------|------|
| 1 | `TaskPanel.tsx:144` | 面板标题文本 | `"📋 LLM 生成任务"` → `"后台任务"` |
| 2 | `TaskPanel.tsx:153` | 空状态提示文本 | `"暂无 LLM 生成任务记录"` → `"暂无后台任务记录"` |
| 3 | `api.ts` | 新增 `cancelLLMTask` 方法 | 调用后端 `POST /projects/{pid}/llm/task/{task_id}/cancel` |
| 4 | `TaskPanel.tsx` | 新增"终止"按钮 | 在运行中任务卡片上，含 loading / 错误提示状态管理 |
| 5 | `TaskPanel.tsx` | 导入 & 状态 | 引入 `useCallback`（可选）、新增 `cancellingMap` 状态 |

---

## 2. 面板标题及空状态文案修改

### 2.1 标题（`TaskPanel.tsx` ~L144）

```tsx
// 修改前
📋 LLM 生成任务

// 修改后
后台任务
```

### 2.2 空状态提示（`TaskPanel.tsx` ~L153）

```tsx
// 修改前
暂无 LLM 生成任务记录

// 修改后
暂无后台任务记录
```

> **说明**: 标题文案的去"LLM"化是为了与面板后续可能承接的非 LLM 类后台任务（音频合成、批量导出等）保持一致。

---

## 3. api.ts 新增 cancelLLMTask 方法

在 `api.ts` 的 `api` 对象中 `getLLMTask` 方法之后新增（约 L384）：

```typescript
// 取消一个正在运行的 LLM 任务
cancelLLMTask: (pid: string, taskId: string) =>
  request<any>(`/projects/${pid}/llm/task/${taskId}/cancel`, { method: "POST" }),
```

- **HTTP 方法**: `POST`（与后端 `@router.post(...)` 一致）
- **返回类型**: `Promise<any>` — 后端返回已取消任务的 JSON 对象（`{ "status": "cancelled", "task_id": "..." }` 或包含完整任务信息的对象）
- **错误处理**: 由 `request` 函数统一抛 `Error`，下层消费时 catch

---

## 4. TaskPanel.tsx 新增"终止"按钮

### 4.1 新增状态变量

在组件顶部（约 L12）新增：

```typescript
const [cancellingMap, setCancellingMap] = useState<Record<string, boolean>>({});
```

用途：记录每个 task_id 是否正在执行取消请求，用于禁用按钮（防重复点击）和展示 loading 态。

### 4.2 取消回调函数

在 `fetchTasks` 之后新增 `handleCancel` 函数：

```typescript
const handleCancel = async (taskId: string) => {
  if (cancellingMap[taskId]) return; // 防重复点击
  setCancellingMap(prev => ({ ...prev, [taskId]: true }));
  try {
    await api.cancelLLMTask(projectId, taskId);
    // 取消成功后立即刷新任务列表
    await fetchTasks();
  } catch (e: any) {
    // 404 / 409 友好提示（见第5节）
    const msg = e?.message || "取消失败";
    if (msg.includes("404")) {
      alert("任务不存在，可能已被移除");
    } else if (msg.includes("409")) {
      if (msg.includes("已完成")) {
        alert("任务已完成，无需取消");
      } else if (msg.includes("已取消")) {
        alert("任务已被取消，无需重复操作");
      } else {
        alert(msg);
      }
    } else {
      alert(`取消失败: ${msg}`);
    }
  } finally {
    setCancellingMap(prev => ({ ...prev, [taskId]: false }));
  }
};
```

### 4.3 按钮渲染位置

在任务卡片 `<div style={cardStyle}>` 内部的第 1 个 `rowStyle` 行（约 L176 `flex: 1` 占位之后，展开/折叠按钮之前），增加条件渲染：

```tsx
{(task.status === "running" || task.status === "running:generating" || task.status === "pending") && (
  <button
    onClick={() => handleCancel(task.id || task.task_id)}
    disabled={cancellingMap[task.id || task.task_id]}
    style={{
      background: "transparent",
      border: "1px solid #ef4444",
      color: cancellingMap[task.id || task.task_id] ? "#6b7280" : "#ef4444",
      borderRadius: 4,
      padding: "2px 8px",
      cursor: cancellingMap[task.id || task.task_id] ? "not-allowed" : "pointer",
      fontSize: 11,
      fontWeight: 500,
    }}
  >
    {cancellingMap[task.id || task.task_id] ? "⏳ 终止中..." : "终止"}
  </button>
)}
```

> **说明**: `task.id` 和 `task.task_id` 兼容后端可能的两种字段命名。

---

## 5. 按钮交互逻辑

### 5.1 显示条件

| 任务状态 | 显示"终止"按钮 | 说明 |
|----------|:--------------:|------|
| `running` | ✅ | 正在运行 |
| `running:generating` | ✅ | LLM 生成中 |
| `pending` | ✅ | 排队等待中 |
| `complete` | ❌ | 已完成 |
| `error` | ❌ | 已失败 |
| `timeout` | ❌ | 已超时 |
| `cancelled` | ❌ | 已取消 |
| 其他未知状态 | ❌ | 保守策略，不显示 |

代码上即：

```typescript
const isActive = task.status === "running"
  || task.status === "running:generating"
  || task.status === "pending";
```

仅在 `isActive` 为 true 时渲染按钮。

### 5.2 交互状态

| 用户操作阶段 | 按钮外观 | disabled | 文案 |
|-------------|---------|---------|------|
| 初始态 | 红色边框文字 | `false` | "终止" |
| 点击后请求中 | 灰色边框文字 | `true` | "⏳ 终止中..." |
| 请求成功 | （任务刷新后按钮消失） | — | — |
| 请求失败（404/409） | 恢复可点击 | `false` | "终止" + alert 提示 |
| 其他网络错误 | 恢复可点击 | `false` | "终止" + alert 提示 |

### 5.3 防重复处理

- `cancellingMap` 为 `Record<taskId, boolean>`，点击后立即置 true 并禁用按钮
- 请求完成后（无论成功/失败）在 `finally` 块中置 false
- 若 `cancellingMap[taskId] === true`，`handleCancel` 入口处直接 return

---

## 6. 调用后端接口的异常处理

### 6.1 后端接口详情

- **路径**: `POST /projects/{project_id}/llm/task/{task_id}/cancel`
- **实现位置**: `app/api/task_routes.py:27`
- **可能返回的 HTTP 错误**:

| 状态码 | 后端条件 | 后端 message |
|--------|---------|-------------|
| 404 | 任务不存在 | `"Task not found"` |
| 409 | 任务已完成 | `"任务已完成，不允许取消"` |
| 409 | 任务已取消 | `"任务已取消"` |

### 6.2 前端处理策略

在前端 catch 块中解析 `e.message`（由 `request` 函数抛出的 `"${status}: ${body}"` 格式）：

```
404 → alert("任务不存在，可能已被移除")
409 (已完成) → alert("任务已完成，无需取消")
409 (已取消) → alert("任务已被取消，无需重复操作")
其它 → alert(`取消失败: ${msg}`)
```

> **注意**: 由于后端直接抛 `HTTPException`，415/422 等参数错误不会出现（URL 路径参数由 FastAPI 自动校验）。

---

## 7. 影响域分析

| 受影响的文件 | 改动类型 | 风险等级 |
|-------------|---------|---------|
| `TaskPanel.tsx` | 标题文案 + 新增按钮 + 状态 | 低 — 纯 UI 逻辑，不涉及数据层 |
| `api.ts` | 新增方法 | 低 — 不影响已有方法签名 |
| 无其他文件 | — | — |

**无需修改后端代码**：后端 `/projects/{project_id}/llm/task/{task_id}/cancel` 端点已完整实现（POST 方法，含 404/409 错误处理）。

**无需修改路由或样式文件**：按钮样式使用内联 style，不依赖 CSS 模块或全局样式表。

---

## 8. 安全标注

> ⚠️ **安全警告**
>
> 本文档为需求规格说明书，**禁止**在本文档中直接嵌入 terminal 命令、shell 脚本或任何可执行代码片段。
> 前端修改应通过 IDE 或手动编辑方式对 `TaskPanel.tsx` 和 `api.ts` 进行，严禁直接在终端使用 `sed`、`patch` 等命令修改生产或开发环境中的上述文件。
> 修改完成后应经过 `npm run build`（或相应构建命令）验证无编译错误。

---

## 附录 A：修改前后对比（关键代码段）

### A.1 面板标题

```diff
- 📋 LLM 生成任务
+ 后台任务
```

### A.2 空状态

```diff
- 暂无 LLM 生成任务记录
+ 暂无后台任务记录
```

### A.3 api.ts 新增方法

```diff
   getLLMTask: (pid: string, taskId: string) =>
     request<any>(`/projects/${pid}/llm/task/${taskId}`),
+  cancelLLMTask: (pid: string, taskId: string) =>
+    request<any>(`/projects/${pid}/llm/task/${taskId}/cancel`, { method: "POST" }),
```

### A.4 TaskPanel.tsx 按钮插入位置

在 `flex: 1` 占位 div（约 L176）与展开/折叠按钮（约 L182）之间插入。

```diff
               <div style={{ flex: 1 }} />
+              {(task.status === "running" || task.status === "running:generating" || task.status === "pending") && (
+                <button ... >终止</button>
+              )}
               <button onClick={() => setExpandedTask(isExpanded ? null : `${i}`)}
```

---

*文档版本: v1.0*
*生成日期: 2026-05-29*

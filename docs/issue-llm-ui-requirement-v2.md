# 需求规格书：LLM 任务面板 UI 精简修改

> 项目：tts-studio  
> 涉及文件：`frontend/src/api.ts`、`frontend/src/components/TaskPanel.tsx`  
> 改动范围：极小化，仅 2 个修改点。面板标题（L144）与空状态（L153）**不改**。

---

## 修改点 ①：任务卡片类型标签统一为"后台任务"

**文件**：`TaskPanel.tsx` L84-94

**现状**：

```tsx
const typeLabel = (t: string) => {
  const labels: Record<string, string> = {
    "outline": "生成大纲",
    "dialogues": "生成对白",
    "dialogue_generation": "生成对白",
    "continuation": "续写剧集",
    "generate_batch": "批量生成音频",
    "refresh": "刷新状态",
  };
  return labels[t] || t;
};
```

**目标**：函数体简化为直接返回固定字符串 `"后台任务"`，不再做任何映射。

```tsx
const typeLabel = (_t: string) => "后台任务";
```

**效果**：
- 每个任务卡片 L172 `<span style={{ fontWeight: 500 }}>{tt}</span>` 统一显示为"后台任务"
- 不再暴露"生成大纲"/"生成对白"/"续写剧集"等具体类型信息

---

## 修改点 ②：新增终止按钮

### 2.1 api.ts — 新增 `cancelLLMTask` 方法

**文件**：`frontend/src/api.ts`，在 `listLLMTasks` / `getLLMTask`（L378-383）之后追加。

**后端路由**：`POST /projects/{project_id}/llm/task/{task_id}/cancel`（已在 `task_routes.py` 中实现）

```ts
// 取消 LLM 任务
cancelLLMTask: (pid: string, taskId: string) =>
  request<any>(`/projects/${pid}/llm/task/${taskId}/cancel`, {
    method: "POST",
  }),
```

### 2.2 TaskPanel.tsx — 状态 + 回调 + 按钮渲染

#### 2.2.1 新增状态（L11 附近）

```tsx
const [cancellingMap, setCancellingMap] = useState<Record<string, boolean>>({});
```

#### 2.2.2 handleCancel 回调（在 fetchTasks 之后、return 之前添加）

```tsx
const handleCancel = async (taskId: string) => {
  setCancellingMap(prev => ({ ...prev, [taskId]: true }));
  try {
    await api.cancelLLMTask(projectId, taskId);
    // 取消成功后刷新列表
    await fetchTasks();
  } catch (e: any) {
    const msg = e.message || "";
    // 404: 任务不存在或已结束 → 静默刷新
    if (msg.includes("404:")) {
      await fetchTasks();
      return;
    }
    // 409: 任务已结束/无法取消 → 提示
    if (msg.includes("409:")) {
      alert(msg.slice(4));
      await fetchTasks();
      return;
    }
    alert(msg || "取消失败");
  } finally {
    setCancellingMap(prev => ({ ...prev, [taskId]: false }));
  }
};
```

#### 2.2.3 按钮渲染（在 L174 时间戳之后、flex 占位之前插入）

在卡片 `rowStyle` 的 `<span style={{ color: "#64748b", fontSize: 11 }}>` （日期）之后、`<div style={{ flex: 1 }} />` 之前，插入终止按钮：

```tsx
{(task.status === "running" || task.status === "running:generating" || task.status === "pending") && (
  <button
    onClick={() => handleCancel(task.id || task.task_id)}
    disabled={cancellingMap[task.id || task.task_id]}
    style={{
      background: "transparent",
      border: "1px solid #ef4444",
      color: cancellingMap[task.id || task.task_id] ? "#9ca3af" : "#ef4444",
      borderRadius: 6,
      padding: "2px 10px",
      cursor: cancellingMap[task.id || task.task_id] ? "not-allowed" : "pointer",
      fontSize: 11,
      fontWeight: 500,
    }}
  >
    {cancellingMap[task.id || task.task_id] ? "⏳ 取消中..." : "✕ 终止"}
  </button>
)}
```

**约束**：
- 仅当 `task.status` 为 `running` / `running:generating` / `pending` 时显示
- 红色边框（`#ef4444`）、红色文字
- 点击后立即 disable（`cancellingMap`），防止重复提交
- 404 → 静默刷新列表（任务已消失）
- 409 → 友好 alert 提示（任务已结束），刷新列表
- 其他错误 → alert 错误信息

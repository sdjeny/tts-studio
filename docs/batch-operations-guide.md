# 批量处理操作进度指导

## 设计原则

1. **不等完成即返回**：拿到 task_id 就算成功，后台异步处理
2. **SSE 流式进度**：后端用 `StreamingResponse(text/event-stream)`，前端用 `fetch` 读 `ReadableStream`
3. **乐观更新**：前端先更新 UI 状态，再发请求，失败时回滚
4. **批量操作粒度**：超过 10 条的操作必须有进度提示

## SSE 通信协议

### 后端响应格式

```
HTTP/1.1 200 OK
Content-Type: text/event-stream
Cache-Control: no-control
X-Accel-Buffering: no

data: {"index": 0, "total": 50, "status": "submitted", "task_id": "xxx"}

data: {"index": 1, "total": 50, "status": "error", "error": "角色不存在"}

data: {"status": "done", "total": 50, "submitted": 49, "failed_count": 1}
```

### 消息类型

| status | 说明 | 字段 |
|--------|------|------|
| `submitted` | 单条处理成功 | `index`, `total`, `task_id` |
| `error` | 单条处理失败 | `index`, `total`, `error` |
| `done` | 全部完成 | `total`, `submitted`, `failed_count` |

### 前端接收范式

```typescript
const resp = await fetch(url, {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ ... }),
});
const reader = resp.body!.getReader();
const decoder = new TextDecoder();
let buf = "";

while (true) {
  const { value, done } = await reader.read();
  if (done) break;
  buf += decoder.decode(value, { stream: true });

  const parts = buf.split("\n\n");
  buf = parts.pop() || ""; // 保留不完整的最后一段

  for (const part of parts) {
    const line = part.trim();
    if (!line.startsWith("data: ")) continue;
    const msg = JSON.parse(line.slice(6));
    if (msg.status === "submitted") {
      // 更新进度: submitted/total
    } else if (msg.status === "error") {
      // 显示错误
    } else if (msg.status === "done") {
      // 显示汇总，刷新数据
    }
  }
}
```

## 需要进度的批量操作清单

### 已实现 ✅

| # | 操作 | 端点 | 进度方式 |
|---|------|------|----------|
| 1 | 批量生成音频 | `POST /generate-batch` | SSE 流式 |

### 待实现 ⬜

| # | 操作 | 端点 | 优先级 | 预计复杂度 |
|---|------|------|--------|-----------|
| 2 | 批量刷新状态 | `POST /refresh-batch` | **高** | 低（逐条调 refresh，SSE 返回） |
| 3 | 批量换角色 | `POST /batch-replace-character` | **高** | 中（遍历所有剧集对白，SSE 返回） |
| 4 | 批量添加对白 | `POST /dialogues/batch` | 中 | 低（通常条数少） |
| 5 | 导入对白 | `POST /import` | 中 | 低 |
| 6 | 导入项目 | `POST /projects/{pid}/import` | 中 | 中（嵌套循环） |
| 7 | 清空剧集对白 | `DELETE /purge-dialogues` | 中 | 低（删除文件+记录） |
| 8 | 生成剧集大纲 | `POST /generate-episodes` | 低 | 高（LLM 调用，需流式输出） |
| 9 | 生成对白 | `POST /generate-dialogues` | 低 | **最高**（多阶段 LLM，需分阶段进度） |
| 10 | 重新生成大纲 | `POST /regenerate-from` | 低 | 高（删除文件 + LLM） |

## 实现模板

### 后端：SSE 端点模板

```python
from fastapi.responses import StreamingResponse
import json as _json

@router.post("/projects/{pid}/episodes/{eid}/xxx-batch")
async def api_batch_xxx(project_id: str, episode_id: str, body: SomeRequest):
    ep = get_episode(project_id, episode_id)
    if not ep:
        raise HTTPException(404, "Episode not found")

    total = len(ep["dialogues"])

    async def _stream():
        success = 0
        failed = 0
        for i, dlg in enumerate(ep["dialogues"]):
            try:
                # ... 处理单条 ...
                success += 1
                yield f"data: {_json.dumps({'index': i, 'total': total, 'status': 'ok'}, ensure_ascii=False)}\n\n"
            except Exception as e:
                failed += 1
                yield f"data: {_json.dumps({'index': i, 'total': total, 'status': 'error', 'error': str(e)}, ensure_ascii=False)}\n\n"

        yield f"data: {_json.dumps({'status': 'done', 'total': total, 'success': success, 'failed': failed}, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        _stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
```

### 前端：批量操作 UI 模板

```tsx
const [batchProgress, setBatchProgress] = useState<{
  running: boolean;
  current: number;
  total: number;
  errors: string[];
}>({ running: false, current: 0, total: 0, errors: [] });

const runBatch = async (ids: string[]) => {
  setBatchProgress({ running: true, current: 0, total: ids.length, errors: [] });

  const resp = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ dialogue_ids: ids }),
  });
  if (!resp.ok) {
    setBatchProgress(p => ({ ...p, running: false }));
    onError("请求失败: " + resp.statusText);
    return;
  }

  const reader = resp.body!.getReader();
  const decoder = new TextDecoder();
  let buf = "";

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buf += decoder.decode(value, { stream: true });

    const parts = buf.split("\n\n");
    buf = parts.pop() || "";

    for (const part of parts) {
      const line = part.trim();
      if (!line.startsWith("data: ")) continue;
      const msg = JSON.parse(line.slice(6));

      if (msg.status === "ok" || msg.status === "submitted") {
        setBatchProgress(p => ({ ...p, current: msg.index + 1 }));
      } else if (msg.status === "error") {
        setBatchProgress(p => ({ ...p, errors: [...p.errors, msg.error] }));
      } else if (msg.status === "done") {
        setBatchProgress(p => ({ ...p, running: false }));
        onChange(); // 刷新数据
      }
    }
  }
};
```

### 前端：进度条组件

```tsx
function BatchProgressBar({ progress }: { progress: { running: boolean; current: number; total: number; errors: string[] } }) {
  if (!progress.running && progress.current === 0) return null;
  const pct = progress.total > 0 ? Math.round((progress.current / progress.total) * 100) : 0;

  return (
    <div style={{ margin: "8px 0" }}>
      <div style={{ display: "flex", justifyContent: "space-between", fontSize: 12, color: "#94a3b8", marginBottom: 4 }}>
        <span>{progress.running ? `处理中... ${progress.current}/${progress.total}` : `完成 ${progress.current}/${progress.total}`}</span>
        <span>{pct}%</span>
      </div>
      <div style={{ height: 4, background: "#1e293b", borderRadius: 2, overflow: "hidden" }}>
        <div style={{
          height: "100%",
          width: `${pct}%`,
          background: progress.errors.length > 0 ? "#f59e0b" : "#22c55e",
          transition: "width 0.3s",
        }} />
      </div>
      {progress.errors.length > 0 && (
        <div style={{ fontSize: 11, color: "#f59e0b", marginTop: 4 }}>
          ⚠ {progress.errors.length} 条失败
        </div>
      )}
    </div>
  );
}
```

## 各操作实现要点

### 批量刷新状态 (`refresh-batch`)

- 逐条调用已有的 `_try_download_audio` 逻辑
- 每条查 TTS 状态，完成则下载，失败则标记
- SSE 返回每条结果

### 批量换角色 (`batch-replace-character`)

- 遍历目标剧集的所有对白
- 匹配 `character_name` 的旧角色，更新为新角色
- SSE 返回每剧集的更新计数
- 注意：同时更新 `character_id` 和 `character_name`

### 生成对白 (`generate-dialogues`) — 最高复杂度

- 阶段 1：LLM 规划幕结构 → 返回进度 `"planning"`
- 阶段 2：逐幕生成对白 → 每幕返回 `"generating_scene"`
- 阶段 3：批量创建对白记录 → `"saving"`
- 使用 SSE 分阶段推送进度

## 注意事项

1. **不要用 EventSource**：EventSource 只支持 GET，批量操作需要 POST 传 body，必须用 `fetch` + `ReadableStream`
2. **api.ts 的 `request<>` 包装不支持流式**：批量操作要直接用 `fetch`，绕过 api.ts
3. **后台任务用 `asyncio.create_task`**：SSE 返回后，下载/处理继续在后台跑
4. **store 写入频率**：每条写完立即 `_write`，避免批量最后一次性写导致数据丢失
5. **错误不中断**：单条失败继续处理其余条，最后汇总报告

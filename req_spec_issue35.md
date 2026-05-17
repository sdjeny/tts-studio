## 需求规格书 — Issue #35：对白生成后台任务改造

---

### 1. 项目背景与目标

#### 1.1 背景
`tts-studio` 的 `POST /api/projects/{project_id}/episodes/{episode_id}/generate-dialogues` 端点当前使用 SSE（Server-Sent Events）流式返回生成进度。前端通过 `EventSource` 或 `fetch` 保持长连接，服务端在 `StreamingResponse` 中通过 async generator（`DialogueGenerator._generate_story()`）逐条 yield 事件。

**核心问题**：当前端断开连接（用户关闭页面、网络抖动、浏览器休眠等），async generator 被 Python asyncio 的 Task 取消机制（`CancelledError`）中断，导致生成过程截断。实测生成 70 段对白仅入库 3 条，数据完整性严重受损。

#### 1.2 目标
将对白生成从「SSE 流式 + 前端长连接依赖」模式改造为「纯后台任务 + 前端轮询」模式，确保：
- 生成任务不依赖前端连接存活
- 前端可随时查询任务进度
- 任务完成后前端可获取完整结果
- 即使前端断开，后台任务继续执行至完成

#### 1.3 改造原则（甲方要求）
1. **纯后台任务模式**，不依赖前端连接
2. **前端能看到进度**（通过轮询）
3. **如果影响结果，宁愿纯后台** — 即宁可放弃实时流式体验，也要保证数据完整性

---

### 2. 用户角色定义

| 角色 | 描述 | 与系统的交互方式 |
|------|------|------------------|
| **内容创作者** | 使用 tts-studio 生成有声故事对白的用户 | 通过前端 Web UI 发起对白生成、查看进度、查看结果 |
| **系统管理员** | 部署和维护 tts-studio 实例 | 通过 API 或配置文件管理任务队列和系统参数 |

---

### 3. 功能需求清单

#### P0 — 必须实现（核心改造）

| 编号 | 需求描述 | 优先级 |
|------|----------|--------|
| FR-01 | **后台任务启动**：`POST /api/projects/{project_id}/episodes/{episode_id}/generate-dialogues` 改为立即返回 `task_id`（HTTP 202 Accepted），在后台异步执行完整的生成流程（LLM 调用 → 故事解析 → 对白入库） | P0 |
| FR-02 | **任务状态持久化**：利用已有 `store.py` 的 `init_generation_task()` / `update_generation_task()` 机制，在任务生命周期中持续更新状态字段（`status`, `current`, `total`, `error`） | P0 |
| FR-03 | **进度轮询**：复用已有端点 `GET /api/projects/{project_id}/generation-status?episode_id={id}`，返回当前任务状态（`running` / `complete` / `error`）、进度（`current`/`total`）、错误信息 | P0 |
| FR-04 | **任务完成通知**：任务完成后，前端通过轮询检测到 `status=complete`，获取生成结果（生成对白数量、新创建角色列表等） | P0 |
| FR-05 | **并发控制**：同一剧集同一时刻只允许一个生成任务运行。如果已有 `running` 状态的任务，返回 409 Conflict 或排队等待 | P0 |

#### P1 — 重要

| 编号 | 需求描述 | 优先级 |
|------|----------|--------|
| FR-06 | **任务取消**：提供 `DELETE /api/projects/{project_id}/generation-tasks/{task_id}` 端点，允许用户手动取消正在运行的后台任务 | P1 |
| FR-07 | **任务历史**：保留已完成/失败的任务记录（不自动清理），前端可查看最近 N 次生成记录 | P1 |
| FR-08 | **错误恢复**：任务失败时，`error` 字段包含详细错误信息（LLM 调用失败、解析失败等），前端可据此决定是否重试 | P1 |

#### P2 — 可选

| 编号 | 需求描述 | 优先级 |
|------|----------|--------|
| FR-09 | **任务队列**：支持多个剧集排队生成，按提交顺序依次执行 | P2 |
| FR-10 | **WebSocket 推送**：在轮询之外，可选提供 WebSocket 端点推送进度更新，减少轮询延迟 | P2 |
| FR-11 | **任务超时**：为后台任务设置最大执行时间（如 30 分钟），超时自动标记为 `error` | P2 |

---

### 4. 非功能需求

#### 4.1 性能
| 编号 | 需求 | 指标 |
|------|------|------|
| NFR-01 | 任务启动响应时间 | API 调用应在 500ms 内返回 `task_id`（不等待 LLM 调用） |
| NFR-02 | 轮询响应时间 | 状态查询 API 应在 200ms 内返回 |
| NFR-03 | 并发任务数 | 支持至少 3 个后台任务同时运行（不同剧集） |
| NFR-04 | 轮询频率 | 前端建议轮询间隔 ≥ 2 秒，避免对 JSON 文件存储造成写竞争 |

#### 4.2 可用性
| 编号 | 需求 | 说明 |
|------|------|------|
| NFR-05 | 服务重启恢复 | 服务重启后，正在运行的任务标记为 `error`（无法恢复执行中的 LLM 调用） |
| NFR-06 | 幂等性 | 同一请求重复提交不应导致重复生成（通过剧集+任务类型去重） |

#### 4.3 安全性
| 编号 | 需求 | 说明 |
|------|------|------|
| NFR-07 | 任务隔离 | 不同项目的任务数据互不可见 |
| NFR-08 | 输入校验 | 与现有端点一致的参数校验（项目/剧集存在性、LLM 配置完整性） |

#### 4.4 可维护性
| 编号 | 需求 | 说明 |
|------|------|------|
| NFR-09 | 代码复用 | 改造时尽量复用 `DialogueGenerator._generate_story()` 的核心生成逻辑，不重写 LLM 调用和解析流程 |
| NFR-10 | 日志 | 后台任务的关键步骤（开始、LLM 调用、解析完成、入库完成、失败）输出结构化日志 |

---

### 5. 边界条件与异常场景

| 编号 | 场景 | 预期行为 |
|------|------|----------|
| EC-01 | 前端在任务运行中关闭页面/断网 | 后台任务继续执行，不受影响 |
| EC-02 | 前端在任务运行中重新打开页面 | 通过轮询接口获取最新进度，继续等待完成 |
| EC-03 | LLM 调用超时（当前 timeout=600s） | 任务标记为 `error`，`error` 字段包含超时信息 |
| EC-04 | LLM 返回空文本 | 任务标记为 `error`，提示"LLM 返回空故事文本" |
| EC-05 | 故事解析失败（`parse_story_with_two_step` 返回空列表） | 任务标记为 `error`，提示"无法解析故事文本" |
| EC-06 | 同一剧集重复提交生成请求 | 返回 409 Conflict，提示"该剧集已有正在运行的任务" |
| EC-07 | 剧集没有摘要 | 返回 400 Bad Request，提示"该剧集没有摘要" |
| EC-08 | LLM 未配置 | 返回 400 Bad Request，提示"LLM 未配置" |
| EC-09 | 项目或剧集不存在 | 返回 404 Not Found |
| EC-10 | 服务进程崩溃/重启 | 重启后所有 `running` 任务标记为 `error`，原因："服务重启，任务中断" |
| EC-11 | 任务执行时间超过预期（如 > 30 分钟） | 可选：实现超时机制，自动标记为 `error` |
| EC-12 | JSON 文件写入失败（磁盘满/权限） | 任务标记为 `error`，包含具体 IO 错误信息 |

---

### 6. 验收标准

#### 6.1 功能验收

| 编号 | 验收项 | 验证方法 |
|------|--------|----------|
| AC-01 | 调用生成 API 后立即返回 `task_id`（HTTP 202），不阻塞 | curl 调用，检查响应状态码和响应体 |
| AC-02 | 后台任务完整执行：LLM 生成 → 解析 → 入库，所有对白正确写入 | 轮询等待 `complete`，检查剧集对白数量与预期一致 |
| AC-03 | 任务运行中，轮询接口返回 `status=running` 及当前进度 | 在生成过程中多次调用轮询接口 |
| AC-04 | 任务完成后，轮询接口返回 `status=complete` 及结果摘要 | 等待任务完成，调用轮询接口 |
| AC-05 | 任务失败时，轮询接口返回 `status=error` 及错误信息 | 模拟 LLM 配置错误，触发失败场景 |
| AC-06 | 前端断开连接后，后台任务继续执行至完成 | 发起生成后立即关闭 curl 连接，等待后检查对白是否完整入库 |
| AC-07 | 同一剧集重复提交返回 409 Conflict | 连续两次调用生成 API |
| AC-08 | 剧集无摘要时返回 400 | 调用生成 API，检查错误信息 |

#### 6.2 回归验收

| 编号 | 验收项 | 验证方法 |
|------|--------|----------|
| AC-09 | 生成的对白格式与改造前一致（角色名、instruct、text 字段正确） | 对比改造前后同一剧集的生成结果 |
| AC-10 | 新角色自动创建逻辑不变 | 生成包含新角色的故事，检查项目角色列表 |
| AC-11 | 角色重复校验/合并逻辑不变 | 生成包含近似角色名的故事，检查合并行为 |
| AC-12 | 已有轮询端点 `GET /api/projects/{project_id}/generation-status` 行为不变 | 调用轮询端点，检查返回格式 |

#### 6.3 非功能验收

| 编号 | 验收项 | 验证方法 |
|------|--------|----------|
| AC-13 | 任务启动 API 响应时间 < 500ms | 多次调用，取 P95 响应时间 |
| AC-14 | 轮询 API 响应时间 < 200ms | 多次调用，取 P95 响应时间 |
| AC-15 | 服务重启后，运行中任务标记为 error | 启动任务后重启服务，检查任务状态 |

---

### 7. 技术方案建议

#### 7.1 改造范围
- **修改文件**：
  - `app/api/episodes.py` — 修改 `api_generate_dialogues` 路由，改为后台任务模式
  - `app/core/dialogue_service.py` — 将 `DialogueGenerator._generate_story()` 从 async generator 改为普通 async function，或保留 generator 但由后台任务驱动消费
  - `app/core/store.py` — 可能需扩展 `generation_tasks` 字段以存储结果摘要

- **新增文件**（可选）：
  - `app/core/task_manager.py` — 后台任务管理器（管理任务生命周期、并发控制）

#### 7.2 核心改造逻辑
```
POST /generate-dialogues
  ├─ 校验项目/剧集/LLM配置
  ├─ 检查是否有 running 任务 → 409
  ├─ init_generation_task() → task_id
  ├─ asyncio.create_task(run_generation(task_id, ...))
  └─ return 202 { "task_id": task_id }

run_generation(task_id, ...):
  ├─ 调用 DialogueGenerator 核心逻辑（LLM → 解析 → 入库）
  ├─ 过程中 update_generation_task(current, total)
  ├─ 成功 → update_generation_task(status="complete", result=...)
  └─ 失败 → update_generation_task(status="error", error=...)

GET /generation-status?episode_id=xxx
  └─ get_generation_task() → 返回任务状态
```

#### 7.3 与现有模式的兼容性
- 改造后 `generate-batch`（TTS 批量生成）和 `refresh-batch`（批量刷新）仍可保留 SSE 模式，因为它们不涉及 LLM 长时间调用，且前端需要实时感知每条对白的处理结果
- 如果未来需要统一，可逐步将这两个端点也迁移到后台任务模式

---

### 8. 附录

#### 8.1 相关文件
| 文件 | 说明 |
|------|------|
| `app/api/episodes.py` (L1370-1381) | 当前 SSE 流式生成端点 |
| `app/core/dialogue_service.py` (L42-397) | `DialogueGenerator` 类及 `_generate_story()` 方法 |
| `app/core/store.py` (L787-846) | `init_generation_task` / `update_generation_task` / `get_generation_task` |
| `app/api/episodes.py` (L1383-1390) | 已有轮询端点 `GET /generation-status` |

#### 8.2 参考实现
- `app/api/episodes.py` 中 `api_generate_batch_audio` (L729-820) 和 `api_batch_refresh_dialogues` (L540-591) 已使用 `init_generation_task`/`update_generation_task` 模式，可作为改造参考
- 区别在于：这两个端点仍使用 SSE 流式返回，而本改造需要将生成逻辑完全移至后台
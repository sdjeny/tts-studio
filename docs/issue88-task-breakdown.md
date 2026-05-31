# Issue #88 — Store 层补全 · 任务分配文档

> **师傅**: Tech Lead / 架构师
> **牛马**: 1 人
> **目标**: 完成 Issue #88 的 store 层逻辑补全，使 `default_style_enabled` 字段在新建剧集/对白时生效
> **方案**: 方案 A（Store 层内部自动读取 project 默认值）
> **总改动量**: ≈ 10 行（纯 Python，零架构变更）

---

## 一、当前状态确认

| 检查项 | 结果 |
|--------|------|
| 本地 main HEAD | `994765d`（已最新） |
| 需求规格说明书 | 已阅读 `/opt/data/workspace/tts-studio/issue88-completion-report.md` |
| 目标文件 | `/opt/data/workspace/tts-studio/app/core/store.py`（共 998 行） |
| 已有实现 | API 层 (`app/api/projects.py`) + 前端 UI 已完成，store 层 4 处缺口未处理 |

---

## 二、子任务拆解

全部由 **1 名牛马** 按顺序执行。改动仅在 `app/core/store.py` 一个文件中，共约 10 行。

### 子任务 1：`create_project()` — 初始化 `default_style_enabled` 字段

- **文件**: `app/core/store.py`
- **函数**: `create_project()`（第 246-273 行）
- **改动内容**: 在 `story_settings` 字典之后（第 269 行末尾 `}` 之后），追加一行：
  ```python
  "default_style_enabled": False,
  ```
- **改后效果**:
  ```python
      "story_settings": {
          "description": "",
          "extra": "",
          "story_arc": "",
      },
      "default_style_enabled": False,   # ← 新增
  }
  ```
- **预期行数**: +1 行

### 子任务 2：`list_projects()` — 添加 backfill + entry 字段暴露

- **文件**: `app/core/store.py`
- **函数**: `list_projects()`（第 195-239 行）
- **改动内容（两处）**:

  **2a — backfill 逻辑**（在 `story_settings` backfill 之后，第 225 行之前）：
  ```python
  if "default_style_enabled" not in p:
      p["default_style_enabled"] = False
      _write_project(entry["id"], p)
      dirty = True
  ```

  **2b — entry 字段组装**（在 `story_settings` 之后，第 235 行附近）：
  ```python
  entry["default_style_enabled"] = p.get("default_style_enabled", False)
  ```

- **预期行数**: +4～5 行

### 子任务 3：`create_episode()` — 读取 project 默认值

- **文件**: `app/core/store.py`
- **函数**: `create_episode()`（第 425-441 行）
- **改动内容**: 第 433 行，将：
  ```python
  "style_enabled": False,  # 剧集默认关闭风格
  ```
  改为：
  ```python
  "style_enabled": project.get("default_style_enabled", False),  # 继承项目默认值
  ```
- **预期行数**: 0 行（仅修改已有行）

### 子任务 4：`add_dialogue()` — 读取 project 默认值

- **文件**: `app/core/store.py`
- **函数**: `add_dialogue()`（第 476-509 行）
- **改动内容**: 第 499 行，将：
  ```python
  "style_enabled": False,  # True=角色风格+场景情绪, False=仅角色风格（默认关闭）
  ```
  改为：
  ```python
  "style_enabled": project.get("default_style_enabled", False),  # 继承项目默认值
  ```
- **预期行数**: 0 行（仅修改已有行）

---

## 三、依赖关系

```
子任务 1 (create_project 初始化)
    ↓（无依赖，可最先做）
子任务 2 (list_projects backfill)
    ↓（无依赖，可并行或随后）
子任务 3 (create_episode 读取)
    ↓（无依赖，但逻辑上建议在 1/2 之后做）
子任务 4 (add_dialogue 读取)
    ↓（无依赖，建议在 1/2 之后做）
```

**实际执行顺序建议**：1 → 2 → 3 → 4（自上而下，代码结构自然顺序）。  
**牛马可一次性全部完成**（所有改动在同一文件、互不冲突）。

---

## 四、验收标准

牛马完成代码修改后，师傅（或 Code Review）按以下标准逐项验收：

| # | 验收项 | 验证方法 |
|---|--------|----------|
| 1 | `create_project()` 返回的字典包含 `"default_style_enabled": false` | 启动服务后 `POST /projects` → 检查 response JSON 含该字段 |
| 2 | `list_projects()` 对旧项目自动 backfill `default_style_enabled: false` | 找一个 `default_style_enabled` 缺失的旧项目 JSON，调用 `GET /projects` 确认已补全 |
| 3 | 当 `default_style_enabled = false` 时，新剧集 `style_enabled` 为 `false` | `POST /projects/{id}/episodes` → 返回的 episode 中 `style_enabled === false` |
| 4 | 当 `default_style_enabled = true` 时，新剧集 `style_enabled` 为 `true` | 先 `PATCH` 设置 `default_style_enabled: true`，再创建剧集 → 确认 `style_enabled === true` |
| 5 | 当 `default_style_enabled = false` 时，新增对白 `style_enabled` 为 `false` | `POST .../dialogues` → 返回的 dialogue 中 `style_enabled === false` |
| 6 | 当 `default_style_enabled = true` 时，新增对白 `style_enabled` 为 `true` | 同上，预期 `style_enabled === true` |
| 7 | 已有剧集/对白的 `style_enabled` 不受影响 | 修改 `default_style_enabled` 后，已存在的剧集/对白值不变化 |
| 8 | AI 生成对白 (`dialogue_service.py`) 也自动继承默认值 | 方案 A 在 store 层内部读取 project，`dialogue_service.py` 无需修改即自动生效 |
| 9 | 代码风格合规 | `ruff check app/core/store.py` / `ruff format app/core/store.py` 通过 |

---

## 五、注意事项

1. **不改 API 层**：`app/api/episodes.py` 的 `api_create_episode()` 和 `api_add_dialogue()` 无需修改——方案 A 在 store 层内部自行读取 project 默认值。
2. **不改 `dialogue_service.py`**：该文件通过 `add_dialogue()` 创建对白，store 层内部读取 project 后自动生效。
3. **不改函数签名**：`create_episode()` 和 `add_dialogue()` 的入参保持不变，仅在函数体内读取 `project` 变量。
4. **`project` 变量已存在**：`create_episode()` 第 426 行和 `add_dialogue()` 第 478 行已调用 `_read_project(project_id)` 得到 `project`，无需额外读取。
5. **提交规范**：Commit message 建议格式为 `fix(store): apply project.default_style_enabled on create_episode/add_dialogue (#88)`。
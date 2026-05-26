#!/usr/bin/env python3
"""Post task breakdown comment to Issue #75."""
import json
import ssl
import urllib.request
import urllib.error
import re

# Extract token from git remote
import subprocess
result = subprocess.run(
    ["git", "remote", "-v"],
    capture_output=True, text=True, cwd="/opt/data/workspace/tts-studio"
)
remote_output = result.stdout
print(f"Git remote output: {remote_output}")

match = re.search(r'https://([^@]+)@', remote_output)
if not match:
    print("ERROR: Could not extract token from git remote")
    exit(1)
token = match.group(1)
print(f"Token extracted (len={len(token)})")

# Build the comment body
comment_body = """## 🛠 Issue #75 持久化优化 — 技术任务拆解

> 作者：师傅（Tech Lead）
> 基于需求文档 `requirements/issue75_persistence_optimization.md` + `app/core/store.py` 分析

---

### 一、函数全景分析

对 `store.py` 中全部 **52 个函数**（含私有辅助函数和 `atomic_update` 上下文管理器）进行了逐一审计，分类如下：

#### 🔴 需改动的函数（共 29 个）

| 类别 | 函数列表 | 改动原因 |
|------|---------|---------|
| **私有基础函数** (5个) | `_ensure_data_dir`, `_read`, `_write`, `_update_timeline_field`, `_ensure_generation_tasks`, `atomic_update` | 彻底重写内部读写路径：从单文件操作改为按项目文件操作 |
| **项目 CRUD** (6个) | `list_projects`, `get_project`, `create_project`, `update_project`, `touch_project`, `delete_project` | 从读全量 `_read()` 改为读/写单项目文件 + 索引 |
| **角色操作** (3个) | `add_character`, `update_character`, `delete_character` | 内联使用 `_read/_write`，需改为 `_read_project/_write_project` |
| **剧集操作** (3个) | `create_episode`, `update_episode`, `delete_episode` | 同上 |
| **对白操作** (7个) | `add_dialogue`, `update_dialogue`, `delete_dialogue`, `insert_dialogue_after`, `reorder_episode_dialogues`, `delete_dialogue_and_audio_files`, `delete_episode_all_dialogues` | 同上 |
| **音频历史** (4个) | `add_audio_to_history`, `set_current_audio`, `remove_audio_from_history`, `clear_audio_history` | 同上 |
| **时间线** (1个) | `save_timeline` | 直接使用 `_read/_write` |
| **生成任务** (5个) | `init_generation_task`, `update_generation_task`, `get_generation_task`, `cancel_generation_task`, `list_generation_tasks` | 同上 |

#### 🟢 无需改动的函数（共 17 个）

这些函数**完全依赖于其他函数**（委托模式），内部实现无需改动：

| 函数 | 委托链 | 说明 |
|------|--------|------|
| `project_characters` | → `get_project` | 读取不变，get_project 返回完整项目，切片即可 |
| `project_episodes` | → `get_project` | 同上，但内含 migration 逻辑需注意（见下文） |
| `get_episode` | → `get_project` | migration 逻辑需确认与新 store 兼容 |
| `episode_dialogues` | → `get_episode` | 纯委托 |
| `get_timeline` | → `get_episode` | 纯委托 |
| `update_dialogue_status` (`line 412`) | → `update_dialogue` | 纯委托，别名 |
| `update_dialogue_status` (`line 645`) | → `update_dialogue` | 重复别名，建议合并或保留 |
| `add_track_to_timeline` | → `_update_timeline_field` | 委托 |
| `update_track_in_timeline` | → `_update_timeline_field` | 委托 |
| `delete_track_from_timeline` | → `_update_timeline_field` | 委托 |
| `add_clip_to_timeline` | → `_update_timeline_field` | 委托 |
| `update_clip_in_timeline` | → `_update_timeline_field` | 委托 |
| `delete_clip_from_timeline` | → `_update_timeline_field` | 委托 |
| `add_imported_audio` | → `_update_timeline_field` | 委托 |
| `add_snapshot` | → `_update_timeline_field` | 委托 |
| `restore_snapshot` | → `_update_timeline_field` | 委托 |
| `_load_tts_defaults` | 独立 | 读取 config.yaml，与持久化无关 |
| `_now` / `_uid` | 工具函数 | 纯工具，不涉及存储 |

> **注意**：`project_episodes` 和 `get_episode` 内含数据迁移逻辑（补充 `raw_text` 字段），这些 migration 代码在迁移到新存储后不再需要，但为兼容旧数据需保留。建议**保留现有 migration 逻辑**——它们通过 `get_project` 获取数据后做修补，在新实现中 `get_project` 返回的已是单项目完整数据，修补后需要写回时需确保调用 `_write_project` 而非 `_write`。

#### 🟡 特殊处理：`atomic_update` 上下文管理器

当前 `atomic_update` 使用模块级锁 `_store_lock` 做全量读-改-写。在新架构下需要重构为：
- 继续保留（API 兼容），但内部不能再用全量 `_write`
- 改为在退出 context 时，对发生变化的所有项目逐一写回
- 或直接废弃，改为按需新增的函数级锁

**建议：保留签名，内部改为对 `data["projects"]` 中的每个项目调用 `_write_project`，并更新索引。**

---

### 二、任务拆解

将全部工作拆解为 **3 个子任务**，其中任务 1 是前置基础，任务 2 和 3 可并行推进。

```
┌─────────────────────────────────────────────────────┐
│                  任务 1: 基础设施层                    │
│   (全局常量 + 新内部函数 + 迁移脚本 + 锁策略)          │
└────────────────────────┬────────────────────────────┘
                         │
          ┌──────────────┴──────────────┐
          ▼                             ▼
┌──────────────────┐       ┌──────────────────────────┐
│  任务 2: 项目层    │       │   任务 3: 子实体层         │
│  Projects CRUD    │       │  Characters/Episodes/    │
│  + Generation     │       │  Dialogues/Audio History │
│  Tasks            │       │  / Timeline              │
└──────────────────┘       └──────────────────────────┘
```

---

### 任务 1：基础设施层（Foundation Layer）

**负责人**：1 位牛马（最资深的，因为需要设计架构骨架）

**工作内容**：

#### 1A. 新增常量与路径函数
```python
# 在 DATA_FILE 下方新增
PROJECTS_DIR = DATA_DIR / "projects"
INDEX_FILE = DATA_DIR / "projects_index.json"
BAK_FILE = DATA_DIR / "studio.json.bak"

def _project_path(project_id: str) -> Path:
    return PROJECTS_DIR / f"{project_id}.json"
```

#### 1B. 新增锁策略
```python
# 替换 _store_lock
_project_locks: dict[str, asyncio.Lock] = {}
_index_lock = asyncio.Lock()

def _get_project_lock(project_id: str) -> asyncio.Lock:
    if project_id not in _project_locks:
        _project_locks[project_id] = asyncio.Lock()
    return _project_locks[project_id]
```

#### 1C. 新增读写函数

| 函数 | 输入 | 输出 | 行为 |
|------|------|------|------|
| `_read_project(project_id)` | `project_id: str` | `dict \| None` | 读取 `projects/{id}.json`，返回项目 dict，不存在返回 None |
| `_write_project(project_id, data)` | `id, data: dict` | `None` | 原子写入（`.tmp` + `os.replace`）到 `projects/{id}.json` |
| `_read_index()` | 无 | `dict` | 读取 `projects_index.json`，空/不存在时返回 `{"version":1, "projects":[]}` |
| `_write_index(data)` | `data: dict` | `None` | 原子写入索引文件，**持有 `_index_lock`** |
| `_index_add_project(pid, name, updated_at)` | 项目元信息 | `None` | 读索引→追加条目→写索引 |
| `_index_remove_project(pid)` | `project_id` | `None` | 读索引→移出条目→写索引 |
| `_index_update_project(pid, name=None, updated_at=None)` | 要更新的字段 | `None` | 读索引→更新匹配条目→写索引 |

#### 1D. 重构 `_ensure_data_dir()`
- 创建 `PROJECTS_DIR` 目录
- 不再自动创建 `DATA_FILE`（旧单文件）
- 检测旧格式并触发自动迁移（见 1E）

#### 1E. 迁移脚本
- 文件：`scripts/migrate_to_split_store.py`
- 逻辑：读取 `studio.json` → 逐个写入 `projects/{id}.json` → 生成 `projects_index.json` → 备份 `studio.json.bak` → 删除 `studio.json`
- 附带 `rollback()` 函数

#### 1F. 自动迁移检测
- 在 `_ensure_data_dir()` 中检测：如果 `DATA_FILE` 存在且 `INDEX_FILE` 不存在，自动执行迁移

#### 1G. 重构 `_read()` 和 `_write()`（兼容层）
- `_read()`：保留但改为**懒加载所有项目文件**，兼容旧调用方
- `_write(data)`：遍历 `data["projects"]`，逐个用 `_write_project` 写入，同时重建索引

**边界**：
- **输入**：无（新增基础设施）
- **输出**：`store.py` 中新增约 10 个内部函数 + 迁移脚本 + 锁机制
- **不涉及**：任何对外函数（`list_projects` 等）的改动

**测试标准**：
1. ✅ `_read_project` 能正确读取已有项目文件，不存在的返回 None
2. ✅ `_write_project` 原子写入成功，中间 `.tmp` 文件不在目标路径
3. ✅ `_read_index` 能读取正确的索引，自动初始化空索引
4. ✅ `_write_index` 原子写入
5. ✅ 迁移脚本能将 22 个项目的 `studio.json` 完整拆分为 22 个独立文件 + 索引
6. ✅ 迁移后验证：每个项目字段值与迁移前完全一致
7. ✅ 回滚脚本能从新格式重建 `studio.json`
8. ✅ `_read()` 兼容旧调用方，返回 `{"projects": [...]}`
9. ✅ `_write(data)` 能将数据正确分发到各文件
10. ✅ 并发锁：不同项目 ID 使用不同锁，索引操作互斥

**依赖**：无（第一个做）

---

### 任务 2：项目层 + 生成任务（Project CRUD + Generation Tasks）

**负责人**：1 位牛马

**工作内容**：

#### 2A. 重构项目 CRUD 函数（6 个）

| 函数 | 新建实现 |
|------|---------|
| `get_project(project_id)` | `return _read_project(project_id)` |
| `list_projects()` | 读取 `_read_index()` → 按 `updated_at` 倒序返回 `[{id, name, updated_at}]` |
| `create_project(name)` | 构造项目 dict → `_write_project(pid, project)` → `_index_add_project(...)` |
| `update_project(pid, name?, **extra)` | `_read_project(pid)` → 修改 → `_write_project(pid, data)` → 如果 name 变了则 `_index_update_project(...)` |
| `touch_project(pid)` | `_read_project(pid)` → 更新 `updated_at` → `_write_project(pid, data)` → `_index_update_project(updated_at=...)` |
| `delete_project(pid)` | 删除文件 `_project_path(pid).unlink()` → `_index_remove_project(pid)` |

#### 2B. 重构 `atomic_update()` 上下文管理器
- 去掉模块级 `_store_lock`
- 退出时遍历 `data["projects"]`，对每个项目调用 `_write_project` + 更新索引

#### 2C. 重构生成任务函数（5 个）

| 函数 | 新建实现 |
|------|---------|
| `_ensure_generation_tasks(data)` | 不再需要（每个项目独立文件，创建时自动有该字段）或者检查单项目 |
| `init_generation_task(pid, eid, type, total)` | `_read_project(pid)` → 添加 task → `_write_project(pid, data)` |
| `update_generation_task(pid, task_id, **fields)` | `_read_project(pid)` → 更新 task → `_write_project(pid, data)` |
| `get_generation_task(pid, eid?, type?)` | `_read_project(pid)` → 筛选 → 返回 |
| `cancel_generation_task(pid, task_id)` | `_read_project(pid)` → 改 status → `_write_project(pid, data)` |
| `list_generation_tasks(pid, eid?, status?)` | `_read_project(pid)` → 筛选排序 → 返回 |

**边界**：
- **输入**：`_read_project`, `_write_project`, 索引函数（由任务 1 提供）
- **输出**：6 个项目函数 + 5 个任务函数 + `atomic_update` 重构完成
- **不涉及**：Characters/Episodes/Dialogues/Audio History/Timeline 函数

**测试标准**：
1. ✅ `list_projects()` 返回所有项目，按 updated_at 倒序，与旧实现结果一致
2. ✅ `get_project(id)` 返回完整项目数据（含角色、剧集、对白等嵌套）
3. ✅ `create_project("测试")` → 文件系统生成 `projects/{id}.json` + 索引新增条目
4. ✅ `update_project(id, name="新名字")` → 项目文件 name 字段更新 + 索引同步
5. ✅ `touch_project(id)` → `updated_at` 更新
6. ✅ `delete_project(id)` → 项目文件删除 + 索引移除
7. ✅ 生成任务全流程：init → update → get → cancel → list 正常
8. ✅ `atomic_update` 上下文管理器正常工作，项目数据正确写回
9. ✅ API 签名零改动（类型检查）

**依赖**：等待任务 1 完成后启动；与任务 3 **并行**

---

### 任务 3：子实体层（Characters / Episodes / Dialogues / Audio History / Timeline）

**负责人**：1 位牛马

**工作内容**：

所有子实体函数的共同改造模式：
```
# 旧模式：
data = _read()               # 读全部项目
for p in data["projects"]:   # 遍历所有项目找目标
    if p["id"] == pid:       # 找到目标项目
        ... modify ...       # 修改子实体
        _write(data)         # 写回全部
        return ...

# 新模式：
project = _read_project(pid)  # 只读一个项目文件
if not project:
    return None/False/[]      
... modify ...               # 修改子实体
_write_project(pid, project) # 只写一个项目文件
return ...
```

#### 3A. 角色操作（3 个）

| 函数 | 新实现要点 |
|------|-----------|
| `add_character(pid, name, voice_id, ...)` | `_read_project(pid)` → 追加 char → `_write_project` |
| `update_character(pid, char_id, **fields)` | `_read_project(pid)` → 更新 char → `_write_project` |
| `delete_character(pid, char_id)` | `_read_project(pid)` → 过滤 → `_write_project` |

#### 3B. 剧集操作（3 个）

| 函数 | 新实现要点 |
|------|-----------|
| `create_episode(pid, title, raw_text)` | `_read_project(pid)` → 追加 ep → `_write_project` |
| `update_episode(pid, eid, **fields)` | `_read_project(pid)` → 更新 ep → `_write_project` |
| `delete_episode(pid, eid)` | `_read_project(pid)` → 过滤 → `_write_project` |

#### 3C. 对白操作（7 个）

| 函数 | 新实现要点 |
|------|-----------|
| `add_dialogue(pid, eid, cid, text, order, instruct)` | `_read_project(pid)` → 找到 ep → 追加 dlg → `_write_project` |
| `update_dialogue(pid, eid, did, **fields)` | `_read_project(pid)` → 更新 dlg → `_write_project` |
| `delete_dialogue(pid, eid, did)` | `_read_project(pid)` → 过滤 → `_write_project` |
| `insert_dialogue_after(pid, eid, after_did, ...)` | `_read_project(pid)` → 插入 dlg → `_write_project` |
| `reorder_episode_dialogues(pid, eid)` | `_read_project(pid)` → 排序 → `_write_project` |
| `delete_dialogue_and_audio_files(pid, eid, did)` | `_read_project(pid)` → 删 dlg+文件 → `_write_project` |
| `delete_episode_all_dialogues(pid, eid)` | `_read_project(pid)` → 清空 → `_write_project` |

#### 3D. 音频历史（4 个）

| 函数 | 新实现要点 |
|------|-----------|
| `add_audio_to_history(pid, eid, did, url, filename)` | `_read_project(pid)` → 追加 entry → `_write_project` |
| `set_current_audio(pid, eid, did, audio_id)` | `_read_project(pid)` → 设置 → `_write_project` |
| `remove_audio_from_history(pid, eid, did, audio_id)` | `_read_project(pid)` → 移除 → fallback → `_write_project` |
| `clear_audio_history(pid, eid, did)` | `_read_project(pid)` → 清空 → `_write_project` |

#### 3E. 时间线（1 个直接 + 1 个内部函数）

| 函数 | 新实现要点 |
|------|-----------|
| `save_timeline(pid, eid, timeline)` | `_read_project(pid)` → 设置 ep.timeline → `_write_project` |
| `_update_timeline_field(pid, eid, updater)` | `_read_project(pid)` → 找到 ep → `updater(timeline)` → `_write_project` |

> 所有委托给 `_update_timeline_field` 的函数（`add_track_to_timeline` 等 9 个）**无需改动**——它们自动获得新行为。

#### 3F. 无需改动的函数确认（需验证它们在新环境下正常工作）
- `project_characters(pid)` → 调用 `get_project(pid)` → 返回 `p["characters"]` ✅
- `project_episodes(pid)` → 调用 `get_project(pid)` → 返回 `p["episodes"]` ✅
  - ⚠️ **注意**：内含 migration 逻辑（补充 `raw_text`），需要与新实现配合：
    - migration 中用了 `data = _read()` + `_write(data)`，应改为 `_read_project(pid)` + `_write_project(pid, project)`
    - 建议：migration 逻辑**保留**，但将底层的读写调用改为项目级
- `get_episode(pid, eid)` → 调用 `get_project(pid)` → 返回 ep ✅
  - ⚠️ 同上，migration 逻辑需要调整为项目级读写
- `episode_dialogues(pid, eid)` → 调用 `get_episode(pid, eid)` ✅
- `get_timeline(pid, eid)` → 调用 `get_episode(pid, eid)` ✅

**边界**：
- **输入**：`_read_project`, `_write_project`（由任务 1 提供）
- **输出**：所有子实体操作函数完成改造
- **不涉及**：项目 CRUD、生成任务、索引操作

**测试标准**：
1. ✅ 角色 CRUD（add/update/delete）正常，只修改目标项目文件
2. ✅ 剧集 CRUD（create/update/delete）正常
3. ✅ 对白 CRUD（add/update/delete/insert/reorder/delete_with_audio）正常
4. ✅ 音频历史（add/set/remove/clear）正常
5. ✅ 时间线（save_timeline + 所有 track/clip/snapshot/imported_audio 操作）正常
6. ✅ 只读函数（project_characters/project_episodes/get_episode/episode_dialogues/get_timeline）在新环境下返回正确数据
7. ✅ 写操作只影响单个项目文件，不修改其他项目文件（文件系统验证）
8. ✅ API 签名零改动
9. ✅ `project_episodes` 和 `get_episode` 中的 migration 逻辑兼容

---

### 三、依赖关系总图

```
        ┌───────────────────────┐
        │  任务 1: 基础设施层    │  ← 先做，预计 2-3 天
        │  (内部函数 + 迁移脚本) │
        └───────────┬───────────┘
                    │ 完成
         ┌──────────┴──────────┐
         ▼                     ▼
┌──────────────────┐  ┌──────────────────────┐
│ 任务 2: 项目层    │  │ 任务 3: 子实体层      │  ← 可并行，预计各 2-3 天
│ (Projects +     │  │ (Chars/Episodes/    │
│  Gen Tasks)      │  │  Dialogues/Audio/   │
│                  │  │  Timeline)           │
└──────────────────┘  └──────────────────────┘
         └──────────────┬──────────────┘
                        ▼
               ┌──────────────────┐
               │ 集成验证 + 收尾   │  ← 1 天
               │ (合并 PR + 测试)  │
               └──────────────────┘
```

| 依赖 | 说明 |
|------|------|
| 任务 2 → 任务 1 | 任务 2 需要任务 1 提供的 `_read_project`、`_write_project`、索引函数 |
| 任务 3 → 任务 1 | 任务 3 也需要任务 1 提供的读写函数 |
| 任务 2 ∥ 任务 3 | **可完全并行** |
| 集成验证 → 任务 2 + 任务 3 | 两个分支完成后合并 PR，跑全量测试 |

---

### 四、风险与建议

1. **`project_episodes` 和 `get_episode` 中的 migration 逻辑**：这两个函数在新架构下需要**小幅修改**——它们内部在使用 `_read()` + `_write()` 做数据迁移，需要改为 `_read_project(pid)` + `_write_project(pid, project)`。建议任务 3 的负责人在改造角色/剧集/对白函数时一同处理，避免遗漏。

2. **并发锁注意**：任务 2 和 3 的负责人需要确保在 `_read_project` → 修改 → `_write_project` 的整个序列中，使用 `_get_project_lock(pid)` 保护原子性。建议在 `_read_project` 和 `_write_project` 内部处理好锁，对外函数无需再显式加锁。

3. **`_write_project` 的原子写**：复用当前 `_write` 中的 `.tmp` + `os.replace` 模式，任务 1 的负责人可以直接从现有 `_write()` 中提取原子写逻辑为一个私有函数 `_atomic_write(filepath, data)`。

4. **测试数据**：可以在 `tests/` 下准备一个含 22 个项目的 `studio.json` 用于迁移和回滚测试。
"""

# Construct the payload
payload = json.dumps({"body": comment_body}).encode("utf-8")
url = "https://api.github.com/repos/sdjeny/tts-studio/issues/75/comments"

# Use the specified SSL context
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

req = urllib.request.Request(
    url,
    data=payload,
    headers={
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "User-Agent": "hermes-agent-task-breakdown",
    },
    method="POST",
)

try:
    with urllib.request.urlopen(req, context=ctx) as resp:
        response_data = resp.read().decode("utf-8")
        print(f"Status: {resp.status}")
        print(f"Response: {response_data}")
        print("\n✅ Comment posted successfully!")
except urllib.error.HTTPError as e:
    print(f"❌ HTTP Error: {e.code} - {e.reason}")
    print(f"Body: {e.read().decode('utf-8')}")
except urllib.error.URLError as e:
    print(f"❌ URL Error: {e.reason}")
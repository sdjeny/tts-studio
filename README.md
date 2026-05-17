# 🎙️ TTS Studio

**有声书/广播剧制作工具** — 从剧本到多角色语音合成一条龙。支持项目级角色管理、LLM 自动对白生成、多轨时间线编辑、批量 TTS 生成、角色音效处理。

---

## 📦 项目结构

```
tts-studio/
├── app/
│   ├── main.py                 # FastAPI 入口，挂载路由 + 前端静态文件
│   ├── config.yaml             # LLM 和 TTS 配置（API Key、模型等）
│   ├── api/
│   │   ├── projects.py         # 项目/角色 CRUD + 音效管理
│   │   ├── episodes.py         # 剧集/对白 CRUD + TTS 生成
│   │   ├── timeline.py         # 多轨时间线编辑（剪辑、混音、导出）
│   │   ├── voices.py           # 获取可用音色列表
│   │   └── config.py           # 配置读取/更新接口
│   └── core/
│       ├── store.py            # JSON 文件持久层（studio.json）
│       ├── dialogue_service.py # 对白生成服务（LLM 生成 + 解析）
│       ├── dialogue_parser.py  # 对白文本解析/切分/后处理
│       ├── llm.py              # OpenAI 协议 LLM 客户端
│       ├── tts.py              # TTS 客户端封装（submit + check status）
│       ├── voice_service.py    # 音色服务（查可用音色）
│       ├── audio_effects.py    # 音效处理引擎（pedalboard）
│       ├── timeline_audio.py   # 时间线混音引擎
│       ├── models.py           # 数据模型定义（已逐步废弃，改用 store.py）
│       └── config_manager.py   # 配置热更新管理
├── frontend/
│   ├── src/
│   │   ├── App.tsx             # 应用外壳（路由：首页/项目详情/设置）
│   │   ├── api.ts              # API 客户端封装
│   │   ├── pages/
│   │   │   ├── ProjectList.tsx     # 🏠 项目列表首页
│   │   │   ├── ProjectDetail.tsx   # 📂 项目详情（含 AI 生成/剧集/角色/设置 tab）
│   │   │   └── SettingsPage.tsx    # ⚙️ 系统设置
│   │   ├── components/
│   │   │   ├── EpisodePanel.tsx    # 📺 剧集面板（新建/列表/批量操作）
│   │   │   ├── DialogueList.tsx    # 💬 对白列表（查看/编辑/生成音频）
│   │   │   ├── CharacterPanel.tsx  # 👤 角色面板（增删改 + 音效设置）
│   │   │   ├── ProjectSettings.tsx # ⚙️ 项目参数设置
│   │   │   └── Timeline.tsx        # 🎬 多轨时间线编辑器
│   │   ├── constants.ts        # 常量定义
│   │   └── types/timeline.ts   # 时间线类型定义
│   ├── index.html
│   ├── vite.config.ts
│   └── package.json
├── tests/                      # 测试文件
├── docs/                       # 设计文档
├── data/
│   ├── studio.json             # 持久化数据
│   ├── audio/                  # 生成的音频文件
│   └── logs/                   # 运行时日志
├── Dockerfile                  # 打包镜像
├── docker-compose.yml          # 容器编排
├── .env.example                # 环境变量示例
└── requirements.txt            # Python 依赖
```

---

## 🏗️ 架构概览

```
浏览器 (SPA React + Vite)
    │  HTTP / JSON
    ▼
FastAPI 后端 (8000)
    ├─ /api/projects/*          → 项目 + 角色 CRUD
    ├─ /api/.../episodes/*      → 剧集 + 对白 CRUD + TTS 生成
    ├─ /api/.../dialogues/*     → 对白增删改 + 音频生成
    ├─ /api/.../timeline/*      → 多轨时间线
    ├─ /api/voices              → 可用音色
    ├─ /api/config              → 配置热更新
    └─ /static/audio/           → 静态音频
    │
    ├─ LLM (OpenAI 协议)         → 对白/大纲生成
    └─ TTS Service               → 语音合成（异步，15min+）
```

---

## 🚀 部署

### Docker 部署（推荐）

```bash
# 1. 配置环境变量
cp .env.example .env
# 编辑 .env：填入 LLM API 地址和密钥

# 2. 启动
docker-compose up -d

# 3. 访问 http://localhost:7860
```

含两个容器：
- `tts-studio`（正式）：7860 → 8000
- `tts-studio-for-test`（测试）：7861 → 8000

### 直接运行

```bash
pip install -r requirements.txt
cd frontend && npm install && npm run build && cd ..
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

---

## ⚙️ 配置

`app/config.yaml`：

```yaml
llm:
  base_url: "https://api.openai.com/v1.com/v1"   # LLM API 地址
  api_key: "sk-xxx"                       # API Key
  model: "gpt-4o"                          # 模型名
  timeout: 120
  max_tokens: 128000
  temperature: 0temperature: 0.7

0tts:
  0base_url: "http://localhost:8420"       # TTS 服务地址
```

**注意**：`config.yaml` 被 volume 挂载，发布时 `rsync` 需 `--exclude='config.yaml'` 防止被覆盖。

---

## 🎬 前端操作方法

### 1. 首页 — 项目列表

| 操作 | 方法 |
|------|------|
| 新建项目 | 输入名称 → 点击"+ 新建项目"或回车 |
| 点进项目 | 点击项目卡片 |
| 重命名 | 点击"重命名"按钮（**非标题文本**，标题文本点击会触发编辑模式，这是已知 UX Issue） |
| 删除项目 | 点击"删除"按钮 → 确认 |
| 导出/导入 | 在项目详情页顶部右侧 |

首页显示：项目名、角色数、剧集数、创建时间、修改时间

### 2. 详情页 — 4 个 Tab

#### 📝 AI 生成（默认 Tab）
完整的 AI 辅助内容生产流程：

1. **写剧情描述** → 编辑摘要框（也可从大纲/小说粘贴）
2. **选角色** → 先定义角色（切换 Characters tab），再回到此页面
3. **设置参数**：
   - `总集数` / `每集时长（分钟）` / `旁白比例`
   - `风格` / `额外指令`
4. **生成大纲** → 点击"🚀 生成大纲"，LLM 生成剧集摘要
5. **选择要生成对白的剧集** → 自动勾选**未生成对白的前 3 集**（已有对白的不勾选）
6. **生成对白** → 点击"💬 确认并生成对白→"
7. **批量生成** → 在剧集面板点击"🚀 批量生成旁白+对白"

> 💡 对白自动 ≤250 字符，超出部分自动切分

#### 📺 剧集
查看/管理所有剧集和对白：

| 操作 | 方法 | 备注 |
|------|------|------|
| 新增剧集 | 输入标题 → 添加 | 生成大纲时自动创建 |
| 查看对白 | 点击剧集展开 | 显示角色、文本、生成状态 |
| 编辑对白 | 点击文本直接编辑 | |
| 删除剧集 | 删除按钮 → 确认 | 包含所有对白和音频 |
| 单条生成音频 | 点对白旁的 🔊 | 异步，15min+ |
| 批量生成音频 | "批量生成"按钮 | 只选尚未生成的 |
| 下载串联音频 | 下载 → 串联下载 | 所有音频混音后下载 |
| 批量替换角色 | 批量换角功能 | 一键替换剧中角色 |

#### 👤 角色
管理项目角色及其音效：

| 操作 | 方法 |
|------|
| 添加角色（名称/音色/语速/音调/风格指令/角色描述） |
| 编辑/删除角色 |
| 角色音效链设置（Pitch/Reverb/Delay/Compressor 等） |
| 音效预览 — 试听效果 |

#### ⚙️ 设置
项目级 TTS 采样参数：
- `temperature` / `do_sample` / `top_k` / `top_p` / `repetition_penalty`

### 3. 🎬 多轨时间线

在剧集详情中进入时间线编辑模式：

| 操作 | 说明 |
|------|------|
| 自动组装 | 已有音频的对白自动排入时间线 |
| 拖拽调整 | 调整 clip 位置（前端实现中） |
| 添加音轨 | BGM、SFX 独立音轨 |
| 导入音频 | 上传 wav/mp3/flac |
| clip 操作 | 分割、复制、淡入淡出 |
| 混音导出 | 下载为 WAV |
| 即时预览 | 浏览器流式试听 |
| 快照 | 保存/恢复时间线版本 |
| RMS 归一化 | 统一音量 |

### 4. ⚙️ 系统设置页
- 全局 LLM 配置（API 地址 / Key / 模型 / 超时 / 温度等）
- 全局 TTS 采样默认参数

---

## 🔗 API 概览

| 路由 | 方法 | 说明 |
|------|------|------|
| `/api/health` | GET | 健康检查 |
| `/api/projects` | GET/POST | 项目列表/创建 |
| `/api/projects/{id}` | GET/PATCH/DELETE | 项目详情/修改/删除 |
| `/api/projects/{id}/characters` | GET/POST | 角色列表/添加 |
| `/api/projects/{id}/characters/{cid}` | PATCH/DELETE | 修改/删除角色 |
| `/api/projects/{id}/episodes` | GET/POST | 剧集列表/创建 |
| `/api/projects/{id}/episodes/{eid}/dialogues` | GET/POST | 对白列表/添加 |
| `/api/projects/{id}/episodes/{eid}/dialogues/batch` | POST | 批量添加对白 |
| `/api/.../dialogues/{did}/generate` | POST | 提交 TTS 生成 |
| `/api/projects/{id}/apply-character-effects/{cid}` | POST | 批量应用角色音效 |
| `/api/.../timeline/*` | POST/GET/PUT/DELETE | 时间线全功能 |
| `/api/voices` | GET | 可用音色列表 |
| `/api/config` | GET/PATCH | 配置读写 |
| `/api/audio-effects/registry` | GET | 音频效果注册表 |
| `/api/audio-effects/presets` | GET | 内置效果预设 |

---

## 🔄 LLM 对白生成流程

### 两步解析法（已废弃，保留兼容）

旧方案：LLM 先生成故事文本 → 再用 `_parse_story_text()` 正则解析提取角色和对话。

### 一步解析法（当前方案）

```
raw_text + 规则 prompt → LLM → 直接返回 JSON 对白数组
```

- `parse_story_direct()`（`dialogue_parser.py`）— 当前主力
- 规则位置重要：字数约束放第 1 条，后处理器 `_chunk_long_texts()` 兜底
- 避免 content/reasoning 分裂的商汤 API 兼容

---

## 🔊 音频效果

基于 Spotify `pedalboard` 库，支持：

| 效果 | 参数 |
|------|------|
| Pitch Shift | `semitones`（-12~+12） |
| Reverb | `room_size` / `wet_level` / `dry_level` / `damping` / `width` / `freeze_mode` |
| Delay | `delay_time` / `feedback` / `mix` |
| Chorus | `rate_depth` / `centre_delay` / `feedback` / `mix` |
| Compressor | `threshold` / `ratio` / `attack` / `release` |
| Gain | `db` |
| Highpass/Lowpass | `cutoff_freq` |

内置预设：`deep_voice` / `radio` / `phone` / `echo` / `muffled` 等。

---

## 🔄 TTS 生成机制

- **异步 fire-and-forget**：提交立即返回 `task_id`，后台轮询下载
- **极慢**：单条平均 33k 秒，建议 15 分钟后手动刷新
- **音色列表**：aiden / dylan / eric / ono_anna / ryan / serena / sohee / uncle_fu / vivian
- **角色自动匹配**：找不到角色 ID 时自动创建兜底
- **出错处理**：写入 `interrupted` 占位，用户可刷新后重试

---

## 💾 数据存储

- **持久化**：`data/studio.json`（JSON 文件，原子写入：先写 `.tmp` 再 `os.replace`）
- **音频文件**：`data/audio/` 目录
- **日志**：`data/logs/main.log`
- **并发安全**：`asyncio.Lock` 保护写操作 + per-project lock 防多集生成数据竞争

---

## 🧪 已知 UX Issues（待完善）

| 优先级 | Issue | 说明 |
|--------|-------|------|
| ✅ 已修复 | 批量生成锁竞争 | PR #59 |
| ✅ 已修复 | 对白字数约束 | PR #60 |
| ✅ 已修复 | 复选框自动勾选 | PR #61 |
| ❌ P2 | 标题点击即编辑 | 易误触，需加图标按钮 |
| ❌ P2 | 剧集详情入口 | 需点击剧集直接进入 |
| ❌ P3 | 首页时间空白 | 创建/修改时间字段缺失 |
| ❌ P3 | 无进度反馈 | 声音生成只能盲等 |

详细列表见 `docs/usage.md` 或 `memory/tts/tts-studio-frontend-ux-issues.md`。

---

## 📚 参考文档

| 文档 | 内容 |
|------|------|
| `docs/character-voice-design.md` | 角色音色设计指南 |
| `docs/two-step-dialogue-parsing.md` | 两步解析法设计文档 |
| `docs/dialogue-generation-plan.md` | 对白生成方案 |
| `docs/dialogue-gen-b2-spec.md` | B2 方案B-2 规格 |
| `docs/batch-operations-guide.md` | 批量操作指南 |
| `docs/insert-dialogue.md` | 对白插入 API |
| `docs/TTS_SAMPLING_PARAMS.md` | TTS 采样参数说明 |
| `docs/timeline.md` | 时间线编辑说明 |
| `docs/CHECKLIST.md` | 发布检查清单 |
| `CHANGELOG.md` | 变更日志 |

---

## 🛠️ 开发

### 前端编译
```bash
cd frontend
npm install --legacy-peer-deps
npm run build
```
修改 `.tsx` 后必须重新编译（SPA 无 HMR）。

### 容器内部署
```bash
rsync -av --exclude='config.yaml' --exclude='__pycache__' app/ hermes@host:/work/docker/tts-studio/app/
docker cp frontend/dist tts-studio-for-test:/app/frontend/
docker restart tts-studio-for-test
```

### 测试
```bash
pytest tests/ -v
```
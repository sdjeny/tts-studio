# TTS Studio

语音合成工作台 — 基于 FastAPI + React 的 Web 应用，支持剧本管理、多角色 TTS 合成、音频效果处理。

## 项目结构

```
tts-studio/
├── app/                          # 后端 (FastAPI)
│   ├── main.py                   # 入口，日志/中间件/路由挂载
│   ├── api/
│   │   ├── projects.py           # 项目/角色/音频效果 API
│   │   └── episodes.py           # 剧集/对白/生成 API
│   │   └── qwen3-tts/            # Qwen3-TTS 子服务（独立 Flask）
│   ├── core/
│   │   ├── store.py              # JSON 文件存储（项目/剧集数据）
│   │   ├── tts.py                # TTS 引擎封装
│   │   ├── llm.py                # LLM 解析（剧本结构化）
│   │   ├── audio_effects.py      # 音频效果链（音效预览/应用）
│   │   ├── config.py             # 配置加载
│   │   └── models.py             # Pydantic 模型
│   └── memory_proxy/             # Memory-Proxy 服务（端口 5000）
│       ├── app.py                # Flask 入口
│       └── docs/                 # 架构文档
├── data/                         # 数据目录（项目根目录）
│   ├── audio/                    # 生成的音频文件
│   ├── logs/
│   │   └── main.log              # 后端日志
│   └── studio.json               # 项目/剧集数据存储
├── frontend/                     # 前端 (React + Vite)
│   ├── src/
│   │   └── api.ts                # API 调用封装
│   └── dist/                     # 构建产物（由 Vite 生成）
├── Dockerfile
├── docker-compose.yml
└── requirements.txt
```

## 启动

### 后端

```bash
cd tts-studio
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

- API 文档: http://localhost:8000/docs
- 健康检查: http://localhost:8000/api/health
- 日志文件: `data/logs/main.log`

### Memory-Proxy（可选）

```bash
cd app/memory_proxy
python app.py
```

监听端口 5000，提供 LLM 代理 + 记忆存储。

### 前端开发

```bash
cd frontend
npm run dev
```

生产构建产物输出到 `frontend/dist/`，由 FastAPI 直接 serve。

## API 概览

### 项目管理

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/projects` | 项目列表 |
| POST | `/api/projects` | 创建项目 |
| GET | `/api/projects/{id}` | 项目详情（含角色、剧集） |
| PATCH | `/api/projects/{id}` | 重命名项目 |
| DELETE | `/api/projects/{id}` | 删除项目 |

### 角色管理

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/projects/{id}/characters` | 角色列表 |
| POST | `/api/projects/{id}/characters` | 添加角色 |
| PATCH | `/api/projects/{id}/characters/{cid}` | 更新角色（音色/音效等） |
| DELETE | `/api/projects/{id}/characters/{cid}` | 删除角色 |

### 剧集 & 对白

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/projects/{id}/episodes/{eid}` | 剧集详情（含对白） |
| POST | `/api/projects/{id}/episodes` | 创建剧集 |
| PATCH | `/api/projects/{id}/episodes/{eid}` | 更新剧集 |
| DELETE | `/api/projects/{id}/episodes/{eid}` | 删除剧集 |
| POST | `/api/projects/{id}/episodes/{eid}/dialogues` | 添加对白 |
| POST | `/api/projects/{id}/episodes/{eid}/dialogues/batch` | 批量添加对白 |
| PATCH | `/api/projects/{id}/episodes/{eid}/dialogues/{did}` | 更新对白 |
| DELETE | `/api/projects/{id}/episodes/{eid}/dialogues/{did}` | 删除对白 |
| DELETE | `/api/projects/{id}/episodes/{eid}/dialogues/{did}/purge` | 删除对白及音频文件 |
| DELETE | `/api/projects/{id}/episodes/{eid}/purge-dialogues` | 批量删除剧集对白 |

### 音频生成

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/projects/{id}/episodes/{eid}/dialogues/{did}/generate` | 提交 TTS 任务（fire-and-forget） |
| POST | `/api/projects/{id}/episodes/{eid}/dialogues/{did}/refresh` | 刷新状态，下载已完成的音频 |
| DELETE | `/api/projects/{id}/episodes/{eid}/dialogues/{did}/history` | 清空音频历史 |
| POST | `/api/projects/{id}/episodes/{eid}/dialogues/{did}/history/{aid}/activate` | 将历史音频设为当前起效 |
| DELETE | `/api/projects/{id}/episodes/{eid}/dialogues/{did}/history/{aid}` | 删除单条历史音频 |
| GET | `/api/projects/{id}/episodes/{eid}/dialogues/{did}/download/{aid}` | 下载单条音频 |
| GET | `/api/projects/{id}/episodes/{eid}/download-all` | 下载剧集全部音频（ZIP） |

TTS 生成是异步的：`generate` 立即返回 `status: "generating"`，后台提交 TTS 任务。前端需手动点"刷新"触发 `refresh` 接口检查状态并下载已完成的音频。**无轮询，纯手动刷新。**

### 音频效果架构

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/audio-effects/registry` | 效果器注册表（参数定义） |
| GET | `/api/audio-effects/presets` | 内置预设列表 |
| POST | `/api/projects/{id}/audio-effects/preview` | 效果预览（试听） |
| POST | `/api/projects/{id}/apply-character-effects/{cid}` | **批量应用角色音效到所有剧集** |
| POST | `/api/projects/{id}/episodes/{eid}/dialogues/{did}/apply-effects` | 对单条对白应用角色音效 |

**音效设计原则**：
- 音效跟随**角色**，不是跟随对白
- TTS 生成后保存为 `raw=True`（原始音频），**不自动应用音效**
- 角色面板配置音效链，通过"✨ 应用音效到全部剧集"按钮批量处理
- 批量应用时，已处理过的音频（`raw=False`）自动跳过
- 角色音效修改后可重新应用
- 旁白角色也有声音（voice_id），只是通常不配置音效

**可用效果器**：`pitch_shift`、`reverb`、`delay`、`chorus`、`compressor`、`gain`、`highpass`、`lowpass`

### 音频记录字段

每条音频历史记录包含：

| 字段 | 类型 | 说明 |
|------|------|------|
| id | string | 唯一标识 |
| url | string | 播放地址（`/static/audio/xxx.wav`） |
| filename | string | 磁盘文件名 |
| created_at | string | 创建时间 |
| raw | boolean | True=原始音频，False=已应用音效 |
| duration | number | 音频时长（秒） |
| status | string | 状态（generating/failed） |
| error | string | 错误信息（失败时） |

### LLM 辅助

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/projects/{id}/generate-episodes` | LLM 生成故事大纲（批量创建剧集） |
| POST | `/api/projects/{id}/episodes/{eid}/generate-dialogues` | LLM 生成对白 |
| POST | `/api/projects/{id}/episodes/{eid}/generate-next` | LLM 生成下一集 |
| POST | `/api/projects/{id}/regenerate-from/{eid}` | 从指定集数重新生成后续 |
| POST | `/api/projects/{id}/batch-replace-character` | 批量替换角色名 |

### 导入导出

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/projects/{id}/episodes/{eid}/export` | 导出剧集 JSON |
| POST | `/api/projects/{id}/episodes/{eid}/import` | 导入剧集 |
| GET | `/api/projects/{id}/export` | 导出整个项目 |
| POST | `/api/projects/{id}/import` | 导入项目 |

## 数据存储

- 所有项目/剧集/对白数据存储在 `data/studio.json`
- 音频文件存储在 `data/audio/`
- 日志文件在 `data/logs/main.log`
- 采用 JSON 文件存储，无数据库依赖

## 注意事项

- 音频文件路径：`data/audio/`（项目根目录），确保磁盘空间充足
- TTS 服务需要配置 `TTS_API_KEY` 环境变量
- 前端构建后需重启 FastAPI 才能 serve 最新产物
- `refresh` 接口返回的是**整个剧集**对象，需从中提取目标对白

# 多轨时间线编辑 (Timeline Editor)

## 概述

TTS Studio 的多轨时间线编辑器借鉴自 [voicebox](https://github.com/jamiepine/voicebox)，允许用户将剧集中的多段对白音频编排合并为完整的剧集音频。

## 核心概念

### 时间线 (Timeline)
每个剧集可以有一个时间线，存储在 `episode.timeline` JSON 字段中。时间线包含：
- **轨道 (Tracks)**：音轨，如"对话"、"背景音乐"、"音效"
- **片段 (Clips)**：音频片段，放置在轨道上的特定时间位置
- **导入音频 (Imported Audio)**：用户上传的背景音乐/音效文件
- **快照 (Snapshots)**：时间线状态的保存点，支持撤销

### 非破坏性编辑
所有编辑操作（裁剪、音量、淡入淡出、效果）都是元数据，原始音频文件永远不会被修改。

## 使用流程

### 1. 自动装配
点击"🎬 从对白自动装配"按钮，系统会：
- 查找所有已完成音频生成的对白
- 按对白顺序依次排列到"对话"轨道
- 片段间距默认 0.5 秒

### 2. 编辑时间线
- **移动片段**：拖拽片段左右移动（调整时间位置）
- **裁剪片段**：拖拽片段左右边缘（调整起点/终点）
- **调整音量**：片段顶部的音量线
- **删除片段**：选中后按 Delete 键或点击 ✕
- **复制片段**：点击 ⧉ 按钮
- **分割片段**：选中后点击工具栏分割按钮

### 3. 轨道操作
- **添加轨道**：点击"+ 添加轨道"按钮
- **静音/独奏**：轨道头部的 M/S 按钮
- **轨道音量**：轨道头部的音量滑块
- **删除轨道**：轨道头部的 ✕ 按钮（不能删除最后一个轨道）

### 4. 导入音频
- 点击"📥 导入音频"按钮
- 支持 WAV, MP3, FLAC, OGG, M4A, AAC, WEBM 格式
- 导入后自动创建"背景音乐"轨道并添加片段

### 5. 音量一致化
- 点击"🔊 音量一致化"按钮
- 对所有片段进行 RMS 归一化（目标 -20 dB）
- 生成新的标准化音频文件

### 6. 预览播放
- 点击 ▶ 按钮播放时间线
- 使用 Web Audio API 实时混音播放
- 空格键播放/暂停

### 7. 导出
- 点击"📤 导出"按钮
- 服务器端混音：numpy 加法混音 → 峰值归一化 → 可选 RMS 归一化
- 输出 WAV 格式

### 8. 快照
- 点击"💾 快照"保存当前状态
- 最多保存 10 个快照
- 可恢复到任意历史快照

## 技术架构

### 数据模型

```json
{
  "timeline": {
    "version": 1,
    "sample_rate": 24000,
    "total_duration": 120.5,
    "master_volume": 1.0,
    "tracks": [
      {
        "id": "track_xxx",
        "name": "对话",
        "type": "dialogue",
        "order": 0,
        "volume": 1.0,
        "muted": false,
        "solo": false,
        "locked": false,
        "height": 80,
        "color": "#3b82f6"
      }
    ],
    "clips": [
      {
        "id": "clip_xxx",
        "track_id": "track_xxx",
        "source_type": "dialogue",
        "source_id": "dlg_xxx",
        "source_audio_id": "audio_xxx",
        "audio_filename": "taskid.wav",
        "offset_in_source": 0.0,
        "duration_in_source": 4.5,
        "start_time": 0.0,
        "duration": 4.5,
        "volume": 1.0,
        "fadeIn": 0.0,
        "fadeOut": 0.0,
        "crossfade_in": 0.0,
        "crossfade_out": 0.0,
        "effects_chain": []
      }
    ],
    "imported_audio": [],
    "snapshots": []
  }
}
```

### 音频处理 (`app/core/timeline_audio.py`)

| 函数 | 说明 |
|------|------|
| `load_audio()` | 加载音频文件，统一采样率，转单声道 |
| `compute_rms_db()` | 计算 RMS 响度 |
| `normalize_rms()` | RMS 归一化到目标 dB |
| `apply_volume_and_fades()` | 音量增益 + 线性淡入淡出 + 等功率交叉淡化 |
| `get_clip_audio()` | 加载单个片段（裁剪+效果+音量+淡入淡出） |
| `mix_timeline()` | 多轨混音主函数（加法混音 → 峰值归一化 → RMS 归一化） |
| `concatenate_clips()` | 单轨顺序拼接（带交叉淡化） |
| `save_audio()` | 保存 numpy 数组为 WAV 文件 |

### 混音算法

1. 计算所有片段的最大结束时间 → 总时长
2. 创建 numpy 零缓冲区
3. 遍历每个轨道（按 order 排序）：
   - 跳过静音轨道
   - 如果有独奏轨道，跳过非独奏轨道
   - 遍历轨道上的每个片段：
     - 加载音频 → 裁剪 → 应用效果 → 应用音量/淡入淡出
     - 乘以轨道音量
     - 加法混音到主缓冲区
4. 峰值归一化（防止削波）
5. 可选 RMS 归一化（目标 -20 dB）

### 前端组件 (`frontend/src/components/Timeline.tsx`)

| 组件 | 说明 |
|------|------|
| `Timeline` | 主组件：工具栏、轨道列表、播放控制 |
| `TimelineRuler` | 时间标尺：刻度线、点击定位、播放头 |
| `ClipWidget` | 片段控件：拖拽移动、左右裁剪手柄、音量线、操作按钮 |
| `TrackHeader` | 轨道头部：名称、静音/独奏/锁定、音量滑块、删除 |

### Web Audio API 预览

- 使用 `AudioContext` 创建主 `GainNode`
- 每个片段创建 `AudioBufferSourceNode` + 独立 `GainNode`
- 使用 `AudioContext.currentTime` 进行采样精确调度
- `requestAnimationFrame` 循环更新播放头位置

## API 参考

所有端点位于 `/api/projects/{project_id}/episodes/{episode_id}/timeline/*`

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/assemble` | 从对白自动装配时间线 |
| GET | `/` | 获取时间线 |
| POST | `/clips` | 添加片段 |
| PUT | `/clips/{cid}` | 更新片段 |
| DELETE | `/clips/{cid}` | 删除片段 |
| POST | `/clips/{cid}/duplicate` | 复制片段 |
| POST | `/clips/{cid}/split` | 分割片段 |
| POST | `/tracks` | 添加轨道 |
| PUT | `/tracks/{tid}` | 更新轨道 |
| DELETE | `/tracks/{tid}` | 删除轨道 |
| POST | `/import-audio` | 导入音频文件 |
| POST | `/normalize` | 音量一致化 |
| POST | `/export` | 混音导出 |
| GET | `/preview` | 预览播放流 |
| POST | `/snapshot` | 保存快照 |
| GET | `/snapshots` | 列快照 |
| POST | `/snapshots/{v}/restore` | 恢复快照 |

## 依赖

- 后端：`numpy`, `soundfile`, `pedalboard`（已有）
- 前端：React 19, TypeScript 5.6, Vite 6（已有）
- 无需额外安装

## 限制

- 目前只支持 WAV 格式导出
- 采样率固定 24000 Hz（与 TTS 输出一致）
- 导入音频自动转换为单声道
- 快照最多保存 10 个
- 时间线数据存储在 JSON 文件中，不适合超大型项目

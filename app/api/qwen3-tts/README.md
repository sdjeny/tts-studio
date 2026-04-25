# Qwen3-TTS API 服务

基于 Qwen3-TTS 模型的异步语音合成 API 服务，支持多角色、情感控制。

## 目录结构

```
qwen3-tts/
├── server.py         # API 服务主程序（Flask）
├── tts_client.py     # 第三方调用客户端（封装 UA/超时/重试）
├── test_api.py       # 自动测试用例（使用 tts_client）
├── test_tts.py       # 原始参考脚本（直接调用模型，不动）
├── config.yaml       # 本地配置（不提交 git）
├── requirements.txt  # pip 依赖
├── start.bat         # Windows 一键启动
└── test_output/      # 测试下载目录（不提交 git）
```

## 快速启动

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置

编辑 `config.yaml`，修改 `model_path` 和 `api.base_url` 为实际值。

### 3. 启动服务

双击 `start.bat`，或：

```bash
python server.py
```

看到 `Running on http://...` 即启动成功。

## API 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/tts/health` | 健康检查 |
| POST | `/tts/submit` | 提交任务，返回 task_id |
| GET | `/tts/status/<id>` | 查询任务状态 |
| GET | `/tts/download/<id>` | 下载音频（wav） |
| GET | `/tts/queue` | 队列概况 |

## 调用示例（tts_client）

```python
from tts_client import TtsClient

client = TtsClient("http://127.0.0.1:8420")

# 提交任务
result = client.submit(
    text="你好，欢迎使用语音合成服务。",
    speaker="Dylan",
    instruct="愉快，轻松，语速中等",
)
print(result.task_id)  # 如：20260426_abc123...

# 等待完成
sr = client.wait(result.task_id)
if sr.ok:
    # 下载音频
    dl = client.download(result.task_id)
    with open("output.wav", "wb") as f:
        f.write(dl.data)
```

## 任务状态流转

```
pending → processing → success / failed
```

- `pending`：排队等待
- `processing`：正在合成
- `success`：合成完成，可下载
- `failed`：合成失败，查看详情中的 error 字段

## 输出文件

- 音频文件存储在 `output_audio/` 目录
- 文件名格式：`YYYYMMDD_<uuid>.wav`，日期前缀方便按天清理

## 配置说明（config.yaml）

```yaml
server:
  host: "0.0.0.0"
  port: 8420

api:
  base_url: "http://127.0.0.1:8420"   # test_api.py 从此读取

model:
  model_path: "C:/path/to/Qwen3-TTS-..."
  device_map: "cpu"       # cpu / cuda
  torch_dtype: "float32"  # float16 / float32 / bfloat16

output:
  base_dir: "output_audio"
```

## 测试

服务启动后，另开终端运行：

```bash
python test_api.py
```

覆盖：健康检查、提交（含 speaker/instruct）、空文本校验、状态查询、队列概况、等待完成、下载、404 校验、多角色情感（旁白/愤怒/温柔）。

## 注意事项

- 服务为**单线程队列**，任务按提交顺序依次处理，不并发
- `tts_client.py` 内部已统一处理 User-Agent，调用方无需关心 CDN 拦截问题
- `config.yaml` 包含本地路径，已加入 `.gitignore`，不会被提交

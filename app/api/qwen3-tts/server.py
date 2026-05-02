"""
Qwen3-TTS 异步 API 服务
- 提交任务 → 返回唯一编号
- 单线程排队处理（不并发）
- 状态查询：pending / processing / success / failed
- 下载音频文件
- 输出文件名带日期前缀，统一管理在 output_audio/ 下
"""
import uuid
import yaml
import threading
import logging
from datetime import datetime
from queue import Queue
from pathlib import Path

from flask import Flask, request, jsonify, send_file

# ── 日志 ──────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("tts-api")

# ── 加载配置 ───────────────────────────────────────────
BASE_DIR = Path(__file__).parent
CONFIG_PATH = BASE_DIR / "config.yaml"

with open(CONFIG_PATH, "r", encoding="utf-8") as f:
    CONFIG = yaml.safe_load(f)

MODEL_PATH = CONFIG["model"]["model_path"]
DEVICE_MAP = CONFIG["model"].get("device_map", "cpu")
TORCH_DTYPE_STR = CONFIG["model"].get("torch_dtype", "float32")
OUTPUT_BASE = Path(CONFIG["output"]["base_dir"])
SERVER_HOST = CONFIG["server"].get("host", "0.0.0.0")
SERVER_PORT = CONFIG["server"].get("port", 8420)

# ── 全局状态 ───────────────────────────────────────────
task_queue: Queue = Queue()
task_store: dict[str, dict] = {}   # task_id → task_info
store_lock = threading.Lock()

# ── Flask 应用 ─────────────────────────────────────────
app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024  # 16 MB


# ──────────────────────────────────────────────────────
# 模型加载（懒加载，首次任务触发）
# ──────────────────────────────────────────────────────
_model = None


def get_model():
    global _model
    if _model is not None:
        return _model

    import torch
    from qwen_tts import Qwen3TTSModel

    dtype_map = {"float16": torch.float16, "float32": torch.float32, "bfloat16": torch.bfloat16}
    torch_dtype = dtype_map.get(TORCH_DTYPE_STR, torch.float32)

    log.info("正在加载模型: %s", MODEL_PATH)
    _model = Qwen3TTSModel.from_pretrained(
        MODEL_PATH,
        device_map=DEVICE_MAP,
        torch_dtype=torch_dtype,
        local_files_only=True,
    )
    log.info("模型加载完成")
    return _model


# ──────────────────────────────────────────────────────
# Worker：单线程从队列取任务并调用 model.generate_custom_voice
# ──────────────────────────────────────────────────────
def worker_loop():
    import soundfile as sf
    import numpy as np

    log.info("Worker 线程启动，等待任务...")
    while True:
        task = task_queue.get()
        if task is None:  # 毒丸退出
            break

        task_id = task["task_id"]
        with store_lock:
            task_store[task_id]["status"] = "processing"
            task_store[task_id]["started_at"] = datetime.now().isoformat()

        try:
            model = get_model()

            text = task["text"]
            language = task.get("language", "Chinese")
            speaker = task.get("speaker", "")
            instruct = task.get("instruct", "")

            # ── 采样控制参数（保守默认值，最小化声音波动） ──────────
            _def_temp = 0.3
            _def_top_k = 20
            _def_top_p = 0.85
            _def_rep_pen = 1.1

            # task 中的值可能为 None（旧客户端未传），此时使用保守默认值
            temperature = task["temperature"] if task.get("temperature") is not None else _def_temp
            do_sample    = task["do_sample"]    if task.get("do_sample")    is not None else True
            top_k        = task["top_k"]        if task.get("top_k")        is not None else _def_top_k
            top_p        = task["top_p"]        if task.get("top_p")        is not None else _def_top_p
            rep_penalty  = task["repetition_penalty"] if task.get("repetition_penalty") is not None else _def_rep_pen

            generate_kwargs = {
                "temperature": temperature,
                "do_sample": do_sample,
                "top_k": top_k,
                "top_p": top_p,
                "repetition_penalty": rep_penalty,
            }

            # 打印完整生成参数，便于排查参数透传问题
            log.info(
                "[%s] 开始生成 | text=%.30s | speaker=%s | instruct=%s | "
                "temp=%.2f | sample=%s | top_k=%d | top_p=%.2f | rep_pen=%.2f",
                task_id[:8], text, speaker, instruct,
                temperature, do_sample, top_k, top_p, rep_penalty,
            )

            wavs, sr = model.generate_custom_voice(
                text=text,
                language=language,
                speaker=speaker,
                instruct=instruct,
                **generate_kwargs,
            )

            clip = wavs[0] if isinstance(wavs, list) else wavs

            OUTPUT_BASE.mkdir(parents=True, exist_ok=True)
            filename = f"{task_id}.wav"
            filepath = OUTPUT_BASE / filename
            sf.write(str(filepath), clip, sr)

            with store_lock:
                task_store[task_id]["status"] = "success"
                task_store[task_id]["file_path"] = str(filepath)
                task_store[task_id]["finished_at"] = datetime.now().isoformat()

            log.info("[%s] 生成成功: %s", task_id[:8], filepath)

        except Exception as e:
            log.error("[%s] 生成失败: %s", task_id[:8], e, exc_info=True)
            with store_lock:
                task_store[task_id]["status"] = "failed"
                task_store[task_id]["error"] = str(e)
                task_store[task_id]["finished_at"] = datetime.now().isoformat()

        finally:
            task_queue.task_done()


# ── 启动 Worker 守护线程 ───────────────────────────────
worker_thread = threading.Thread(target=worker_loop, daemon=True)
worker_thread.start()


# ──────────────────────────────────────────────────────
# 路由
# ──────────────────────────────────────────────────────

@app.route("/tts/submit", methods=["POST"])
def submit_task():
    """提交 TTS 任务，返回 task_id"""
    data = request.get_json(silent=True) or {}

    text = data.get("text", "").strip()
    if not text:
        return jsonify({"error": "text 不能为空"}), 400

    date_prefix = datetime.now().strftime("%Y%m%d")
    task_id = f"{date_prefix}_{uuid.uuid4().hex}"
    task = {
        "task_id": task_id,
        "text": text,
        "language": data.get("language", "Chinese"),
        "speaker": data.get("speaker", ""),
        "instruct": data.get("instruct", ""),
        # ── 采样控制参数（可选，未传则使用 worker 中的保守默认值） ──
        "temperature": data.get("temperature"),          # float | None
        "do_sample": data.get("do_sample"),              # bool | None
        "top_k": data.get("top_k"),                      # int | None
        "top_p": data.get("top_p"),                      # float | None
        "repetition_penalty": data.get("repetition_penalty"),  # float | None
        "status": "pending",
        "submitted_at": datetime.now().isoformat(),
    }

    with store_lock:
        task_store[task_id] = task

    task_queue.put(task)
    pos = task_queue.qsize()

    log.info("[%s] 任务入队，当前排队: %d", task_id[:8], pos)
    return jsonify({"task_id": task_id, "position": pos}), 202


@app.route("/tts/status/<task_id>", methods=["GET"])
def query_status(task_id):
    """查询任务状态"""
    with store_lock:
        task = task_store.get(task_id)
    if not task:
        return jsonify({"error": "task_id 不存在"}), 404

    resp = {
        "task_id": task_id,
        "status": task["status"],
        "submitted_at": task.get("submitted_at"),
    }
    if task["status"] == "processing":
        resp["started_at"] = task.get("started_at")
    elif task["status"] == "success":
        resp["finished_at"] = task.get("finished_at")
        resp["download_url"] = f"/tts/download/{task_id}"
    elif task["status"] == "failed":
        resp["finished_at"] = task.get("finished_at")
        resp["error"] = task.get("error")

    return jsonify(resp)


@app.route("/tts/download/<task_id>", methods=["GET"])
def download_audio(task_id):
    """下载生成的音频文件"""
    with store_lock:
        task = task_store.get(task_id)
    if not task:
        return jsonify({"error": "task_id 不存在"}), 404
    if task["status"] != "success":
        return jsonify({"error": f"任务状态不是 success，当前: {task['status']}"}), 404

    filepath = Path(task["file_path"])
    if not filepath.exists():
        return jsonify({"error": "音频文件不存在，可能已被清理"}), 404

    return send_file(str(filepath), mimetype="audio/wav", as_attachment=True,
                     download_name=f"{task_id}.wav")


@app.route("/tts/queue", methods=["GET"])
def queue_info():
    """查看队列概况"""
    with store_lock:
        all_tasks = list(task_store.values())

    pending = sum(1 for t in all_tasks if t["status"] == "pending")
    processing = sum(1 for t in all_tasks if t["status"] == "processing")
    success = sum(1 for t in all_tasks if t["status"] == "success")
    failed = sum(1 for t in all_tasks if t["status"] == "failed")

    return jsonify({
        "queue_size": task_queue.qsize(),
        "total": len(all_tasks),
        "pending": pending,
        "processing": processing,
        "success": success,
        "failed": failed,
    })


@app.route("/tts/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})


# ──────────────────────────────────────────────────────
# 入口
# ──────────────────────────────────────────────────────
if __name__ == "__main__":
    log.info("启动 Qwen3-TTS API 服务 %s:%d", SERVER_HOST, SERVER_PORT)
    app.run(host=SERVER_HOST, port=SERVER_PORT, debug=False)

"""
Qwen3-TTS 异步 API 服务（Base 模型 - Voice Clone）
- 加载 Qwen3-TTS-12Hz-1.7B-Base 模型
- 提交任务 → 返回唯一编号
- 单线程排队处理（不并发）
- 状态查询：pending / processing / success / failed
- 下载音频文件
- 输出文件名带日期前缀，统一管理在 output_audio/ 下
- Voice Clone 管理：从参考音频生成说话人 embedding pt 文件

每个说话人存储结构（voice_clones/<name>/）：
  ├── meta.json        { name, description, ref_text, created_at }
  ├── ref_audio.wav    参考音频
  └── embedding.pt     VoiceClonePromptItem 序列化
"""
import uuid
import yaml
import threading
import logging
import json
import base64
import io
from datetime import datetime
from queue import Queue
from pathlib import Path

from flask import Flask, request, jsonify, send_file, Response

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

# Voice Clone 存储根目录：每个说话人一个子目录
CLONE_DIR = BASE_DIR / "voice_clones"
CLONE_DIR.mkdir(parents=True, exist_ok=True)

# ── 全局状态 ───────────────────────────────────────────
task_queue: Queue = Queue()
task_store: dict[str, dict] = {}   # task_id → task_info
store_lock = threading.Lock()

# ── Flask 应用 ─────────────────────────────────────────
app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024  # 50 MB（支持上传参考音频）


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

    log.info("正在加载 Base 模型: %s", MODEL_PATH)
    _model = Qwen3TTSModel.from_pretrained(
        MODEL_PATH,
        device_map=DEVICE_MAP,
        torch_dtype=torch_dtype,
        local_files_only=True,
    )
    log.info("Base 模型加载完成")
    return _model


# ──────────────────────────────────────────────────────
# Voice Clone 工具函数
# ──────────────────────────────────────────────────────
def _clone_dir(name: str) -> Path:
    """获取说话人存储目录"""
    return CLONE_DIR / name


def _clone_pt_path(name: str) -> Path:
    return _clone_dir(name) / "embedding.pt"


def _clone_audio_path(name: str) -> Path:
    return _clone_dir(name) / "ref_audio.wav"


def list_voice_clones() -> list[dict]:
    """列出所有已保存的 voice clone"""
    clones = []
    for d in sorted(CLONE_DIR.iterdir()):
        if not d.is_dir():
            continue
        meta_path = d / "meta.json"
        pt_path = d / "embedding.pt"
        audio_path = d / "ref_audio.wav"
        meta = {}
        if meta_path.exists():
            try:
                with open(meta_path, "r", encoding="utf-8") as f:
                    meta = json.load(f)
            except Exception:
                pass
        clones.append({
            "name": d.name,
            "description": meta.get("description", ""),
            "ref_text": meta.get("ref_text", ""),
            "created_at": meta.get("created_at", ""),
            "has_audio": audio_path.exists(),
            "has_pt": pt_path.exists(),
            "pt_size_bytes": pt_path.stat().st_size if pt_path.exists() else 0,
        })
    return clones


def load_voice_clone_prompt(name: str):
    """加载 voice clone 的 embedding pt"""
    pt_path = _clone_pt_path(name)
    if not pt_path.exists():
        return None
    import torch
    data = torch.load(str(pt_path), map_location="cpu", weights_only=False)
    return data


def save_voice_clone(name: str, prompt_item, audio_data, audio_sr,
                     ref_text: str = "", description: str = ""):
    """
    保存 voice clone：
    - meta.json: { name, description, ref_text, created_at }
    - ref_audio.wav: 参考音频
    - embedding.pt: VoiceClonePromptItem 序列化
    """
    import torch
    import soundfile as sf

    d = _clone_dir(name)
    d.mkdir(parents=True, exist_ok=True)

    # 1. 保存参考音频
    audio_path = d / "ref_audio.wav"
    sf.write(str(audio_path), audio_data, audio_sr)

    # 2. 保存 embedding pt（VoiceClonePromptItem 序列化）
    save_data = {
        "ref_code": prompt_item.ref_code,
        "ref_spk_embedding": prompt_item.ref_spk_embedding,
        "x_vector_only_mode": prompt_item.x_vector_only_mode,
        "icl_mode": prompt_item.icl_mode,
        "ref_text": prompt_item.ref_text,
    }
    pt_path = d / "embedding.pt"
    torch.save(save_data, str(pt_path))

    # 3. 保存元数据（name 即目录名，不额外存 id）
    meta = {
        "name": name,
        "description": description,
        "ref_text": ref_text or (prompt_item.ref_text or ""),
        "created_at": datetime.now().isoformat(),
    }
    meta_path = d / "meta.json"
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)


# ──────────────────────────────────────────────────────
# Worker：单线程从队列取任务并调用 model.generate_voice_clone
# ──────────────────────────────────────────────────────
def worker_loop():
    import soundfile as sf

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

            # ── 加载 voice clone prompt ──────────────────────
            voice_clone_prompt = None
            if speaker:
                prompt_data = load_voice_clone_prompt(speaker)
                if prompt_data is not None:
                    voice_clone_prompt = prompt_data
                    log.info("[%s] 已加载 voice clone: %s", task_id[:8], speaker)
                else:
                    log.warning("[%s] voice clone '%s' 未找到", task_id[:8], speaker)

            # 打印完整生成参数
            log.info(
                "[%s] 开始生成 | text=%.30s | speaker=%s | instruct=%s | "
                "temp=%.2f | sample=%s | top_k=%d | top_p=%.2f | rep_pen=%.2f",
                task_id[:8], text, speaker, instruct,
                temperature, do_sample, top_k, top_p, rep_penalty,
            )

            # ── 调用 Base 模型的 generate_voice_clone ──────────
            if voice_clone_prompt is not None:
                wavs, sr = model.generate_voice_clone(
                    text=text,
                    language=language,
                    voice_clone_prompt=voice_clone_prompt,
                    non_streaming_mode=True,
                    **generate_kwargs,
                )
            else:
                raise ValueError(
                    f"speaker '{speaker}' 对应的 voice clone 不存在。"
                    f"请先在管理页面创建 voice clone，或提供有效的 speaker 名称。"
                    f"可用的 voice clone: {[c['name'] for c in list_voice_clones()]}"
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
# 原有 TTS API 路由（接口不变，内部改为 Base 模型）
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
        "temperature": data.get("temperature"),
        "do_sample": data.get("do_sample"),
        "top_k": data.get("top_k"),
        "top_p": data.get("top_p"),
        "repetition_penalty": data.get("repetition_penalty"),
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


@app.route("/tts/speakers", methods=["GET"])
def list_speakers():
    """获取说话人列表（name + description）"""
    clones = list_voice_clones()
    speakers = [{"name": c["name"], "description": c.get("description", "")} for c in clones]
    return jsonify({"speakers": speakers})


# ──────────────────────────────────────────────────────
# Voice Clone 管理 API
# ──────────────────────────────────────────────────────

@app.route("/tts/clones", methods=["GET"])
def list_clones():
    """列出所有 voice clone"""
    clones = list_voice_clones()
    return jsonify({"clones": clones})


@app.route("/tts/clones", methods=["POST"])
def create_clone():
    """
    从参考音频创建 voice clone。
    支持两种输入方式：
    1. multipart/form-data: 上传音频文件 (field: audio) + name + instruct(即 ref_text)
    2. JSON: { "name": "Aiden", "audio_base64": "...", "instruct": "参考文本" }
    """
    name = ""
    audio_data = None
    audio_sr = None
    ref_text = ""
    description = ""
    x_vector_only = False

    ct = request.content_type or ""
    log.info("[create_clone] content_type=%s, content_length=%s", ct, request.content_length)

    if "multipart/form-data" in ct:
        name = (request.form.get("name") or "").strip()
        ref_text = (request.form.get("instruct") or "").strip()
        description = (request.form.get("description") or "").strip()
        x_vector_only = (request.form.get("x_vector_only") or "false").lower() == "true"

        log.info("[create_clone] form: name=%s, ref_text=%s, has_audio=%s", name, ref_text, "audio" in request.files)

        if "audio" not in request.files:
            log.warning("[create_clone] 400: 未找到 audio 字段，files=%s", list(request.files.keys()))
            return jsonify({"error": "请上传音频文件（field: audio）"}), 400
        audio_file = request.files["audio"]
        if not audio_file.filename:
            log.warning("[create_clone] 400: 音频文件名为空")
            return jsonify({"error": "音频文件为空"}), 400

        import soundfile as sf
        try:
            raw_bytes = audio_file.read()
            log.info("[create_clone] 音频文件大小: %d bytes", len(raw_bytes))
            data, sr = sf.read(io.BytesIO(raw_bytes))
            audio_data = data
            audio_sr = sr
            log.info("[create_clone] 音频读取成功: sr=%d, shape=%s", sr, data.shape)
        except Exception as e:
            log.error("[create_clone] 400: 音频读取失败: %s", e)
            return jsonify({"error": f"无法读取音频文件: {e}"}), 400
    else:
        data = request.get_json(silent=True) or {}
        name = (data.get("name") or "").strip()
        ref_text = (data.get("instruct") or "").strip()
        description = (data.get("description") or "").strip()
        x_vector_only = data.get("x_vector_only", False)

        audio_b64 = data.get("audio_base64", "")
        if not audio_b64:
            log.warning("[create_clone] 400: 非 multipart 且无 audio_base64")
            return jsonify({"error": "请提供 audio_base64 或上传音频文件"}), 400

        import soundfile as sf
        try:
            raw = base64.b64decode(audio_b64)
            audio_data, audio_sr = sf.read(io.BytesIO(raw))
        except Exception as e:
            log.error("[create_clone] 400: base64 解码失败: %s", e)
            return jsonify({"error": f"无法解码音频: {e}"}), 400

    if not name:
        log.warning("[create_clone] 400: name 为空")
        return jsonify({"error": "name 不能为空"}), 400
    if audio_data is None:
        log.warning("[create_clone] 400: audio_data 为空")
        return jsonify({"error": "音频数据为空"}), 400

    # 检查是否已存在
    if _clone_dir(name).exists():
        return jsonify({"error": f"voice clone '{name}' 已存在，请先删除或使用其他名称"}), 409

    try:
        model = get_model()
        ref_audio_input = (audio_data, audio_sr)

        prompt_items = model.create_voice_clone_prompt(
            ref_audio=ref_audio_input,
            ref_text=ref_text if ref_text else None,
            x_vector_only_mode=x_vector_only,
        )

        if not prompt_items:
            return jsonify({"error": "无法从参考音频提取 voice prompt"}), 500

        save_voice_clone(
            name, prompt_items[0],
            audio_data=audio_data, audio_sr=audio_sr,
            ref_text=ref_text, description=description,
        )

        log.info("Voice clone 创建成功: %s (x_vector_only=%s)", name, x_vector_only)

        return jsonify({
            "ok": True,
            "name": name,
            "x_vector_only": x_vector_only,
            "has_ref_text": bool(ref_text),
        }), 201

    except Exception as e:
        log.error("创建 voice clone 失败: %s", e, exc_info=True)
        # 清理可能的部分写入
        import shutil
        d = _clone_dir(name)
        if d.exists():
            shutil.rmtree(str(d))
        return jsonify({"error": f"创建 voice clone 失败: {e}"}), 500


@app.route("/tts/clones/<name>", methods=["DELETE"])
def delete_clone(name):
    """删除 voice clone（整个目录）"""
    import shutil
    d = _clone_dir(name)
    if not d.exists():
        return jsonify({"error": f"voice clone '{name}' 不存在"}), 404
    shutil.rmtree(str(d))
    log.info("Voice clone 已删除: %s", name)
    return jsonify({"ok": True, "deleted": name})


@app.route("/tts/clones/<name>/download", methods=["GET"])
def download_clone_pt(name):
    """下载 voice clone 的 embedding.pt 文件"""
    pt_path = _clone_pt_path(name)
    if not pt_path.exists():
        return jsonify({"error": f"voice clone '{name}' 不存在"}), 404
    return send_file(str(pt_path), mimetype="application/octet-stream",
                     as_attachment=True, download_name=f"{name}_embedding.pt")


@app.route("/tts/clones/<name>/audio", methods=["GET"])
def download_clone_audio(name):
    """获取参考音频"""
    audio_path = _clone_audio_path(name)
    if not audio_path.exists():
        return jsonify({"error": f"voice clone '{name}' 的参考音频不存在"}), 404
    return send_file(str(audio_path), mimetype="audio/wav")


# ──────────────────────────────────────────────────────
# Voice Clone 管理 Web 页面
# ──────────────────────────────────────────────────────

CLONE_PAGE_HTML = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Voice Clone 管理 - Qwen3-TTS</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #0f1117; color: #e2e8f0; min-height: 100vh; }
  .container { max-width: 960px; margin: 0 auto; padding: 24px 16px; }
  h1 { font-size: 24px; font-weight: 700; margin-bottom: 8px; color: #fff; }
  .subtitle { color: #94a3b8; font-size: 14px; margin-bottom: 32px; }

  .card { background: #1e2130; border: 1px solid #2d3748; border-radius: 12px; padding: 24px; margin-bottom: 24px; }
  .card h2 { font-size: 18px; font-weight: 600; margin-bottom: 16px; color: #a78bfa; }
  .form-row { display: flex; gap: 16px; margin-bottom: 16px; flex-wrap: wrap; }
  .form-group { flex: 1; min-width: 200px; }
  .form-group label { display: block; font-size: 13px; font-weight: 500; color: #94a3b8; margin-bottom: 6px; }
  .form-group input[type="text"], .form-group textarea, .form-group select {
    width: 100%; padding: 10px 12px; background: #0f1117; border: 1px solid #374151; border-radius: 8px;
    color: #e2e8f0; font-size: 14px; outline: none; transition: border-color 0.2s;
  }
  .form-group input:focus, .form-group textarea:focus { border-color: #7c3aed; }
  .form-group textarea { resize: vertical; min-height: 60px; }

  .audio-upload { border: 2px dashed #374151; border-radius: 8px; padding: 20px; text-align: center; cursor: pointer; transition: border-color 0.2s; }
  .audio-upload:hover { border-color: #7c3aed; }
  .audio-upload input[type="file"] { display: none; }
  .audio-upload .icon { font-size: 32px; margin-bottom: 8px; }
  .audio-upload .hint { font-size: 13px; color: #64748b; }
  .audio-upload .filename { font-size: 14px; color: #a78bfa; margin-top: 8px; }
  .audio-preview { margin-top: 12px; }
  .audio-preview audio { width: 100%; height: 36px; }

  .btn { padding: 10px 20px; border: none; border-radius: 8px; font-size: 14px; font-weight: 600; cursor: pointer; transition: all 0.2s; display: inline-block; }
  .btn-primary { background: #7c3aed; color: #fff; }
  .btn-primary:hover { background: #6d28d9; }
  .btn-primary:disabled { background: #4c1d95; cursor: not-allowed; opacity: 0.6; }
  .btn-danger { background: #7f1d1d; color: #fca5a5; padding: 6px 12px; font-size: 12px; }
  .btn-danger:hover { background: #991b1b; }
  .btn-outline { background: transparent; border: 1px solid #374151; color: #94a3b8; padding: 6px 12px; font-size: 12px; }
  .btn-outline:hover { border-color: #7c3aed; color: #a78bfa; }

  .status { padding: 12px 16px; border-radius: 8px; font-size: 14px; margin-bottom: 16px; display: none; }
  .status.success { background: #052e16; border: 1px solid #166534; color: #86efac; display: block; }
  .status.error { background: #450a0a; border: 1px solid #991b1b; color: #fca5a5; display: block; }
  .status.info { background: #0c1445; border: 1px solid #1e40af; color: #93c5fd; display: block; }

  /* Clone 列表 - 表格风格 */
  .clone-table { width: 100%; border-collapse: collapse; }
  .clone-table th { text-align: left; font-size: 12px; font-weight: 600; color: #64748b; padding: 8px 12px; border-bottom: 1px solid #2d3748; }
  .clone-table td { padding: 12px; border-bottom: 1px solid #1e293b; font-size: 13px; vertical-align: middle; }
  .clone-table tr:hover td { background: #1a1d2e; }
  .clone-name { font-weight: 600; color: #fff; }
  .clone-desc { color: #94a3b8; font-size: 12px; }
  .clone-ref-text { color: #64748b; font-size: 12px; max-width: 200px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .clone-date { color: #64748b; font-size: 12px; white-space: nowrap; }
  .clone-actions { display: flex; gap: 6px; flex-wrap: nowrap; }
  .clone-actions .btn { padding: 4px 10px; font-size: 11px; }

  .badge { display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: 500; }
  .badge-green { background: #052e16; color: #86efac; }
  .badge-red { background: #450a0a; color: #fca5a5; }

  .empty { text-align: center; padding: 40px; color: #64748b; font-size: 14px; }

  .toggle { display: flex; align-items: center; gap: 8px; margin-bottom: 16px; }
  .toggle input[type="checkbox"] { width: 18px; height: 18px; accent-color: #7c3aed; }
  .toggle label { font-size: 13px; color: #94a3b8; }

  .spinner { display: inline-block; width: 16px; height: 16px; border: 2px solid #fff; border-top-color: transparent; border-radius: 50%; animation: spin 0.6s linear infinite; margin-right: 8px; vertical-align: middle; }
  @keyframes spin { to { transform: rotate(360deg); } }
</style>
</head>
<body>
<div class="container">
  <h1>🎙️ Voice Clone 管理</h1>
  <p class="subtitle">基于 Qwen3-TTS Base 模型 — 从参考音频克隆声音，生成 .pt 向量文件供后续复用</p>

  <div id="status" class="status"></div>

  <!-- 创建 Clone -->
  <div class="card">
    <h2>创建 Voice Clone</h2>
    <div class="form-row">
      <div class="form-group">
        <label>说话人名称 *</label>
        <input type="text" id="cloneName" placeholder="如：Aiden、Dylan、自定义名称..." />
      </div>
      <div class="form-group">
        <label>描述</label>
        <input type="text" id="cloneDesc" placeholder="如：阳光美声男中音" />
      </div>
    </div>
    <div class="form-group" style="margin-bottom:16px">
      <label>参考音频 *（WAV/FLAC/MP3，建议 3-10 秒清晰人声）</label>
      <div class="audio-upload" id="dropZone" onclick="document.getElementById('audioFile').click()">
        <div class="icon">📁</div>
        <div>点击选择或拖拽音频文件到此处</div>
        <div class="hint" id="fileHint">支持 WAV、FLAC、MP3 格式</div>
        <div class="filename" id="fileName"></div>
        <input type="file" id="audioFile" accept="audio/*" />
      </div>
      <div class="audio-preview" id="audioPreview" style="display:none">
        <audio id="audioPlayer" controls></audio>
      </div>
    </div>
    <div class="form-group" style="margin-bottom:16px">
      <label>参考文本（可选，填写后可启用 ICL 模式提升效果）</label>
      <textarea id="refText" placeholder="输入参考音频中说的内容，如：Hello, this is a sample voice for cloning."></textarea>
    </div>
    <div class="toggle">
      <input type="checkbox" id="xvecOnly" />
      <label for="xvecOnly">仅使用说话人向量（x_vector_only 模式，不需要参考文本，但效果可能略低）</label>
    </div>
    <button class="btn btn-primary" id="createBtn" onclick="createClone()">
      生成 Voice Clone
    </button>
  </div>

  <!-- 测试生成 -->
  <div class="card">
    <h2>🎤 测试生成</h2>
    <p style="font-size:13px;color:#64748b;margin-bottom:12px;">使用已创建的 voice clone 合成测试音频</p>
    <div class="form-row">
      <div class="form-group">
        <label>选择说话人</label>
        <select id="genSpeaker">
          <option value="">-- 选择 --</option>
        </select>
      </div>
      <div class="form-group">
        <label>语言</label>
        <select id="genLang">
          <option value="Chinese">中文</option>
          <option value="English">英文</option>
          <option value="Japanese">日文</option>
          <option value="Korean">韩文</option>
          <option value="Auto">自动</option>
        </select>
      </div>
    </div>
    <div class="form-group" style="margin-bottom:16px">
      <label>合成文本 *</label>
      <textarea id="genText" placeholder="输入要合成的文本..." style="min-height:80px"></textarea>
    </div>
    <div class="form-row" style="margin-bottom:16px">
      <div class="form-group">
        <label>Temperature</label>
        <input type="text" id="genTemp" value="0.3" />
      </div>
      <div class="form-group">
        <label>Top K</label>
        <input type="text" id="genTopK" value="20" />
      </div>
      <div class="form-group">
        <label>Top P</label>
        <input type="text" id="genTopP" value="0.85" />
      </div>
      <div class="form-group">
        <label>重复惩罚</label>
        <input type="text" id="genRepPen" value="1.1" />
      </div>
    </div>
    <button class="btn btn-primary" id="genBtn" onclick="generateTest()">合成测试音频</button>
    <div id="genResult" style="margin-top:16px;display:none">
      <audio id="genAudio" controls style="width:100%;height:36px"></audio>
    </div>
  </div>

  <!-- Clone 列表 -->
  <div class="card">
    <h2>已保存的 Voice Clone <span id="cloneCount" style="color:#64748b;font-weight:400;font-size:14px"></span></h2>
    <div id="cloneList"></div>
  </div>
</div>

<script>
const API = '';

function showStatus(msg, type) {
  const el = document.getElementById('status');
  el.textContent = msg;
  el.className = 'status ' + type;
  if (type !== 'info') setTimeout(() => { el.className = 'status'; }, 5000);
}

// 文件选择
const audioFile = document.getElementById('audioFile');
const dropZone = document.getElementById('dropZone');
let selectedFile = null;

audioFile.addEventListener('change', e => {
  if (e.target.files.length > 0) selectFile(e.target.files[0]);
});

dropZone.addEventListener('dragover', e => { e.preventDefault(); dropZone.style.borderColor = '#7c3aed'; });
dropZone.addEventListener('dragleave', () => { dropZone.style.borderColor = '#374151'; });
dropZone.addEventListener('drop', e => {
  e.preventDefault(); dropZone.style.borderColor = '#374151';
  if (e.dataTransfer.files.length > 0) selectFile(e.dataTransfer.files[0]);
});

function selectFile(f) {
  selectedFile = f;
  document.getElementById('fileName').textContent = '已选: ' + f.name + ' (' + (f.size/1024).toFixed(1) + ' KB)';
  document.getElementById('fileHint').style.display = 'none';
  const url = URL.createObjectURL(f);
  const player = document.getElementById('audioPlayer');
  player.src = url;
  document.getElementById('audioPreview').style.display = 'block';
}

// 创建 Clone
async function createClone() {
  const name = document.getElementById('cloneName').value.trim();
  const desc = document.getElementById('cloneDesc').value.trim();
  const refText = document.getElementById('refText').value.trim();
  const xvecOnly = document.getElementById('xvecOnly').checked;

  if (!name) return showStatus('请输入说话人名称', 'error');
  if (!selectedFile) return showStatus('请选择参考音频文件', 'error');

  const btn = document.getElementById('createBtn');
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner"></span>正在生成（首次需加载模型，可能需要几分钟）...';
  showStatus('正在处理，请稍候...', 'info');

  const fd = new FormData();
  fd.append('audio', selectedFile);
  fd.append('name', name);
  fd.append('description', desc);
  if (refText) fd.append('instruct', refText);
  if (xvecOnly) fd.append('x_vector_only', 'true');

  try {
    const r = await fetch('/tts/clones', { method: 'POST', body: fd });
    const d = await r.json();
    if (r.ok) {
      showStatus('✅ Voice clone "' + name + '" 创建成功！', 'success');
      document.getElementById('cloneName').value = '';
      document.getElementById('cloneDesc').value = '';
      document.getElementById('refText').value = '';
      document.getElementById('xvecOnly').checked = false;
      selectedFile = null;
      document.getElementById('fileName').textContent = '';
      document.getElementById('fileHint').style.display = '';
      document.getElementById('audioPreview').style.display = 'none';
      audioFile.value = '';
      await loadClones();
    } else {
      showStatus('❌ ' + (d.error || '创建失败'), 'error');
    }
  } catch (e) {
    showStatus('❌ 网络错误: ' + e.message, 'error');
  } finally {
    btn.disabled = false;
    btn.textContent = '生成 Voice Clone';
  }
}

// 加载 Clone 列表
async function loadClones() {
  try {
    const r = await fetch('/tts/clones');
    const d = await r.json();
    const clones = d.clones || [];
    const listEl = document.getElementById('cloneList');
    const countEl = document.getElementById('cloneCount');
    const speakerSel = document.getElementById('genSpeaker');

    countEl.textContent = '(' + clones.length + ')';

    // 更新下拉框
    speakerSel.innerHTML = '<option value="">-- 选择 --</option>';
    clones.forEach(c => {
      const opt = document.createElement('option');
      opt.value = c.name;
      opt.textContent = c.name;
      speakerSel.appendChild(opt);
    });

    if (clones.length === 0) {
      listEl.innerHTML = '<div class="empty">暂无 voice clone，请先创建一个</div>';
      return;
    }

    let html = '<table class="clone-table"><thead><tr>'
      + '<th>名称</th><th>描述</th><th>参考文本</th><th>参考音频</th><th>.pt</th><th>创建时间</th><th>操作</th>'
      + '</tr></thead><tbody>';

    clones.forEach(c => {
      html += '<tr>'
        + '<td><span class="clone-name">' + esc(c.name) + '</span></td>'
        + '<td><span class="clone-desc">' + esc(c.description || '-') + '</span></td>'
        + '<td><span class="clone-ref-text" title="' + esc(c.ref_text || '') + '">' + esc(c.ref_text || '-') + '</span></td>'
        + '<td>' + (c.has_audio
            ? '<audio src="/tts/clones/' + encodeURIComponent(c.name) + '/audio" controls style="height:28px;width:160px"></audio>'
            : '<span class="badge badge-red">无</span>') + '</td>'
        + '<td>' + (c.has_pt
            ? '<span class="badge badge-green">' + (c.pt_size_bytes/1024).toFixed(1) + ' KB</span>'
            : '<span class="badge badge-red">无</span>') + '</td>'
        + '<td><span class="clone-date">' + (c.created_at ? c.created_at.replace('T',' ').slice(0,19) : '-') + '</span></td>'
        + '<td><div class="clone-actions">'
        + (c.has_pt ? '<a class="btn btn-outline" href="/tts/clones/' + encodeURIComponent(c.name) + '/download" download>⬇ .pt</a>' : '')
        + '<button class="btn btn-danger" onclick="deleteClone(\'' + esc(c.name) + '\')">删除</button>'
        + '</div></td>'
        + '</tr>';
    });

    html += '</tbody></table>';
    listEl.innerHTML = html;
  } catch (e) {
    console.error('加载 clone 列表失败:', e);
  }
}

// 删除 Clone
async function deleteClone(name) {
  if (!confirm('确定删除 voice clone "' + name + '" 吗？')) return;
  try {
    const r = await fetch('/tts/clones/' + encodeURIComponent(name), { method: 'DELETE' });
    if (r.ok) {
      showStatus('已删除 "' + name + '"', 'success');
      await loadClones();
    } else {
      const d = await r.json();
      showStatus('删除失败: ' + d.error, 'error');
    }
  } catch (e) {
    showStatus('网络错误: ' + e.message, 'error');
  }
}

// 测试生成
async function generateTest() {
  const speaker = document.getElementById('genSpeaker').value;
  const text = document.getElementById('genText').value.trim();
  const lang = document.getElementById('genLang').value;

  if (!speaker) return showStatus('请选择说话人', 'error');
  if (!text) return showStatus('请输入合成文本', 'error');

  const btn = document.getElementById('genBtn');
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner"></span>合成中...';
  showStatus('正在合成，请稍候...', 'info');

  const payload = {
    text: text,
    language: lang,
    speaker: speaker,
    temperature: parseFloat(document.getElementById('genTemp').value) || 0.3,
    top_k: parseInt(document.getElementById('genTopK').value) || 20,
    top_p: parseFloat(document.getElementById('genTopP').value) || 0.85,
    repetition_penalty: parseFloat(document.getElementById('genRepPen').value) || 1.1,
    do_sample: true,
  };

  try {
    const subR = await fetch('/tts/submit', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    const subD = await subR.json();
    if (!subR.ok) return showStatus('提交失败: ' + subD.error, 'error');

    const taskId = subD.task_id;
    showStatus('任务已提交 (' + taskId.slice(0,8) + '...)，等待生成...', 'info');

    const result = await pollTask(taskId);
    if (result.status === 'success') {
      const dlR = await fetch('/tts/download/' + taskId);
      const blob = await dlR.blob();
      const url = URL.createObjectURL(blob);
      document.getElementById('genAudio').src = url;
      document.getElementById('genResult').style.display = 'block';
      showStatus('✅ 合成完成！', 'success');
    } else {
      showStatus('❌ 生成失败: ' + (result.error || result.status), 'error');
    }
  } catch (e) {
    showStatus('❌ 错误: ' + e.message, 'error');
  } finally {
    btn.disabled = false;
    btn.textContent = '合成测试音频';
  }
}

function pollTask(taskId) {
  return new Promise(resolve => {
    const interval = setInterval(async () => {
      const r = await fetch('/tts/status/' + taskId);
      const d = await r.json();
      if (d.status === 'success' || d.status === 'failed') {
        clearInterval(interval);
        resolve(d);
      }
    }, 2000);
    setTimeout(() => { clearInterval(interval); resolve({status:'timeout', error:'等待超时'}); }, 300000);
  });
}

function esc(s) {
  const d = document.createElement('div');
  d.textContent = s == null ? '' : String(s);
  return d.innerHTML;
}

// 初始化
loadClones();
</script>
</body>
</html>"""


@app.route("/tts/clones/ui", methods=["GET"])
def clone_ui():
    """Voice Clone 管理页面"""
    return Response(CLONE_PAGE_HTML, mimetype="text/html")


# ──────────────────────────────────────────────────────
# 入口
# ──────────────────────────────────────────────────────
if __name__ == "__main__":
    log.info("启动 Qwen3-TTS API 服务 (Base 模型) %s:%d", SERVER_HOST, SERVER_PORT)
    log.info("Voice Clone 管理页面: http://localhost:%d/tts/clones/ui", SERVER_PORT)
    app.run(host=SERVER_HOST, port=SERVER_PORT, debug=False)

"""
Qwen3-TTS API 客户端
供第三方调用，内部统一处理 User-Agent、超时、重试等细节

用法：
    from tts_client import TtsClient

    client = TtsClient("https://your-server.com")
    task_id = client.submit(text="你好世界", speaker="Dylan", instruct="愉快")
    result = client.wait(task_id)
    if result.ok:
        data = client.download(task_id)
        with open("out.wav", "wb") as f:
            f.write(data)
"""
import json
import time
import urllib.request
import urllib.error
from dataclasses import dataclass, field


# ──────────────────────────────────────────────────────
# 配置
# ──────────────────────────────────────────────────────
_DEFAULT_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
_DEFAULT_TIMEOUT = 120  # 秒
_DEFAULT_POLL_INTERVAL = 5  # 秒
_DEFAULT_MAX_WAIT = 600  # 秒


# ──────────────────────────────────────────────────────
# 数据结构
# ──────────────────────────────────────────────────────
@dataclass
class SubmitResult:
    task_id: str = ""
    position: int = 0
    raw: dict = field(default_factory=dict)
    error: str = ""


@dataclass
class StatusResult:
    task_id: str = ""
    status: str = ""          # pending / processing / success / failed
    submitted_at: str = ""
    started_at: str = ""
    finished_at: str = ""
    download_url: str = ""
    error: str = ""
    raw: dict = field(default_factory=dict)

    @property
    def ok(self):
        return self.status == "success"

    @property
    def done(self):
        return self.status in ("success", "failed")


@dataclass
class DownloadResult:
    data: bytes = b""
    status_code: int = 0
    error: str = ""

    @property
    def ok(self):
        return self.status_code == 200 and len(self.data) > 0


# ──────────────────────────────────────────────────────
# 客户端
# ──────────────────────────────────────────────────────
class TtsClient:
    def __init__(self, base_url: str, timeout: int = _DEFAULT_TIMEOUT,
                 poll_interval: int = _DEFAULT_POLL_INTERVAL,
                 max_wait: int = _DEFAULT_MAX_WAIT,
                 user_agent: str = _DEFAULT_UA):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.poll_interval = poll_interval
        self.max_wait = max_wait
        self._ua = user_agent

    # ── 内部请求 ──────────────────────────────────────
    def _request(self, method: str, path: str, data: dict = None):
        url = self.base_url + path
        body = json.dumps(data).encode("utf-8") if data else None
        headers = {
            "Content-Type": "application/json",
            "User-Agent": self._ua,
        }
        req = urllib.request.Request(url, data=body, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                raw = resp.read()
                try:
                    return json.loads(raw), resp.status
                except (json.JSONDecodeError, ValueError):
                    return {"_raw": raw}, resp.status
        except urllib.error.HTTPError as e:
            raw = e.read()
            try:
                return json.loads(raw), e.code
            except (json.JSONDecodeError, ValueError):
                return {"_raw": raw, "_http_error": e.code}, e.code

    def _download(self, url: str):
        req = urllib.request.Request(url, headers={"User-Agent": self._ua})
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            return resp.read(), resp.status

    # ── 提交任务 ──────────────────────────────────────
    def submit(self, text: str, language: str = "Chinese",
               speaker: str = "", instruct: str = "") -> SubmitResult:
        r, code = self._request("POST", "/tts/submit", {
            "text": text,
            "language": language,
            "speaker": speaker,
            "instruct": instruct,
        })
        if code == 202:
            return SubmitResult(task_id=r["task_id"], position=r.get("position", 0), raw=r)
        return SubmitResult(error=r.get("error", f"HTTP {code}"), raw=r)

    # ── 查询状态 ──────────────────────────────────────
    def status(self, task_id: str) -> StatusResult:
        r, code = self._request("GET", f"/tts/status/{task_id}")
        if code == 200:
            return StatusResult(
                task_id=task_id,
                status=r.get("status", ""),
                submitted_at=r.get("submitted_at", ""),
                started_at=r.get("started_at", ""),
                finished_at=r.get("finished_at", ""),
                download_url=r.get("download_url", ""),
                error=r.get("error", ""),
                raw=r,
            )
        return StatusResult(task_id=task_id, status="error",
                            error=r.get("error", f"HTTP {code}"), raw=r)

    # ── 下载音频 ──────────────────────────────────────
    def download(self, task_id: str) -> DownloadResult:
        sr = self.status(task_id)
        if not sr.ok:
            return DownloadResult(error=f"任务未完成: {sr.status}", status_code=0)
        url = self.base_url + sr.download_url
        try:
            data, code = self._download(url)
            return DownloadResult(data=data, status_code=code)
        except urllib.error.HTTPError as e:
            return DownloadResult(error=str(e), status_code=e.code)
        except Exception as e:
            return DownloadResult(error=str(e), status_code=0)

    # ── 等待完成 ──────────────────────────────────────
    def wait(self, task_id: str, poll_interval: int = None,
             max_wait: int = None) -> StatusResult:
        interval = poll_interval or self.poll_interval
        deadline = time.time() + (max_wait or self.max_wait)
        while time.time() < deadline:
            sr = self.status(task_id)
            if sr.done:
                return sr
            time.sleep(interval)
        return StatusResult(task_id=task_id, status="timeout", error="等待超时")

    # ── 队列概况 ──────────────────────────────────────
    def queue_info(self) -> dict:
        r, code = self._request("GET", "/tts/queue")
        if code == 200:
            return r
        return {"error": r.get("error", f"HTTP {code}")}

    # ── 健康检查 ──────────────────────────────────────
    def health(self) -> bool:
        r, code = self._request("GET", "/tts/health")
        return code == 200 and r.get("status") == "ok"

"""OpenAI 协议 LLM 客户端."""
import json
import urllib.request
import urllib.error
from pathlib import Path

_CONFIG_PATH = Path(__file__).resolve().parent.parent / "config.yaml"
_config = None


def _load_config():
    global _config
    if _config is not None:
        return _config
    try:
        import yaml
        with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
            _config = yaml.safe_load(f) or {}
    except Exception:
        _config = {}
    return _config


def get_llm_config():
    cfg = _load_config()
    return cfg.get("llm", {})


def chat(messages: list[dict], **overrides) -> str:
    """
    发送 chat 请求，返回 assistant 回复文本。
    messages: [{"role": "system"|"user"|"assistant", "content": "..."}]
    overrides 可覆盖: model, max_tokens, temperature, timeout
    """
    cfg = get_llm_config()
    base_url = cfg.get("base_url", "").rstrip("/")
    api_key = cfg.get("api_key", "")
    model = cfg.get("model", "gpt-4o")
    timeout = cfg.get("timeout", 300)
    max_tokens = cfg.get("max_tokens", 4096)
    temperature = cfg.get("temperature", 0.7)

    # 允许调用方覆盖
    model = overrides.get("model", model)
    max_tokens = overrides.get("max_tokens", max_tokens)
    temperature = overrides.get("temperature", temperature)
    timeout = overrides.get("timeout", timeout)

    if not base_url:
        raise Exception("LLM base_url 未配置，请检查 app/config.yaml")
    if not api_key:
        raise Exception("LLM api_key 未配置，请检查 app/config.yaml")

    url = f"{base_url}/chat/completions"
    body = json.dumps({
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
    }).encode("utf-8")

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }

    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
            data = json.loads(raw)
            choices = data.get("choices", [])
            if choices:
                return choices[0].get("message", {}).get("content", "")
            raise Exception(f"LLM 返回无 choices: {raw[:200]}")
    except urllib.error.HTTPError as e:
        raw = e.read()
        raise Exception(f"LLM API 错误 {e.code}: {raw[:200]}")
    except Exception as e:
        raise Exception(f"LLM 请求失败: {e}")


def chat_json(messages: list[dict], **overrides) -> dict:
    """发送 chat 请求，期望返回 JSON，解析为 dict。"""
    import re
    text = chat(messages, **overrides)
    text = text.strip()
    # 去掉 <think>...</think> 推理块（MiniMax 等模型会输出）
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
    # 尝试提取 JSON（可能被 ```json ... ``` 包裹）
    if text.startswith("```"):
        lines = text.split("\n")
        lines = lines[1:]  # 去掉 ```json
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    # 找到第一个 { 和最后一个 }，提取完整 JSON 对象
    # 防止 LLM 在 JSON 后面追加解释文字导致 json.loads 失败
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        text = text[start:end + 1]
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        raise Exception(f"LLM 返回非 JSON: {text[:200]}")

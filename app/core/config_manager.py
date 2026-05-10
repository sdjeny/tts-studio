"""配置管理模块 - config.yaml 的读写与 API Key 脱敏工具。"""

import os
import re
import time
import yaml
from pathlib import Path

CONFIG_PATH = Path(__file__).resolve().parent.parent / "config.yaml"


def load_config() -> dict:
    """读取 config.yaml 并返回字典。"""
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def mask_api_key(key: str) -> str:
    """API Key 脱敏：保留前4后4，中间用 **** 替代。

    如果 key 长度 <= 8，直接返回 "****"。
    """
    if len(key) <= 8:
        return "****"
    return key[:4] + "****" + key[-4:]


def is_masked_key(value: str) -> bool:
    """判断一个字符串是否为脱敏后的 API Key 值。"""
    return bool(re.match(r"^.{4}\*{4,}.{0,4}$", value))


def save_config(config: dict) -> None:
    """原子写入 config.yaml：先写 .tmp 再 rename，避免写入中途崩溃导致文件损坏。"""
    tmp = CONFIG_PATH.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        yaml.safe_dump(config, f, allow_unicode=True, default_flow_style=False)
    os.replace(str(tmp), str(CONFIG_PATH))


def trigger_reload():
    """通过 touch main.py 触发 uvicorn --reload 热更新。"""
    time.sleep(0.5)
    main_py = Path(__file__).resolve().parent.parent.parent / "main.py"
    main_py.touch()


# 敏感字段名（匹配时做脱敏）
_SENSITIVE_KEYS = {"api_key", "secret_key", "token", "password"}


def _sanitize_value(key: str, value):
    """对敏感字段值做脱敏。"""
    if isinstance(value, str) and any(sk in key.lower() for sk in _SENSITIVE_KEYS):
        return mask_api_key(value)
    return value


def _sanitize_dict(d: dict) -> dict:
    """递归脱敏字典中的敏感字段。"""
    result = {}
    for k, v in d.items():
        if isinstance(v, dict):
            result[k] = _sanitize_dict(v)
        else:
            result[k] = _sanitize_value(k, v)
    return result


def _deep_update(base: dict, update: dict) -> dict:
    """递归合并 update 到 base（只更新提供的键）。"""
    for k, v in update.items():
        if k in base and isinstance(base[k], dict) and isinstance(v, dict):
            _deep_update(base[k], v)
        else:
            base[k] = v
    return base


class ConfigManager:
    """配置管理器 — 封装读取、脱敏、更新操作。"""

    def get_sanitized_config(self) -> dict:
        """返回脱敏后的配置（敏感字段用 **** 掩盖）。"""
        cfg = load_config()
        return _sanitize_dict(cfg)

    def update_config(self, data: dict) -> dict:
        """部分更新配置并持久化，返回更新后的完整脱敏配置。

        - 跳过值为脱敏标记的字段（is_masked_key）。
        - 写入后触发 uvicorn 热更新。
        """
        cfg = load_config()

        # 过滤掉脱敏后的占位值，避免覆盖真实 key
        clean = _strip_masked(data)
        _deep_update(cfg, clean)
        save_config(cfg)
        trigger_reload()
        return _sanitize_dict(cfg)


def _strip_masked(d: dict) -> dict:
    """递归移除值为脱敏标记的字段，避免误覆盖。"""
    result = {}
    for k, v in d.items():
        if isinstance(v, dict):
            result[k] = _strip_masked(v)
        elif isinstance(v, str) and is_masked_key(v):
            continue  # 跳过脱敏值
        else:
            result[k] = v
    return result


config_manager = ConfigManager()

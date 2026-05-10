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

"""Config API — GET / PATCH 配置接口。"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Any

from app.core.config_manager import config_manager

router = APIRouter()


class ConfigUpdate(BaseModel):
    """PATCH 请求体 — 接受任意嵌套字典。"""
    data: dict[str, Any]


@router.get("/config")
async def get_config():
    """返回当前配置（敏感字段已脱敏）。"""
    return config_manager.get_sanitized_config()


@router.patch("/config")
async def update_config(body: ConfigUpdate):
    """部分更新配置，返回更新后的完整脱敏配置。

    - 敏感字段传脱敏值（如 `xxxx****yyyy`）会被自动跳过，不会覆盖真实 key。
    - 写入后触发 uvicorn 热更新。
    """
    try:
        return config_manager.update_config(body.data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"配置更新失败: {e}")

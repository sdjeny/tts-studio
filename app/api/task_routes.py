"""LLM 任务状态查询路由。"""

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from app.core.task_manager import TaskManager

router = APIRouter()


@router.get("/projects/{project_id}/llm/task/{task_id}")
async def api_get_llm_task(project_id: str, task_id: str):
    """查询单个任务的当前状态。"""
    task = TaskManager.get(project_id, task_id)
    if not task:
        raise HTTPException(404, "Task not found or expired")
    return JSONResponse(task)


@router.get("/projects/{project_id}/llm/tasks")
async def api_list_llm_tasks(project_id: str):
    """列出项目的所有 LLM 生成任务（最近20条）。"""
    from app.core.store import get_generation_task
    # 用 None 触发列表查询 — 根据 store.py 实际接口调整
    tasks = get_generation_task(project_id)
    if not tasks:
        return {"tasks": []}
    # 如果是 dict 则包装
    if isinstance(tasks, dict):
        return {"tasks": [tasks]}
    return {"tasks": tasks[:20]}
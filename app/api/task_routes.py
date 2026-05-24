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
    """列出项目的所有 LLM 生成任务（最近50条）。"""
    from app.core.store import list_generation_tasks
    tasks = list_generation_tasks(project_id)
    return {"tasks": tasks[:50]}


@router.post("/projects/{project_id}/llm/task/{task_id}/cancel")
async def api_cancel_llm_task(project_id: str, task_id: str):
    """取消一个正在运行或卡住的任务。"""
    from app.core.store import cancel_generation_task, list_generation_tasks
    from app.core.task_manager import TaskManager

    # 通过 list_generation_tasks 查找目标任务
    tasks = list_generation_tasks(project_id)
    task = None
    for t in tasks:
        if t.get("id") == task_id or t.get("task_id") == task_id:
            task = t
            break
    if not task:
        raise HTTPException(404, "Task not found")
    if task.get("status") in ("complete",):
        raise HTTPException(409, "任务已完成，不允许取消")
    if task.get("status") == "cancelled":
        raise HTTPException(409, "任务已取消")
    cancel_generation_task(project_id, task_id)
    episode_id = task.get("episode_id", "")
    task_type = task.get("type", task.get("task_type", ""))
    if episode_id and task_type:
        TaskManager.release(episode_id, task_type)
    # 返回最新状态
    tasks_updated = list_generation_tasks(project_id)
    for t in tasks_updated:
        if t.get("id") == task_id or t.get("task_id") == task_id:
            return JSONResponse(t)
    return JSONResponse({"status": "cancelled", "task_id": task_id})
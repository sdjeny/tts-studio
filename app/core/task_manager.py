"""统一任务管理器 — 封装生成任务的生命周期管理。"""

import uuid, asyncio, time
from typing import Optional

# 锁定状态 (episode_id, task_type) -> lock info
_locks: dict[tuple[str, str], dict] = {}
# 跨项目锁
_project_locks: dict[str, asyncio.Lock] = {}


class TaskManager:
    TASK_TYPES = ("outline", "dialogues", "continuation", "generate_batch", "refresh", "single_audio")
    
    @staticmethod
    def create(project_id: str, episode_id: str, task_type: str, total: int = 0) -> str:
        """创建任务记录，返回 task_id。"""
        from app.core.store import init_generation_task
        return init_generation_task(project_id, episode_id, task_type, total=total)
    
    @staticmethod
    def get(project_id: str, task_id: str) -> Optional[dict]:
        """通过 task_id 查任务。"""
        from app.core.store import get_generation_task
        return get_generation_task(project_id, task_id=task_id)
    
    @staticmethod
    def update(project_id: str, task_id: str, **kwargs):
        """更新任务状态。"""
        from app.core.store import update_generation_task
        update_generation_task(project_id, task_id, **kwargs)
    
    @staticmethod
    def try_acquire(project_id: str, episode_id: str, task_type: str) -> bool:
        """尝试获取锁定。成功返回 True，失败（已锁定）返回 False。"""
        key = (episode_id, task_type)
        if key in _locks and _locks[key].get("active", False):
            # 检查是否超时（兜底清理）
            elapsed = time.time() - _locks[key].get("started_at", 0)
            if elapsed < 300:  # 5分钟内有效
                return False
            # 超时清理
            del _locks[key]
        _locks[key] = {"active": True, "started_at": time.time(), "project_id": project_id}
        return True
    
    @staticmethod
    def release(episode_id: str, task_type: str):
        """释放锁定。"""
        key = (episode_id, task_type)
        if key in _locks:
            del _locks[key]

    @staticmethod
    def has_active_tasks(project_id: str) -> list:
        """查询项目是否有活跃的 LLM 任务。返回活跃任务列表（空=无）。"""
        from app.core.store import list_generation_tasks

        active = []

        # 1. 检查内存锁中的活跃任务
        for key, info in _locks.items():
            if info.get("project_id") == project_id and info.get("active", False):
                elapsed = time.time() - info.get("started_at", 0)
                if elapsed < 300:  # 5分钟内有效
                    ep_id, task_type = key
                    active.append({"episode_id": ep_id, "type": task_type,
                                   "source": "memory_lock", "elapsed": round(elapsed, 1)})

        # 2. 检查持久化任务中的 running/pending 状态
        persisted = list_generation_tasks(project_id, status="running") + \
                    list_generation_tasks(project_id, status="pending")
        # 去重：已在内存锁中的不重复添加
        for task in persisted:
            already = any(
                t.get("type") == task.get("type") and
                t.get("episode_id") == task.get("episode_id")
                for t in active
            )
            if not already:
                active.append({
                    "episode_id": task.get("episode_id", ""),
                    "type": task.get("type", ""),
                    "source": "persisted",
                    "task_id": task.get("task_id", ""),
                    "progress": f"{task.get('current', 0)}/{task.get('total', 0)}" if task.get("total") else "",
                })

        return active

    @staticmethod
    def get_project_lock(project_id: str) -> asyncio.Lock:
        """获取项目级 asyncio 锁（用于批量串行）。"""
        if project_id not in _project_locks:
            _project_locks[project_id] = asyncio.Lock()
        return _project_locks[project_id]
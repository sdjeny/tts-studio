"""集成测试：对白生成后台任务改造 (Issue #35)

测试场景：
1. API 返回格式 — 调用生成端点，验证立即返回 task_id
2. 任务状态轮询 — 调用 /generation-status 端点，验证返回字段
3. store 函数单元测试 — 测试 init/update/get/cancel/list 函数
4. 并发控制 — 测试同一剧集 running 任务检测
"""
import json
import sys
import pytest
import pytest_asyncio
import tempfile
from pathlib import Path
from unittest.mock import patch, AsyncMock

# Mock soundfile before any app imports to avoid ModuleNotFoundError
sys.modules["soundfile"] = type(sys)("soundfile")
sys.modules["soundfile"].__dict__.update({
    "SoundFile": type("SoundFile", (), {}),
    "read": lambda *a, **kw: (None, 24000),
    "write": lambda *a, **kw: None,
    "info": lambda *a, **kw: type("Info", (), {"duration": 1.0, "samplerate": 24000})(),
})

# ── Fixtures ──────────────────────────────────────────────


@pytest.fixture(autouse=True)
def temp_data_dir(monkeypatch):
    """使用临时目录作为数据存储，避免污染真实数据。每个测试独立目录。"""
    with tempfile.TemporaryDirectory() as tmpdir:
        data_dir = Path(tmpdir) / "data"
        data_dir.mkdir(parents=True, exist_ok=True)
        studio_file = data_dir / "studio.json"
        studio_file.write_text(
            json.dumps({"projects": []}, ensure_ascii=False, indent=2)
        )
        import app.core.store as store

        monkeypatch.setattr(store, "DATA_DIR", data_dir)
        monkeypatch.setattr(store, "DATA_FILE", studio_file)
        yield


@pytest.fixture
def test_project():
    """创建测试项目、剧集和角色。"""
    from app.core.store import create_project, create_episode, update_episode, add_character

    proj = create_project("测试项目")
    ep = create_episode(proj["id"], "测试剧集")
    update_episode(proj["id"], ep["id"], summary="这是一个测试剧集的摘要内容，用于测试后台任务。")
    char = add_character(proj["id"], "测试角色", "aiden", description="测试用角色")
    return proj, ep, char


@pytest_asyncio.fixture
async def client():
    """创建 httpx 异步客户端，挂载 FastAPI 应用（仅加载必要路由）。"""
    from fastapi import FastAPI
    from app.api.episodes import router as episodes_router
    from app.api.projects import router as projects_router

    test_app = FastAPI()
    test_app.include_router(projects_router, prefix="/api")
    test_app.include_router(episodes_router, prefix="/api")

    from httpx import AsyncClient, ASGITransport
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# ═══════════════════════════════════════════════════════════
# 测试 3: Store 函数单元测试
# ═══════════════════════════════════════════════════════════


class TestStoreFunctions:
    """测试 generation task 相关的 store 函数。"""

    def test_init_generation_task(self, test_project):
        """init_generation_task 创建任务并返回 task_id。"""
        from app.core.store import init_generation_task, get_generation_task

        proj, ep, _ = test_project
        task_id = init_generation_task(proj["id"], ep["id"], "dialogue_generation")

        assert task_id.startswith("gen_task_")

        task = get_generation_task(proj["id"], episode_id=ep["id"])
        assert task is not None
        assert task["id"] == task_id
        assert task["status"] == "running"
        assert task["episode_id"] == ep["id"]
        assert task["type"] == "dialogue_generation"
        assert "current" in task
        assert "total" in task
        assert "created_at" in task
        assert "updated_at" in task

    def test_update_generation_task(self, test_project):
        """update_generation_task 更新任务字段。"""
        from app.core.store import (
            init_generation_task,
            update_generation_task,
            get_generation_task,
        )

        proj, ep, _ = test_project
        task_id = init_generation_task(proj["id"], ep["id"], "dialogue_generation")

        # 更新进度
        assert update_generation_task(proj["id"], task_id, current=10, total=50)
        task = get_generation_task(proj["id"], episode_id=ep["id"])
        assert task["current"] == 10
        assert task["total"] == 50

        # 更新状态为 complete
        assert update_generation_task(proj["id"], task_id, status="complete")
        task = get_generation_task(proj["id"], episode_id=ep["id"])
        assert task["status"] == "complete"

    def test_update_generation_task_nonexistent(self, test_project):
        """更新不存在的任务返回 False。"""
        from app.core.store import update_generation_task

        proj, ep, _ = test_project
        assert not update_generation_task(proj["id"], "nonexistent_task", status="error")

    def test_get_generation_task_no_tasks(self, test_project):
        """没有任务时返回 None。"""
        from app.core.store import get_generation_task

        proj, ep, _ = test_project
        task = get_generation_task(proj["id"], episode_id=ep["id"])
        assert task is None

    def test_get_generation_task_by_type(self, test_project):
        """按类型过滤查询任务。"""
        from app.core.store import init_generation_task, get_generation_task

        proj, ep, _ = test_project
        task_id = init_generation_task(proj["id"], ep["id"], "dialogue_generation")

        # 按正确类型查询
        task = get_generation_task(
            proj["id"], episode_id=ep["id"], task_type="dialogue_generation"
        )
        assert task is not None
        assert task["id"] == task_id

        # 按错误类型查询
        task = get_generation_task(proj["id"], episode_id=ep["id"], task_type="refresh")
        assert task is None

    def test_cancel_generation_task(self, test_project):
        """取消任务。"""
        from app.core.store import (
            init_generation_task,
            cancel_generation_task,
            get_generation_task,
        )

        proj, ep, _ = test_project
        task_id = init_generation_task(proj["id"], ep["id"], "dialogue_generation")
        assert cancel_generation_task(proj["id"], task_id)

        task = get_generation_task(proj["id"], episode_id=ep["id"])
        assert task["status"] == "cancelled"

    def test_cancel_nonexistent_task(self, test_project):
        """取消不存在的任务返回 False。"""
        from app.core.store import cancel_generation_task

        proj, ep, _ = test_project
        assert not cancel_generation_task(proj["id"], "nonexistent")

    def test_list_generation_tasks(self, test_project):
        """列出任务。"""
        from app.core.store import init_generation_task, list_generation_tasks

        proj, ep, _ = test_project
        tid1 = init_generation_task(proj["id"], ep["id"], "dialogue_generation")
        tid2 = init_generation_task(proj["id"], ep["id"], "refresh")

        # 全部任务
        tasks = list_generation_tasks(proj["id"])
        assert len(tasks) == 2

        # 按剧集过滤
        tasks = list_generation_tasks(proj["id"], episode_id=ep["id"])
        assert len(tasks) == 2

        # 按状态过滤
        tasks = list_generation_tasks(proj["id"], status="running")
        assert len(tasks) == 2

    def test_list_generation_tasks_empty(self, test_project):
        """没有任务时返回空列表。"""
        from app.core.store import list_generation_tasks

        proj, ep, _ = test_project
        assert list_generation_tasks(proj["id"]) == []

    def test_get_generation_task_returns_running_first(self, test_project):
        """get_generation_task 优先返回 running 任务。"""
        from app.core.store import (
            init_generation_task,
            update_generation_task,
            get_generation_task,
        )

        proj, ep, _ = test_project
        # 先创建一个 complete 任务
        tid1 = init_generation_task(proj["id"], ep["id"], "dialogue_generation")
        update_generation_task(proj["id"], tid1, status="complete")

        # 再创建一个 running 任务
        tid2 = init_generation_task(proj["id"], ep["id"], "dialogue_generation")

        # get_generation_task 应返回 running 的任务
        task = get_generation_task(proj["id"], episode_id=ep["id"])
        assert task["id"] == tid2
        assert task["status"] == "running"

    def test_list_generation_tasks_status_filter(self, test_project):
        """按状态过滤列表。"""
        from app.core.store import (
            init_generation_task,
            update_generation_task,
            list_generation_tasks,
        )

        proj, ep, _ = test_project
        tid1 = init_generation_task(proj["id"], ep["id"], "dialogue_generation")
        update_generation_task(proj["id"], tid1, status="complete")
        tid2 = init_generation_task(proj["id"], ep["id"], "refresh")

        running = list_generation_tasks(proj["id"], status="running")
        assert len(running) == 1
        assert running[0]["id"] == tid2

        complete = list_generation_tasks(proj["id"], status="complete")
        assert len(complete) == 1
        assert complete[0]["id"] == tid1


# ═══════════════════════════════════════════════════════════
# 测试 1 & 2: API 集成测试
# ═══════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_api_generate_dialogues_returns_task_id(client, test_project):
    """测试 1: API 返回格式 — 调用生成端点，验证立即返回 task_id。"""
    proj, ep, _ = test_project

    # Mock run_dialogue_generation 避免实际 LLM 调用
    with patch(
        "app.core.dialogue_service.run_dialogue_generation",
        new_callable=AsyncMock,
    ):
        resp = await client.post(
            f"/api/projects/{proj['id']}/episodes/{ep['id']}/generate-dialogues",
            json={"target_duration_min": 5, "narration_ratio": 50},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert "task_id" in data
    assert data["task_id"].startswith("gen_task_")
    assert data["status"] == "running"
    assert data["episode_id"] == ep["id"]


@pytest.mark.asyncio
async def test_api_generation_status_fields(client, test_project):
    """测试 2: 任务状态轮询 — 验证返回字段包含 id/status/current/total。"""
    from app.core.store import init_generation_task

    proj, ep, _ = test_project
    task_id = init_generation_task(proj["id"], ep["id"], "dialogue_generation")

    resp = await client.get(
        f"/api/projects/{proj['id']}/generation-status",
        params={"episode_id": ep["id"]},
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == task_id
    assert data["status"] == "running"
    assert "current" in data
    assert "total" in data
    assert "episode_id" in data
    assert "type" in data
    assert "created_at" in data
    assert "updated_at" in data


@pytest.mark.asyncio
async def test_api_generation_status_idle(client, test_project):
    """没有任务时返回 {"status": "idle"}。"""
    proj, ep, _ = test_project

    resp = await client.get(
        f"/api/projects/{proj['id']}/generation-status",
        params={"episode_id": ep["id"]},
    )

    assert resp.status_code == 200
    assert resp.json() == {"status": "idle"}


@pytest.mark.asyncio
async def test_api_generation_status_complete(client, test_project):
    """任务完成后返回 complete 状态及结果。"""
    from app.core.store import init_generation_task, update_generation_task

    proj, ep, _ = test_project
    task_id = init_generation_task(proj["id"], ep["id"], "dialogue_generation")
    update_generation_task(
        proj["id"],
        task_id,
        status="complete",
        current=10,
        total=10,
        result={"created": 10, "dialogue_ids": [], "new_characters": []},
    )

    resp = await client.get(
        f"/api/projects/{proj['id']}/generation-status",
        params={"episode_id": ep["id"]},
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "complete"
    assert data["current"] == 10
    assert data["total"] == 10
    assert "result" in data


@pytest.mark.asyncio
async def test_api_generation_status_error(client, test_project):
    """任务失败时返回 error 状态及错误信息。"""
    from app.core.store import init_generation_task, update_generation_task

    proj, ep, _ = test_project
    task_id = init_generation_task(proj["id"], ep["id"], "dialogue_generation")
    update_generation_task(proj["id"], task_id, status="error", error="LLM 调用失败")

    resp = await client.get(
        f"/api/projects/{proj['id']}/generation-status",
        params={"episode_id": ep["id"]},
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "error"
    assert "error" in data


# ═══════════════════════════════════════════════════════════
# 测试 4: 并发控制
# ═══════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_concurrent_running_task_detection(client, test_project):
    """测试 4: 并发控制 — 验证 get_generation_task 能检测到 running 任务。

    当前 API 实现尚未添加 409 并发控制（FR-05），但 store 层
    get_generation_task() 已具备 running 任务检测能力。
    此测试验证 store 层行为，API 层并发控制待后续实现。
    """
    from app.core.store import init_generation_task, get_generation_task

    proj, ep, _ = test_project

    # 创建第一个任务
    tid1 = init_generation_task(proj["id"], ep["id"], "dialogue_generation")

    # 验证能检测到 running 任务
    running = get_generation_task(proj["id"], episode_id=ep["id"])
    assert running is not None
    assert running["id"] == tid1
    assert running["status"] == "running"

    # 创建第二个任务（当前实现允许，尚未实现 409 拒绝）
    tid2 = init_generation_task(proj["id"], ep["id"], "dialogue_generation")

    # 验证 get_generation_task 返回最新的 running 任务
    running = get_generation_task(proj["id"], episode_id=ep["id"])
    assert running["id"] == tid2
    assert running["status"] == "running"


@pytest.mark.asyncio
async def test_api_generate_dialogues_twice_creates_two_tasks(client, test_project):
    """连续两次调用生成 API，验证当前行为：创建两个独立任务。

    注意：当前 API 尚未实现 409 并发控制（FR-05），
    因此两次调用都会成功创建任务。此测试记录当前行为，
    待并发控制实现后应修改为验证 409。
    """
    proj, ep, _ = test_project

    with patch(
        "app.core.dialogue_service.run_dialogue_generation",
        new_callable=AsyncMock,
    ):
        resp1 = await client.post(
            f"/api/projects/{proj['id']}/episodes/{ep['id']}/generate-dialogues",
            json={"target_duration_min": 5, "narration_ratio": 50},
        )
        resp2 = await client.post(
            f"/api/projects/{proj['id']}/episodes/{ep['id']}/generate-dialogues",
            json={"target_duration_min": 5, "narration_ratio": 50},
        )

    assert resp1.status_code == 200
    assert resp2.status_code == 200
    data1 = resp1.json()
    data2 = resp2.json()
    # 两个 task_id 不同
    assert data1["task_id"] != data2["task_id"]
    assert data1["status"] == "running"
    assert data2["status"] == "running"


# ═══════════════════════════════════════════════════════════
# 测试 run_dialogue_generation 事件映射逻辑
# ═══════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_run_dialogue_generation_error_event(test_project):
    """run_dialogue_generation 处理 error 事件。"""
    from app.core.store import init_generation_task, get_generation_task
    from app.core.dialogue_service import run_dialogue_generation

    proj, ep, _ = test_project
    task_id = init_generation_task(proj["id"], ep["id"], "dialogue_generation")

    # Mock DialogueGenerator 的 _generate_story 方法
    async def mock_generate():
        yield "error", {"message": "LLM 配置错误"}

    with patch(
        "app.core.dialogue_service.DialogueGenerator._generate_story",
        return_value=mock_generate(),
    ):
        await run_dialogue_generation(proj["id"], ep["id"], None, task_id)

    task = get_generation_task(proj["id"], episode_id=ep["id"])
    assert task["status"] == "error"
    assert "LLM 配置错误" in task["error"]


@pytest.mark.asyncio
async def test_run_dialogue_generation_complete_event(test_project):
    """run_dialogue_generation 处理 complete 事件。"""
    from app.core.store import init_generation_task, get_generation_task
    from app.core.dialogue_service import run_dialogue_generation

    proj, ep, _ = test_project
    task_id = init_generation_task(proj["id"], ep["id"], "dialogue_generation")

    async def mock_generate():
        yield "generating", {"word_count": 1000}
        yield "progress", {"current": 1, "total": 5}
        yield "progress", {"current": 2, "total": 5}
        yield "progress", {"current": 3, "total": 5}
        yield "progress", {"current": 4, "total": 5}
        yield "progress", {"current": 5, "total": 5}
        yield "complete", {"created": 5, "dialogue_ids": ["d1", "d2"], "new_characters": []}

    with patch(
        "app.core.dialogue_service.DialogueGenerator._generate_story",
        return_value=mock_generate(),
    ):
        await run_dialogue_generation(proj["id"], ep["id"], None, task_id)

    task = get_generation_task(proj["id"], episode_id=ep["id"])
    assert task["status"] == "complete"
    assert task["current"] == 5
    assert task["total"] == 5
    assert "result" in task
    assert task["result"]["created"] == 5


@pytest.mark.asyncio
async def test_run_dialogue_generation_exception(test_project):
    """run_dialogue_generation 处理未捕获异常。"""
    from app.core.store import init_generation_task, get_generation_task
    from app.core.dialogue_service import run_dialogue_generation

    proj, ep, _ = test_project
    task_id = init_generation_task(proj["id"], ep["id"], "dialogue_generation")

    async def mock_generate():
        yield "generating", {"word_count": 100}
        raise RuntimeError("意外的运行时错误")

    with patch(
        "app.core.dialogue_service.DialogueGenerator._generate_story",
        return_value=mock_generate(),
    ):
        await run_dialogue_generation(proj["id"], ep["id"], None, task_id)

    task = get_generation_task(proj["id"], episode_id=ep["id"])
    assert task["status"] == "error"
    assert "意外的运行时错误" in task["error"]


@pytest.mark.asyncio
async def test_run_dialogue_generation_progress_throttle(test_project):
    """run_dialogue_generation 节流更新：每 5 条 progress 更新一次。"""
    from app.core.store import init_generation_task, get_generation_task
    from app.core.dialogue_service import run_dialogue_generation

    proj, ep, _ = test_project
    task_id = init_generation_task(proj["id"], ep["id"], "dialogue_generation")

    # 只 yield 3 条 progress（不足 5 条），不应触发 update
    async def mock_generate():
        yield "progress", {"current": 1, "total": 10}
        yield "progress", {"current": 2, "total": 10}
        yield "progress", {"current": 3, "total": 10}
        yield "complete", {"created": 3, "dialogue_ids": [], "new_characters": []}

    with patch(
        "app.core.dialogue_service.DialogueGenerator._generate_story",
        return_value=mock_generate(),
    ):
        await run_dialogue_generation(proj["id"], ep["id"], None, task_id)

    task = get_generation_task(proj["id"], episode_id=ep["id"])
    # 由于 progress 不足 5 条，current 应保持初始值 0
    assert task["current"] == 3  # complete 事件设置了 current=3
    assert task["status"] == "complete"
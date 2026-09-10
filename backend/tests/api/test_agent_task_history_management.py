from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.api import deps
from app.api.v1.endpoints.agent_tasks import router as agent_tasks_router
from app.db.base import Base
from app.models.agent_task import AgentTask, AgentTaskStatus
from app.models.audit_session import AuditSession
from app.models.project import Project
from app.models.user import User


def _app() -> FastAPI:
    app = FastAPI()
    app.include_router(agent_tasks_router, prefix="/api/v1/agent-tasks")
    return app



async def _seed(session_factory, *, task_status: str = AgentTaskStatus.COMPLETED):
    async with session_factory() as db:
        db.add_all([
            User(
                id="user-1", email="owner@example.com", hashed_password="hash",
                full_name="Owner", is_active=True,
            ),
            Project(
                id="project-1", name="Demo", owner_id="user-1", source_type="repository",
            ),
            AgentTask(
                id="task-1", project_id="project-1", created_by="user-1",
                name="Audit", version_label="test", status=task_status,
                created_at=datetime.now(timezone.utc),
            ),
            AuditSession(
                id="session-1", project_id="project-1", task_id="task-1",
                runtime_stack="runtime", state="completed",
            ),
        ])
        await db.commit()


def _override_dependencies(app: FastAPI, session_factory):
    async def override_get_db():
        async with session_factory() as db:
            yield db

    async def override_get_current_user():
        return SimpleNamespace(id="user-1", is_active=True)

    app.dependency_overrides[deps.get_db] = override_get_db
    app.dependency_overrides[deps.get_current_user] = override_get_current_user


@pytest.mark.asyncio
async def test_delete_finished_task_removes_runtime_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await _seed(session_factory)

    app = _app()
    _override_dependencies(app, session_factory)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.delete("/api/v1/agent-tasks/task-1")

    async with session_factory() as db:
        assert await db.get(AgentTask, "task-1") is None
        assert await db.get(AuditSession, "session-1") is None
    await engine.dispose()
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_delete_active_task_is_rejected():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await _seed(session_factory, task_status=AgentTaskStatus.RUNNING)

    app = _app()
    _override_dependencies(app, session_factory)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.delete("/api/v1/agent-tasks/task-1")

    async with session_factory() as db:
        assert await db.get(AgentTask, "task-1") is not None
    await engine.dispose()
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_status_filter_rejects_unknown_status_and_filters_valid_status():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await _seed(session_factory, task_status=AgentTaskStatus.FAILED)

    app = _app()
    _override_dependencies(app, session_factory)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        valid = await client.get("/api/v1/agent-tasks/", params={"status": "failed"})
        invalid = await client.get("/api/v1/agent-tasks/", params={"status": "not-a-status"})

    await engine.dispose()
    assert valid.status_code == 200
    assert [item["id"] for item in valid.json()] == ["task-1"]
    assert invalid.status_code == 400

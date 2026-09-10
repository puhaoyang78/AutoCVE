from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    file_path = Path(path)
    text = file_path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{path}: expected one match, found {count}")
    file_path.write_text(text.replace(old, new, 1), encoding="utf-8")


# A non-zero program exit is an execution observation, not a RunCode infrastructure
# failure. Sanitizers and deliberate crash harnesses use non-zero exits to report
# the vulnerability, so keep their stdout/stderr visible to the verification agent.
run_code_path = "backend/app/services/agent/tools/run_code.py"
text = Path(run_code_path).read_text(encoding="utf-8")
old_languages = "python, php, javascript, ruby, go, java, c, cpp, bash"
if text.count(old_languages) < 3:
    raise RuntimeError("RunCode language list changed unexpectedly")
Path(run_code_path).write_text(
    text.replace(old_languages, "python, php, javascript, ruby, go, java, c, cpp, c++, bash"),
    encoding="utf-8",
)

replace_once(
    run_code_path,
    '''        return ToolResult(\n            success=result.get("success", False),\n            data="\\n".join(output_parts),\n            error=result.get("error"),\n''',
    '''        return ToolResult(\n            # A non-zero target-process exit can be the expected vulnerability signal\n            # (for example ASan/UBSan). Only sandbox/infrastructure errors make the\n            # tool call itself fail; the exit code remains available in metadata.\n            success=result.get("error") is None,\n            data="\\n".join(output_parts),\n            error=result.get("error"),\n''',
)

# Clarify the independent embedding configuration in the sample environment. DeepSeek
# is suitable for the main LLM but its API key must not silently be treated as an
# OpenAI embedding key.
env_path = "backend/env.example"
replace_once(
    env_path,
    '''# 嵌入模型 provider: openai, ollama, cohere, huggingface\nEMBEDDING_PROVIDER=openai\n''',
    '''# 嵌入模型 provider: openai, ollama, cohere, huggingface\n# 注意：嵌入模型与主 LLM 独立配置。若主模型使用 DeepSeek，不要让 OpenAI\n# embedding 复用 DeepSeek API Key；请另填 EMBEDDING_API_KEY，或改用 Ollama 等。\nEMBEDDING_PROVIDER=openai\n''',
)

# Extend the existing C/C++ tests with the execution-result contract.
cpp_test = Path("backend/tests/services/test_run_code_cpp.py")
cpp_text = cpp_test.read_text(encoding="utf-8")
if "test_nonzero_program_exit_remains_visible_to_agent" not in cpp_text:
    cpp_text += '''\n\nclass _FakeSandbox:\n    is_available = True\n\n    async def initialize(self):\n        return None\n\n    async def execute_command(self, command: str, timeout: int):\n        return {\n            "success": False,\n            "stdout": "",\n            "stderr": "ERROR: AddressSanitizer: heap-use-after-free",\n            "exit_code": 1,\n            "error": None,\n        }\n\n\nclass _BrokenSandbox(_FakeSandbox):\n    async def execute_command(self, command: str, timeout: int):\n        return {\n            "success": False,\n            "stdout": "",\n            "stderr": "",\n            "exit_code": -1,\n            "error": "sandbox timeout",\n        }\n\n\ndef test_run_code_language_schema_mentions_cpp_alias():\n    assert "c++" in RunCodeTool().description\n\n\nimport pytest\n\n\n@pytest.mark.asyncio\nasync def test_nonzero_program_exit_remains_visible_to_agent():\n    result = await RunCodeTool(sandbox_manager=_FakeSandbox())._execute(\n        code="int main(void) { return 1; }",\n        language="c",\n    )\n    assert result.success is True\n    assert result.metadata["exit_code"] == 1\n    assert "AddressSanitizer" in result.data\n    assert "AddressSanitizer" in result.to_string()\n\n\n@pytest.mark.asyncio\nasync def test_sandbox_error_still_marks_run_code_failure():\n    result = await RunCodeTool(sandbox_manager=_BrokenSandbox())._execute(\n        code="int main(void) { return 0; }",\n        language="c",\n    )\n    assert result.success is False\n    assert result.error == "sandbox timeout"\n'''
    cpp_test.write_text(cpp_text, encoding="utf-8")

# Add focused regression coverage for the history-management endpoints introduced in
# the previous pass. This uses the same in-memory API style as the existing route tests.
history_test = Path("backend/tests/api/test_agent_task_history_management.py")
history_test.write_text('''from datetime import datetime, timezone\nfrom types import SimpleNamespace\n\nimport pytest\nfrom fastapi import FastAPI\nfrom httpx import ASGITransport, AsyncClient\nfrom sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine\n\nfrom app.api import deps\nfrom app.api.v1.endpoints.agent_tasks import router as agent_tasks_router\nfrom app.db.base import Base\nfrom app.models.agent_task import AgentTask, AgentTaskStatus\nfrom app.models.audit_session import AuditSession\nfrom app.models.project import Project\nfrom app.models.user import User\n\n\ndef _app() -> FastAPI:\n    app = FastAPI()\n    app.include_router(agent_tasks_router, prefix="/api/v1/agent-tasks")\n    return app\n\n\n\nasync def _seed(session_factory, *, task_status: str = AgentTaskStatus.COMPLETED):\n    async with session_factory() as db:\n        db.add_all([\n            User(\n                id="user-1", email="owner@example.com", hashed_password="hash",\n                full_name="Owner", is_active=True,\n            ),\n            Project(\n                id="project-1", name="Demo", owner_id="user-1", source_type="repository",\n            ),\n            AgentTask(\n                id="task-1", project_id="project-1", created_by="user-1",\n                name="Audit", version_label="test", status=task_status,\n                created_at=datetime.now(timezone.utc),\n            ),\n            AuditSession(\n                id="session-1", project_id="project-1", task_id="task-1",\n                runtime_stack="runtime", state="completed",\n            ),\n        ])\n        await db.commit()\n\n\ndef _override_dependencies(app: FastAPI, session_factory):\n    async def override_get_db():\n        async with session_factory() as db:\n            yield db\n\n    async def override_get_current_user():\n        return SimpleNamespace(id="user-1", is_active=True)\n\n    app.dependency_overrides[deps.get_db] = override_get_db\n    app.dependency_overrides[deps.get_current_user] = override_get_current_user\n\n\n@pytest.mark.asyncio\nasync def test_delete_finished_task_removes_runtime_session():\n    engine = create_async_engine("sqlite+aiosqlite:///:memory:")\n    session_factory = async_sessionmaker(engine, expire_on_commit=False)\n    async with engine.begin() as conn:\n        await conn.run_sync(Base.metadata.create_all)\n    await _seed(session_factory)\n\n    app = _app()\n    _override_dependencies(app, session_factory)\n    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:\n        response = await client.delete("/api/v1/agent-tasks/task-1")\n\n    async with session_factory() as db:\n        assert await db.get(AgentTask, "task-1") is None\n        assert await db.get(AuditSession, "session-1") is None\n    await engine.dispose()\n    assert response.status_code == 200\n\n\n@pytest.mark.asyncio\nasync def test_delete_active_task_is_rejected():\n    engine = create_async_engine("sqlite+aiosqlite:///:memory:")\n    session_factory = async_sessionmaker(engine, expire_on_commit=False)\n    async with engine.begin() as conn:\n        await conn.run_sync(Base.metadata.create_all)\n    await _seed(session_factory, task_status=AgentTaskStatus.RUNNING)\n\n    app = _app()\n    _override_dependencies(app, session_factory)\n    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:\n        response = await client.delete("/api/v1/agent-tasks/task-1")\n\n    async with session_factory() as db:\n        assert await db.get(AgentTask, "task-1") is not None\n    await engine.dispose()\n    assert response.status_code == 409\n\n\n@pytest.mark.asyncio\nasync def test_status_filter_rejects_unknown_status_and_filters_valid_status():\n    engine = create_async_engine("sqlite+aiosqlite:///:memory:")\n    session_factory = async_sessionmaker(engine, expire_on_commit=False)\n    async with engine.begin() as conn:\n        await conn.run_sync(Base.metadata.create_all)\n    await _seed(session_factory, task_status=AgentTaskStatus.FAILED)\n\n    app = _app()\n    _override_dependencies(app, session_factory)\n    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:\n        valid = await client.get("/api/v1/agent-tasks/", params={"status": "failed"})\n        invalid = await client.get("/api/v1/agent-tasks/", params={"status": "not-a-status"})\n\n    await engine.dispose()\n    assert valid.status_code == 200\n    assert [item["id"] for item in valid.json()] == ["task-1"]\n    assert invalid.status_code == 400\n''', encoding="utf-8")

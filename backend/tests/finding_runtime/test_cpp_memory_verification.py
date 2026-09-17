from __future__ import annotations

import asyncio

from app.services.agent.tools.base import AgentTool, ToolResult
from app.services.finding_runtime.tools.verify_cpp_memory import VerifyCppMemoryInput, VerifyCppMemoryTool
from app.services.runtime_core import build_runtime_tool_registry
from app.services.runtime_core.tool_runtime import ToolExecutionContext


class FakeRunCodeTool(AgentTool):
    def __init__(self, *, output: str, exit_code: int = 1, success: bool = True):
        super().__init__()
        self.output = output
        self.exit_code = exit_code
        self.execution_success = success

    @property
    def name(self) -> str:
        return "run_code"

    @property
    def description(self) -> str:
        return "fake run code"

    async def _execute(self, **kwargs):
        return ToolResult(
            success=self.execution_success,
            data=self.output,
            error=None if self.execution_success else "sandbox unavailable",
            metadata={"exit_code": self.exit_code, "language": kwargs.get("language")},
        )


class FakeReadTool(AgentTool):
    def __init__(self, project_root: str):
        super().__init__()
        self.project_root = project_root

    @property
    def name(self) -> str:
        return "read_file"

    @property
    def description(self) -> str:
        return "fake reader"

    async def _execute(self, **kwargs):
        return ToolResult(success=True, data=kwargs)


class FakeSessionStore:
    pass


def context() -> ToolExecutionContext:
    return ToolExecutionContext(
        session_id="session-1",
        turn_id="turn-1",
        tool_use_id="tool-use-1",
        tool_call_id="tool-call-1",
    )


def test_cpp_memory_verifier_marks_asan_signal_as_dynamic_success():
    tool = VerifyCppMemoryTool(
        run_code_tool=FakeRunCodeTool(
            output="ERROR: AddressSanitizer: heap-buffer-overflow on address 0x1234",
            exit_code=1,
        )
    )

    result = asyncio.run(
        tool.execute(
            VerifyCppMemoryInput(
                code="int main(void) { return 0; }",
                language="c",
                description="reproduce bounds candidate",
            ),
            context(),
        )
    )

    assert result.is_error is False
    assert result.output_payload["dynamic"] is True
    assert result.output_payload["success"] is True
    assert result.output_payload["sanitizer_detected"] is True
    assert "asan" in result.output_payload["sanitizers"]


def test_cpp_memory_verifier_keeps_clean_run_unconfirmed():
    tool = VerifyCppMemoryTool(
        run_code_tool=FakeRunCodeTool(output="completed normally", exit_code=0)
    )

    result = asyncio.run(
        tool.execute(
            VerifyCppMemoryInput(code="int main(void) { return 0; }", language="c"),
            context(),
        )
    )

    assert result.is_error is False
    assert result.output_payload["success"] is False
    assert result.output_payload["sanitizer_detected"] is False


def test_shared_runtime_registry_adds_cpp_verifier_only_for_finding():
    agent_tools = {"read_file": FakeReadTool("/repo")}

    finding_registry = build_runtime_tool_registry(
        session_store=FakeSessionStore(),
        agent_tools=agent_tools,
        agent_type="finding",
    )
    recon_registry = build_runtime_tool_registry(
        session_store=FakeSessionStore(),
        agent_tools=agent_tools,
        agent_type="recon",
    )

    assert finding_registry.get("VerifyCppMemory") is not None
    assert recon_registry.get("VerifyCppMemory") is None

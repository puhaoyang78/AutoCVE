from .memory_runtime import RuntimeMemoryManager, build_memory_message
from .models import AgentRuntimeState, InvokedSkillState, SessionRuntimeState
from .permission_runtime import RuntimePermissionRuntime, ToolPermissionDecision
from .runtime_session_checkpoint_store import RuntimeSessionCheckpointStore
from .skill_discovery import SkillDiscoveryScheduler
from .skill_runtime import SkillInvocationRuntime
from .tool_runtime import (
    RuntimeTool,
    StreamingToolExecutor,
    ToolExecutionContext,
    ToolExecutionUpdate,
    ToolOrchestrator,
    ToolRegistry,
    build_runtime_tool,
)


def _infer_agent_project_root(agent_tools):
    for key in ("read_file", "list_files", "search_code"):
        tool = (agent_tools or {}).get(key)
        project_root = getattr(tool, "project_root", None)
        if isinstance(project_root, str) and project_root.strip():
            return project_root
    return "."


def build_runtime_tool_registry(*args, **kwargs):
    from .runtime_tool_registry import build_runtime_tool_registry as _build_runtime_tool_registry

    registry = _build_runtime_tool_registry(*args, **kwargs)
    agent_type = str(kwargs.get("agent_type") or "").strip()
    if agent_type == "finding" and registry.get("VerifyCppMemory") is None:
        from app.services.finding_runtime.tools.verify_cpp_memory import VerifyCppMemoryTool

        registry.register(
            VerifyCppMemoryTool(
                project_root=_infer_agent_project_root(kwargs.get("agent_tools") or {}),
            )
        )
    return registry


__all__ = [
    "RuntimeMemoryManager",
    "build_memory_message",
    "AgentRuntimeState",
    "InvokedSkillState",
    "SessionRuntimeState",
    "RuntimeSessionRegistry",
    "runtime_session_registry",
    "RuntimePermissionRuntime",
    "ToolPermissionDecision",
    "RuntimeSessionCheckpointStore",
    "build_runtime_tool_registry",
    "SkillDiscoveryScheduler",
    "SkillInvocationRuntime",
    "RuntimeTool",
    "StreamingToolExecutor",
    "ToolExecutionContext",
    "ToolExecutionUpdate",
    "ToolOrchestrator",
    "ToolPermissionDecision",
    "ToolRegistry",
    "build_runtime_tool",
]

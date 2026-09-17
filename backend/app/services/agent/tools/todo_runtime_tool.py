from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from app.services.finding_runtime.models import ToolExecutionPayload
from app.services.runtime_core.interaction_runtime import InteractionRuntime
from app.services.runtime_core.tool_runtime import RuntimeTool, ToolExecutionContext


class TodoWriteInput(BaseModel):
    action: Literal["write", "list"] = "write"
    title: str = ""
    details: str | None = None
    category: Literal["todo", "candidate_decision"] = "todo"
    candidate_id: str | None = None
    disposition: Literal["active", "rejected", "verified", "deferred"] | None = None
    supporting_facts: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _validate_payload(self):
        if self.action == "list":
            return self
        if not str(self.title or "").strip():
            raise ValueError("write action requires title")
        if self.category != "candidate_decision":
            return self
        if not str(self.candidate_id or "").strip():
            raise ValueError("candidate_decision requires candidate_id")
        if self.disposition is None:
            raise ValueError("candidate_decision requires disposition")
        facts = [str(item or "").strip() for item in self.supporting_facts if str(item or "").strip()]
        self.supporting_facts = facts
        if self.disposition in {"rejected", "verified"} and not facts:
            raise ValueError(f"{self.disposition} candidate decisions require supporting facts")
        return self


class TodoWriteRuntimeTool(RuntimeTool):
    name = "TodoWrite"
    description = (
        "记录或读取当前 Agent 的普通待办与候选漏洞状态。"
        "普通计划使用 action=write, category=todo。"
        "候选状态使用 action=write, category=candidate_decision，并提供 candidate_id、disposition 和 supporting_facts；"
        "rejected/verified 必须记录直接源码事实或动态验证结果。"
        "恢复审计或准备重新检查候选前，使用 action=list, category=candidate_decision 读取既有候选决策，"
        "避免重复审计已经被有效控制阻断或已经验证的候选。"
    )
    input_model = TodoWriteInput
    should_defer = True
    always_load = True
    search_hint = "记录或读取待办、候选漏洞状态和排除事实"

    def __init__(self, session_store):
        super().__init__()
        self._session_store = session_store
        self._interaction_runtime = InteractionRuntime()

    async def execute(self, parsed_input: TodoWriteInput, context: ToolExecutionContext) -> ToolExecutionPayload:
        runtime_state = self._session_store.load_runtime_state(context.session_id)

        if parsed_input.action == "list":
            if parsed_input.category == "candidate_decision":
                decisions = dict(runtime_state.metadata.get("candidate_decisions") or {})
                return ToolExecutionPayload(
                    content=f"Loaded {len(decisions)} persisted candidate decisions.",
                    output_payload={"candidate_decisions": decisions},
                    metadata={"interaction": "candidate_decision_list", "count": len(decisions)},
                )
            agent_state = runtime_state.ensure_agent_state(context.agent_type)
            todos = [dict(item) for item in agent_state.pending_todos]
            return ToolExecutionPayload(
                content=f"Loaded {len(todos)} pending todos.",
                output_payload={"todos": todos},
                metadata={"interaction": "todo_list", "count": len(todos)},
            )

        if parsed_input.category == "candidate_decision":
            candidate_id = str(parsed_input.candidate_id or "").strip()
            candidate_decisions = runtime_state.metadata.setdefault("candidate_decisions", {})
            decision = {
                "candidate_id": candidate_id,
                "title": parsed_input.title.strip(),
                "details": str(parsed_input.details or "").strip() or None,
                "disposition": parsed_input.disposition,
                "supporting_facts": list(parsed_input.supporting_facts),
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
            candidate_decisions[candidate_id] = decision
            self._session_store.replace_runtime_state(context.session_id, runtime_state)
            return ToolExecutionPayload(
                content=f"Candidate decision recorded: {candidate_id} -> {parsed_input.disposition}",
                output_payload={"candidate_decision": decision},
                metadata={"interaction": "candidate_decision", "disposition": parsed_input.disposition},
            )

        todo = self._interaction_runtime.create_todo(
            runtime_state,
            agent_type=context.agent_type,
            title=parsed_input.title,
            details=parsed_input.details,
        )
        self._session_store.replace_runtime_state(context.session_id, runtime_state)
        return ToolExecutionPayload(
            content=f"Todo recorded: {todo['title']}",
            output_payload={"todo": todo},
            metadata={"interaction": "todo"},
        )

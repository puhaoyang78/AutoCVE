from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from app.services.finding_runtime.models import ToolExecutionPayload
from app.services.runtime_core.interaction_runtime import InteractionRuntime
from app.services.runtime_core.tool_runtime import RuntimeTool, ToolExecutionContext


class TodoWriteInput(BaseModel):
    title: str = Field(..., min_length=1)
    details: str | None = None
    category: Literal["todo", "candidate_decision"] = "todo"
    candidate_id: str | None = None
    disposition: Literal["active", "rejected", "verified", "deferred"] | None = None
    evidence: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _validate_candidate_decision(self):
        if self.category != "candidate_decision":
            return self
        if not str(self.candidate_id or "").strip():
            raise ValueError("candidate_decision requires candidate_id")
        if self.disposition is None:
            raise ValueError("candidate_decision requires disposition")
        normalized_evidence = [str(item or "").strip() for item in self.evidence if str(item or "").strip()]
        self.evidence = normalized_evidence
        if self.disposition in {"rejected", "verified"} and not normalized_evidence:
            raise ValueError(f"{self.disposition} candidate decisions require direct evidence")
        return self


class TodoWriteRuntimeTool(RuntimeTool):
    name = "TodoWrite"
    description = (
        "记录当前 Agent 的普通待办或候选漏洞状态。"
        "普通计划使用 category=todo。"
        "对已经检查过的漏洞候选，使用 category=candidate_decision 并提供 candidate_id、disposition 和证据；"
        "特别是 rejected/verified 必须记录直接源码或动态验证证据，这些状态会持久化到运行时会话，"
        "用于恢复任务时避免重复审计同一候选。"
    )
    input_model = TodoWriteInput
    should_defer = True
    always_load = True
    search_hint = "记录待办、候选漏洞状态或排除证据"

    def __init__(self, session_store):
        super().__init__()
        self._session_store = session_store
        self._interaction_runtime = InteractionRuntime()

    async def execute(self, parsed_input: TodoWriteInput, context: ToolExecutionContext) -> ToolExecutionPayload:
        runtime_state = self._session_store.load_runtime_state(context.session_id)
        if parsed_input.category == "candidate_decision":
            candidate_id = str(parsed_input.candidate_id or "").strip()
            candidate_decisions = runtime_state.metadata.setdefault("candidate_decisions", {})
            decision = {
                "candidate_id": candidate_id,
                "title": parsed_input.title.strip(),
                "details": str(parsed_input.details or "").strip() or None,
                "disposition": parsed_input.disposition,
                "evidence": list(parsed_input.evidence),
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

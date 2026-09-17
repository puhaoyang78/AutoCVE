from __future__ import annotations

import asyncio
from types import SimpleNamespace

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.services.finding_runtime.adapters.finding import FindingRuntimeAdapter
from app.services.finding_runtime.session_store import AuditSessionStore
from app.services.finding_runtime.skills import (
    FINDING_AUDIT_SKILL,
    FINDING_KNOWLEDGE_SKILL,
    FINDING_REPORT_SKILL,
    RuntimeSkillTool,
)
from app.services.finding_runtime.tooling import ToolExecutionContext


class FakeSkillService:
    @staticmethod
    def get_skill_entry(user_id, skill_ref, agent_type=None):
        del user_id, agent_type
        return SimpleNamespace(
            slug=skill_ref,
            name=skill_ref,
            is_active=True,
            agent=None,
            disable_model_invocation=False,
            user_invocable=True,
            allowed_tools=[],
            effort=None,
            execution_context=None,
            paths=[],
            hooks={},
            source_type="test",
            source_url=None,
            model=None,
        )

    @staticmethod
    async def get_skill_body(user_id, skill_ref, agent_type=None):
        del user_id, agent_type
        return {"skill": skill_ref, "content": f"{skill_ref} body"}

    @staticmethod
    async def list_skill_resources(user_id, skill_ref, resource_name="", agent_type=None):
        del user_id, agent_type
        return {"skill": skill_ref, "resource_name": resource_name, "items": []}

    @staticmethod
    async def get_skill_resource(user_id, skill_ref, resource_name, agent_type=None):
        del user_id, agent_type
        return {"skill": skill_ref, "resource": resource_name, "content": "resource"}


def build_store() -> AuditSessionStore:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return AuditSessionStore(session_factory=sessionmaker(bind=engine))


def execute_skill(store: AuditSessionStore, session_id: str, skill_ref: str):
    turn_id = store.open_turn(session_id, model_name="test")
    tool = RuntimeSkillTool(session_store=store, skill_service=FakeSkillService())
    return asyncio.run(
        tool.execute(
            tool.input_model(skill_ref=skill_ref, action="body"),
            ToolExecutionContext(
                session_id=session_id,
                turn_id=turn_id,
                tool_use_id=f"use-{skill_ref}",
                tool_call_id=f"call-{skill_ref}",
            ),
        )
    )


def test_audit_phase_allows_audit_and_knowledge_but_blocks_report_skill():
    store = build_store()
    session_id = store.create_session(project_id="project-1")

    assert execute_skill(store, session_id, FINDING_AUDIT_SKILL).is_error is False
    assert execute_skill(store, session_id, FINDING_KNOWLEDGE_SKILL).is_error is False

    blocked = execute_skill(store, session_id, FINDING_REPORT_SKILL)
    assert blocked.is_error is True
    assert blocked.output_payload["reason"] == "finding_skill_phase_mismatch"


def test_report_phase_allows_only_report_skill():
    store = build_store()
    session_id = store.create_session(project_id="project-1")
    runtime_state = store.load_runtime_state(session_id)
    runtime_state.metadata["report_generation_mode"] = True
    store.replace_runtime_state(session_id, runtime_state)

    assert execute_skill(store, session_id, FINDING_REPORT_SKILL).is_error is False
    assert execute_skill(store, session_id, FINDING_AUDIT_SKILL).is_error is True
    assert execute_skill(store, session_id, FINDING_KNOWLEDGE_SKILL).is_error is True


def test_phase_routing_keeps_report_skill_out_of_audit_primary():
    skill_context = SimpleNamespace(
        route_plan={},
        available_skills=[
            {"slug": FINDING_AUDIT_SKILL, "paths": {"skill_file_path": "/skills/audit/SKILL.md"}},
            {"slug": FINDING_KNOWLEDGE_SKILL, "paths": {"skill_file_path": "/skills/knowledge/SKILL.md"}},
            {"slug": FINDING_REPORT_SKILL, "paths": {"skill_file_path": "/skills/report/SKILL.md"}},
        ],
        route_message="",
    )
    discovery = {
        "selected_skill": FINDING_REPORT_SKILL,
        "ranked_candidates": [
            {
                "skill_ref": FINDING_REPORT_SKILL,
                "score": 30,
                "trigger_reasons": ["report_request_alignment"],
                "suggested_stage": "body",
            },
            {
                "skill_ref": FINDING_KNOWLEDGE_SKILL,
                "score": 5,
                "trigger_reasons": ["binding_match"],
                "suggested_stage": "body",
            },
        ],
    }

    adapter = object.__new__(FindingRuntimeAdapter)
    adapter._apply_discovery_snapshot(skill_context, discovery, report_generation_mode=False)

    assert skill_context.route_plan["primary_skill"] == FINDING_AUDIT_SKILL
    assert FINDING_REPORT_SKILL in skill_context.route_plan["deferred_skills"]
    assert FINDING_KNOWLEDGE_SKILL not in skill_context.route_plan["secondary_skills"]


def test_report_phase_selects_report_skill_as_primary():
    skill_context = SimpleNamespace(
        route_plan={},
        available_skills=[
            {"slug": FINDING_AUDIT_SKILL, "paths": {"skill_file_path": "/skills/audit/SKILL.md"}},
            {"slug": FINDING_KNOWLEDGE_SKILL, "paths": {"skill_file_path": "/skills/knowledge/SKILL.md"}},
            {"slug": FINDING_REPORT_SKILL, "paths": {"skill_file_path": "/skills/report/SKILL.md"}},
        ],
        route_message="",
    )

    adapter = object.__new__(FindingRuntimeAdapter)
    adapter._apply_discovery_snapshot(skill_context, {"ranked_candidates": []}, report_generation_mode=True)

    assert skill_context.route_plan["primary_skill"] == FINDING_REPORT_SKILL
    assert skill_context.route_plan["secondary_skills"] == []
    assert FINDING_AUDIT_SKILL in skill_context.route_plan["deferred_skills"]

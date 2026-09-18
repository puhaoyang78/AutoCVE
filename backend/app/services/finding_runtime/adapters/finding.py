from __future__ import annotations

import inspect
from typing import Any

from app.services.agent.skill_service import SkillService
from app.services.finding_runtime.models import RuntimeMessageRole, TranscriptItem
from app.services.finding_runtime.query_transitions import hydrate_query_loop_state
from app.services.finding_runtime.skills import (
    FINDING_AUDIT_SKILL,
    FINDING_KNOWLEDGE_SKILL,
    FINDING_REPORT_SKILL,
    RuntimeSkillCatalog,
)
from app.services.runtime_core.explicit_skill_loader import load_explicit_skill_injections
from app.services.runtime_core.memory_runtime import (
    RuntimeMemoryManager,
    build_runtime_memory_prompt,
)
from app.services.runtime_core.skill_discovery import SkillDiscoveryScheduler
from app.services.runtime_core.skill_mentions import collect_explicit_skill_mentions


class FindingRuntimeAdapter:

    DEFAULT_USER_MESSAGE = "Continue the audit with the current Finding objective."

    def __init__(
        self,
        *,
        session_store,
        runner,
        skill_catalog: RuntimeSkillCatalog | None = None,
        memory_manager: RuntimeMemoryManager | None = None,
        discovery_scheduler: SkillDiscoveryScheduler | None = None,
        skill_service: Any = SkillService,
    ):
        self._session_store = session_store
        self._runner = runner
        self._skill_catalog = skill_catalog or RuntimeSkillCatalog()
        self._memory_manager = memory_manager or RuntimeMemoryManager(
            session_factory=getattr(session_store, "_session_factory", None)
        )
        self._discovery_scheduler = discovery_scheduler or SkillDiscoveryScheduler()
        self._skill_service = skill_service

    async def run(
        self,
        *,
        project_id: str,
        task_id: str | None,
        system_prompt: str,
        recon_payload: dict,
        user_message: str | None = None,
        model_name: str = "finding-runtime",
        on_session_created=None,
        on_user_message_created=None,
    ) -> dict:
        session_id = self._session_store.create_session(
            project_id=project_id,
            task_id=task_id,
            runtime_stack="runtime",
            system_prompt=system_prompt,
            recon_payload=recon_payload,
        )
        if on_session_created is not None:
            maybe_awaitable = on_session_created(session_id)
            if inspect.isawaitable(maybe_awaitable):
                await maybe_awaitable
        effective_user_message = user_message or self.DEFAULT_USER_MESSAGE
        skill_context, explicit_skill_injection_text, discovery_snapshot = await self._resolve_skill_context(
            session_id=session_id,
            base_system_prompt=system_prompt,
            user_message=effective_user_message,
            recon_payload=recon_payload,
        )
        self._session_store.replace_skills(
            session_id,
            skill_context.available_skills,
            matched_skill_refs=self._matched_skill_refs(skill_context.matched_skills),
        )

        memory_bundle = await self._memory_manager.preload(
            agent_type="finding",
            system_prompt=system_prompt,
            recon_payload=recon_payload,
            user_message=effective_user_message,
            skill_context={
                "prompt": skill_context.prompt,
                "route_plan": skill_context.route_plan,
            },
        )
        self._session_store.replace_memories(session_id, memory_bundle.all_memories)

        enriched_system_prompt = self._compose_system_prompt(
            base_system_prompt=system_prompt,
            skill_context=skill_context,
            explicit_skill_injection_text=explicit_skill_injection_text,
            memories=memory_bundle.all_memories,
        )
        self._session_store.update_system_prompt(session_id, enriched_system_prompt)
        self._persist_runtime_metadata(
            session_id=session_id,
            base_system_prompt=system_prompt,
            user_message=effective_user_message,
            skill_context=skill_context,
            discovery_snapshot=discovery_snapshot,
        )

        user_message_id = self._session_store.append_message(
            session_id,
            TranscriptItem(
                role=RuntimeMessageRole.USER,
                content=effective_user_message,
            ),
        )
        if on_user_message_created is not None:
            maybe_awaitable = on_user_message_created(user_message_id)
            if inspect.isawaitable(maybe_awaitable):
                await maybe_awaitable
        runner_result = await self._runner.run_once(session_id=session_id, model_name=model_name)
        return {
            "session_id": session_id,
            "runner_result": runner_result,
            "skill_route": skill_context.route_plan,
            "memory_counts": {
                "instruction": len(memory_bundle.instructions),
                "recall": len(memory_bundle.recalls),
            },
        }

    async def refresh_session_context(self, *, session_id: str) -> dict:
        snapshot = self._session_store.load_session_snapshot(session_id)
        runtime_state = self._session_store.load_runtime_state(session_id)
        query_loop_state = self._session_store.load_query_loop_state(session_id)
        base_system_prompt = str(runtime_state.metadata.get("base_system_prompt") or snapshot.session.system_prompt or "").strip()
        effective_user_message = self._resolve_latest_user_message(snapshot.messages, runtime_state.metadata.get("last_user_message"))
        recon_payload = dict(snapshot.session.recon_payload or {})
        skill_context, explicit_skill_injection_text, discovery_snapshot = await self._resolve_skill_context(
            session_id=session_id,
            base_system_prompt=base_system_prompt,
            user_message=effective_user_message,
            recon_payload=recon_payload,
        )
        self._session_store.replace_skills(
            session_id,
            skill_context.available_skills,
            matched_skill_refs=self._matched_skill_refs(skill_context.matched_skills),
        )
        memories = self._session_store.list_memories(session_id)
        enriched_system_prompt = self._compose_system_prompt(
            base_system_prompt=base_system_prompt,
            skill_context=skill_context,
            explicit_skill_injection_text=explicit_skill_injection_text,
            memories=memories,
        )
        self._session_store.update_system_prompt(session_id, enriched_system_prompt)
        self._persist_runtime_metadata(
            session_id=session_id,
            base_system_prompt=base_system_prompt,
            user_message=effective_user_message,
            skill_context=skill_context,
            discovery_snapshot=discovery_snapshot,
        )
        refreshed_transcript = [
            TranscriptItem(
                role=RuntimeMessageRole(message.role),
                content=message.content,
                name=message.name,
                metadata=dict(message.message_metadata or {}),
                payload=dict(message.payload or {}),
            )
            for message in snapshot.messages
        ]
        self._session_store.save_query_loop_state(
            session_id,
            hydrate_query_loop_state(query_loop_state, messages=refreshed_transcript),
        )
        return {
            "prompt": skill_context.prompt,
            "route_plan": skill_context.route_plan,
            "route_message": skill_context.route_message,
        }

    async def _resolve_skill_context(self, *, session_id: str, base_system_prompt: str, user_message: str, recon_payload: dict):
        skill_context = await self._skill_catalog.preload(
            user_id=None,
            agent_type="finding",
            context={
                "recon_data": recon_payload,
                "project_info": recon_payload.get("project_info", {}),
                "task": user_message,
                "config": {},
            },
        )
        runtime_state = self._session_store.load_runtime_state(session_id)
        report_generation_mode = bool(runtime_state.metadata.get("report_generation_mode"))
        discovery_snapshot = self._discovery_scheduler.discover(
            agent_type="finding",
            runtime_state=runtime_state,
            available_skills=skill_context.available_skills,
            matched_skills=skill_context.matched_skills,
            task=user_message,
            latest_user_message=user_message,
            recon_payload=recon_payload,
        )
        self._apply_discovery_snapshot(
            skill_context,
            discovery_snapshot,
            report_generation_mode=report_generation_mode,
        )
        explicit_mentions = collect_explicit_skill_mentions(
            mention_sources=[
                ("user", user_message),
                ("system", base_system_prompt),
                ("route", skill_context.route_message),
            ],
            available_skills=skill_context.available_skills,
        )
        explicit_mentions = self._filter_explicit_mentions_for_phase(
            explicit_mentions,
            report_generation_mode=report_generation_mode,
            discovery_snapshot=discovery_snapshot,
        )
        explicit_skill_injection_text = await load_explicit_skill_injections(
            session_store=self._session_store,
            agent_type="finding",
            session_id=session_id,
            mentions=explicit_mentions,
            skill_service=self._skill_service,
        )
        return skill_context, explicit_skill_injection_text, discovery_snapshot

    def _apply_discovery_snapshot(
        self,
        skill_context,
        discovery_snapshot: dict[str, object],
        *,
        report_generation_mode: bool = False,
    ) -> None:
        route_plan = dict(skill_context.route_plan or {})
        ranked = list(discovery_snapshot.get("ranked_candidates") or [])
        available_by_ref = {
            self._skill_ref(item): item
            for item in skill_context.available_skills
            if self._skill_ref(item)
        }

        if report_generation_mode:
            selected_skill = FINDING_REPORT_SKILL if FINDING_REPORT_SKILL in available_by_ref else None
            secondary_refs: list[str] = []
        else:
            selected_skill = FINDING_AUDIT_SKILL if FINDING_AUDIT_SKILL in available_by_ref else None
            knowledge_candidate = next(
                (
                    item
                    for item in ranked
                    if str(item.get("skill_ref") or "").strip() == FINDING_KNOWLEDGE_SKILL
                    and self._should_offer_knowledge_skill(item)
                ),
                None,
            )
            secondary_refs = [FINDING_KNOWLEDGE_SKILL] if knowledge_candidate is not None else []
            if selected_skill is None:
                selected_skill = str(discovery_snapshot.get("selected_skill") or "").strip() or None
                if selected_skill == FINDING_REPORT_SKILL:
                    selected_skill = None

        ranked_refs = [
            str(item.get("skill_ref") or "").strip()
            for item in ranked
            if str(item.get("skill_ref") or "").strip()
        ]
        deferred_refs = [
            ref
            for ref in available_by_ref.keys()
            if ref not in ([selected_skill] if selected_skill else []) and ref not in secondary_refs
        ]
        if selected_skill:
            route_plan["primary_skill"] = selected_skill
            skill_file_path = ((available_by_ref.get(selected_skill) or {}).get("paths") or {}).get("skill_file_path")
            route_plan["startup_reads"] = [skill_file_path] if skill_file_path else route_plan.get("startup_reads", [])
        else:
            route_plan["primary_skill"] = None
            route_plan["startup_reads"] = []
        route_plan["secondary_skills"] = secondary_refs
        route_plan["deferred_skills"] = deferred_refs
        route_plan["discovery_ranked_skills"] = ranked_refs
        route_plan["discovery_selected_skill"] = selected_skill
        route_plan["skill_phase"] = "report_finalization" if report_generation_mode else "audit"
        route_plan["selection_reason"] = list(route_plan.get("selection_reason") or []) + self._phase_selection_reason(
            report_generation_mode=report_generation_mode,
            knowledge_enabled=FINDING_KNOWLEDGE_SKILL in secondary_refs,
        )
        skill_context.route_plan = route_plan
        discovery_message = self._build_discovery_message(ranked, selected_skill)
        if discovery_message:
            base_route_message = str(skill_context.route_message or "").strip()
            skill_context.route_message = "\n\n".join(part for part in [base_route_message, discovery_message] if part)

    @staticmethod
    def _should_offer_knowledge_skill(candidate: dict[str, Any]) -> bool:
        reasons = {str(item) for item in candidate.get("trigger_reasons") or []}
        score = int(candidate.get("score") or 0)
        return score >= 12 and bool(reasons.intersection({"direct_user_mention", "ai_context_alignment", "path_overlap"}))

    @staticmethod
    def _filter_explicit_mentions_for_phase(
        mentions,
        *,
        report_generation_mode: bool,
        discovery_snapshot: dict[str, object],
    ):
        if report_generation_mode:
            return [mention for mention in mentions if mention.skill_ref == FINDING_REPORT_SKILL]

        knowledge_enabled = any(
            str(item.get("skill_ref") or "").strip() == FINDING_KNOWLEDGE_SKILL
            and FindingRuntimeAdapter._should_offer_knowledge_skill(item)
            for item in (discovery_snapshot.get("ranked_candidates") or [])
        )
        filtered = []
        for mention in mentions:
            if mention.skill_ref == FINDING_AUDIT_SKILL:
                filtered.append(mention)
                continue
            if mention.skill_ref == FINDING_KNOWLEDGE_SKILL and (
                mention.source == "user" or knowledge_enabled
            ):
                filtered.append(mention)
        return filtered

    @staticmethod
    def _phase_selection_reason(*, report_generation_mode: bool, knowledge_enabled: bool) -> list[str]:
        if report_generation_mode:
            return ["Finding report phase selects cve-report-writer and suppresses discovery skills."]
        reasons = ["Finding audit phase keeps code-audit-finding as the primary source-review skill."]
        if knowledge_enabled:
            reasons.append("secknowledge-skill is available as targeted knowledge support for the current candidate.")
        else:
            reasons.append("secknowledge-skill remains deferred until a concrete candidate needs knowledge support.")
        reasons.append("cve-report-writer remains deferred until report finalization.")
        return reasons

    @staticmethod
    def _skill_ref(item: dict) -> str:
        return str(item.get("slug") or item.get("id") or item.get("name") or "").strip()

    def _persist_runtime_metadata(
        self,
        *,
        session_id: str,
        base_system_prompt: str,
        user_message: str,
        skill_context,
        discovery_snapshot: dict[str, object],
    ) -> None:
        runtime_state = self._session_store.load_runtime_state(session_id)
        runtime_state.metadata["base_system_prompt"] = base_system_prompt
        runtime_state.metadata["last_user_message"] = user_message
        runtime_state.record_skill_catalog_snapshot(
            agent_type="finding",
            available_skills=self._skill_refs(skill_context.available_skills),
            matched_skills=self._skill_refs(skill_context.matched_skills),
            primary_skill=str(skill_context.route_plan.get("primary_skill") or "").strip() or None,
        )
        runtime_state.record_skill_discovery_snapshot(
            agent_type="finding",
            selected_skill=str(discovery_snapshot.get("selected_skill") or "").strip() or None,
            ranked_candidates=list(discovery_snapshot.get("ranked_candidates") or []),
            latest_user_message=user_message,
        )
        self._session_store.replace_runtime_state(session_id, runtime_state)

    @staticmethod
    def _skill_refs(items: list[dict]) -> list[str]:
        refs: list[str] = []
        for item in items or []:
            ref = str(item.get("slug") or item.get("id") or item.get("name") or "").strip()
            if ref and ref not in refs:
                refs.append(ref)
        return refs

    @classmethod
    def _matched_skill_refs(cls, items: list[dict]) -> set[str]:
        return set(cls._skill_refs(items))

    def _resolve_latest_user_message(self, messages: list, fallback: str | None) -> str:
        for message in reversed(messages or []):
            if getattr(message, "role", None) == RuntimeMessageRole.USER.value:
                content = str(getattr(message, "content", "") or "").strip()
                if content:
                    return content
        resolved_fallback = str(fallback or "").strip()
        return resolved_fallback or self.DEFAULT_USER_MESSAGE

    @staticmethod
    def _compose_system_prompt(*, base_system_prompt: str, skill_context, explicit_skill_injection_text: str, memories: list) -> str:
        prompt_sections = [build_runtime_memory_prompt(str(base_system_prompt or "").strip(), [])]
        if skill_context.prompt.strip():
            prompt_sections.append(skill_context.prompt.strip())
        if skill_context.route_message.strip():
            prompt_sections.append(skill_context.route_message.strip())
        if explicit_skill_injection_text.strip():
            prompt_sections.append(explicit_skill_injection_text.strip())
        prompt_without_memories = "\n\n".join(section for section in prompt_sections if section)
        return build_runtime_memory_prompt(prompt_without_memories, memories)

    @staticmethod
    def _selection_reason_lines(ranked: list[dict]) -> list[str]:
        if not ranked:
            return []
        top = ranked[0]
        reasons = ", ".join(str(item) for item in top.get("trigger_reasons") or []) or "heuristic score"
        return [f"Discovery scheduler selected {top.get('skill_ref')} using: {reasons}."]

    @staticmethod
    def _build_discovery_message(ranked: list[dict], selected_skill: str | None) -> str:
        if not ranked:
            return ""
        top_lines = []
        for item in ranked[:3]:
            top_lines.append(
                f"- {item.get('skill_ref')}: score={item.get('score')}, stage={item.get('suggested_stage')}, reasons={', '.join(item.get('trigger_reasons') or []) or 'none'}"
            )
        header = f"Phase-aware skill selection: {selected_skill}" if selected_skill else "Phase-aware skill selection found no active primary skill."
        return "\n".join([header, "Top discovery candidates (advisory only):", *top_lines])

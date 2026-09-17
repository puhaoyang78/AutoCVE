from __future__ import annotations

import json
import time
from typing import Any, Dict

from .base import AgentConfig, AgentPattern, AgentResult, AgentType, BaseAgent
from .finding_skill_protocol import build_finding_skill_protocol
from app.services.finding_runtime.bridge import FindingRuntimeBridge
from app.services.finding_runtime.models import RuntimeCompletionMode


FINDING_SYSTEM_PROMPT = """你是 AutoCVE 的 Finding Agent，负责基于项目源码发现真实、可复现的高价值安全漏洞。

工作原则：
1. 不预设项目一定存在漏洞，允许最终 findings 为空。
2. 从 Recon 给出的入口点和高风险路径开始，优先阅读真实源码，再扩展调用关系和数据流。
3. 每个候选都同时检查攻击链和阻断条件，包括认证、授权、输入校验、sanitizer、边界检查、allowlist、配置和可达性。
4. 只报告 source 到 sink 链路可以明确闭合、影响清楚且达到 high/critical 的问题。
5. 静态链路成立但尚未动态确认时使用 candidate；不得把尚未验证的判断写成 confirmed。
6. confirmed 必须有完整 finding_flow，并至少包含一条成功的动态 verification record。
7. C/C++ 内存安全候选在能够构造忠实局部 harness 时使用 VerifyCppMemory；无法可靠复现时保持 candidate。
8. 对已经检查过的候选使用 TodoWrite 的 candidate_decision 持久化结论，恢复任务时先读取已有决策，避免重复审计。
9. 不以漏洞数量、严重度积分、历史案例或模型置信度替代项目自身源码事实。
10. 只有主要攻击面已经覆盖、候选已分类并且结果可以最终提交时，才调用 FinalizeFinding。

最终结果由 FinalizeFinding 提交。每个 finding 必须包含 source、sink、exploit_chain、PoC、impact、cve_justification、verification_notes；confirmed 还必须包含 finding_flow 和 verification_records。被有效安全控制明确阻断的候选放入 rejected_candidates，并提供 blocking_controls。
"""


class FindingAgent(BaseAgent):
    """Single-path Finding agent backed exclusively by the persistent runtime."""

    def __init__(self, llm_service, tools: Dict[str, Any], event_emitter=None):
        system_prompt = f"{FINDING_SYSTEM_PROMPT}\n\n{build_finding_skill_protocol()}"
        config = AgentConfig(
            name="Finding",
            agent_type=AgentType.FINDING,
            pattern=AgentPattern.REACT,
            max_iterations=50,
            system_prompt=system_prompt,
        )
        super().__init__(config, llm_service, tools, event_emitter)
        self._runtime_bridge_factory = None

    def _build_runtime_bridge(self, user_id: str | None) -> FindingRuntimeBridge:
        if callable(self._runtime_bridge_factory):
            return self._runtime_bridge_factory(user_id)
        return FindingRuntimeBridge(
            llm_service=self.llm_service,
            tools=self.tools,
            user_id=user_id,
        )

    @staticmethod
    def _extract_recon_data(input_data: Dict[str, Any]) -> Dict[str, Any]:
        previous_results = input_data.get("previous_results", {}) or {}
        recon_data = previous_results.get("recon", {})
        if isinstance(recon_data, dict) and isinstance(recon_data.get("data"), dict):
            recon_data = recon_data["data"]
        return recon_data if isinstance(recon_data, dict) else {}

    @staticmethod
    def _resolve_max_turns(input_data: Dict[str, Any]) -> int:
        config = input_data.get("config", {}) or {}
        for raw_value in (config.get("max_iterations"), input_data.get("max_iterations"), 50):
            try:
                value = int(raw_value)
            except (TypeError, ValueError):
                continue
            if value > 0:
                return value
        return 50

    @staticmethod
    def _completion_mode(bridge_result: Dict[str, Any], payload: Dict[str, Any]) -> RuntimeCompletionMode | None:
        runner_result = bridge_result.get("runner_result")
        candidates = [
            getattr(runner_result, "completion_mode", None),
            runner_result.get("completion_mode") if isinstance(runner_result, dict) else None,
            payload.get("runtime_completion_mode"),
            payload.get("completion_mode"),
        ]
        for raw_value in candidates:
            if raw_value is None:
                continue
            if isinstance(raw_value, RuntimeCompletionMode):
                return raw_value
            try:
                return RuntimeCompletionMode(str(raw_value))
            except ValueError:
                continue
        return None

    @staticmethod
    def _build_user_message(input_data: Dict[str, Any], recon_data: Dict[str, Any]) -> str:
        project_info = input_data.get("project_info", {}) or {}
        config = input_data.get("config", {}) or {}
        task_text = str(input_data.get("task_context") or input_data.get("task") or "").strip()
        target_files = config.get("target_files") or []
        focus = config.get("focus_vulnerabilities") or config.get("target_vulnerabilities") or []
        compact_recon = {
            "project_profile": recon_data.get("project_profile", {}),
            "entry_points": recon_data.get("entry_points", []),
            "priority_paths": recon_data.get("priority_paths", []),
            "audit_targets": recon_data.get("audit_targets", {}),
            "summary": recon_data.get("summary", ""),
        }
        return "\n".join(
            [
                "请开始 Finding 阶段源码审计。",
                f"项目：{project_info.get('name') or 'unknown'}",
                f"项目根目录：{project_info.get('root') or project_info.get('workspace_root') or '.'}",
                f"任务上下文：{task_text or '无额外说明'}",
                f"指定目标文件：{json.dumps(target_files, ensure_ascii=False)}",
                f"关注漏洞类型：{json.dumps(focus, ensure_ascii=False)}",
                "Recon 导航数据：",
                json.dumps(compact_recon, ensure_ascii=False, indent=2),
                "请先检查高价值入口和路径，持续调用工具直到主要攻击面已覆盖；完成后调用 FinalizeFinding。",
            ]
        )

    def _build_event_sink(self):
        if self.event_emitter is None:
            return None

        async def event_sink(event: Dict[str, Any]) -> None:
            event_type = str(event.get("type") or "activity")
            message = str(event.get("message") or event.get("content") or event_type)
            await self.emit_event(
                f"runtime_{event_type}",
                message[:500],
                metadata={"runtime_event": {key: value for key, value in event.items() if key != "content"}},
            )

        return event_sink

    async def run(self, input_data: Dict[str, Any]) -> AgentResult:
        started_at = time.time()
        project_info = input_data.get("project_info", {}) or {}
        config = input_data.get("config", {}) or {}
        recon_data = self._extract_recon_data(input_data)
        project_id = str(
            input_data.get("project_id")
            or project_info.get("project_id")
            or project_info.get("id")
            or "runtime-project"
        )
        task_id = str(input_data.get("task_id") or "").strip() or None
        user_id = str(config.get("user_id") or "").strip() or None

        await self.emit_agent_start_debug(
            {
                "task_id": task_id,
                "project_id": project_id,
                "project_info": project_info,
                "recon_summary": recon_data.get("summary", ""),
            }
        )
        await self.emit_thinking("Starting Finding runtime...")

        try:
            bridge = self._build_runtime_bridge(user_id)
            bridge_result = await bridge.run(
                project_id=project_id,
                task_id=task_id,
                system_prompt=self.config.system_prompt or FINDING_SYSTEM_PROMPT,
                recon_payload=recon_data,
                user_message=self._build_user_message(input_data, recon_data),
                model_name=self.agent_type.value,
                max_turns=self._resolve_max_turns(input_data),
                event_sink=self._build_event_sink(),
            )
            payload = bridge_result.get("final_payload")
            if not isinstance(payload, dict):
                payload = {
                    "findings": [],
                    "rejected_candidates": [],
                    "summary": "Finding runtime ended without a final structured result.",
                }

            completion_mode = self._completion_mode(bridge_result, payload)
            payload["runtime_session_id"] = bridge_result.get("session_id")
            if completion_mode is not None:
                payload["runtime_completion_mode"] = completion_mode.value

            incomplete = completion_mode in {
                RuntimeCompletionMode.INCOMPLETE,
                RuntimeCompletionMode.FALLBACK_RECOVERED,
            }
            summary = str(payload.get("summary") or "Finding runtime complete")
            await self.emit_llm_complete(summary, 0)
            return AgentResult(
                success=not incomplete,
                data=payload,
                error=summary if incomplete else None,
                iterations=int(bridge_result.get("turn_count") or 0),
                tool_calls=int(bridge_result.get("tool_call_count") or 0),
                tokens_used=0,
                duration_ms=int((time.time() - started_at) * 1000),
                metadata={
                    "runtime_session_id": bridge_result.get("session_id"),
                    **({"runtime_completion_mode": completion_mode.value} if completion_mode is not None else {}),
                },
                handoff=None,
            )
        except Exception as exc:
            await self.emit_event("error", f"Finding runtime failed: {exc}")
            return AgentResult(
                success=False,
                data={
                    "findings": [],
                    "rejected_candidates": [],
                    "summary": "Finding runtime failed before finalization.",
                },
                error=str(exc),
                duration_ms=int((time.time() - started_at) * 1000),
                handoff=None,
            )

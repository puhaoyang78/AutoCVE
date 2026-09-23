from __future__ import annotations

from typing import Any

from pydantic import ValidationError

from app.services.finding_runtime.final_finding_contract import (
    FinalizedFindingPayload,
    format_validation_errors,
)
from app.services.finding_runtime.fingerprint import build_payload_fingerprint
from app.services.finding_runtime.models import ToolExecutionPayload
from app.services.runtime_core.tool_runtime import RuntimeTool, ToolExecutionContext


class InvalidFinalizeFindingInput:
    def __init__(self, raw_input: dict[str, Any], validation_error: ValidationError):
        self.raw_input = dict(raw_input or {})
        self.validation_error = validation_error


class FinalizeFindingTool(RuntimeTool):
    name = "FinalizeFinding"
    description = (
        "提交 Finding 阶段的最终结构化审计结论。这是终点工具，不是记录中间发现的工具。\n\n"
        "一旦 FinalizeFinding 调用成功，Finding 阶段会立即终止。因此只有在主要攻击面已经检查完、"
        "候选已经分类并且最终结果可以提交时才调用。\n\n"
        "提交结构：\n"
        "- findings：最终可报告漏洞。\n"
        "- rejected_candidates：已被有效安全控制或不可达条件明确阻断的候选。\n"
        "- summary：覆盖范围、限制和最终结论。\n\n"
        "每个 finding 必须包含 source、sink、exploit_chain、PoC、impact、cve_justification 和 verification_notes。"
        "建议同时提交 finding_flow，描述 source、传播/转换、guard/sanitizer、sink 及其关系。\n\n"
        "Finding Flow 规则：\n"
        "- 至少包含 source 和 sink，并存在 source→sink 的有向路径。\n"
        "- controls 用于记录 authentication、authorization、validation、sanitizer、bounds_check、allowlist、"
        "reachability、configuration 等保护机制。\n"
        "- control.status 只能是 absent、bypassable、effective、unknown。\n"
        "- effective 控制会阻断候选，该候选必须进入 rejected_candidates。\n\n"
        "验证状态规则：\n"
        "- candidate：静态链路成立但仍需验证，必须 needs_verification=true。\n"
        "- confirmed：必须 needs_verification=false，必须提供 finding_flow，不能保留 unknown 控制，"
        "并至少包含一条 dynamic=true、success=true 的 verification_records。\n"
        "- C/C++ 内存安全候选优先使用 VerifyCppMemory，通过 ASan/UBSan 沙箱结果确认。"
        "无法安全复现时保持 candidate，不得仅凭模型判断标记 confirmed。\n\n"
        "Rejected Candidate 规则：\n"
        "- 每项必须包含 reason 和 blocking_controls。\n"
        "- blocking_controls 至少包含一个 status=effective 的直接阻断控制。\n"
        "- 尚未验证、暂时不确定或低置信度不等于 rejected。\n\n"
        "如果还需要读取文件、追踪调用链、检查保护条件或动态验证，不要调用 FinalizeFinding，继续审计。"
        "审计完成且没有可报告漏洞时，可以提交 findings=[]。"
    )
    input_model = FinalizedFindingPayload
    always_load = True

    def validate_input(self, raw_input: dict[str, Any]) -> FinalizedFindingPayload | InvalidFinalizeFindingInput:
        try:
            return FinalizedFindingPayload.model_validate(raw_input or {})
        except ValidationError as exc:
            return InvalidFinalizeFindingInput(raw_input or {}, exc)

    def is_concurrency_safe(self, parsed_input: Any = None) -> bool:
        del parsed_input
        return False

    async def execute(
        self,
        parsed_input: FinalizedFindingPayload | InvalidFinalizeFindingInput,
        context: ToolExecutionContext,
    ) -> ToolExecutionPayload:
        del context
        if isinstance(parsed_input, InvalidFinalizeFindingInput):
            validation_errors = format_validation_errors(parsed_input.validation_error)
            return ToolExecutionPayload(
                content=(
                    "FinalizeFinding 已拒绝本次提交，尚未形成最终结果。请按以下具体校验错误修正参数后再次提交。"
                    "字段缺失或多余是提交格式错误，不代表必须重新审计或执行动态验证。"
                    "只使用已有证据，保持真实验证状态，不得补造内容。\n"
                    + "\n".join(error["message"] for error in validation_errors[1:] or validation_errors)
                ),
                output_payload={
                    "finalization_rejected": True,
                    "validation_errors": validation_errors,
                    "required_finding_fields": [
                        "vulnerability_type",
                        "severity",
                        "title",
                        "description",
                        "file_path",
                        "line_start",
                        "line_end",
                        "code_snippet",
                        "source",
                        "sink",
                        "suggestion",
                        "confidence",
                        "needs_verification",
                        "verdict",
                        "exploit_chain",
                        "poc",
                        "impact",
                        "cve_justification",
                        "verification_notes",
                    ],
                    "confirmed_requires": [
                        "finding_flow",
                        "no_unknown_or_effective_controls",
                        "successful_dynamic_verification_record",
                    ],
                },
                metadata={"finalization_rejected": True},
                is_error=True,
            )

        final_payload = parsed_input.model_dump(mode="json", exclude_none=True)
        for finding in final_payload.get("findings") or []:
            finding["fingerprint"] = build_payload_fingerprint(finding)
        return ToolExecutionPayload(
            content="Received final vulnerability findings.",
            output_payload={
                "final_payload": final_payload,
                "completion_mode": "finalize_tool",
                "terminal_action": "finalize_finding",
            },
            metadata={
                "finalize_finding": True,
                "findings_count": len(final_payload.get("findings") or []),
                "rejected_candidates_count": len(final_payload.get("rejected_candidates") or []),
            },
        )

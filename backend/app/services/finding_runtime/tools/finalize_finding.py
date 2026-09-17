from __future__ import annotations

from typing import Any

from pydantic import ValidationError

from app.services.finding_runtime.final_finding_contract import (
    FinalizedFindingPayload,
    format_validation_errors,
)
from app.services.finding_runtime.fingerprint import FINGERPRINT_VERSION, build_payload_fingerprint
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
        "重要：一旦 FinalizeFinding 调用成功，Finding 阶段会立即终止，后续不会继续搜索、验证或补充漏洞。"
        "因此，只有在已经完成充分审计并准备结束整个 Finding 阶段时，才允许调用本工具。\n\n"
        "不要在发现第一个漏洞后立即调用本工具。发现一个漏洞后，应继续搜索其他独立攻击面；"
        "同时对候选寻找正向证据和反证，而不是为了增加漏洞数量强行闭合利用链。\n\n"
        "提交结构：\n"
        "- findings：最终可报告漏洞。\n"
        "- rejected_candidates：已经被有效安全控制、不可达性或其它直接证据否定的候选。"
        "被否定的候选不要继续塞进 findings，也不要在后续轮次重复审计。\n"
        "- summary：已覆盖攻击面、剩余限制和最终结论。\n\n"
        "每个 finding 必须包含基础漏洞字段、source、sink、exploit_chain、PoC、impact、"
        "cve_justification 和 verification_notes。建议同时提交 evidence_graph，显式描述 source、传播节点、"
        "guard/sanitizer、sink 及其关系。\n\n"
        "Evidence Graph 规则：\n"
        "- graph 至少包含 source 和 sink，并存在 source→sink 的有向路径。\n"
        "- controls 中记录 authentication、authorization、validation、sanitizer、bounds_check、allowlist、"
        "reachability、configuration 等保护机制。\n"
        "- control.status 只能是 absent、bypassable、effective、unknown。\n"
        "- 如果存在 effective 阻断控制，该候选不能进入 findings，应转入 rejected_candidates。\n\n"
        "验证状态规则：\n"
        "- candidate：静态证据链可以闭合，但尚未获得足够动态证据；必须 needs_verification=true。\n"
        "- confirmed：必须 needs_verification=false，并提供 evidence_graph；不能保留 unknown 控制；"
        "还必须至少提供一条 dynamic=true、success=true 的 verification_evidence。\n"
        "- 对 C/C++ 内存安全候选，优先使用 ASan/UBSan 或等价沙箱复现证据；仅凭模型判断、历史案例或"
        "源码直觉不得标记 confirmed。\n\n"
        "Rejected Candidate 规则：\n"
        "- rejected_candidates 中每项必须包含 reason 和 blocking_evidence。\n"
        "- blocking_evidence 至少有一个 status=effective 的直接阻断证据，例如严格 allowlist、有效权限校验、"
        "可靠 bounds check、不可达分支或确定的配置约束。\n"
        "- 不要把‘暂时没看懂’、‘尚未验证’或低置信度当成 rejected；这类情况仍是未闭合候选。\n\n"
        "如果还需要继续读取文件、追踪调用链、检查 guard/sanitizer、验证 PoC 或补齐证据，"
        "不要调用 FinalizeFinding，继续使用 Read/Grep/Glob/Skill/Bash/PowerShell 等工具。\n"
        "审计完成且没有可报告漏洞时，可以提交 findings=[]；此时仍可以通过 rejected_candidates 记录已经"
        "被源码证据明确否定的高价值候选。"
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
                    "FinalizeFinding 已拒绝本次提交，因为最终审计结论不满足证据契约。"
                    "请继续调用工具补齐缺失证据、处理有效阻断控制或修正验证状态后再次提交。"
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
                        "evidence_graph",
                        "no_unknown_or_effective_controls",
                        "successful_dynamic_verification_evidence",
                    ],
                },
                metadata={"finalization_rejected": True},
                is_error=True,
            )

        final_payload = parsed_input.model_dump(mode="json", exclude_none=True)
        for finding in final_payload.get("findings") or []:
            finding["stable_fingerprint"] = build_payload_fingerprint(finding)
            finding["fingerprint_version"] = FINGERPRINT_VERSION
        return ToolExecutionPayload(
            content="Received final evidence-backed vulnerability findings.",
            output_payload={
                "final_payload": final_payload,
                "completion_mode": "finalize_tool",
                "terminal_action": "finalize_finding",
            },
            metadata={
                "finalize_finding": True,
                "findings_count": len(final_payload.get("findings") or []),
                "rejected_candidates_count": len(final_payload.get("rejected_candidates") or []),
                "fingerprint_version": FINGERPRINT_VERSION,
            },
        )

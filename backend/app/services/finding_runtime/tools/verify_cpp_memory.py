from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, Field

from app.services.agent.tools.run_code import RunCodeTool
from app.services.finding_runtime.models import ToolExecutionPayload
from app.services.runtime_core.tool_runtime import RuntimeTool, ToolExecutionContext

_SANITIZER_PATTERNS = {
    "asan": re.compile(r"AddressSanitizer|ERROR:\s*AddressSanitizer", re.IGNORECASE),
    "ubsan": re.compile(r"UndefinedBehaviorSanitizer|runtime error:", re.IGNORECASE),
}


class VerifyCppMemoryInput(BaseModel):
    code: str = Field(min_length=1, description="Standalone C/C++ harness that reproduces the concrete memory-safety candidate.")
    language: Literal["c", "cpp", "c++"] = Field(description="Harness language.")
    timeout: int = Field(default=60, ge=1, le=180, description="Sandbox execution timeout in seconds.")
    description: str = Field(default="", description="Short description of the candidate being verified.")


class VerifyCppMemoryTool(RuntimeTool):
    name = "VerifyCppMemory"
    description = (
        "Conditionally verify a concrete C/C++ memory-safety candidate with an isolated standalone harness. "
        "The harness is compiled with AddressSanitizer and UndefinedBehaviorSanitizer by the existing RunCode backend. "
        "Use this only after source review has identified a specific source/sink, lifetime, or bounds candidate and a local harness can faithfully reproduce it. "
        "A sanitizer diagnostic supports confirmation; a clean run does not by itself prove the production path safe."
    )
    input_model = VerifyCppMemoryInput
    search_hint = "verify C C++ memory corruption with ASan UBSan sanitizer harness"

    def __init__(self, *, project_root: str = ".", run_code_tool: RunCodeTool | None = None):
        self._run_code_tool = run_code_tool or RunCodeTool(project_root=project_root)

    def is_concurrency_safe(self, parsed_input: VerifyCppMemoryInput) -> bool:
        del parsed_input
        return False

    async def execute(self, parsed_input: VerifyCppMemoryInput, context: ToolExecutionContext) -> ToolExecutionPayload:
        del context
        result = await self._run_code_tool.execute(
            code=parsed_input.code,
            language=parsed_input.language,
            timeout=parsed_input.timeout,
            description=parsed_input.description,
        )
        metadata = dict(result.metadata or {})
        rendered = str(result.data or "")
        sanitizer_types = [name for name, pattern in _SANITIZER_PATTERNS.items() if pattern.search(rendered)]
        sanitizer_detected = bool(sanitizer_types)
        infrastructure_ok = bool(result.success)
        success = infrastructure_ok and sanitizer_detected
        method = "+".join(sanitizer_types) if sanitizer_types else "asan+ubsan"
        summary = (
            f"Dynamic sanitizer failure detected ({method})."
            if success
            else "Harness executed without a recognized ASan/UBSan diagnostic."
            if infrastructure_ok
            else f"Dynamic verification could not run: {result.error or 'sandbox execution failed'}"
        )

        return ToolExecutionPayload(
            content="\n".join(
                [
                    summary,
                    rendered,
                    "Use success=true to create a successful verification record for a confirmed memory-safety finding. "
                    "If success=false, keep the result as candidate unless another direct dynamic result confirms it.",
                ]
            ).strip(),
            output_payload={
                "dynamic": True,
                "success": success,
                "method": method,
                "tool": self.name,
                "summary": summary,
                "details": rendered,
                "sanitizer_detected": sanitizer_detected,
                "sanitizers": sanitizer_types,
                "exit_code": metadata.get("exit_code"),
                "infrastructure_ok": infrastructure_ok,
            },
            metadata={
                "verification": "cpp_memory_sanitizer",
                "success": success,
                "sanitizers": sanitizer_types,
                **metadata,
            },
            is_error=not infrastructure_ok,
        )

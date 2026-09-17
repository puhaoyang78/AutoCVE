from __future__ import annotations

from enum import StrEnum


class FindingRuntimeStack(StrEnum):
    RUNTIME = "runtime"


def coerce_finding_runtime_stack(value: str | None) -> FindingRuntimeStack:
    del value
    return FindingRuntimeStack.RUNTIME

"""Persistent Finding runtime."""

from .models import RuntimeMessageRole, RuntimeSessionState, RuntimeStopReason, TranscriptItem

__all__ = [
    "FindingRuntimeBridge",
    "RuntimeMessageRole",
    "RuntimeSessionState",
    "RuntimeStopReason",
    "TranscriptItem",
]


def __getattr__(name: str):
    if name == "FindingRuntimeBridge":
        from .bridge import FindingRuntimeBridge

        return FindingRuntimeBridge
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator


def _clean_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _has_text(value: Any) -> bool:
    return bool(_clean_text(value))


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ExploitChainStep(_StrictModel):
    step: int = Field(ge=1)
    location: str = Field(min_length=1)
    description: str = Field(min_length=1)
    data_state: str = ""
    bypass_reason: str = ""

    @field_validator("location", "description", "data_state", "bypass_reason", mode="before")
    @classmethod
    def _strip_text_fields(cls, value: Any) -> str:
        return _clean_text(value)


class EvidenceNode(_StrictModel):
    id: str = Field(min_length=1)
    kind: Literal[
        "entry_point",
        "source",
        "propagation",
        "transform",
        "guard",
        "sanitizer",
        "sink",
        "impact",
    ]
    location: str = Field(min_length=1)
    description: str = Field(min_length=1)
    data_state: str = ""

    @field_validator("id", "location", "description", "data_state", mode="before")
    @classmethod
    def _strip_text_fields(cls, value: Any) -> str:
        return _clean_text(value)


class EvidenceEdge(_StrictModel):
    source_id: str = Field(min_length=1)
    target_id: str = Field(min_length=1)
    relation: str = Field(min_length=1)

    @field_validator("source_id", "target_id", "relation", mode="before")
    @classmethod
    def _strip_text_fields(cls, value: Any) -> str:
        return _clean_text(value)


class EvidenceControl(_StrictModel):
    kind: Literal[
        "authentication",
        "authorization",
        "validation",
        "sanitizer",
        "bounds_check",
        "type_check",
        "allowlist",
        "configuration",
        "reachability",
        "lifetime",
        "other",
    ]
    status: Literal["absent", "bypassable", "effective", "unknown"]
    location: str = Field(min_length=1)
    description: str = Field(min_length=1)
    bypass_reason: str = ""

    @field_validator("location", "description", "bypass_reason", mode="before")
    @classmethod
    def _strip_text_fields(cls, value: Any) -> str:
        return _clean_text(value)


class EvidenceGraph(_StrictModel):
    nodes: list[EvidenceNode] = Field(min_length=2)
    edges: list[EvidenceEdge] = Field(min_length=1)
    controls: list[EvidenceControl] = Field(default_factory=list)

    @model_validator(mode="after")
    def _validate_source_to_sink_path(self):
        node_ids = [node.id for node in self.nodes]
        if len(node_ids) != len(set(node_ids)):
            raise ValueError("evidence_graph node ids must be unique")

        known_ids = set(node_ids)
        for edge in self.edges:
            if edge.source_id not in known_ids or edge.target_id not in known_ids:
                raise ValueError("evidence_graph edges must reference existing node ids")

        source_ids = {node.id for node in self.nodes if node.kind == "source"}
        sink_ids = {node.id for node in self.nodes if node.kind == "sink"}
        if not source_ids:
            raise ValueError("evidence_graph must contain at least one source node")
        if not sink_ids:
            raise ValueError("evidence_graph must contain at least one sink node")

        adjacency: dict[str, set[str]] = {}
        for edge in self.edges:
            adjacency.setdefault(edge.source_id, set()).add(edge.target_id)

        pending = list(source_ids)
        visited = set(source_ids)
        while pending:
            current = pending.pop()
            if current in sink_ids:
                return self
            for target in adjacency.get(current, set()):
                if target not in visited:
                    visited.add(target)
                    pending.append(target)
        raise ValueError("evidence_graph must contain a directed path from source to sink")


class VerificationEvidence(_StrictModel):
    method: Literal[
        "static_review",
        "asan",
        "ubsan",
        "sandbox_poc",
        "integration_test",
        "runtime_trace",
        "external_reproduction",
        "other",
    ]
    dynamic: bool = False
    success: bool
    tool: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    evidence: str = Field(min_length=1)

    @field_validator("tool", "summary", "evidence", mode="before")
    @classmethod
    def _strip_text_fields(cls, value: Any) -> str:
        return _clean_text(value)


class RejectedCandidate(_StrictModel):
    candidate_id: str = ""
    vulnerability_type: str = Field(min_length=1)
    title: str = Field(min_length=1)
    file_path: str = ""
    reason: str = Field(min_length=1)
    blocking_evidence: list[EvidenceControl] = Field(min_length=1)
    confidence: float = Field(ge=0.0, le=1.0)

    @field_validator("candidate_id", "vulnerability_type", "title", "file_path", "reason", mode="before")
    @classmethod
    def _strip_text_fields(cls, value: Any) -> str:
        return _clean_text(value)

    @model_validator(mode="after")
    def _must_have_effective_block(self):
        if not any(item.status == "effective" for item in self.blocking_evidence):
            raise ValueError("rejected candidates must include at least one effective blocking control")
        return self


class PocStep(_StrictModel):
    step: int = Field(ge=1)
    action: str = Field(min_length=1)
    request: str = ""
    expected_response: str = ""

    @field_validator("action", "request", "expected_response", mode="before")
    @classmethod
    def _strip_text_fields(cls, value: Any) -> str:
        return _clean_text(value)


class PocPayload(_StrictModel):
    description: str = Field(min_length=1)
    preconditions: list[str] = Field(default_factory=list)
    steps: list[PocStep] = Field(min_length=1)
    payload: str = ""
    impact: str = Field(min_length=1)
    cve_justification: str = Field(min_length=1)

    @field_validator("description", "payload", "impact", "cve_justification", mode="before")
    @classmethod
    def _strip_text_fields(cls, value: Any) -> str:
        return _clean_text(value)

    @field_validator("preconditions", mode="before")
    @classmethod
    def _strip_preconditions(cls, value: Any) -> list[str]:
        if not isinstance(value, list):
            return []
        return [_clean_text(item) for item in value if _has_text(item)]


class FinalizedFinding(_StrictModel):
    vulnerability_type: str = Field(min_length=1)
    severity: Literal["critical", "high"]
    title: str = Field(min_length=1)
    description: str = Field(min_length=1)
    file_path: str = Field(min_length=1)
    line_start: int = Field(ge=1)
    line_end: int = Field(ge=1)
    code_snippet: str = Field(min_length=1)
    source: str = Field(min_length=1)
    sink: str = Field(min_length=1)
    suggestion: str = Field(min_length=1)
    confidence: float = Field(ge=0.0, le=1.0)
    needs_verification: bool
    verdict: Literal["candidate", "confirmed"]
    exploit_chain: list[ExploitChainStep] = Field(min_length=1)
    evidence_graph: EvidenceGraph | None = None
    verification_evidence: list[VerificationEvidence] = Field(default_factory=list)
    poc: PocPayload
    impact: str = Field(min_length=1)
    cve_justification: str = Field(min_length=1)
    verification_notes: str = Field(min_length=1)

    @field_validator(
        "vulnerability_type",
        "title",
        "description",
        "file_path",
        "code_snippet",
        "source",
        "sink",
        "suggestion",
        "impact",
        "cve_justification",
        "verification_notes",
        mode="before",
    )
    @classmethod
    def _strip_required_text(cls, value: Any) -> str:
        return _clean_text(value)

    @field_validator("severity", "verdict", mode="before")
    @classmethod
    def _normalize_lowercase(cls, value: Any) -> str:
        return _clean_text(value).lower()

    @field_validator("line_end")
    @classmethod
    def _line_end_must_not_precede_start(cls, value: int, info) -> int:
        line_start = info.data.get("line_start")
        if isinstance(line_start, int) and value < line_start:
            raise ValueError("line_end must be greater than or equal to line_start")
        return value

    @model_validator(mode="after")
    def _verification_state_must_be_consistent(self):
        if self.verdict == "confirmed" and self.needs_verification:
            raise ValueError("confirmed findings cannot still require verification")
        if self.verdict == "candidate" and not self.needs_verification:
            raise ValueError("candidate findings must remain marked as needing verification")

        if self.evidence_graph is not None:
            effective_controls = [
                control
                for control in self.evidence_graph.controls
                if control.status == "effective"
            ]
            if effective_controls:
                raise ValueError(
                    "reportable findings cannot contain an effective blocking control; "
                    "move the candidate to rejected_candidates"
                )

        if self.verdict == "confirmed":
            if self.evidence_graph is None:
                raise ValueError("confirmed findings require an evidence_graph")
            unresolved_controls = [
                control
                for control in self.evidence_graph.controls
                if control.status == "unknown"
            ]
            if unresolved_controls:
                raise ValueError("confirmed findings cannot retain unknown security controls")
            if not any(item.dynamic and item.success for item in self.verification_evidence):
                raise ValueError("confirmed findings require successful dynamic verification evidence")
        return self


class FinalizedFindingPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    findings: list[FinalizedFinding] = Field(default_factory=list)
    rejected_candidates: list[RejectedCandidate] = Field(default_factory=list)
    summary: str = Field(min_length=1)
    completion_note: str | None = None
    needs_handoff: bool | None = None

    @field_validator("summary", "completion_note", mode="before")
    @classmethod
    def _strip_optional_text(cls, value: Any) -> str | None:
        if value is None:
            return None
        return _clean_text(value)


def has_meaningful_poc(poc: Any) -> bool:
    if not isinstance(poc, dict):
        return False
    if _has_text(poc.get("description")) or _has_text(poc.get("payload")):
        return True
    preconditions = poc.get("preconditions")
    if isinstance(preconditions, list) and any(_has_text(item) for item in preconditions):
        return True
    steps = poc.get("steps")
    if isinstance(steps, list):
        for step in steps:
            if not isinstance(step, dict):
                continue
            if any(_has_text(step.get(key)) for key in ("action", "request", "expected_response")):
                return True
    return False


def filter_meaningful_exploit_chain(exploit_chain: Any) -> list[dict[str, Any]]:
    if not isinstance(exploit_chain, list):
        return []
    filtered: list[dict[str, Any]] = []
    for step in exploit_chain:
        if not isinstance(step, dict):
            continue
        if _has_text(step.get("location")) or _has_text(step.get("description")):
            filtered.append(step)
    return filtered


def has_meaningful_exploit_chain(exploit_chain: Any) -> bool:
    return bool(filter_meaningful_exploit_chain(exploit_chain))


def is_placeholder_finding(finding: Any) -> bool:
    if not isinstance(finding, dict):
        return False
    if set(finding.keys()) <= {"reason", "summary", "notes", "note"}:
        return True
    title = _clean_text(finding.get("title")).lower()
    return (
        title in {"unknown finding", "other vulnerability", "vulnerability"}
        and not _has_text(finding.get("description"))
        and not _has_text(finding.get("file_path"))
        and not _has_text(finding.get("source"))
        and not _has_text(finding.get("sink"))
    )


def format_validation_errors(exc: ValidationError) -> list[dict[str, str]]:
    details: list[dict[str, str]] = []
    messages: list[str] = []
    for error in exc.errors():
        field = ".".join(str(part) for part in error.get("loc", ())) or "payload"
        message = f"{field}: {error.get('msg', 'invalid value')}"
        details.append({"field": field, "message": message})
        messages.append(message)
    if not details:
        return [{"field": "payload", "message": "FinalizeFinding payload is invalid."}]
    return [
        {
            "field": "payload",
            "message": "FinalizeFinding payload is invalid: " + "; ".join(messages),
        },
        *details,
    ]

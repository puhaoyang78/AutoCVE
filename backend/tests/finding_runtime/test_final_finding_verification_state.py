from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.services.finding_runtime.final_finding_contract import FinalizedFinding, FinalizedFindingPayload


def finding_flow(*, control_status: str = "absent") -> dict:
    return {
        "nodes": [
            {
                "id": "source",
                "kind": "source",
                "location": "src/download.py:10",
                "description": "HTTP path parameter",
                "data_state": "attacker controlled",
            },
            {
                "id": "sink",
                "kind": "sink",
                "location": "src/download.py:12",
                "description": "filesystem open",
                "data_state": "unsanitized path",
            },
        ],
        "edges": [{"source_id": "source", "target_id": "sink", "relation": "flows_to"}],
        "controls": [
            {
                "kind": "validation",
                "status": control_status,
                "location": "src/download.py:11",
                "description": "Path validation reviewed.",
                "bypass_reason": "Validation is absent." if control_status == "absent" else "",
            }
        ],
    }


def finding_payload(*, verdict: str, needs_verification: bool) -> dict:
    return {
        "vulnerability_type": "path_traversal",
        "severity": "high",
        "title": "Path traversal in download endpoint",
        "description": "Attacker-controlled path reaches a filesystem read without sufficient containment.",
        "file_path": "src/download.py",
        "line_start": 10,
        "line_end": 12,
        "code_snippet": "open(base / user_path).read()",
        "source": "HTTP path parameter",
        "sink": "filesystem open",
        "suggestion": "Resolve and enforce containment under the intended base directory.",
        "confidence": 0.9,
        "needs_verification": needs_verification,
        "verdict": verdict,
        "exploit_chain": [
            {
                "step": 1,
                "location": "src/download.py:10-12",
                "description": "User path reaches filesystem open.",
                "data_state": "attacker controlled",
                "bypass_reason": "No containment check",
            }
        ],
        "poc": {
            "description": "Request a parent-directory path.",
            "preconditions": ["Endpoint is reachable"],
            "steps": [{"step": 1, "action": "Send traversal path", "request": "../secret", "expected_response": "File content"}],
            "payload": "../secret",
            "impact": "Read files outside the intended directory.",
            "cve_justification": "Externally reachable path traversal crosses a filesystem trust boundary.",
        },
        "impact": "Read files outside the intended directory.",
        "cve_justification": "Externally reachable path traversal crosses a filesystem trust boundary.",
        "verification_notes": "Static source-to-sink chain reviewed; dynamic reproduction status recorded separately.",
    }


def test_candidate_must_still_need_verification():
    with pytest.raises(ValidationError):
        FinalizedFinding.model_validate(finding_payload(verdict="candidate", needs_verification=False))


def test_confirmed_must_not_still_need_verification():
    payload = finding_payload(verdict="confirmed", needs_verification=True)
    payload["finding_flow"] = finding_flow()
    with pytest.raises(ValidationError):
        FinalizedFinding.model_validate(payload)


def test_candidate_can_remain_static():
    candidate = FinalizedFinding.model_validate(finding_payload(verdict="candidate", needs_verification=True))
    assert candidate.verdict == "candidate"
    assert candidate.finding_flow is None


def test_confirmed_requires_flow_and_successful_dynamic_verification():
    payload = finding_payload(verdict="confirmed", needs_verification=False)
    with pytest.raises(ValidationError):
        FinalizedFinding.model_validate(payload)

    payload["finding_flow"] = finding_flow()
    with pytest.raises(ValidationError):
        FinalizedFinding.model_validate(payload)

    payload["verification_records"] = [
        {
            "method": "sandbox_poc",
            "dynamic": True,
            "success": True,
            "tool": "sandbox",
            "summary": "Traversal reproduced in the isolated target harness.",
            "details": "Request ../secret returned content outside the intended base directory.",
        }
    ]
    confirmed = FinalizedFinding.model_validate(payload)
    assert confirmed.verdict == "confirmed"


def test_effective_control_blocks_reportable_finding():
    payload = finding_payload(verdict="candidate", needs_verification=True)
    payload["finding_flow"] = finding_flow(control_status="effective")
    with pytest.raises(ValidationError, match="effective blocking control"):
        FinalizedFinding.model_validate(payload)


def test_rejected_candidate_requires_effective_blocking_control():
    base = {
        "findings": [],
        "summary": "Candidate was disproved by direct source review.",
        "rejected_candidates": [
            {
                "candidate_id": "path-1",
                "vulnerability_type": "path_traversal",
                "title": "Rejected traversal candidate",
                "file_path": "src/download.py",
                "reason": "Canonical path containment dominates the filesystem read.",
                "confidence": 0.98,
                "blocking_controls": [
                    {
                        "kind": "validation",
                        "status": "bypassable",
                        "location": "src/download.py:11",
                        "description": "Containment check reviewed.",
                        "bypass_reason": "Not proven effective in this variant.",
                    }
                ],
            }
        ],
    }
    with pytest.raises(ValidationError, match="effective blocking control"):
        FinalizedFindingPayload.model_validate(base)

    base["rejected_candidates"][0]["blocking_controls"][0]["status"] = "effective"
    base["rejected_candidates"][0]["blocking_controls"][0]["bypass_reason"] = ""
    parsed = FinalizedFindingPayload.model_validate(base)
    assert len(parsed.rejected_candidates) == 1

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.services.finding_runtime.final_finding_contract import FinalizedFinding


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
    with pytest.raises(ValidationError):
        FinalizedFinding.model_validate(finding_payload(verdict="confirmed", needs_verification=True))


def test_consistent_candidate_and_confirmed_states_are_accepted():
    candidate = FinalizedFinding.model_validate(finding_payload(verdict="candidate", needs_verification=True))
    confirmed = FinalizedFinding.model_validate(finding_payload(verdict="confirmed", needs_verification=False))

    assert candidate.verdict == "candidate"
    assert confirmed.verdict == "confirmed"

from __future__ import annotations

from app.services.finding_runtime.fingerprint import build_payload_fingerprint


def finding_payload(*, line_start: int, line_end: int, code_snippet: str) -> dict:
    return {
        "vulnerability_type": "path_traversal",
        "file_path": "src/download.py",
        "line_start": line_start,
        "line_end": line_end,
        "code_snippet": code_snippet,
        "source": "HTTP path parameter",
        "sink": "filesystem open",
        "exploit_chain": [
            {
                "step": 1,
                "location": f"src/download.py:{line_start}-{line_end}",
                "description": "User path reaches filesystem open",
            }
        ],
        "finding_flow": {
            "nodes": [
                {"id": "source", "kind": "source", "location": f"src/download.py:{line_start}", "description": "input"},
                {"id": "sink", "kind": "sink", "location": f"src/download.py:{line_end}", "description": "open"},
            ],
            "edges": [{"source_id": "source", "target_id": "sink", "relation": "flows_to"}],
            "controls": [],
        },
    }


def test_fingerprint_is_stable_across_line_and_snippet_changes():
    first = build_payload_fingerprint(
        finding_payload(line_start=10, line_end=12, code_snippet="open(base / user_path).read()")
    )
    shifted = build_payload_fingerprint(
        finding_payload(line_start=110, line_end=112, code_snippet="return open(base / user_path).read()")
    )

    assert first == shifted
    assert len(first) == 24


def test_fingerprint_changes_when_security_semantics_change():
    original = finding_payload(line_start=10, line_end=12, code_snippet="open(base / user_path).read()")
    changed = dict(original)
    changed["sink"] = "subprocess execution"

    assert build_payload_fingerprint(original) != build_payload_fingerprint(changed)

from __future__ import annotations

import hashlib
import re
from typing import Any


_LINE_SUFFIX_RE = re.compile(r":\d+(?:[-:]\d+)?(?:-\d+)?$")
_WHITESPACE_RE = re.compile(r"\s+")


def _normalize_text(value: Any) -> str:
    return _WHITESPACE_RE.sub(" ", str(value or "").strip().lower())


def _normalize_path(value: Any) -> str:
    normalized = str(value or "").strip().replace("\\", "/")
    normalized = _LINE_SUFFIX_RE.sub("", normalized)
    while normalized.startswith("./"):
        normalized = normalized[2:]
    return normalized.lower()


def _location_path(value: Any) -> str:
    text = str(value or "").strip()
    return _normalize_path(text) if text else ""


def _raw_finding(record: Any) -> dict[str, Any]:
    metadata = getattr(record, "finding_metadata", None)
    if not isinstance(metadata, dict):
        return {}
    raw = metadata.get("raw_finding")
    return dict(raw) if isinstance(raw, dict) else {}


def _flow_shape(raw: dict[str, Any]) -> str:
    flow = raw.get("finding_flow")
    if not isinstance(flow, dict):
        return ""
    nodes = flow.get("nodes")
    if not isinstance(nodes, list):
        return ""
    kinds = [
        _normalize_text(node.get("kind"))
        for node in nodes
        if isinstance(node, dict) and _normalize_text(node.get("kind"))
    ]
    return ">".join(kinds)


def _entry_paths(raw: dict[str, Any]) -> str:
    values: list[str] = []
    for key in ("entry_point_refs", "priority_path_refs"):
        items = raw.get(key)
        if not isinstance(items, list):
            continue
        for item in items:
            normalized = _location_path(item)
            if normalized and normalized not in values:
                values.append(normalized)
    exploit_chain = raw.get("exploit_chain")
    if isinstance(exploit_chain, list):
        for step in exploit_chain:
            if not isinstance(step, dict):
                continue
            normalized = _location_path(step.get("location"))
            if normalized and normalized not in values:
                values.append(normalized)
    return ",".join(values[:8])


def _hash_components(components: list[str]) -> str:
    canonical = "|".join(components)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:24]


def build_payload_fingerprint(finding: dict[str, Any]) -> str:
    payload = dict(finding or {})
    return _hash_components(
        [
            _normalize_text(payload.get("vulnerability_type")),
            _normalize_path(payload.get("file_path")),
            _normalize_text(payload.get("function_name") or payload.get("class_name")),
            _normalize_text(payload.get("source")),
            _normalize_text(payload.get("sink")),
            _flow_shape(payload),
            _entry_paths(payload),
        ]
    )


def build_finding_fingerprint(record: Any) -> str:
    raw = _raw_finding(record)
    return _hash_components(
        [
            _normalize_text(getattr(record, "vulnerability_type", "")),
            _normalize_path(getattr(record, "file_path", "")),
            _normalize_text(getattr(record, "function_name", "") or getattr(record, "class_name", "")),
            _normalize_text(getattr(record, "source", "")),
            _normalize_text(getattr(record, "sink", "")),
            _flow_shape(raw),
            _entry_paths(raw),
        ]
    )

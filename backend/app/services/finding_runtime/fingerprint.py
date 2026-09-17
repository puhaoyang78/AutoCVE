from __future__ import annotations

import hashlib
import re
from typing import Any


FINGERPRINT_VERSION = "v2"
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
    if not text:
        return ""
    return _normalize_path(text)


def _raw_finding(record: Any) -> dict[str, Any]:
    metadata = getattr(record, "finding_metadata", None)
    if not isinstance(metadata, dict):
        return {}
    raw = metadata.get("raw_finding")
    return dict(raw) if isinstance(raw, dict) else {}


def _evidence_graph_shape(raw: dict[str, Any]) -> str:
    graph = raw.get("evidence_graph")
    if not isinstance(graph, dict):
        return ""
    nodes = graph.get("nodes")
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
    """Build a stable fingerprint directly from a finalized finding payload."""

    payload = dict(finding or {})
    components = [
        FINGERPRINT_VERSION,
        _normalize_text(payload.get("vulnerability_type")),
        _normalize_path(payload.get("file_path")),
        _normalize_text(payload.get("function_name") or payload.get("class_name")),
        _normalize_text(payload.get("source")),
        _normalize_text(payload.get("sink")),
        _evidence_graph_shape(payload),
        _entry_paths(payload),
    ]
    return _hash_components(components)


def build_finding_fingerprint(record: Any) -> str:
    """Build a location-stable semantic fingerprint for an AgentFinding-like object."""

    raw = _raw_finding(record)
    components = [
        FINGERPRINT_VERSION,
        _normalize_text(getattr(record, "vulnerability_type", "")),
        _normalize_path(getattr(record, "file_path", "")),
        _normalize_text(getattr(record, "function_name", "") or getattr(record, "class_name", "")),
        _normalize_text(getattr(record, "source", "")),
        _normalize_text(getattr(record, "sink", "")),
        _evidence_graph_shape(raw),
        _entry_paths(raw),
    ]
    return _hash_components(components)


def fingerprint_version(record: Any) -> str | None:
    metadata = getattr(record, "finding_metadata", None)
    if not isinstance(metadata, dict):
        return None
    value = str(metadata.get("fingerprint_version") or "").strip()
    return value or None


def _seed_v2_fingerprint_on_init(target: Any, args: tuple[Any, ...], kwargs: dict[str, Any]) -> None:
    del target, args
    metadata = kwargs.get("finding_metadata")
    if not isinstance(metadata, dict):
        return
    raw = metadata.get("raw_finding")
    if not isinstance(raw, dict):
        return
    stable_fingerprint = str(raw.get("stable_fingerprint") or "").strip()
    version = str(raw.get("fingerprint_version") or "").strip()
    if not stable_fingerprint or version != FINGERPRINT_VERSION:
        return
    kwargs.setdefault("fingerprint", stable_fingerprint)
    normalized_metadata = dict(metadata)
    normalized_metadata["fingerprint_version"] = FINGERPRINT_VERSION
    kwargs["finding_metadata"] = normalized_metadata


def _persist_v2_fingerprint(mapper: Any, connection: Any, target: Any) -> None:
    del mapper, connection
    metadata = dict(getattr(target, "finding_metadata", None) or {})
    previous_version = str(metadata.get("fingerprint_version") or "legacy").strip() or "legacy"
    target.fingerprint = build_finding_fingerprint(target)
    metadata["fingerprint_version"] = FINGERPRINT_VERSION
    if previous_version != FINGERPRINT_VERSION:
        metadata.setdefault("fingerprint_migrated_from", previous_version)
    target.finding_metadata = metadata


def _migrate_v2_fingerprint_on_load(target: Any, context: Any) -> None:
    del context
    metadata = dict(getattr(target, "finding_metadata", None) or {})
    previous_version = str(metadata.get("fingerprint_version") or "legacy").strip() or "legacy"
    if previous_version == FINGERPRINT_VERSION:
        return
    target.fingerprint = build_finding_fingerprint(target)
    metadata["fingerprint_version"] = FINGERPRINT_VERSION
    metadata["fingerprint_migrated_from"] = previous_version
    target.finding_metadata = metadata


def install_agent_finding_fingerprint_hooks(model: Any) -> None:
    """Seed, migrate, and persist v2 fingerprints for AgentFinding rows."""

    from sqlalchemy import event

    if not event.contains(model, "init", _seed_v2_fingerprint_on_init):
        event.listen(model, "init", _seed_v2_fingerprint_on_init, propagate=True)
    if not event.contains(model, "load", _migrate_v2_fingerprint_on_load):
        event.listen(model, "load", _migrate_v2_fingerprint_on_load, propagate=True)
    if not event.contains(model, "before_insert", _persist_v2_fingerprint):
        event.listen(model, "before_insert", _persist_v2_fingerprint, propagate=True)
    if not event.contains(model, "before_update", _persist_v2_fingerprint):
        event.listen(model, "before_update", _persist_v2_fingerprint, propagate=True)

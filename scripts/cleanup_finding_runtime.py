from pathlib import Path
import re

root = Path(__file__).resolve().parents[1]


def load(path: str) -> str:
    return (root / path).read_text(encoding="utf-8-sig")


def save(path: str, text: str) -> None:
    (root / path).write_text(text, encoding="utf-8")


# query_loop.py: only native structured tool calls.
path = "backend/app/services/finding_runtime/query_loop.py"
text = load(path)
text = text.replace("from app.services.agent.json_parser import AgentJsonParser\n", "")
text = text.replace("    ALLOW_LEGACY_TEXT_TOOL_CALLS = False\n", "")
text = text.replace('        legacy_text_tool_calls = list(collected.get("legacy_text_tool_calls") or [])\n', "")
start = "        if not tool_requests and legacy_text_tool_calls and tool_definitions and self._tool_orchestrator is not None:\n"
end = "        if tool_requests:\n"
assert start in text and end in text
before, rest = text.split(start, 1)
_, after = rest.split(end, 1)
text = before + end + after

nonstream_old = '''            raw_tool_calls = list(model_response.tool_calls or [])
            legacy_text_tool_calls: list[dict[str, object]] = []
            if not raw_tool_calls and model_response.content and tool_definitions and self._tool_orchestrator is not None:
                extracted_tool_calls = self._extract_text_tool_calls(model_response.content)
                if self.ALLOW_LEGACY_TEXT_TOOL_CALLS:
                    raw_tool_calls = extracted_tool_calls
                else:
                    legacy_text_tool_calls = list(extracted_tool_calls)
'''
assert nonstream_old in text
text = text.replace(nonstream_old, "            raw_tool_calls = list(model_response.tool_calls or [])\n", 1)
text = text.replace('                "legacy_text_tool_calls": legacy_text_tool_calls,\n', "", 1)
stream_start = "        legacy_text_tool_calls: list[dict[str, object]] = []\n"
stream_end = "        return {\n"
assert stream_start in text
before, rest = text.split(stream_start, 1)
_, after = rest.split(stream_end, 1)
text = before + stream_end + after
text = text.replace('            "legacy_text_tool_calls": legacy_text_tool_calls,\n', "", 1)
text, count = re.subn(
    r"\n    @classmethod\n    def _should_issue_legacy_tool_syntax_nudge\(.*?\n        return nudge_count < 1\n",
    "",
    text,
    count=1,
    flags=re.S,
)
assert count == 1
parser_marker = "    @staticmethod\n    def _extract_text_tool_calls(content: str) -> list[dict[str, object]]:\n"
assert parser_marker in text
text = text.split(parser_marker, 1)[0].rstrip() + "\n"
text = text.replace(
    '"2. 如果已经充分完成主要攻击面覆盖，并且准备结束整个 Finding 阶段，必须调用 FinalizeFinding；或输出严格可解析的 "\n'
    '                    "{\\"findings\\": [...], \\"summary\\": \\"...\\"} JSON。\\\n\\\n"\n',
    '"2. 如果已经充分完成主要攻击面覆盖，并且准备结束整个 Finding 阶段，必须调用 FinalizeFinding 提交最终结构化结果。\\\n\\\n"\n',
)
for token in ("legacy_text_tool_calls", "ALLOW_LEGACY_TEXT_TOOL_CALLS", "LEGACY_TOOL_SYNTAX_NUDGE", "AgentJsonParser"):
    assert token not in text, token
save(path, text)

# agent_tasks.py: current runtime only and one fingerprint function.
path = "backend/app/api/v1/endpoints/agent_tasks.py"
text = load(path)
text = text.replace("import hashlib\n", "")
text = text.replace("from app.services.finding_runtime.config import FindingRuntimeStack, coerce_finding_runtime_stack\n", "")
anchor = "from app.services.finding_runtime.final_finding_contract import has_meaningful_poc, is_placeholder_finding\n"
assert anchor in text
if "from app.services.finding_runtime.fingerprint import build_finding_fingerprint\n" not in text:
    text = text.replace(anchor, anchor + "from app.services.finding_runtime.fingerprint import build_finding_fingerprint\n")
text = re.sub(r"\n    finding_runtime_stack: Optional\[str\] = Field\([^\n]*\)\n", "\n", text, count=1)
text = text.replace("    finding_runtime_stack: str = FindingRuntimeStack.RUNTIME.value\n", "")
text = text.replace("    evidence_type: Optional[str] = None\n", "")
text = text.replace("    evidence_gaps: List[str] = Field(default_factory=list)\n", "")
text, count = re.subn(
    r"\ndef _resolve_task_runtime_stack\(agent_config: Any\) -> str:\n.*?\n\ndef _extract_finding_runtime_payload",
    "\n\ndef _extract_finding_runtime_payload",
    text,
    count=1,
    flags=re.S,
)
assert count == 1
text = text.replace('        "origin": candidate.get("origin") or "transcript_recovery",\n', "")
text = text.replace('        "evidence_type": candidate.get("evidence_type") or "transcript_recovery",\n', "")
text = text.replace('        "evidence_gaps": candidate.get("evidence_gaps") or [],\n', "")
text = text.replace("_bootstrap_legacy_agent_memories", "_bootstrap_agent_memories")
text = text.replace("legacy_agents", "agents")
text = text.replace("# Running task registry kept for cancellation and legacy task lookups.", "# Running task registry kept for cancellation and task lookups.")
text = text.replace('            runtime_agent_config = dict(task.agent_config or {})\n            finding_runtime_stack = runtime_agent_config.get("finding_runtime_stack") or "legacy"\n', "")
text = text.replace('            workflow_config["finding_runtime_stack"] = finding_runtime_stack\n', "")
text = text.replace('                    "finding_runtime_stack": finding_runtime_stack,\n', "")
text = text.replace('                "finding_runtime_stack": finding_runtime_stack,\n', "")
text, count = re.subn(
    r'        agent_config=\{"finding_runtime_stack": coerce_finding_runtime_stack\(request\.finding_runtime_stack or getattr\(settings, "FINDING_RUNTIME_STACK_DEFAULT", FindingRuntimeStack\.LEGACY\.value\)\)\.value\},',
    "        agent_config={},",
    text,
    count=1,
)
assert count == 1
text = re.sub(r'\n        setattr\(task, "finding_runtime_stack", _resolve_task_runtime_stack\(task\.agent_config\)\)', "", text)
text = re.sub(r'\n        "finding_runtime_stack": _resolve_task_runtime_stack\(task\.agent_config\),', "", text)
text = text.replace("    if session.runtime_stack == FindingRuntimeStack.RUNTIME.value:\n", "    if session is not None:\n", 1)
text = text.replace("            if session is not None and session.runtime_stack == FindingRuntimeStack.RUNTIME.value:\n", "            if session is not None:\n", 1)
text = text.replace('    if raw_finding.get("origin") and metadata.get("origin") != raw_finding.get("origin"):\n        metadata["origin"] = raw_finding.get("origin")\n        changed = True\n', "")
text = text.replace('    if raw_finding.get("evidence_type") and metadata.get("evidence_type") != raw_finding.get("evidence_type"):\n        metadata["evidence_type"] = raw_finding.get("evidence_type")\n        changed = True\n', "")
text = text.replace('                    "origin": finding.get("origin"),\n                    "evidence_type": finding.get("evidence_type"),\n', "")
marker = '    if changed:\n        metadata["raw_finding"] = raw_finding\n'
assert marker in text
text = text.replace(
    marker,
    '    if metadata.get("raw_finding") != raw_finding:\n        metadata["raw_finding"] = raw_finding\n        changed = True\n    if changed:\n',
    1,
)
text = text.replace("_build_finding_fingerprint(", "build_finding_fingerprint(")
text, count = re.subn(
    r"\ndef build_finding_fingerprint\(record: AgentFinding\) -> str:\n.*?\n\nasync def _save_findings",
    "\n\nasync def _save_findings",
    text,
    count=1,
    flags=re.S,
)
assert count == 1
text = text.replace(
    "        existing_by_fingerprint[build_finding_fingerprint(existing)] = existing\n",
    "        fingerprint = build_finding_fingerprint(existing)\n        existing.fingerprint = fingerprint\n        existing_by_fingerprint[fingerprint] = existing\n",
)
text = text.replace(
    "            fingerprint = build_finding_fingerprint(record)\n            existing = existing_by_fingerprint.get(fingerprint)\n",
    "            fingerprint = build_finding_fingerprint(record)\n            record.fingerprint = fingerprint\n            existing = existing_by_fingerprint.get(fingerprint)\n",
)
text = re.sub(r"^.*finding_runtime_stack.*\n", "", text, flags=re.M)
for token in ("FindingRuntimeStack", "coerce_finding_runtime_stack", "evidence_type", "evidence_gaps", "_bootstrap_legacy", "_build_finding_fingerprint"):
    assert token not in text, token
save(path, text)

# ORM: delete obsolete line/snippet fingerprint implementation.
path = "backend/app/models/agent_task.py"
text = load(path)
text, count = re.subn(
    r"\n    def generate_fingerprint\(self\) -> str:\n.*?(?=\n    def to_dict\(self\) -> dict:)",
    "",
    text,
    count=1,
    flags=re.S,
)
assert count == 1
save(path, text)

# Direct-audit projection: use only the current finding payload/metadata fields.
path = "backend/app/services/direct_audit_vulnerability_service.py"
text = load(path)
text = text.replace('                "origin": "direct_finding",\n                "evidence_type": "direct_audit_report_bundle",\n', "")
text = text.replace('            "origin": "direct_finding",\n            "evidence_type": "direct_audit_report_bundle",\n', "")
assert "evidence_type" not in text
save(path, text)

# OneClick always uses the current Finding runtime; remove its old selector.
path = "backend/app/services/one_click_cve/runner.py"
text = load(path)
text = text.replace(
    '        agent_config={\n            "finding_runtime_stack": getattr(settings, "FINDING_RUNTIME_STACK_DEFAULT", "runtime"),\n            "one_click_cve_batch_id": batch_id,\n        },',
    '        agent_config={"one_click_cve_batch_id": batch_id},',
)
assert "finding_runtime_stack" not in text
save(path, text)

# Settings and removed runtime selector.
path = "backend/app/core/config.py"
text = load(path)
text = re.sub(r"^\s*FINDING_RUNTIME_STACK_DEFAULT\s*:.*\n", "", text, flags=re.M)
save(path, text)
config_path = root / "backend/app/services/finding_runtime/config.py"
if config_path.exists():
    config_path.unlink()

for scan_root in (root / "backend/app", root / "backend/tests"):
    for file in scan_root.rglob("*.py"):
        body = file.read_text(encoding="utf-8-sig")
        for token in (
            "FindingRuntimeStack",
            "finding_runtime_stack",
            "LEGACY_TOOL_SYNTAX_NUDGE",
            "LEGACY_FINAL_JSON",
            "legacy_text_tool_calls",
            "ALLOW_LEGACY_TEXT_TOOL_CALLS",
            "stable_fingerprint",
            "fingerprint_version",
            "evidence_type",
            "evidence_gaps",
            "evidence_graph",
            "verification_evidence",
            "_bootstrap_legacy_agent_memories",
        ):
            if token in body:
                raise SystemExit(f"Forbidden leftover {token} in {file}")

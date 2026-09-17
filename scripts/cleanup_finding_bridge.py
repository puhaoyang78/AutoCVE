from pathlib import Path
import re

root = Path(__file__).resolve().parents[1]
path = root / "backend/app/services/finding_runtime/bridge.py"
text = path.read_text(encoding="utf-8-sig")

text = text.replace(
    '    "如果审计已经充分完成：调用 FinalizeFinding 提交结构化结果；或输出可解析的 {\\"findings\\": [...], \\"summary\\": \\"...\\"} JSON。\\n"\n',
    '    "如果审计已经充分完成：调用 FinalizeFinding 提交结构化结果。\\n"\n',
)

legacy_branch = '''        if role == "assistant":
            legacy_tool_summary = RuntimeLLMModelClient._summarize_legacy_tool_call_content(content)
            if legacy_tool_summary is not None:
                return {"role": "user", "content": legacy_tool_summary}
            return {"role": "assistant", "content": content}
'''
assert legacy_branch in text
text = text.replace(
    legacy_branch,
    '        if role == "assistant":\n            return {"role": "assistant", "content": content}\n',
    1,
)

text, count = re.subn(
    r'\n    @staticmethod\n    def _summarize_legacy_tool_call_content\(content: str\) -> str \| None:\n.*?(?=\n    @staticmethod\n    def _normalize_tool_call)',
    '',
    text,
    count=1,
    flags=re.S,
)
assert count == 1

text, count = re.subn(
    r'''\n    @staticmethod\n    def extract_final_payload\(snapshot: Any\) -> dict\[str, Any\] \| None:\n.*?(?=\n    @classmethod\n    def _recover_findings_from_assistant_transcript)''',
    '''
    @staticmethod
    def extract_final_payload(snapshot: Any) -> dict[str, Any] | None:
        for message in reversed(getattr(snapshot, "messages", []) or []):
            if getattr(message, "role", "") != "tool_result":
                continue
            payload = getattr(message, "payload", {}) or {}
            if not isinstance(payload, dict):
                continue
            output = payload.get("output")
            if not isinstance(output, dict):
                continue
            final_payload = output.get("final_payload")
            if isinstance(final_payload, dict):
                return dict(final_payload)
        return None

''',
    text,
    count=1,
    flags=re.S,
)
assert count == 1

text = text.replace(
    '"Recovered from the runtime assistant transcript after final JSON finalization failed. "',
    '"Recovered from the runtime assistant transcript after structured finalization failed. "',
)
text = text.replace('                        "origin": "transcript_recovery",\n', '')
text = text.replace('                        "evidence_type": "transcript_recovery",\n', '')
text = text.replace('                        "evidence_gaps": ["recovered_after_finalizer_failure"],\n', '')

for token in (
    "_summarize_legacy_tool_call_content",
    "evidence_type",
    "evidence_gaps",
    "final JSON finalization",
    "或输出可解析的",
):
    assert token not in text, token

path.write_text(text, encoding="utf-8")

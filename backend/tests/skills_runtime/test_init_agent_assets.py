import json

import pytest

from app.services.init_agent_assets import init_agent_assets
from app.services.skill_file_service import SkillFileService


@pytest.mark.asyncio
async def test_init_agent_assets_stays_local_and_binds_canonical_skill(tmp_path, monkeypatch):
    monkeypatch.setattr(SkillFileService, "project_root", classmethod(lambda cls: tmp_path))

    skill_dir = tmp_path / "skill_library" / "code-audit-finding"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\n"
        "name: code-audit-finding\n"
        "description: Local bundled finding skill\n"
        "tags: [finding, code-audit]\n"
        "---\n\n"
        "# code-audit-finding\n",
        encoding="utf-8",
    )

    async def fail_import(*args, **kwargs):
        raise AssertionError("init_agent_assets should not import GitHub skills")

    monkeypatch.setattr(SkillFileService, "import_github_skill", classmethod(fail_import))

    await init_agent_assets()

    bindings = json.loads(
        (tmp_path / "skill_library" / "agents" / "finding" / "bindings.json").read_text(encoding="utf-8")
    )
    installed_index = json.loads(
        (tmp_path / "skill_library" / ".runtime" / "installed_skills.json").read_text(encoding="utf-8")
    )
    assert bindings["skills"][0]["slug"] == "code-audit-finding"
    assert bindings["skills"][0]["always_include"] is True
    assert not (tmp_path / "skill_library" / "agents" / "finding" / "code-audit-finding").exists()
    assert installed_index["skills"][0]["slug"] == "code-audit-finding"
    assert installed_index["skills"][0]["bound_agents"] == ["audit_chat", "finding"]


@pytest.mark.asyncio
async def test_init_agent_assets_migrates_finding_bindings_to_phased_defaults(tmp_path, monkeypatch):
    monkeypatch.setattr(SkillFileService, "project_root", classmethod(lambda cls: tmp_path))

    for slug in (
        "code-audit-finding",
        "secknowledge-skill",
        "cve-report-writer",
        "code-security",
    ):
        skill_dir = tmp_path / "skill_library" / slug
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text(
            f"---\nname: {slug}\ndescription: test skill\n---\n\n# {slug}\n",
            encoding="utf-8",
        )

    SkillFileService.ensure_agent_bindings("finding")
    SkillFileService.upsert_binding(
        "finding",
        "secknowledge-skill",
        enabled=True,
        always_include=True,
        sort_order=0,
    )
    SkillFileService.upsert_binding(
        "finding",
        "cve-report-writer",
        enabled=True,
        always_include=True,
        sort_order=0,
    )
    SkillFileService.upsert_binding(
        "finding",
        "code-security",
        enabled=True,
        always_include=True,
        sort_order=1,
    )

    await init_agent_assets()

    bindings = SkillFileService.get_agent_bindings("finding")["skills"]
    by_slug = {item["slug"]: item for item in bindings}

    assert set(by_slug) == {
        "code-audit-finding",
        "secknowledge-skill",
        "cve-report-writer",
    }
    assert by_slug["code-audit-finding"]["always_include"] is True
    assert by_slug["code-audit-finding"]["sort_order"] == 0
    assert by_slug["secknowledge-skill"]["always_include"] is False
    assert by_slug["secknowledge-skill"]["sort_order"] == 10
    assert by_slug["cve-report-writer"]["always_include"] is False
    assert by_slug["cve-report-writer"]["sort_order"] == 20

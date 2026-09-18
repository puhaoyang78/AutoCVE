from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class SkillEntry:
    slug: str
    name: str
    description: str
    skill_file: str
    folder_path: str
    tags: list[str] = field(default_factory=list)
    when_to_use: str | None = None
    allowed_tools: list[str] = field(default_factory=list)
    argument_hint: str | None = None
    argument_names: list[str] = field(default_factory=list)
    version: str | None = None
    model: str | None = None
    disable_model_invocation: bool = False
    user_invocable: bool = True
    execution_context: str | None = None
    agent: str | None = None
    effort: str | None = None
    shell: dict[str, Any] | None = None
    hooks: dict[str, Any] = field(default_factory=dict)
    paths: list[str] = field(default_factory=list)
    frontmatter: dict[str, Any] = field(default_factory=dict)
    metadata_json: dict[str, Any] = field(default_factory=dict)
    source_type: str = "manual"
    source_url: str | None = None
    content: str = ""
    skill_body: str = ""
    extension_manifest: list[dict[str, Any]] = field(default_factory=list)
    is_system: bool = False
    is_active: bool = True


@dataclass(slots=True)
class SkillBinding:
    agent_type: str
    slug: str
    enabled: bool = True
    always_include: bool = False
    sort_order: int = 0
    match_keywords: list[str] = field(default_factory=list)
    match_config: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class SkillRoutePlan:
    primary_skill: str | None = None
    secondary_skills: list[str] = field(default_factory=list)
    mandatory_reads: list[str] = field(default_factory=list)
    recommended_reads: list[str] = field(default_factory=list)
    selection_reason: list[str] = field(default_factory=list)
    startup_reads: list[str] = field(default_factory=list)
    deferred_skills: list[str] = field(default_factory=list)
    deferred_skill_reads: list[str] = field(default_factory=list)


@dataclass(slots=True)
class SkillPromptState:
    entries: list[SkillEntry] = field(default_factory=list)
    matched: list[SkillEntry] = field(default_factory=list)
    prompt: str = ""
    route_plan: SkillRoutePlan = field(default_factory=SkillRoutePlan)


@dataclass(slots=True)
class SkillSnapshot:
    prompt: str = ""
    skills: list[str] = field(default_factory=list)

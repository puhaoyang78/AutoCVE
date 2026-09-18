from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class AgentSkillBindingBase(BaseModel):
    agent_type: str = Field(..., description="Target agent type")
    enabled: bool = Field(True, description="Whether this binding is enabled")
    always_include: bool = Field(False, description="Always inject this skill metadata at agent startup")
    sort_order: int = Field(0, description="Binding order inside the agent")
    match_keywords: list[str] = Field(default_factory=list, description="Keywords used to decide whether the skill body should be loaded later")
    match_config: dict[str, Any] = Field(default_factory=dict, description="Reserved binding config")


class AgentSkillBindingCreate(AgentSkillBindingBase):
    pass


class AgentSkillBindingUpdate(BaseModel):
    enabled: bool | None = None
    always_include: bool | None = None
    sort_order: int | None = None
    match_keywords: list[str] | None = None
    match_config: dict[str, Any] | None = None


class AgentSkillBindingResponse(AgentSkillBindingBase):
    id: str
    skill_id: str
    bindings_file: str | None = None
    skill_file: str | None = None
    created_by: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class SkillBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    slug: str = Field(..., min_length=1, max_length=160)
    description: str = Field(..., min_length=1)
    source_type: str = Field("manual", description="manual/local/github")
    source_url: str | None = None
    content: str | None = None
    metadata_json: dict[str, Any] = Field(default_factory=dict)
    tags: list[str] = Field(default_factory=list)
    extension_manifest: list[dict[str, Any]] = Field(default_factory=list)
    extension_payload: dict[str, Any] = Field(default_factory=dict)
    is_active: bool = True
    is_system: bool = False


class SkillCreate(SkillBase):
    bindings: list[AgentSkillBindingCreate] = Field(default_factory=list)


class SkillUpdate(BaseModel):
    name: str | None = None
    slug: str | None = None
    description: str | None = None
    source_type: str | None = None
    source_url: str | None = None
    content: str | None = None
    metadata_json: dict[str, Any] | None = None
    tags: list[str] | None = None
    extension_manifest: list[dict[str, Any]] | None = None
    extension_payload: dict[str, Any] | None = None
    is_active: bool | None = None
    is_system: bool | None = None


class SkillMetadataResponse(BaseModel):
    id: str
    name: str
    slug: str
    description: str
    tags: list[str] = Field(default_factory=list)
    source_type: str
    source_url: str | None = None
    metadata_json: dict[str, Any] = Field(default_factory=dict)
    is_system: bool = False
    is_active: bool = True
    bindings: list[AgentSkillBindingResponse] = Field(default_factory=list)
    folder_path: str | None = None
    skill_file: str | None = None
    bindings_file: str | None = None
    created_by: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class SkillResponse(SkillMetadataResponse):
    content: str | None = None
    extension_manifest: list[dict[str, Any]] = Field(default_factory=list)
    extension_payload: dict[str, Any] = Field(default_factory=dict)


class SkillListResponse(BaseModel):
    items: list[SkillMetadataResponse]
    total: int


class SkillImportRequest(BaseModel):
    repo_url: str
    agent_type: str | None = None
    bind_to_agent: bool = True
    enabled: bool = True
    always_include: bool = False
    match_keywords: list[str] = Field(default_factory=list)

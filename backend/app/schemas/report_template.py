from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ReportTemplateBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    description: str | None = None
    report_type: str = Field("final_vulnerability_report")
    output_format: str = Field("markdown")
    content: str = Field(..., min_length=1)
    variables: dict[str, Any] = Field(default_factory=dict)
    metadata_json: dict[str, Any] = Field(default_factory=dict)
    is_active: bool = True
    sort_order: int = 0


class ReportTemplateCreate(ReportTemplateBase):
    slug: str | None = None
    is_default: bool = False
    is_system: bool = False


class ReportTemplateUpdate(BaseModel):
    name: str | None = None
    slug: str | None = None
    description: str | None = None
    report_type: str | None = None
    output_format: str | None = None
    content: str | None = None
    variables: dict[str, Any] | None = None
    metadata_json: dict[str, Any] | None = None
    is_active: bool | None = None
    sort_order: int | None = None
    is_default: bool | None = None
    is_system: bool | None = None


class ReportTemplateResponse(ReportTemplateBase):
    id: str
    slug: str
    is_default: bool = False
    is_system: bool = False
    folder_path: str | None = None
    template_file: str | None = None
    created_by: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class ReportTemplateListResponse(BaseModel):
    items: list[ReportTemplateResponse]
    total: int


class AgentTaskReportResponse(BaseModel):
    task_id: str
    template_id: str | None = None
    output_format: str
    title: str | None = None
    content: str
    report_json: dict[str, Any] | None = None
    report_metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime | None = None
    updated_at: datetime | None = None

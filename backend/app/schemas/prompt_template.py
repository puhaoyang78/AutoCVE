"""
提示词模板 Schema
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class PromptTemplateBase(BaseModel):
    """提示词模板基础Schema"""
    name: str = Field(..., min_length=1, max_length=100, description="模板名称")
    description: str | None = Field(None, description="模板描述")
    template_type: str = Field("system", description="模板类型: system/user/analysis")
    content_zh: str | None = Field(None, description="中文提示词")
    content_en: str | None = Field(None, description="英文提示词")
    variables: dict[str, str] | None = Field(default_factory=dict, description="模板变量说明")
    is_active: bool = Field(True, description="是否启用")
    sort_order: int = Field(0, description="排序权重")


class PromptTemplateCreate(PromptTemplateBase):
    """创建提示词模板"""
    pass


class PromptTemplateUpdate(BaseModel):
    """更新提示词模板"""
    name: str | None = Field(None, min_length=1, max_length=100)
    description: str | None = None
    template_type: str | None = None
    content_zh: str | None = None
    content_en: str | None = None
    variables: dict[str, str] | None = None
    is_default: bool | None = None
    is_active: bool | None = None
    sort_order: int | None = None


class PromptTemplateResponse(PromptTemplateBase):
    """提示词模板响应"""
    id: str
    is_default: bool = False
    is_system: bool = False
    created_by: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class PromptTemplateListResponse(BaseModel):
    """提示词模板列表响应"""
    items: list[PromptTemplateResponse]
    total: int


class PromptTestRequest(BaseModel):
    """提示词测试请求"""
    content: str = Field(..., description="提示词内容")
    language: str = Field("python", description="编程语言")
    code: str = Field(..., description="测试代码")
    output_language: str = Field("zh", description="输出语言: zh/en")


class PromptTestResponse(BaseModel):
    """提示词测试响应"""
    success: bool
    result: dict[str, Any] | None = None
    error: str | None = None
    execution_time: float | None = None

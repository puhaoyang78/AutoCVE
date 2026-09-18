"""
审计规则 Schema
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

# ==================== 审计规则 ====================

class AuditRuleBase(BaseModel):
    """审计规则基础Schema"""
    rule_code: str = Field(..., min_length=1, max_length=50, description="规则标识")
    name: str = Field(..., min_length=1, max_length=200, description="规则名称")
    description: str | None = Field(None, description="规则描述")
    category: str = Field(..., description="规则类别: security/bug/performance/style/maintainability")
    severity: str = Field("medium", description="严重程度: critical/high/medium/low")
    custom_prompt: str | None = Field(None, description="自定义检测提示词")
    fix_suggestion: str | None = Field(None, description="修复建议模板")
    reference_url: str | None = Field(None, max_length=500, description="参考链接")
    enabled: bool = Field(True, description="是否启用")
    sort_order: int = Field(0, description="排序权重")


class AuditRuleCreate(AuditRuleBase):
    """创建审计规则"""
    pass


class AuditRuleUpdate(BaseModel):
    """更新审计规则"""
    rule_code: str | None = Field(None, min_length=1, max_length=50)
    name: str | None = Field(None, min_length=1, max_length=200)
    description: str | None = None
    category: str | None = None
    severity: str | None = None
    custom_prompt: str | None = None
    fix_suggestion: str | None = None
    reference_url: str | None = None
    enabled: bool | None = None
    sort_order: int | None = None


class AuditRuleResponse(AuditRuleBase):
    """审计规则响应"""
    id: str
    rule_set_id: str
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


# ==================== 审计规则集 ====================

class AuditRuleSetBase(BaseModel):
    """审计规则集基础Schema"""
    name: str = Field(..., min_length=1, max_length=100, description="规则集名称")
    description: str | None = Field(None, description="规则集描述")
    language: str = Field("all", description="适用语言")
    rule_type: str = Field("custom", description="规则集类型: security/quality/performance/custom")
    severity_weights: dict[str, int] | None = Field(
        default_factory=lambda: {"critical": 10, "high": 5, "medium": 2, "low": 1},
        description="严重程度权重"
    )
    is_active: bool = Field(True, description="是否启用")
    sort_order: int = Field(0, description="排序权重")


class AuditRuleSetCreate(AuditRuleSetBase):
    """创建审计规则集"""
    rules: list[AuditRuleCreate] | None = Field(default_factory=list, description="规则列表")


class AuditRuleSetUpdate(BaseModel):
    """更新审计规则集"""
    name: str | None = Field(None, min_length=1, max_length=100)
    description: str | None = None
    language: str | None = None
    rule_type: str | None = None
    severity_weights: dict[str, int] | None = None
    is_default: bool | None = None
    is_active: bool | None = None
    sort_order: int | None = None


class AuditRuleSetResponse(AuditRuleSetBase):
    """审计规则集响应"""
    id: str
    is_default: bool = False
    is_system: bool = False
    created_by: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    rules: list[AuditRuleResponse] = Field(default_factory=list)
    rules_count: int = 0
    enabled_rules_count: int = 0

    model_config = ConfigDict(from_attributes=True)


class AuditRuleSetListResponse(BaseModel):
    """审计规则集列表响应"""
    items: list[AuditRuleSetResponse]
    total: int


class AuditRuleSetExport(BaseModel):
    """规则集导出格式"""
    name: str
    description: str | None
    language: str
    rule_type: str
    severity_weights: dict[str, int]
    rules: list[AuditRuleBase]
    export_version: str = "1.0"


class AuditRuleSetImport(BaseModel):
    """规则集导入格式"""
    name: str
    description: str | None = None
    language: str = "all"
    rule_type: str = "custom"
    severity_weights: dict[str, int] | None = None
    rules: list[AuditRuleCreate]

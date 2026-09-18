from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from app.api import deps
from app.db.session import get_db
from app.models.audit import AuditIssue, AuditTask
from app.models.project import Project
from app.models.user import User
from app.services.scanner import task_control

router = APIRouter()


# Schemas
class AuditIssueSchema(BaseModel):
    id: str
    task_id: str
    file_path: str
    line_number: int | None = None
    column_number: int | None = None
    issue_type: str
    severity: str
    title: str | None = None
    message: str | None = None
    description: str | None = None
    suggestion: str | None = None
    code_snippet: str | None = None
    ai_explanation: str | None = None
    status: str
    resolved_by: str | None = None
    resolved_at: datetime | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class IssueUpdateSchema(BaseModel):
    status: str | None = None


class ProjectSchema(BaseModel):
    id: str
    name: str
    description: str | None = None
    source_type: str | None = None
    repository_url: str | None = None
    repository_type: str | None = None
    default_branch: str | None = None
    programming_languages: str | None = None
    owner_id: str
    is_active: bool
    created_at: datetime
    updated_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class AuditTaskSchema(BaseModel):
    id: str
    project_id: str
    task_type: str
    status: str
    branch_name: str | None = None
    exclude_patterns: str | None = None
    scan_config: str | None = None
    total_files: int = 0
    scanned_files: int = 0
    total_lines: int = 0
    issues_count: int = 0
    quality_score: float = 0.0
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_by: str
    created_at: datetime
    project: ProjectSchema | None = None

    model_config = ConfigDict(from_attributes=True)


@router.get("/", response_model=list[AuditTaskSchema])
async def list_tasks(
    project_id: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """
    List tasks for current user's projects.
    """
    # 先获取当前用户的项目ID列表
    projects_result = await db.execute(
        select(Project.id).where(Project.owner_id == current_user.id)
    )
    user_project_ids = [p[0] for p in projects_result.fetchall()]

    query = select(AuditTask).options(selectinload(AuditTask.project))
    # 只返回当前用户项目的任务
    query = query.where(AuditTask.project_id.in_(user_project_ids)) if user_project_ids else query.where(False)
    if project_id:
        query = query.where(AuditTask.project_id == project_id)
    query = query.order_by(AuditTask.created_at.desc())
    result = await db.execute(query)
    return result.scalars().all()


@router.get("/{id}", response_model=AuditTaskSchema)
async def read_task(
    id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """
    Get task status by ID.
    """
    result = await db.execute(
        select(AuditTask)
        .options(selectinload(AuditTask.project))
        .where(AuditTask.id == id)
    )
    task = result.scalars().first()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    # 检查权限：只有任务创建者可以查看
    if task.created_by != current_user.id:
        raise HTTPException(status_code=403, detail="无权查看此任务")

    return task


@router.post("/{id}/cancel")
async def cancel_task(
    id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """
    Cancel a running task.
    """
    result = await db.execute(select(AuditTask).where(AuditTask.id == id))
    task = result.scalars().first()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    # 检查权限：只有任务创建者可以取消
    if task.created_by != current_user.id:
        raise HTTPException(status_code=403, detail="无权取消此任务")

    if task.status not in ["pending", "running"]:
        raise HTTPException(status_code=400, detail="只能取消待处理或运行中的任务")

    # 标记任务为取消
    task_control.cancel_task(id)

    # 更新数据库状态
    task.status = "cancelled"
    task.completed_at = datetime.now(UTC)
    await db.commit()

    return {"message": "任务已取消", "task_id": id}


@router.get("/{id}/issues", response_model=list[AuditIssueSchema])
async def read_task_issues(
    id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """
    Get issues for a specific task.
    """
    # 先检查任务是否存在且属于当前用户
    task_result = await db.execute(
        select(AuditTask).where(AuditTask.id == id)
    )
    task = task_result.scalars().first()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    # 检查权限：只有任务创建者可以查看问题
    if task.created_by != current_user.id:
        raise HTTPException(status_code=403, detail="无权查看此任务的问题")

    result = await db.execute(
        select(AuditIssue)
        .where(AuditIssue.task_id == id)
        .order_by(
            # 按严重程度排序
            AuditIssue.severity.desc(),
            AuditIssue.created_at.desc()
        )
    )
    return result.scalars().all()


@router.patch("/{task_id}/issues/{issue_id}", response_model=AuditIssueSchema)
async def update_issue(
    task_id: str,
    issue_id: str,
    issue_update: IssueUpdateSchema,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """
    Update issue status (e.g., resolve, mark as false positive).
    """
    result = await db.execute(
        select(AuditIssue)
        .where(AuditIssue.id == issue_id, AuditIssue.task_id == task_id)
    )
    issue = result.scalars().first()
    if not issue:
        raise HTTPException(status_code=404, detail="问题不存在")

    if issue_update.status:
        issue.status = issue_update.status
        if issue_update.status == "resolved":
            issue.resolved_by = current_user.id
            issue.resolved_at = datetime.now(UTC)

    await db.commit()
    await db.refresh(issue)
    return issue


@router.get("/{id}/report/pdf")
async def export_task_report_pdf(
    id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """
    Export task audit report as PDF.
    """
    from fastapi.responses import Response

    from app.services.report_generator import ReportGenerator

    # 获取任务
    result = await db.execute(
        select(AuditTask)
        .options(selectinload(AuditTask.project))
        .where(AuditTask.id == id)
    )
    task = result.scalars().first()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    # 检查权限
    if task.created_by != current_user.id:
        raise HTTPException(status_code=403, detail="无权导出此任务报告")

    # 获取问题列表
    issues_result = await db.execute(
        select(AuditIssue)
        .where(AuditIssue.task_id == id)
        .order_by(AuditIssue.severity.desc(), AuditIssue.created_at.desc())
    )
    issues = issues_result.scalars().all()

    # 转换为字典
    task_dict = {
        'id': task.id,
        'status': task.status,
        'branch_name': task.branch_name,
        'total_files': task.total_files,
        'scanned_files': task.scanned_files,
        'total_lines': task.total_lines,
        'issues_count': task.issues_count,
        'quality_score': task.quality_score,
        'created_at': task.created_at.isoformat() if task.created_at else None,
        'completed_at': task.completed_at.isoformat() if task.completed_at else None,
    }

    issues_list = [
        {
            'title': issue.title,
            'description': issue.description,
            'severity': issue.severity,
            'issue_type': issue.issue_type,
            'file_path': issue.file_path,
            'line_number': issue.line_number,
            'column_number': issue.column_number,
            'code_snippet': issue.code_snippet,
            'suggestion': issue.suggestion,
        }
        for issue in issues
    ]

    project_name = task.project.name if task.project else "Unknown Project"

    # 生成 PDF
    pdf_bytes = ReportGenerator.generate_task_report(task_dict, issues_list, project_name)

    # 返回 PDF 文件
    filename = f"audit-report-{task.id[:8]}-{datetime.now(UTC).strftime('%Y%m%d')}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"'
        }
    )

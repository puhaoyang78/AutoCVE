from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    file_path = Path(path)
    text = file_path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{path}: expected one match, found {count}")
    file_path.write_text(text.replace(old, new, 1), encoding="utf-8")


# Backend: validate the status filter using the existing string constants.
replace_once(
    "backend/app/api/v1/endpoints/agent_tasks.py",
    """    if status:\n        try:\n            query = query.where(AgentTask.status == AgentTaskStatus(status))\n        except ValueError:\n            pass\n""",
    """    if status:\n        valid_statuses = {\n            AgentTaskStatus.PENDING,\n            AgentTaskStatus.INITIALIZING,\n            AgentTaskStatus.RUNNING,\n            AgentTaskStatus.PLANNING,\n            AgentTaskStatus.INDEXING,\n            AgentTaskStatus.ANALYZING,\n            AgentTaskStatus.VERIFYING,\n            AgentTaskStatus.REPORTING,\n            AgentTaskStatus.COMPLETED,\n            AgentTaskStatus.FAILED,\n            AgentTaskStatus.CANCELLED,\n            AgentTaskStatus.PAUSED,\n        }\n        if status not in valid_statuses:\n            raise HTTPException(status_code=400, detail=f\"Invalid task status: {status}\")\n        query = query.where(AgentTask.status == status)\n""",
)

# Backend: finished Agent tasks can be deleted. AuditSession.task_id has no FK,
# so task-scoped sessions are explicitly removed before deleting the task.
replace_once(
    "backend/app/api/v1/endpoints/agent_tasks.py",
    """    logger.info(f\"[Cancel] Task {task_id} cancelled successfully\")\n    return {\"message\": \"Task cancelled\", \"task_id\": task_id}\n\n\n@router.get(\"/{task_id}/events\")\n""",
    """    logger.info(f\"[Cancel] Task {task_id} cancelled successfully\")\n    return {\"message\": \"Task cancelled\", \"task_id\": task_id}\n\n\n@router.delete(\"/{task_id}\")\nasync def delete_agent_task(\n    task_id: str,\n    db: AsyncSession = Depends(get_db),\n    current_user: User = Depends(deps.get_current_user),\n) -> Any:\n    \"\"\"Delete a finished Agent audit record and its runtime sessions.\"\"\"\n    task = await db.get(AgentTask, task_id)\n    if not task:\n        raise HTTPException(status_code=404, detail=\"Task not found\")\n\n    project = await db.get(Project, task.project_id)\n    if not project or project.owner_id != current_user.id:\n        raise HTTPException(status_code=403, detail=\"Access denied\")\n\n    if task.status not in {\n        AgentTaskStatus.COMPLETED,\n        AgentTaskStatus.FAILED,\n        AgentTaskStatus.CANCELLED,\n        AgentTaskStatus.PAUSED,\n    }:\n        raise HTTPException(status_code=409, detail=\"Active task must be cancelled before deletion\")\n\n    sessions_result = await db.execute(select(AuditSession).where(AuditSession.task_id == task_id))\n    for audit_session in sessions_result.scalars().all():\n        await db.delete(audit_session)\n\n    await db.delete(task)\n    await db.commit()\n    clear_task_cancellation(task_id)\n    logger.info(\"Deleted Agent task %s and its runtime sessions\", task_id)\n    return {\"message\": \"Task deleted\", \"task_id\": task_id}\n\n\n@router.get(\"/{task_id}/events\")\n""",
)

# Frontend API: fetch the complete paginated history and expose resume/delete.
replace_once(
    "frontend/src/shared/api/agentTasks.ts",
    """export async function getAgentTasks(params?: {\n  project_id?: string;\n  status?: string;\n  skip?: number;\n  limit?: number;\n}): Promise<AgentTask[]> {\n  const response = await apiClient.get(\"/agent-tasks/\", { params });\n  return response.data;\n}\n""",
    """export async function getAgentTasks(params?: {\n  project_id?: string;\n  status?: string;\n  skip?: number;\n  limit?: number;\n}): Promise<AgentTask[]> {\n  const response = await apiClient.get(\"/agent-tasks/\", { params });\n  return response.data;\n}\n\nexport async function getAllAgentTasks(params?: {\n  project_id?: string;\n  status?: string;\n}): Promise<AgentTask[]> {\n  const pageSize = 100;\n  const tasks: AgentTask[] = [];\n  let skip = 0;\n\n  while (true) {\n    const page = await getAgentTasks({ ...params, skip, limit: pageSize });\n    tasks.push(...page);\n    if (page.length < pageSize) return tasks;\n    skip += page.length;\n  }\n}\n""",
)

replace_once(
    "frontend/src/shared/api/agentTasks.ts",
    """export async function cancelAgentTask(taskId: string): Promise<{ message: string; task_id: string }> {\n  const response = await apiClient.post(`/agent-tasks/${taskId}/cancel`);\n  return response.data;\n}\n""",
    """export async function cancelAgentTask(taskId: string): Promise<{ message: string; task_id: string }> {\n  const response = await apiClient.post(`/agent-tasks/${taskId}/cancel`);\n  return response.data;\n}\n\nexport async function resumeAgentTask(taskId: string): Promise<{ message: string; task_id: string }> {\n  const response = await apiClient.post(`/agent-tasks/${taskId}/resume`);\n  return response.data;\n}\n\nexport async function deleteAgentTask(taskId: string): Promise<{ message: string; task_id: string }> {\n  const response = await apiClient.delete(`/agent-tasks/${taskId}`);\n  return response.data;\n}\n""",
)

# Task list UX: load all history, show cancelled filter, resume and delete actions.
replace_once(
    "frontend/src/pages/AuditTasks.tsx",
    """\tDownload,\n\tMessagesSquare,\n} from \"lucide-react\";\n""",
    """\tDownload,\n\tMessagesSquare,\n\tRotateCcw,\n\tTrash2,\n} from \"lucide-react\";\n""",
)
replace_once(
    "frontend/src/pages/AuditTasks.tsx",
    """\tgetAgentTasks,\n\tcancelAgentTask,\n\tgetAgentFindings,\n""",
    """\tgetAllAgentTasks,\n\tcancelAgentTask,\n\tresumeAgentTask,\n\tdeleteAgentTask,\n\tgetAgentFindings,\n""",
)
replace_once(
    "frontend/src/pages/AuditTasks.tsx",
    "\t\t\tconst data = await getAgentTasks();\n",
    "\t\t\tconst data = await getAllAgentTasks();\n",
)
replace_once(
    "frontend/src/pages/AuditTasks.tsx",
    "\tconst [exportingTaskId, setExportingTaskId] = useState<string | null>(null);\n",
    "\tconst [resumingAgentTaskId, setResumingAgentTaskId] = useState<string | null>(null);\n\tconst [deletingAgentTaskId, setDeletingAgentTaskId] = useState<string | null>(null);\n\tconst [exportingTaskId, setExportingTaskId] = useState<string | null>(null);\n",
)

handler_marker = "\n\t// 打开快速扫描任务导出对话框\n"
handlers = """
\tconst handleResumeAgentTask = async (taskId: string) => {
\t\tif (resumingAgentTaskId) return;
\t\ttry {
\t\t\tsetResumingAgentTaskId(taskId);
\t\t\tawait resumeAgentTask(taskId);
\t\t\ttoast.success("Agent任务已恢复");
\t\t\tawait loadAgentTasks(false);
\t\t} catch (error: any) {
\t\t\ttoast.error(error?.response?.data?.detail || "恢复Agent任务失败");
\t\t} finally {
\t\t\tsetResumingAgentTaskId(null);
\t\t}
\t};

\tconst handleDeleteAgentTask = async (task: AgentTask) => {
\t\tif (deletingAgentTaskId) return;
\t\tif (!window.confirm(`确定删除审计记录“${task.name || "Agent审计任务"}”吗？关联审计会话也会一并删除。`)) return;
\t\ttry {
\t\t\tsetDeletingAgentTaskId(task.id);
\t\t\tawait deleteAgentTask(task.id);
\t\t\tsetAgentTasks((current) => current.filter((item) => item.id !== task.id));
\t\t\ttoast.success("审计记录已删除");
\t\t} catch (error: any) {
\t\t\ttoast.error(error?.response?.data?.detail || "删除审计记录失败");
\t\t} finally {
\t\t\tsetDeletingAgentTaskId(null);
\t\t}
\t};
"""
text = Path("frontend/src/pages/AuditTasks.tsx").read_text(encoding="utf-8")
if text.count(handler_marker) != 1:
    raise RuntimeError("AuditTasks handler marker mismatch")
Path("frontend/src/pages/AuditTasks.tsx").write_text(text.replace(handler_marker, handlers + handler_marker, 1), encoding="utf-8")

failed_filter = """\t\t\t\t\t\t<Button\n\t\t\t\t\t\t\tsize=\"sm\"\n\t\t\t\t\t\t\tonClick={() => setStatusFilter(\"failed\")}\n\t\t\t\t\t\t\tclassName={`h-10 ${statusFilter === \"failed\" ? \"bg-rose-500/90 border-rose-500/50 text-foreground hover:bg-rose-500\" : \"cyber-btn-outline\"}`}\n\t\t\t\t\t\t>\n\t\t\t\t\t\t\t失败\n\t\t\t\t\t\t</Button>\n"""
replace_once(
    "frontend/src/pages/AuditTasks.tsx",
    failed_filter,
    failed_filter + """\t\t\t\t\t\t<Button\n\t\t\t\t\t\t\tsize=\"sm\"\n\t\t\t\t\t\t\tonClick={() => setStatusFilter(\"cancelled\")}\n\t\t\t\t\t\t\tclassName={`h-10 ${statusFilter === \"cancelled\" ? \"bg-slate-500/90 border-slate-500/50 text-foreground hover:bg-slate-500\" : \"cyber-btn-outline\"}`}\n\t\t\t\t\t\t>\n\t\t\t\t\t\t\t已取消\n\t\t\t\t\t\t</Button>\n""",
)

session_marker = "\t\t\t\t\t\t\t{task.runtime_session_id && (\n"
management_buttons = """\t\t\t\t\t\t\t{["failed", "cancelled", "paused"].includes(task.status) && (
\t\t\t\t\t\t\t\t<Button size="sm" className="cyber-btn-outline h-9" onClick={() => handleResumeAgentTask(task.id)} disabled={resumingAgentTaskId === task.id}>
\t\t\t\t\t\t\t\t\t<RotateCcw className="w-4 h-4 mr-2" />
\t\t\t\t\t\t\t\t\t{resumingAgentTaskId === task.id ? "恢复中..." : "继续审计"}
\t\t\t\t\t\t\t\t</Button>
\t\t\t\t\t\t\t)}
\t\t\t\t\t\t\t{["completed", "failed", "cancelled", "paused"].includes(task.status) && (
\t\t\t\t\t\t\t\t<Button size="sm" className="cyber-btn-outline h-9 text-rose-400 hover:text-rose-300" onClick={() => handleDeleteAgentTask(task)} disabled={deletingAgentTaskId === task.id}>
\t\t\t\t\t\t\t\t\t<Trash2 className="w-4 h-4 mr-2" />
\t\t\t\t\t\t\t\t\t{deletingAgentTaskId === task.id ? "删除中..." : "删除记录"}
\t\t\t\t\t\t\t\t</Button>
\t\t\t\t\t\t\t)}
"""
text = Path("frontend/src/pages/AuditTasks.tsx").read_text(encoding="utf-8")
if text.count(session_marker) != 1:
    raise RuntimeError("AuditTasks session marker mismatch")
Path("frontend/src/pages/AuditTasks.tsx").write_text(text.replace(session_marker, management_buttons + session_marker, 1), encoding="utf-8")

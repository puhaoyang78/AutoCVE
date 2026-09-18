"""
Agent 工具集

提供 Agent 使用的各种工具，包括：
- 基础工具（文件操作、代码搜索）
- 分析工具（模式匹配、数据流分析）
- 外部安全工具（Semgrep、Bandit等）
- 协作工具（Think、Agent通信）
- 报告工具（漏洞报告）
- 智能扫描工具（批量扫描、快速审计）
"""

# 新增：Agent协作工具
from .agent_tools import (
    AgentFinishTool,
    CollectSubAgentResultsTool,
    CreateSubAgentTool,
    RunSubAgentsTool,
    SendMessageTool,
    ViewAgentGraphTool,
    WaitForMessageTool,
)
from .base import AgentTool, ToolResult
from .code_analysis_tool import DataFlowAnalysisTool

# 外部安全工具
from .external_tools import (
    BanditTool,
    GitleaksTool,
    NpmAuditTool,
    OSVScannerTool,
    SafetyTool,
    SemgrepTool,
    TruffleHogTool,
)
from .file_tool import FileReadTool, FileSearchTool, ListFilesTool, ReadManyFilesTool

# 新增：扫描完成工具
from .finish_tool import FinishScanTool
from .interaction_agent_tools import (
    AskUserTool,
    EnterPlanModeTool,
    ExitPlanModeTool,
    TodoWriteTool,
)

# 新增：Kunlun-M 静态代码分析工具 (MIT License)
from .kunlun_tool import KunlunMTool, KunlunPluginTool, KunlunRuleListTool
from .pattern_tool import PatternMatchTool
from .rag_tool import FunctionContextTool, RAGQueryTool, SecurityCodeSearchTool

# 新增：漏洞报告工具
from .reporting_tool import CreateVulnerabilityReportTool

# 新增：通用代码执行工具 (LLM 驱动的 Fuzzing Harness)
from .run_code import ExtractFunctionTool, RunCodeTool

# 多语言代码测试工具
from .sandbox_language import (
    GoTestTool,
    JavaScriptTestTool,
    JavaTestTool,
    PhpTestTool,
    PythonTestTool,
    RubyTestTool,
    ShellTestTool,
    UniversalCodeTestTool,
)
from .sandbox_tool import (
    SandboxHttpTool,
    SandboxManager,
    SandboxTool,
    VulnerabilityVerifyTool,
)

# 漏洞验证专用工具
from .sandbox_vuln import (
    CommandInjectionTestTool,
    DeserializationTestTool,
    PathTraversalTestTool,
    SqlInjectionTestTool,
    SstiTestTool,
    UniversalVulnTestTool,
    XssTestTool,
)
from .shared_catalog import (
    build_agent_skill_tools,
    build_agent_tool_catalog,
    build_shared_agent_tool_catalog,
    shared_skill_library_roots,
)

# 新增：智能扫描工具
from .smart_scan_tool import QuickAuditTool, SmartScanTool

# 新增：思考和推理工具
from .thinking_tool import ReflectTool, ThinkTool

__all__ = [
    # 基础
    "AgentTool",
    "ToolResult",

    # RAG 工具
    "RAGQueryTool",
    "SecurityCodeSearchTool",
    "FunctionContextTool",

    # 代码分析
    "PatternMatchTool",
    "CodeAnalysisTool",
    "DataFlowAnalysisTool",
    "VulnerabilityValidationTool",

    # 文件操作
    "FileReadTool",
    "ReadManyFilesTool",
    "FileSearchTool",
    "ListFilesTool",

    # 沙箱
    "SandboxTool",
    "SandboxHttpTool",
    "VulnerabilityVerifyTool",
    "SandboxManager",

    # 多语言代码测试工具
    "PhpTestTool",
    "PythonTestTool",
    "JavaScriptTestTool",
    "JavaTestTool",
    "GoTestTool",
    "RubyTestTool",
    "ShellTestTool",
    "UniversalCodeTestTool",

    # 漏洞验证专用工具
    "CommandInjectionTestTool",
    "SqlInjectionTestTool",
    "XssTestTool",
    "PathTraversalTestTool",
    "SstiTestTool",
    "DeserializationTestTool",
    "UniversalVulnTestTool",

    # 外部安全工具
    "SemgrepTool",
    "BanditTool",
    "GitleaksTool",
    "NpmAuditTool",
    "SafetyTool",
    "TruffleHogTool",
    "OSVScannerTool",

    # 思考和推理工具
    "ThinkTool",
    "ReflectTool",

    # 漏洞报告工具
    "CreateVulnerabilityReportTool",

    # 扫描完成工具
    "FinishScanTool",

    # Agent协作工具
    "CreateSubAgentTool",
    "SendMessageTool",
    "ViewAgentGraphTool",
    "WaitForMessageTool",
    "AgentFinishTool",
    "RunSubAgentsTool",
    "CollectSubAgentResultsTool",

    # 智能扫描工具
    "SmartScanTool",
    "QuickAuditTool",

    # Kunlun-M 工具 (MIT License - https://github.com/LoRexxar/Kunlun-M)
    "KunlunMTool",
    "KunlunRuleListTool",
    "KunlunPluginTool",

    # 通用代码执行工具 (LLM 驱动的 Fuzzing Harness)
    "RunCodeTool",
    "ExtractFunctionTool",
    "TodoWriteTool",
    "AskUserTool",
    "EnterPlanModeTool",
    "ExitPlanModeTool",
    "build_shared_agent_tool_catalog",
    "build_agent_skill_tools",
    "build_agent_tool_catalog",
    "shared_skill_library_roots",
    "SkillBodyTool",
    "SkillResourceTool",
]

from .skill_tool import SkillBodyTool, SkillResourceTool

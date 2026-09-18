"""LLM-backed data-flow analysis tool."""

import asyncio
import logging

from pydantic import BaseModel, Field

from .base import AgentTool, ToolResult

logger = logging.getLogger(__name__)


class DataFlowAnalysisInput(BaseModel):
    """Data-flow analysis input."""

    source_code: str = Field(description="包含数据源的代码")
    sink_code: str | None = Field(default=None, description="包含数据汇的代码（如危险函数）")
    variable_name: str = Field(description="要追踪的变量名")
    file_path: str = Field(default="unknown", description="文件路径")


class DataFlowAnalysisTool(AgentTool):
    """Use the configured LLM to trace a variable from source to sink."""

    def __init__(self, llm_service):
        super().__init__()
        self.llm_service = llm_service

    @property
    def name(self) -> str:
        return "dataflow_analysis"

    @property
    def description(self) -> str:
        return """分析代码中的数据流，追踪变量从源（如用户输入）到汇（如危险函数）的路径。

使用场景:
- 追踪用户输入如何流向危险函数
- 分析变量是否经过净化处理
- 识别污点传播路径

输入:
- source_code: 包含数据源的代码
- sink_code: 包含数据汇的代码（可选）
- variable_name: 要追踪的变量名
- file_path: 文件路径"""

    @property
    def args_schema(self):
        return DataFlowAnalysisInput

    async def _execute(
        self,
        source_code: str,
        variable_name: str,
        sink_code: str | None = None,
        file_path: str = "unknown",
        **kwargs,
    ) -> ToolResult:
        analysis_prompt = f"""分析以下代码中变量 '{variable_name}' 的数据流。

源代码:
```
{source_code}
```
"""
        if sink_code:
            analysis_prompt += f"""
汇代码（可能的危险函数）:
```
{sink_code}
```
"""

        analysis_prompt += f"""
请分析:
1. 变量 '{variable_name}' 的来源是什么？（用户输入、配置、数据库等）
2. 变量在传递过程中是否经过了净化/验证？
3. 变量最终流向了哪些危险函数？
4. 是否存在安全风险？

请返回 JSON 格式的分析结果，包含:
- source_type: 数据源类型
- sanitized: 是否经过净化
- sanitization_methods: 使用的净化方法
- dangerous_sinks: 流向的危险函数列表
- risk_level: 风险等级 (high/medium/low/none)
- explanation: 详细解释
- recommendation: 建议
"""

        try:
            result = await asyncio.wait_for(
                self.llm_service.analyze_code_with_custom_prompt(
                    code=source_code,
                    language="text",
                    custom_prompt=analysis_prompt,
                ),
                timeout=120.0,
            )
        except TimeoutError:
            logger.warning("数据流分析 LLM 调用超时")
            return ToolResult(
                success=False,
                error="数据流分析 LLM 调用超时（120 秒）",
            )
        except Exception as exc:
            logger.exception("数据流分析 LLM 调用失败")
            return ToolResult(
                success=False,
                error=f"数据流分析 LLM 调用失败: {exc}",
            )

        if not result:
            return ToolResult(
                success=False,
                error="数据流分析 LLM 未返回有效结果",
            )

        if isinstance(result, dict):
            if not result.get("source_type") and not result.get("risk_level"):
                return ToolResult(
                    success=False,
                    error="数据流分析 LLM 返回结果缺少 source_type 和 risk_level",
                )

            output_parts = [f"📊 数据流分析结果 - 变量: {variable_name}\n"]

            if result.get("source_type"):
                output_parts.append(f"数据源: {result.get('source_type')}")
            if result.get("sanitized") is not None:
                sanitized = "✅ 是" if result.get("sanitized") else "❌ 否"
                output_parts.append(f"是否净化: {sanitized}")
            if result.get("sanitization_methods"):
                methods = result.get("sanitization_methods", [])
                if isinstance(methods, list):
                    output_parts.append(f"净化方法: {', '.join(methods)}")
                else:
                    output_parts.append(f"净化方法: {methods}")
            if result.get("dangerous_sinks"):
                sinks = result.get("dangerous_sinks", [])
                if isinstance(sinks, list):
                    output_parts.append(f"危险函数: {', '.join(sinks)}")
                else:
                    output_parts.append(f"危险函数: {sinks}")
            if result.get("risk_level"):
                risk_icons = {
                    "high": "🔴",
                    "medium": "🟠",
                    "low": "🟡",
                    "none": "🟢",
                }
                risk_level = str(result.get("risk_level") or "")
                output_parts.append(
                    f"风险等级: {risk_icons.get(risk_level, '⚪')} {risk_level.upper()}"
                )
            if result.get("explanation"):
                output_parts.append(f"\n分析: {result.get('explanation')}")
            if result.get("recommendation"):
                output_parts.append(f"\n建议: {result.get('recommendation')}")
        else:
            output_parts = [
                f"📊 数据流分析结果 - 变量: {variable_name}\n",
                str(result),
            ]

        return ToolResult(
            success=True,
            data="\n".join(output_parts),
            metadata={
                "variable": variable_name,
                "file_path": file_path,
                "analysis": result,
            },
        )

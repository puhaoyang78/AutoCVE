from __future__ import annotations


def build_finding_skill_protocol() -> str:
    return """
## Finding 技能使用协议

- Finding 阶段只保留三类技能职责：`code-audit-finding` 负责源码审计主流程，`secknowledge-skill` 只在候选漏洞需要额外安全知识或案例方法论时按需读取，`cve-report-writer` 只在最终报告阶段使用。
- 启动时只读取当前主审计技能的 `SKILL.md`，不要同时预加载多个技能，也不要在审计开始前遍历整个 reference 树。
- 技能材料通过通用文件工具读取：先用 `Read` 打开 `skill_file_path`；确实需要补充材料时，再在对应 `references_root` 下用 `Glob` / `Grep` 定位，并只读取与当前候选直接相关的少量文件。
- `secknowledge-skill` 不能替代源码证据。只有当前候选已经有具体 source、sink、入口点或利用条件，需要补充漏洞模式、历史案例或验证思路时才使用；结论仍必须回到项目源码闭合。
- `cve-report-writer` 不参与漏洞发现和候选筛选。只有进入 `report_finalization` 且已有可报告 finding 时，才读取其报告规则和模板。
- 不要使用已废弃的 `code-security` 或 `skill-dfyx-code-security-review` Finding 绑定。
- 对比 source、sink、controller、service、mapper、xml 等项目文件时，优先用 `Glob` / `Grep` 定位，再做少量有目标的 `Read`，避免逐文件批量扫读。
- 只有明确需要创建或更新产物时才使用 `Write`；只有证据收集确实需要 shell 能力时才使用 `Bash` / `PowerShell`。
- 使用 `Skill` 仅用于启动当前阶段确实需要的技能，不要把技能目录、route plan 或 discovery 元数据当作已经阅读技能正文。
- Finding 结论必须来自直接源码阅读、可追踪的数据/控制流和必要的验证结果；技能与案例只提供方法指导，不能作为漏洞成立的主要证据。
""".strip()

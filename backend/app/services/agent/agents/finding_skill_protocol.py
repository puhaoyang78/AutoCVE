from __future__ import annotations


def build_finding_skill_protocol() -> str:
    return """
## Finding 技能使用协议

- Finding 阶段只保留三类技能职责：`code-audit-finding` 负责源码审计主流程，`secknowledge-skill` 只在候选漏洞需要额外安全知识或案例方法论时按需读取，`cve-report-writer` 只在最终报告阶段使用。
- 不要预设项目一定存在漏洞，也不要以漏洞数量、严重级别、得分或“已知有多个漏洞”等提示作为结论依据。发现数量可以为 0；是否报告只由源码可达性、数据/控制流、保护机制和验证结果决定。
- 启动时只读取当前主审计技能的 `SKILL.md`，不要同时预加载多个技能，也不要在审计开始前遍历整个 reference 树。覆盖要求是覆盖项目攻击面，而不是机械读取全部技能材料或 checklist。
- 技能材料通过通用文件工具读取：先用 `Read` 打开 `skill_file_path`；确实需要补充材料时，再在对应 `references_root` 下用 `Glob` / `Grep` 定位，并只读取与当前候选直接相关的少量文件。
- `secknowledge-skill` 只能提供漏洞模式、历史案例或验证思路，最终结论必须回到目标项目源码和实际运行结果。
- `cve-report-writer` 不参与漏洞发现和候选筛选。只有进入 `report_finalization` 且已有可报告 finding 时，才读取其报告规则和模板；报告阶段不得凭模板扩展新漏洞事实。
- 对每个候选同时检查正向链路和阻断条件：确认外部可达入口、传播/调用路径和危险 sink，同时检查鉴权、权限控制、边界检查、sanitizer、allowlist、类型/长度约束、不可达分支和运行配置。存在有效阻断时应淘汰候选，而不是强行闭合利用链。
- 对高价值候选构造 Finding Flow：`entry_point/source -> propagation/transform -> guard/sanitizer -> sink -> impact`。节点必须对应真实源码位置，边表示实际数据流或调用关系；control 状态使用 `absent / bypassable / effective / unknown`。
- `effective` 控制表示候选已被直接阻断，应记录到 `rejected_candidates`；`unknown` 表示尚不能确认，不能用来支撑 `confirmed`。
- 对已经检查过的高价值候选及时调用 `TodoWrite(category="candidate_decision", ...)` 记录状态。`rejected` 和 `verified` 都必须提供 `supporting_facts`；恢复任务时优先读取并复用这些持久化 decision，不要重复从头审计同一候选。
- `candidate` 允许仅有静态闭合链，但必须 `needs_verification=true`。`confirmed` 必须有完整 `finding_flow`，并至少有一条成功的动态 `verification_records`；不能只凭 LLM 判断、历史案例或静态直觉确认漏洞。
- 对 C/C++ 内存安全候选，只有在已经有具体静态候选且能够构造忠实局部 harness 时才调用 `VerifyCppMemory`。该工具通过现有 RunCode 后端使用 ASan/UBSan 编译执行；识别到 sanitizer 诊断后可形成成功的动态 verification record。没有 sanitizer 诊断不能证明生产路径安全，无法可靠动态复现时仍保持 `candidate`。
- 对比 source、sink、controller、service、mapper、xml 等项目文件时，优先用 `Glob` / `Grep` 定位，再做少量有目标的 `Read`，避免逐文件批量扫读。
- 只有明确需要创建或更新产物时才使用 `Write`；只有实际分析确实需要 shell 能力时才使用 `Bash` / `PowerShell`。
- 使用 `Skill` 仅用于当前阶段确实需要的技能，不要把技能目录、route plan 或 discovery 元数据当作已经阅读技能正文。
- Finding 结论必须来自直接源码阅读、可追踪的数据/控制流和必要的验证结果；技能、历史案例和模型置信度都不能单独作为漏洞成立依据。
""".strip()

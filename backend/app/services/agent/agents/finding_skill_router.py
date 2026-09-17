from __future__ import annotations

from typing import Any, Dict, Iterable, List, Sequence, Set


LANGUAGE_RESOURCE_MAP: Dict[str, List[str]] = {
    "c": ["references/checklists/c_cpp.md", "references/languages/c_cpp.md"],
    "c++": ["references/checklists/c_cpp.md", "references/languages/c_cpp.md"],
    "cpp": ["references/checklists/c_cpp.md", "references/languages/c_cpp.md"],
    "c#": ["references/checklists/dotnet.md", "references/languages/dotnet.md"],
    ".net": ["references/checklists/dotnet.md", "references/languages/dotnet.md"],
    "dotnet": ["references/checklists/dotnet.md", "references/languages/dotnet.md"],
    "go": ["references/checklists/go.md", "references/languages/go.md"],
    "golang": ["references/checklists/go.md", "references/languages/go.md"],
    "java": ["references/checklists/java.md", "references/languages/java.md"],
    "javascript": ["references/checklists/javascript.md", "references/languages/javascript.md"],
    "node": ["references/checklists/javascript.md", "references/languages/javascript.md"],
    "node.js": ["references/checklists/javascript.md", "references/languages/javascript.md"],
    "php": ["references/checklists/php.md", "references/languages/php.md"],
    "python": ["references/checklists/python.md", "references/languages/python.md"],
    "ruby": ["references/checklists/ruby.md", "references/languages/ruby.md"],
    "rust": ["references/checklists/rust.md", "references/languages/rust.md"],
}

FRAMEWORK_RESOURCE_MAP: Dict[str, List[str]] = {
    "django": ["references/frameworks/django.md"],
    "dotnet": ["references/frameworks/dotnet.md"],
    "asp.net": ["references/frameworks/dotnet.md"],
    "express": ["references/frameworks/express.md"],
    "fastapi": ["references/frameworks/fastapi.md"],
    "flask": ["references/frameworks/flask.md"],
    "gin": ["references/frameworks/gin.md"],
    "graphql": ["references/security/graphql.md"],
    "java web": ["references/frameworks/java_web_framework.md"],
    "koa": ["references/frameworks/koa.md"],
    "laravel": ["references/frameworks/laravel.md"],
    "mybatis": ["references/frameworks/mybatis_security.md"],
    "nest": ["references/frameworks/nest_fastify.md"],
    "fastify": ["references/frameworks/nest_fastify.md"],
    "rails": ["references/frameworks/rails.md"],
    "rust web": ["references/frameworks/rust_web.md"],
    "spring": ["references/frameworks/spring.md"],
}

SECURITY_ROUTE_RULES: List[Dict[str, Any]] = [
    {
        "keywords": {"auth", "authorization", "authentication", "idor", "jwt", "login", "oauth", "permission", "rbac", "role", "session", "tenant", "ownership"},
        "resources": ["references/security/authentication_authorization.md", "references/security/business_logic.md"],
        "case_candidates": ["references/wooyun/unauthorized-access.md", "references/wooyun/logic-flaws.md"],
    },
    {
        "keywords": {"archive", "download", "export", "file", "import", "path", "template", "traversal", "upload", "zip"},
        "resources": ["references/security/file_operations.md"],
        "case_candidates": ["references/wooyun/file-traversal.md", "references/wooyun/file-upload.md"],
    },
    {
        "keywords": {"body", "form", "input", "param", "parameter", "parser", "payload", "query", "schema", "serialize", "validation"},
        "resources": ["references/security/input_validation.md"],
    },
    {
        "keywords": {"api", "endpoint", "gateway", "graphql", "grpc", "http", "rest", "router"},
        "resources": ["references/security/api_security.md", "references/security/api_gateway_proxy.md"],
    },
    {
        "keywords": {"approval", "balance", "concurrent", "duplicate", "idempot", "inventory", "order", "payment", "queue", "race", "retry", "stock", "wallet"},
        "resources": ["references/security/race_conditions.md"],
        "case_candidates": ["references/wooyun/logic-flaws.md"],
    },
    {"keywords": {"internal", "service", "trust", "microservice", "signature"}, "resources": ["references/security/cross_service_trust.md"]},
    {"keywords": {"async", "consumer", "kafka", "mq", "queue", "rabbitmq", "stream"}, "resources": ["references/security/message_queue_async.md"]},
    {"keywords": {"oauth", "oidc", "saml"}, "resources": ["references/security/oauth_oidc_saml.md"]},
    {"keywords": {"realtime", "socket", "websocket", "ws"}, "resources": ["references/security/realtime_protocols.md"]},
    {"keywords": {"cron", "job", "schedule", "scheduler", "task"}, "resources": ["references/security/scheduled_tasks.md"]},
    {"keywords": {"function", "lambda", "serverless"}, "resources": ["references/security/serverless.md"]},
    {"keywords": {"agent", "llm", "model", "prompt", "rag"}, "resources": ["references/security/llm_security.md"]},
]


def _stringify(value: Any) -> Iterable[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        items: List[str] = []
        for nested_value in value.values():
            items.extend(_stringify(nested_value))
        return items
    if isinstance(value, (list, tuple, set)):
        items: List[str] = []
        for nested_value in value:
            items.extend(_stringify(nested_value))
        return items
    return [str(value)]


def _normalized_tokens(values: Iterable[Any]) -> Set[str]:
    tokens: Set[str] = set()
    for value in values:
        for raw in _stringify(value):
            lowered = raw.lower()
            for piece in lowered.replace("/", " ").replace("\\", " ").replace("-", " ").replace("_", " ").split():
                token = piece.strip(".,:;()[]{}'\"")
                if token:
                    tokens.add(token)
            if lowered:
                tokens.add(lowered)
    return tokens


def _append_unique(items: List[str], values: Sequence[str]) -> None:
    for value in values:
        if value not in items:
            items.append(value)


def resolve_finding_skill_routes(context: Dict[str, Any], skill_context: Dict[str, Any] | None = None) -> Dict[str, Any]:
    recon_data = context.get("recon_data", {}) or {}
    project_profile = recon_data.get("project_profile", {}) or {}
    project_info = context.get("project_info", {}) or {}
    route_plan = (skill_context or {}).get("route_plan") or {}

    language_tokens = _normalized_tokens([project_profile.get("languages", []), project_info.get("languages", [])])
    framework_tokens = _normalized_tokens([project_profile.get("frameworks", []), project_info.get("frameworks", [])])
    signal_tokens = _normalized_tokens(
        [
            context.get("task"),
            context.get("task_context"),
            context.get("focus_vulnerabilities", []),
            recon_data.get("summary"),
            recon_data.get("priority_paths", []),
            recon_data.get("entry_points", []),
            context.get("target_files", []),
        ]
    )

    required: List[str] = []
    optional: List[str] = []
    cases: List[str] = []

    for token in sorted(language_tokens):
        resources = LANGUAGE_RESOURCE_MAP.get(token)
        if resources:
            _append_unique(required, resources)

    for token in sorted(framework_tokens | signal_tokens):
        resources = FRAMEWORK_RESOURCE_MAP.get(token)
        if resources:
            _append_unique(required, resources)

    for rule in SECURITY_ROUTE_RULES:
        if signal_tokens.intersection(rule["keywords"]) or framework_tokens.intersection(rule["keywords"]):
            _append_unique(required, rule["resources"])
            _append_unique(cases, rule.get("case_candidates", []))

    if required:
        _append_unique(optional, ["references/checklists/universal.md"])

    return {
        "primary_skill": route_plan.get("primary_skill"),
        "secondary_skills": list(route_plan.get("secondary_skills", [])),
        "mandatory_reads": required,
        "recommended_reads": optional,
        "case_candidates": cases,
        "progressive_disclosure": ["references/wooyun/INDEX.md", "references/cases/real_world_vulns.md"],
        "selection_reason": list(route_plan.get("selection_reason", [])),
    }

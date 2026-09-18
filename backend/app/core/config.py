import secrets
from pathlib import Path

from pydantic import AnyHttpUrl, Field, ValidationInfo, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_MANAGED_PROJECTS_ROOT = str(Path(__file__).resolve().parents[3] / "projects")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(case_sensitive=True, env_file=".env", extra="ignore")

    PROJECT_NAME: str = "AutoCVE"
    API_V1_STR: str = "/api/v1"

    SECRET_KEY: str = Field(default_factory=lambda: secrets.token_urlsafe(48))
    ENABLE_DEMO_DATA: bool = False
    @field_validator("SECRET_KEY", mode="before")
    @classmethod
    def normalize_secret_key(cls, v: str | None) -> str:
        value = str(v or "").strip()
        if not value or value == "changethis_in_production_to_a_long_random_string":
            return secrets.token_urlsafe(48)
        return value

    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 8

    BACKEND_CORS_ORIGINS: list[AnyHttpUrl] = []

    @field_validator("BACKEND_CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: str | list[str]) -> list[str] | str:
        if isinstance(v, str) and not v.startswith("["):
            return [item.strip() for item in v.split(",") if item.strip()]
        if isinstance(v, (list, str)):
            return v
        raise ValueError(v)

    POSTGRES_SERVER: str = "db"
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "postgres"
    POSTGRES_DB: str = "autocve"
    DATABASE_URL: str | None = None

    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def assemble_db_connection(cls, v: str | None, info: ValidationInfo) -> str:
        if isinstance(v, str):
            return v
        values = info.data
        return (
            f"postgresql+asyncpg://{values.get('POSTGRES_USER')}:{values.get('POSTGRES_PASSWORD')}"
            f"@{values.get('POSTGRES_SERVER')}/{values.get('POSTGRES_DB')}"
        )

    LLM_PROVIDER: str = "openai"
    LLM_API_KEY: str | None = None
    LLM_MODEL: str | None = None
    LLM_BASE_URL: str | None = None
    LLM_TIMEOUT: int = 150
    LLM_TEMPERATURE: float = 0.1
    LLM_MAX_TOKENS: int = 4096
    LLM_ENDPOINT_PROTOCOL: str = "openai_chat"
    LLM_TOOL_MESSAGE_FORMAT: str = "auto"
    LLM_FIRST_TOKEN_TIMEOUT: int = 30
    LLM_STREAM_TIMEOUT: int = 60
    SUB_AGENT_TIMEOUT_SECONDS: int = 600
    TOOL_TIMEOUT_SECONDS: int = 60

    OPENAI_API_KEY: str | None = None
    OPENAI_BASE_URL: str | None = None
    GEMINI_API_KEY: str | None = None
    CLAUDE_API_KEY: str | None = None
    QWEN_API_KEY: str | None = None
    DEEPSEEK_API_KEY: str | None = None
    ZHIPU_API_KEY: str | None = None
    MOONSHOT_API_KEY: str | None = None
    BAIDU_API_KEY: str | None = None
    MINIMAX_API_KEY: str | None = None
    DOUBAO_API_KEY: str | None = None
    MIMO_API_KEY: str | None = None
    OLLAMA_BASE_URL: str | None = "http://localhost:11434/v1"

    GITHUB_TOKEN: str | None = None
    GITLAB_TOKEN: str | None = None
    GITEA_TOKEN: str | None = None

    MAX_ANALYZE_FILES: int = 0
    MAX_FILE_SIZE_BYTES: int = 200 * 1024
    LLM_CONCURRENCY: int = 3
    LLM_GAP_MS: int = 2000
    ZIP_STORAGE_PATH: str = "./uploads/zip_files"
    PROJECT_SOURCE_STORAGE_PATH: str = "./uploads/project_sources"
    MANAGED_PROJECTS_ROOT: str = DEFAULT_MANAGED_PROJECTS_ROOT
    OUTPUT_LANGUAGE: str = "zh-CN"

    CHECKMARX_FEATURE_ENABLED: bool = False
    CHECKMARX_BASE_URL: str | None = None
    CHECKMARX_CLIENT_ID: str = "resource_owner_sast_client"
    CHECKMARX_CLIENT_SECRET: str | None = None
    CHECKMARX_SCOPE: str = "access_control_api sast_api"
    CHECKMARX_PRESET_ID: int = 36
    CHECKMARX_FORCE_SCAN: bool = True
    CHECKMARX_IS_INCREMENTAL: bool = False
    CHECKMARX_TIMEOUT_CONNECT: int = 10
    CHECKMARX_TIMEOUT_READ: int = 30
    CHECKMARX_SCAN_UPLOAD_READ_TIMEOUT: int = 300
    CHECKMARX_SCAN_TIMEOUT: int = 3600
    CHECKMARX_SCAN_POLL_INTERVAL: int = 10
    CHECKMARX_SAST_ACCEPT_API_VERSION: str = "default"
    CHECKMARX_HELP_SAST_ACCEPT_API_VERSION: str = "default"
    CHECKMARX_HELP_RESULTS_DELAY: float = 0.25
    CHECKMARX_HELP_RESULTS_429_RETRIES: int = 12
    CHECKMARX_HELP_RESULTS_429_BASE_WAIT: float = 2.0
    CHECKMARX_UPLOAD_DIR: str = "./uploads/checkmarx"
    CHECKMARX_WORKFLOW_ENABLED: bool = True
    WORKFLOW_URL: str | None = None
    WORKFLOW_API_TOKEN: str | None = None
    WORKFLOW_USER: str = "autocve"
    WORKFLOW_TIMEOUT: float = 300.0

    EMBEDDING_PROVIDER: str = "openai"
    EMBEDDING_MODEL: str = "text-embedding-3-small"
    EMBEDDING_API_KEY: str | None = None
    EMBEDDING_BASE_URL: str | None = None
    VECTOR_DB_PATH: str = "./data/vector_db"

    SSH_CONFIG_PATH: str = "./data/ssh"
    SSH_CLONE_TIMEOUT: int = 300
    SSH_TEST_TIMEOUT: int = 15
    SSH_CONNECT_TIMEOUT: int = 10

    AGENT_MAX_ITERATIONS: int = 50
    AGENT_TOKEN_BUDGET: int = 100000
    AGENT_TIMEOUT_SECONDS: int = 1800
    AGENT_EVENT_QUEUE_MAX_SIZE: int = 1000
    AGENT_TOKEN_EVENT_CHUNK_SIZE: int = 20
    AGENT_TOKEN_EVENT_FLUSH_INTERVAL_MS: int = 100
    AGENT_TASK_EXECUTION_MODE: str = "inline"
    AGENT_TASK_QUEUE_NAME: str = "autocve:arq:agent_tasks"
    AGENT_WORKER_CONCURRENCY: int = 2
    AGENT_WORKER_JOB_TIMEOUT_SECONDS: int = 3600
    AGENT_WORKER_MAX_TRIES: int = 2
    AGENT_EVENT_STREAM_ENABLED: bool = False
    AGENT_EVENT_STREAM_MAXLEN: int = 5000
    AGENT_EVENT_STREAM_BLOCK_MS: int = 15000
    ONE_CLICK_CVE_EXECUTION_MODE: str = "inline"
    ONE_CLICK_CVE_QUEUE_NAME: str = "autocve:arq:one_click_cve_batches"
    ONE_CLICK_CVE_WORKER_CONCURRENCY: int = 1
    ONE_CLICK_CVE_WORKER_JOB_TIMEOUT_SECONDS: int = 10800
    ONE_CLICK_CVE_WORKER_MAX_TRIES: int = 1
    ONE_CLICK_CVE_MAX_REPOSITORY_SIZE_KB: int = 512000
    ONE_CLICK_CVE_AGENT_TIMEOUT_SECONDS: int = 3000
    AUDIT_SESSION_RESUME_TIMEOUT_SECONDS: int = 3000
    REDIS_URL: str = "redis://localhost:6379/0"
    SANDBOX_IMAGE: str = "autocve-sandbox:latest"
    SANDBOX_MEMORY_LIMIT: str = "512m"
    SANDBOX_CPU_LIMIT: float = 1.0
    SANDBOX_TIMEOUT: int = 60
    SANDBOX_NETWORK_MODE: str = "none"
    SANDBOX_CAP_DROP: str = (
        "SYS_ADMIN,NET_ADMIN,SYS_PTRACE,SYS_RAWIO,SYS_MODULE,SYS_BOOT,"
        "MKNOD,AUDIT_WRITE,AUDIT_CONTROL,SETFCAP,MAC_OVERRIDE,MAC_ADMIN"
    )
    SANDBOX_NO_NEW_PRIVILEGES: bool = True

    RAG_CHUNK_SIZE: int = 1500
    RAG_CHUNK_OVERLAP: int = 50
    RAG_TOP_K: int = 10



settings = Settings()

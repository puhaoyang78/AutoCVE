from pathlib import Path

path = Path("backend/env.example")
text = path.read_text(encoding="utf-8")
replacements = {
    "AGENT_MAX_ITERATIONS=5": "AGENT_MAX_ITERATIONS=50",
    "AGENT_TIMEOUT=1800": "AGENT_TIMEOUT_SECONDS=1800",
    "VECTOR_DB_TYPE=chroma\n\n# ChromaDB 配置（本地模式）\nCHROMA_PERSIST_DIRECTORY=./data/chroma": "# 向量数据库持久化目录\nVECTOR_DB_PATH=./data/vector_db",
    "SANDBOX_NETWORK_DISABLED=true": "SANDBOX_NETWORK_MODE=none",
    "SANDBOX_TIMEOUT=30": "SANDBOX_TIMEOUT=60",
}
for old, new in replacements.items():
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"expected one occurrence of {old!r}, found {count}")
    text = text.replace(old, new, 1)
path.write_text(text, encoding="utf-8")

"""
RAG (Retrieval-Augmented Generation) 系统
用于代码索引和语义检索

🔥 v2.0 改进：
- 支持嵌入模型变更检测和自动重建
- 支持增量索引更新（基于文件 hash）
- 支持索引版本控制和状态查询
"""

from .embeddings import EmbeddingService
from .indexer import (
    INDEX_VERSION,
    CodeIndexer,
    IndexingProgress,
    IndexingResult,
    IndexStatus,
    IndexUpdateMode,
)
from .retriever import CodeRetriever
from .splitter import CodeChunk, CodeSplitter

__all__ = [
    "CodeSplitter",
    "CodeChunk",
    "EmbeddingService",
    "CodeIndexer",
    "CodeRetriever",
    "IndexingProgress",
    "IndexingResult",
    "IndexStatus",
    "IndexUpdateMode",
    "INDEX_VERSION",
]


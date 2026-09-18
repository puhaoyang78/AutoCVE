"""
LLM 服务模块

提供统一的 LLM 调用接口，支持：
- 多提供商支持（OpenAI, Claude, Gemini, DeepSeek 等）
- Prompt Caching（减少 Token 消耗）
- Memory Compression（对话历史压缩）
- 流式输出
- 智能重试
"""

from .memory_compressor import MemoryCompressor
from .prompt_cache import (
    CacheConfig,
    CacheStats,
    CacheStrategy,
    PromptCacheManager,
    estimate_tokens,
    prompt_cache_manager,
)
from .service import LLMService
from .types import (
    LLMConfig,
    LLMError,
    LLMMessage,
    LLMProvider,
    LLMRequest,
    LLMResponse,
    LLMUsage,
)

__all__ = [
    # Service
    "LLMService",
    # Types
    "LLMConfig",
    "LLMProvider",
    "LLMMessage",
    "LLMRequest",
    "LLMResponse",
    "LLMUsage",
    "LLMError",
    # Prompt Cache
    "PromptCacheManager",
    "CacheConfig",
    "CacheStrategy",
    "CacheStats",
    "prompt_cache_manager",
    "estimate_tokens",
    # Memory Compression
    "MemoryCompressor",
]

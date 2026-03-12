"""LLM management with OpenAI-compatible providers for local/cloud models."""

from .manager import LLMGenerationError, LLMManager, LLMModelAdapter, build_summary_model_adapter

__all__ = [
    "LLMGenerationError",
    "LLMManager",
    "LLMModelAdapter",
    "build_summary_model_adapter",
]

"""LLM management with OpenAI-compatible providers for local/cloud models."""

from .manager import LLMManager, build_summary_model_adapter

__all__ = ["LLMManager", "build_summary_model_adapter"]


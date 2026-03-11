from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass

from config import LLMConfig
from core.model_adapter import ModelAdapter, PromptRegistry, PromptTemplate

from .openai_compatible_client import OpenAICompatibleClient
from .types import LLMRequest

DEFAULT_SYSTEM_PROMPT = "你是客服工单系统的助手，输出简洁、准确、可执行。"


@dataclass(frozen=True)
class LLMManager:
    config: LLMConfig
    client: OpenAICompatibleClient

    @classmethod
    def from_config(cls, config: LLMConfig) -> LLMManager:
        client = OpenAICompatibleClient(
            base_url=config.base_url,
            api_key=config.api_key,
            timeout_seconds=config.timeout_seconds,
        )
        return cls(config=config, client=client)

    def generate(self, prompt: str, *, system_prompt: str = DEFAULT_SYSTEM_PROMPT) -> str:
        request = LLMRequest(
            model=self.config.model,
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=self.config.temperature,
            max_tokens=self.config.max_tokens,
        )
        return self.client.complete(request)

    def generate_stream(
        self, prompt: str, *, system_prompt: str = DEFAULT_SYSTEM_PROMPT
    ) -> Iterator[str]:
        request = LLMRequest(
            model=self.config.model,
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=self.config.temperature,
            max_tokens=self.config.max_tokens,
        )
        return self.client.stream_complete(request)


class OpenAICompatibleProvider:
    name = "openai_compatible"

    def __init__(self, manager: LLMManager) -> None:
        self._manager = manager

    def complete(self, prompt: str) -> str:
        return self._manager.generate(prompt)


def build_summary_model_adapter(config: LLMConfig) -> ModelAdapter | None:
    if not config.enabled:
        return None
    provider = OpenAICompatibleProvider(LLMManager.from_config(config))
    registry = PromptRegistry(
        [
            PromptTemplate(
                task="intake_summary",
                version="v1",
                template=(
                    "请为客服 intake 总结以下工单，输出一段话：\n"
                    "- 工单对象: {ticket}\n"
                ),
            ),
            PromptTemplate(
                task="case_summary",
                version="v1",
                template=(
                    "请为客服 case 总结以下工单，输出一段话：\n"
                    "- 工单对象: {ticket}\n"
                    "- 事件时间线: {timeline}\n"
                ),
            ),
            PromptTemplate(
                task="wrap_up_summary",
                version="v1",
                template=(
                    "请生成收尾摘要：\n"
                    "- 工单对象: {ticket}\n"
                    "- 结论: {resolution}\n"
                ),
            ),
        ]
    )
    return ModelAdapter([provider], registry)


from __future__ import annotations

from core.summary_engine import SummaryEngine
from llm.manager import LLMGenerationError
from storage.models import Ticket


def _ticket() -> Ticket:
    return Ticket(
        ticket_id="TCK-TEST-001",
        channel="wecom",
        session_id="sess-1",
        thread_id="thread-1",
        customer_id=None,
        title="道闸故障",
        latest_message="道闸无法抬杆",
        intent="repair",
        priority="P2",
        status="open",
        queue="support",
        assignee=None,
        needs_handoff=False,
    )


class _TraceableSuccessAdapter:
    def generate(
        self,
        task: str,
        variables: dict[str, str],
        *,
        preferred_provider: str | None = None,
    ) -> str:
        _ = task
        _ = variables
        _ = preferred_provider
        return "ignored"

    def generate_with_trace(
        self,
        task: str,
        variables: dict[str, str],
        *,
        preferred_provider: str | None = None,
        prompt_version: str | None = None,
        system_prompt: str = "你是客服助手",
    ) -> tuple[str, dict[str, object]]:
        _ = preferred_provider
        _ = prompt_version
        _ = system_prompt
        return (
            f"AI摘要: {variables.get('ticket')}",
            {
                "provider": "openai_compatible",
                "model": "qwen3.5:9b",
                "prompt_key": task,
                "prompt_version": "v1",
                "latency_ms": 23,
                "request_id": "req-001",
                "token_usage": {"total_tokens": 12},
                "retry_count": 0,
                "success": True,
                "error": None,
                "fallback_used": False,
            },
        )


class _TraceableFailAdapter:
    def generate(
        self,
        task: str,
        variables: dict[str, str],
        *,
        preferred_provider: str | None = None,
    ) -> str:
        _ = task
        _ = variables
        _ = preferred_provider
        raise RuntimeError("should not be called")

    def generate_with_trace(
        self,
        task: str,
        variables: dict[str, str],
        *,
        preferred_provider: str | None = None,
        prompt_version: str | None = None,
        system_prompt: str = "你是客服助手",
    ) -> tuple[str, dict[str, object]]:
        _ = variables
        _ = preferred_provider
        _ = prompt_version
        _ = system_prompt
        raise LLMGenerationError(
            f"{task} failed",
            trace_metadata={
                "provider": "openai_compatible",
                "model": "qwen3.5:9b",
                "prompt_key": task,
                "prompt_version": "v1",
                "latency_ms": 110,
                "request_id": "req-failed",
                "token_usage": None,
                "retry_count": 2,
                "success": False,
                "error": "upstream timeout",
                "fallback_used": True,
                "degraded": True,
            },
        )


def test_summary_engine_exposes_llm_trace_metadata_on_success() -> None:
    engine = SummaryEngine(model_adapter=_TraceableSuccessAdapter())
    summary = engine.case_summary(_ticket(), [])
    trace = engine.last_generation_metadata()

    assert summary.startswith("AI摘要")
    assert trace["provider"] == "openai_compatible"
    assert trace["prompt_version"] == "v1"
    assert trace["success"] is True
    assert trace["degraded"] is False


def test_summary_engine_fallback_preserves_failure_metadata() -> None:
    engine = SummaryEngine(model_adapter=_TraceableFailAdapter())
    summary = engine.case_summary(_ticket(), [])
    trace = engine.last_generation_metadata()

    assert "工单TCK-TEST-001" in summary
    assert trace["success"] is False
    assert trace["fallback_used"] is True
    assert trace["degraded"] is True
    assert trace["error"] == "upstream timeout"

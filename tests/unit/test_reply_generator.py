from __future__ import annotations

from core.handoff_manager import HandoffDecision
from core.intent_router import IntentDecision
from core.recommended_actions_engine import ActionEvidence, RecommendedAction
from core.reply_generator import ReplyGenerator
from llm.manager import LLMGenerationError
from storage.models import KBDocument, Ticket, TicketEvent


def _ticket() -> Ticket:
    return Ticket(
        ticket_id="TCK-REPLY-001",
        channel="wecom",
        session_id="sess-reply-001",
        thread_id="thread-reply-001",
        customer_id=None,
        title="停车场道闸故障",
        latest_message="道闸抬杆失败",
        intent="repair",
        priority="P2",
        status="pending",
        queue="support",
        assignee="u_ops_01",
        needs_handoff=False,
    )


def _docs() -> list[KBDocument]:
    return [
        KBDocument(
            doc_id="doc-case-001",
            source_type="history_case",
            title="道闸故障处理案例",
            content="检查控制器供电并复位",
            score=0.92,
        )
    ]


def _recommendations() -> list[RecommendedAction]:
    return [
        RecommendedAction(
            action="联系现场工程师",
            reason="疑似硬件故障，需要现场排查",
            source="history_case:doc-case-001",
            risk="响应延迟风险",
            confidence=0.88,
            evidence=(ActionEvidence(doc_id="doc-case-001", source_type="history_case"),),
        )
    ]


def _events() -> list[TicketEvent]:
    return [
        TicketEvent(
            event_id="evt-reply-1",
            ticket_id="TCK-REPLY-001",
            event_type="ticket_created",
            actor_type="system",
            actor_id="ticket-api",
        ),
        TicketEvent(
            event_id="evt-reply-2",
            ticket_id="TCK-REPLY-001",
            event_type="ticket_assigned",
            actor_type="agent",
            actor_id="u_ops_01",
        ),
    ]


class _JsonReplyAdapter:
    def __init__(self, *, reply_text: str) -> None:
        self._reply_text = reply_text

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
        return (
            f'{{"reply_text":"{self._reply_text}"}}',
            {
                "provider": "openai_compatible",
                "model": "qwen3.5:9b",
                "prompt_key": task,
                "prompt_version": "v1",
                "latency_ms": 18,
                "request_id": "req-reply-001",
                "token_usage": {"total_tokens": 25},
                "retry_count": 0,
                "success": True,
                "fallback_used": False,
            },
        )


class _ProviderFailAdapter:
    def generate_with_trace(
        self,
        task: str,
        variables: dict[str, str],
        *,
        preferred_provider: str | None = None,
        prompt_version: str | None = None,
        system_prompt: str = "你是客服助手",
    ) -> tuple[str, dict[str, object]]:
        _ = task
        _ = variables
        _ = preferred_provider
        _ = prompt_version
        _ = system_prompt
        raise LLMGenerationError(
            "provider failed",
            trace_metadata={
                "provider": "openai_compatible",
                "model": "qwen3.5:9b",
                "prompt_key": "intake_user_reply",
                "prompt_version": "v1",
                "success": False,
                "error": "upstream unavailable",
                "fallback_used": True,
                "degraded": True,
            },
        )


class _TimeoutAdapter:
    def generate_with_trace(
        self,
        task: str,
        variables: dict[str, str],
        *,
        preferred_provider: str | None = None,
        prompt_version: str | None = None,
        system_prompt: str = "你是客服助手",
    ) -> tuple[str, dict[str, object]]:
        _ = task
        _ = variables
        _ = preferred_provider
        _ = prompt_version
        _ = system_prompt
        raise RuntimeError("timeout while calling provider")


class _InvalidSchemaAdapter:
    def generate_with_trace(
        self,
        task: str,
        variables: dict[str, str],
        *,
        preferred_provider: str | None = None,
        prompt_version: str | None = None,
        system_prompt: str = "你是客服助手",
    ) -> tuple[str, dict[str, object]]:
        _ = task
        _ = variables
        _ = preferred_provider
        _ = prompt_version
        _ = system_prompt
        return (
            "这是不符合schema的回复",
            {
                "provider": "openai_compatible",
                "model": "qwen3.5:9b",
                "prompt_key": "intake_user_reply",
                "prompt_version": "v1",
                "success": True,
                "fallback_used": False,
                "degraded": False,
            },
        )


def _intent(intent: str) -> IntentDecision:
    return IntentDecision(intent=intent, confidence=0.91, is_low_confidence=False, reason="test")


def _handoff(should_handoff: bool) -> HandoffDecision:
    return HandoffDecision(
        should_handoff=should_handoff,
        reason="complaint_requires_human" if should_handoff else "no-trigger",
        payload={},
    )


def test_reply_generator_builds_faq_reply_from_llm() -> None:
    generator = ReplyGenerator(model_adapter=_JsonReplyAdapter(reply_text="这是FAQ自然回复"))
    result = generator.generate(
        message_text="如何申请停车优惠",
        intent=_intent("faq"),
        ticket=_ticket(),
        retrieved_docs=_docs(),
        summary="FAQ摘要",
        recommendations=_recommendations(),
        handoff=_handoff(False),
        events=_events(),
        fallback_reply="fallback",
    )

    assert result.reply_text == "这是FAQ自然回复"
    assert result.generation_type == "faq"
    assert result.metadata["prompt_key"] == "faq_reply"
    assert result.metadata["fallback_used"] is False


def test_reply_generator_builds_progress_reply_from_llm() -> None:
    generator = ReplyGenerator(model_adapter=_JsonReplyAdapter(reply_text="工单正在由u_ops_01跟进"))
    result = generator.generate(
        message_text="我的工单到哪了，谁在跟进",
        intent=_intent("progress_query"),
        ticket=_ticket(),
        retrieved_docs=_docs(),
        summary="进度摘要",
        recommendations=_recommendations(),
        handoff=_handoff(False),
        events=_events(),
        fallback_reply="fallback",
    )

    assert result.reply_text == "工单正在由u_ops_01跟进"
    assert result.generation_type == "progress"
    assert result.metadata["prompt_key"] == "progress_reply"


def test_reply_generator_builds_handoff_reply_from_llm() -> None:
    generator = ReplyGenerator(model_adapter=_JsonReplyAdapter(reply_text="已转人工处理，请稍候"))
    result = generator.generate(
        message_text="我要投诉并转人工",
        intent=_intent("complaint"),
        ticket=_ticket(),
        retrieved_docs=_docs(),
        summary="投诉摘要",
        recommendations=_recommendations(),
        handoff=_handoff(True),
        events=_events(),
        fallback_reply="fallback",
    )

    assert result.reply_text == "已转人工处理，请稍候"
    assert result.generation_type == "handoff"
    assert result.metadata["prompt_key"] == "handoff_reply"


def test_reply_generator_builds_generic_reply_from_llm() -> None:
    generator = ReplyGenerator(model_adapter=_JsonReplyAdapter(reply_text="我们已收到并处理中"))
    result = generator.generate(
        message_text="停车场抬杆故障",
        intent=_intent("repair"),
        ticket=_ticket(),
        retrieved_docs=_docs(),
        summary="报修摘要",
        recommendations=_recommendations(),
        handoff=_handoff(False),
        events=_events(),
        fallback_reply="fallback",
    )

    assert result.reply_text == "我们已收到并处理中"
    assert result.generation_type == "generic"
    assert result.metadata["prompt_key"] == "intake_user_reply"


def test_reply_generator_fallback_when_provider_failed() -> None:
    generator = ReplyGenerator(model_adapter=_ProviderFailAdapter())
    result = generator.generate(
        message_text="停车场抬杆故障",
        intent=_intent("repair"),
        ticket=_ticket(),
        retrieved_docs=_docs(),
        summary="报修摘要",
        recommendations=_recommendations(),
        handoff=_handoff(False),
        events=_events(),
        fallback_reply="fallback",
    )

    assert result.reply_text == "fallback"
    assert result.metadata["fallback_used"] is True
    assert result.metadata["degrade_reason"] == "llm_provider_error"


def test_reply_generator_fallback_when_timeout() -> None:
    generator = ReplyGenerator(model_adapter=_TimeoutAdapter())
    result = generator.generate(
        message_text="停车场抬杆故障",
        intent=_intent("repair"),
        ticket=_ticket(),
        retrieved_docs=_docs(),
        summary="报修摘要",
        recommendations=_recommendations(),
        handoff=_handoff(False),
        events=_events(),
        fallback_reply="fallback",
    )

    assert result.reply_text == "fallback"
    assert result.metadata["fallback_used"] is True
    assert result.metadata["degrade_reason"] == "llm_timeout"


def test_reply_generator_fallback_when_schema_parse_failed() -> None:
    generator = ReplyGenerator(model_adapter=_InvalidSchemaAdapter())
    result = generator.generate(
        message_text="停车场抬杆故障",
        intent=_intent("repair"),
        ticket=_ticket(),
        retrieved_docs=_docs(),
        summary="报修摘要",
        recommendations=_recommendations(),
        handoff=_handoff(False),
        events=_events(),
        fallback_reply="fallback",
    )

    assert result.reply_text == "fallback"
    assert result.metadata["fallback_used"] is True
    assert result.metadata["degrade_reason"] == "schema_parse_error"

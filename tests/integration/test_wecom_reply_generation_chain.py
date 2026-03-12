from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from channel_adapters.wecom_adapter import WeComAdapter
from core.handoff_manager import HandoffManager
from core.intent_router import IntentRouter
from core.recommended_actions_engine import RecommendedActionsEngine
from core.reply_generator import ReplyGenerator
from core.retriever import Retriever
from core.sla_engine import SlaEngine
from core.summary_engine import SummaryEngine
from core.ticket_api import TicketAPI
from core.tool_router import ToolRouter
from core.trace_logger import JsonTraceLogger
from core.workflow_engine import WorkflowEngine
from openclaw_adapter.bindings import GatewayBindings
from openclaw_adapter.channel_router import ChannelRouter
from openclaw_adapter.gateway import OpenClawGateway
from openclaw_adapter.session_mapper import SessionMapper
from scripts.wecom_bridge_server import process_wecom_message
from storage.ticket_repository import TicketRepository
from workflows.case_collab_workflow import CaseCollabWorkflow
from workflows.support_intake_workflow import SupportIntakeWorkflow


class _ReplyAdapter:
    def generate_with_trace(
        self,
        task: str,
        variables: dict[str, str],
        *,
        preferred_provider: str | None = None,
        prompt_version: str | None = None,
        system_prompt: str = "你是客服助手",
    ) -> tuple[str, dict[str, Any]]:
        _ = preferred_provider
        _ = prompt_version
        _ = system_prompt
        ticket_id = variables.get("ticket_id", "unknown")
        if task == "progress_reply":
            text = f"LLM进度回复：工单{ticket_id}正在处理，请耐心等待。"
        elif task == "handoff_reply":
            text = f"LLM人工回复：工单{ticket_id}已转人工处理。"
        elif task == "faq_reply":
            text = "LLM FAQ回复：已为你匹配相关知识库说明。"
        else:
            text = f"LLM通用回复：工单{ticket_id}已受理。"
        return (
            f'{{"reply_text":"{text}"}}',
            {
                "provider": "openai_compatible",
                "model": "qwen3.5:9b",
                "prompt_key": task,
                "prompt_version": "v1",
                "latency_ms": 25,
                "request_id": f"req-{task}",
                "token_usage": {"total_tokens": 30},
                "retry_count": 0,
                "success": True,
                "error": None,
                "fallback_used": False,
                "degraded": False,
            },
        )


@dataclass(frozen=True)
class _Runtime:
    gateway: OpenClawGateway
    intake_workflow: SupportIntakeWorkflow


def test_wecom_bridge_reply_generation_prefers_llm_and_records_trace(tmp_path: Path) -> None:
    sqlite_path = tmp_path / "tickets.db"
    trace_log_path = tmp_path / "gateway.log"
    bindings = GatewayBindings(
        channel_router=ChannelRouter({"wecom": WeComAdapter()}),
        session_mapper=SessionMapper(sqlite_path),
        trace_logger=JsonTraceLogger(trace_log_path),
    )
    gateway = OpenClawGateway(bindings)

    repo = TicketRepository(sqlite_path)
    repo.apply_migrations()
    ticket_api = TicketAPI(repo, session_mapper=bindings.session_mapper)
    retriever = Retriever(Path(__file__).resolve().parents[2] / "seed_data")
    tool_router = ToolRouter(
        ticket_api=ticket_api,
        retriever=retriever,
        trace_logger=bindings.trace_logger,
    )
    policy_path = (
        Path(__file__).resolve().parents[2]
        / "seed_data"
        / "sla_rules"
        / "default_sla_rules.json"
    )
    workflow_engine = WorkflowEngine(
        ticket_api=ticket_api,
        intent_router=IntentRouter(),
        tool_router=tool_router,
        summary_engine=SummaryEngine(),
        handoff_manager=HandoffManager.from_file(policy_path),
        sla_engine=SlaEngine.from_file(policy_path),
        recommendation_engine=RecommendedActionsEngine(),
        trace_logger=bindings.trace_logger,
        reply_generator=ReplyGenerator(model_adapter=_ReplyAdapter()),
    )
    intake_workflow = SupportIntakeWorkflow(
        workflow_engine,
        case_collab_workflow=CaseCollabWorkflow(ticket_api),
        ticket_api=ticket_api,
    )
    runtime = _Runtime(gateway=gateway, intake_workflow=intake_workflow)

    first = process_wecom_message(
        runtime,
        {
            "ReqId": "trace-wecom-1",
            "FromUserName": "u-wecom-1",
            "Content": "停车场抬杆故障",
            "MsgId": "msg-wecom-1",
        },
    )
    second = process_wecom_message(
        runtime,
        {
            "ReqId": "trace-wecom-2",
            "FromUserName": "u-wecom-1",
            "Content": "我的工单到哪了，谁在跟进？",
            "MsgId": "msg-wecom-2",
        },
    )

    assert first.status == "ok"
    assert second.status == "ok"
    assert first.ticket_id is not None
    assert second.ticket_id == first.ticket_id
    assert "LLM进度回复" in second.reply_text
    assert second.reply_text != "已收到，我们正在处理你的工单。"

    trace_events = bindings.trace_logger.query_by_trace("trace-wecom-2", limit=200)
    reply_events = [item for item in trace_events if item.get("event_type") == "reply_generated"]
    assert reply_events
    payload = reply_events[-1].get("payload")
    assert isinstance(payload, dict)
    assert payload["provider"] == "openai_compatible"
    assert payload["model"] == "qwen3.5:9b"
    assert payload["prompt_key"] == "progress_reply"
    assert payload["prompt_version"] == "v1"
    assert payload["fallback_used"] is False
    assert payload["generation_type"] == "progress"
    assert isinstance(payload.get("grounding_sources"), list)

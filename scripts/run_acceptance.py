from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from config import load_app_config
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
from llm import build_summary_model_adapter
from openclaw_adapter.bindings import build_default_bindings
from openclaw_adapter.gateway import OpenClawGateway
from scripts.trace_kpi import DEFAULT_REQUIRED_EVENTS, generate_trace_kpi
from storage.models import InboundEnvelope
from storage.ticket_repository import TicketRepository
from workflows.case_collab_workflow import CaseCollabWorkflow
from workflows.support_intake_workflow import SupportIntakeWorkflow


@dataclass(frozen=True)
class AcceptanceRuntime:
    gateway: OpenClawGateway
    intake_workflow: SupportIntakeWorkflow
    trace_logger: JsonTraceLogger


def _seed_root() -> Path:
    return Path(__file__).resolve().parents[1] / "seed_data"


def _default_policy_path() -> Path:
    return _seed_root() / "sla_rules" / "default_sla_rules.json"


def _default_sample_path() -> Path:
    return _seed_root() / "acceptance_samples" / "default_samples.json"


def build_runtime(environment: str | None) -> AcceptanceRuntime:
    app_config = load_app_config(environment)
    bindings = build_default_bindings(app_config)
    gateway = OpenClawGateway(bindings)

    sqlite_path = Path(app_config.storage.sqlite_path)
    repo = TicketRepository(sqlite_path)
    repo.apply_migrations()
    ticket_api = TicketAPI(repo, session_mapper=bindings.session_mapper)

    policy_path = _default_policy_path()
    retriever = Retriever(_seed_root())
    tool_router = ToolRouter(
        ticket_api=ticket_api,
        retriever=retriever,
        trace_logger=bindings.trace_logger,
    )
    model_adapter = build_summary_model_adapter(app_config.llm)
    workflow_engine = WorkflowEngine(
        ticket_api=ticket_api,
        intent_router=IntentRouter(),
        tool_router=tool_router,
        summary_engine=SummaryEngine(model_adapter=model_adapter),
        handoff_manager=HandoffManager.from_file(policy_path),
        sla_engine=SlaEngine.from_file(policy_path),
        recommendation_engine=RecommendedActionsEngine(),
        trace_logger=bindings.trace_logger,
        reply_generator=ReplyGenerator(model_adapter=model_adapter),
    )
    intake_workflow = SupportIntakeWorkflow(
        workflow_engine,
        case_collab_workflow=CaseCollabWorkflow(ticket_api),
        ticket_api=ticket_api,
    )
    return AcceptanceRuntime(
        gateway=gateway,
        intake_workflow=intake_workflow,
        trace_logger=bindings.trace_logger,
    )


def load_samples(sample_path: Path) -> list[dict[str, Any]]:
    payload = json.loads(sample_path.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        items = payload
    elif isinstance(payload, dict) and isinstance(payload.get("samples"), list):
        items = payload["samples"]
    else:
        raise ValueError(f"Unsupported acceptance sample structure: {sample_path}")

    normalized: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        normalized.append(item)
    return normalized


def run_acceptance(
    *,
    environment: str | None,
    sample_path: Path,
    output_dir: Path,
    sample_id: str | None = None,
) -> dict[str, Any]:
    samples = load_samples(sample_path)
    if sample_id is not None:
        samples = [item for item in samples if str(item.get("id", "")) == sample_id]
    if not samples:
        raise ValueError("No acceptance samples selected")

    runtime = build_runtime(environment)
    run_token = datetime.now(UTC).strftime("%Y%m%d%H%M%S")
    trace_ids: set[str] = set()
    sample_results: list[dict[str, Any]] = []

    for sample in samples:
        result = _run_single_sample(runtime, sample, run_token=run_token)
        trace_ids.add(result["trace_id"])
        sample_results.append(result)

    passed_count = sum(1 for item in sample_results if item["passed"])
    failed = [item for item in sample_results if not item["passed"]]
    summary: dict[str, Any] = {
        "generated_at": datetime.now(UTC).isoformat(),
        "environment": environment,
        "sample_path": str(sample_path),
        "total": len(sample_results),
        "passed": passed_count,
        "failed": len(sample_results) - passed_count,
        "results": sample_results,
        "failed_repro_commands": [item["replay_command"] for item in failed],
    }

    trace_kpi = generate_trace_kpi(
        environment=environment,
        log_path=runtime.trace_logger.path,
        trace_ids=trace_ids,
        required_events=DEFAULT_REQUIRED_EVENTS,
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    summary_json_path = output_dir / "acceptance_summary.json"
    summary_md_path = output_dir / "acceptance_summary.md"
    trace_kpi_path = output_dir / "trace_kpi.json"
    summary_json_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    trace_kpi_path.write_text(json.dumps(trace_kpi, ensure_ascii=False, indent=2), encoding="utf-8")
    summary_md_path.write_text(_to_markdown(summary, trace_kpi), encoding="utf-8")

    summary["summary_json_path"] = str(summary_json_path)
    summary["summary_md_path"] = str(summary_md_path)
    summary["trace_kpi_path"] = str(trace_kpi_path)
    return summary


def _run_single_sample(
    runtime: AcceptanceRuntime,
    sample: dict[str, Any],
    *,
    run_token: str,
) -> dict[str, Any]:
    sample_name = str(sample.get("id") or "unknown-sample")
    channel = str(sample.get("channel") or "telegram")
    base_session_id = str(sample.get("session_id") or f"accept-{sample_name}")
    session_id = f"{base_session_id}-{run_token}"
    text = str(sample.get("text") or "")
    base_trace_id = str(sample.get("trace_id") or f"trace_accept_{sample_name}")
    trace_id = f"{base_trace_id}-{run_token}"
    expected_status = str(sample.get("expected_status") or "ok")

    failures: list[str] = []
    replay_payload = _build_payload(
        channel=channel,
        session_id=session_id,
        text=text,
        trace_id=trace_id,
    )
    replay_result = runtime.gateway.receive(channel, replay_payload)
    replay_status = str(replay_result.get("status"))
    if replay_status != expected_status:
        failures.append(f"status mismatch: expected={expected_status}, actual={replay_status}")

    ticket_id: str | None = None
    ticket_action: str | None = None
    handoff_required: bool | None = None
    recommendation_count = 0
    if replay_status == "ok":
        inbound = replay_result.get("inbound")
        if not isinstance(inbound, dict):
            failures.append("missing inbound payload for workflow intake")
        else:
            envelope = InboundEnvelope(
                channel=str(inbound.get("channel", channel)),
                session_id=str(inbound.get("session_id", session_id)),
                message_text=str(inbound.get("message_text", text)),
                metadata=dict(inbound.get("metadata", {})),
            )
            intake = runtime.intake_workflow.run(envelope)
            ticket_id = intake.ticket_id
            ticket_action = intake.ticket_action
            handoff_required = intake.handoff_required
            recommendation_count = len(intake.outcome.recommendations)

            expected_action = sample.get("expected_ticket_action")
            if expected_action is not None and ticket_action != str(expected_action):
                failures.append(
                    f"ticket_action mismatch: expected={expected_action}, actual={ticket_action}"
                )

            expected_handoff = sample.get("expected_handoff")
            if expected_handoff is not None and handoff_required != bool(expected_handoff):
                failures.append(
                    "handoff mismatch: "
                    f"expected={bool(expected_handoff)}, actual={handoff_required}"
                )

            expected_reply_contains = sample.get("expected_reply_contains")
            if expected_reply_contains and str(expected_reply_contains) not in intake.reply_text:
                failures.append(f"reply missing fragment: {expected_reply_contains}")

            if bool(sample.get("expect_history_case_top")):
                docs = intake.outcome.retrieved_docs
                if not docs or docs[0].source_type != "history_case":
                    failures.append("history_case not ranked as top result")

            if sample.get("require_recommendation_evidence", True):
                if any(not action.evidence for action in intake.outcome.recommendations):
                    failures.append("recommendation without evidence detected")

    trace_events = runtime.trace_logger.query_by_trace(trace_id, limit=500)
    event_types = {
        str(item.get("event_type"))
        for item in trace_events
        if isinstance(item.get("event_type"), str)
    }
    missing_events = [event for event in DEFAULT_REQUIRED_EVENTS if event not in event_types]
    if missing_events:
        failures.append(f"missing required events: {', '.join(missing_events)}")

    replay_command = _build_replay_command(
        channel=channel,
        session_id=session_id,
        text=text,
        trace_id=trace_id,
    )
    return {
        "id": sample_name,
        "trace_id": trace_id,
        "passed": not failures,
        "failures": failures,
        "ticket_id": ticket_id,
        "ticket_action": ticket_action,
        "handoff_required": handoff_required,
        "recommendation_count": recommendation_count,
        "replay_command": replay_command,
        "missing_required_events": missing_events,
    }


def _build_payload(
    *,
    channel: str,
    session_id: str,
    text: str,
    trace_id: str,
) -> dict[str, object]:
    if channel == "telegram":
        return {
            "trace_id": trace_id,
            "message": {"chat": {"id": session_id, "username": "acceptance"}, "text": text},
        }
    if channel == "wecom":
        return {
            "trace_id": trace_id,
            "FromUserName": session_id,
            "Content": text,
            "MsgId": f"{trace_id}-msg",
        }
    if channel == "feishu":
        return {
            "trace_id": trace_id,
            "event": {
                "sender": {"sender_id": {"open_id": session_id}},
                "message": {"text": text, "message_id": f"{trace_id}-msg"},
            },
            "tenant_key": "acceptance-tenant",
        }
    raise ValueError(f"Unsupported channel: {channel}")


def _build_replay_command(*, channel: str, session_id: str, text: str, trace_id: str) -> str:
    safe_text = text.replace('"', '\\"')
    return (
        "python scripts/replay_gateway_event.py "
        f"--env dev --channel {channel} --session-id {session_id} "
        f'--text "{safe_text}" --trace-id {trace_id}'
    )


def _to_markdown(summary: dict[str, Any], trace_kpi: dict[str, Any]) -> str:
    lines = [
        "# Acceptance Summary",
        "",
        f"- generated_at: {summary['generated_at']}",
        f"- total: {summary['total']}",
        f"- passed: {summary['passed']}",
        f"- failed: {summary['failed']}",
        "",
        "## Trace KPI",
        "",
        f"- chain_complete_rate: {trace_kpi['chain_complete_rate']}",
        f"- critical_missing_rate: {trace_kpi['critical_missing_rate']}",
        "",
        "## Sample Results",
        "",
    ]
    for item in summary["results"]:
        status = "PASS" if item["passed"] else "FAIL"
        lines.append(f"- [{status}] {item['id']} trace_id={item['trace_id']}")
        if item["failures"]:
            for failure in item["failures"]:
                lines.append(f"  - {failure}")
            lines.append(f"  - reproduce: `{item['replay_command']}`")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run fixed-sample acceptance replay and KPI report"
    )
    parser.add_argument("--env", default=None, help="Environment name (dev/prod)")
    parser.add_argument("--samples", default=None, help="Acceptance samples json path")
    parser.add_argument("--sample-id", default=None, help="Run only one sample ID")
    parser.add_argument(
        "--output-dir",
        default="storage/acceptance",
        help="Directory for acceptance summary and KPI outputs",
    )
    args = parser.parse_args()

    sample_path = Path(args.samples) if args.samples else _default_sample_path()
    summary = run_acceptance(
        environment=args.env,
        sample_path=sample_path,
        output_dir=Path(args.output_dir),
        sample_id=args.sample_id,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if int(summary["failed"]) == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())

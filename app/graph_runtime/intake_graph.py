from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Protocol, TypedDict


class IntakeGraphState(TypedDict, total=False):
    session_id: str
    user_id: str
    text: str
    channel: str
    metadata: dict[str, Any]


class InvestigationAgentProtocol(Protocol):
    def analyze(
        self,
        ticket_id: str,
        *,
        question: str | None = None,
        actor_id: str = "system",
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]: ...


def build_intake_graph(intake_service: Any, investigation_agent: InvestigationAgentProtocol | None = None):
    """Build a minimal intake orchestration entrypoint with observable trace."""

    def run_intake(payload: IntakeGraphState, *, previous: dict[str, Any] | None = None) -> dict[str, Any]:
        session_id = str(payload.get("session_id", ""))
        text = str(payload.get("text", ""))
        metadata = payload.get("metadata", {}) or {}
        trace_steps: list[dict[str, Any]] = []

        _record_trace(trace_steps, "input_received", {"session_id": session_id})
        intent = _classify_intent(intake_service, text=text, metadata=metadata)
        _record_trace(trace_steps, "intent_classified", {"intent": intent})

        intake_result = _run_intake_service(intake_service, session_id=session_id, text=text)
        _record_trace(trace_steps, "intake_applied", {"status": intake_result.get("status")})

        investigation_result: dict[str, Any] | None = None
        if investigation_agent is not None and _should_investigate(intent=intent, metadata=metadata):
            ticket_id = str(metadata.get("ticket_id") or session_id)
            question = str(metadata.get("investigation_question") or text or "Please analyze this ticket.")
            actor_id = str(metadata.get("actor_id") or "system")
            investigation_result = investigation_agent.analyze(
                ticket_id,
                question=question,
                actor_id=actor_id,
                metadata=metadata,
            )
            _record_trace(
                trace_steps,
                "investigation_completed",
                {"ticket_id": ticket_id, "advice_only": True},
            )

        decision = {
            "route": "investigate" if investigation_result is not None else "direct_reply",
            "high_risk_action_executed": False,
        }
        _record_trace(trace_steps, "decision_made", decision)

        return {
            "session_id": session_id,
            "user_id": payload.get("user_id"),
            "channel": payload.get("channel"),
            "intent": intent,
            "decision": decision,
            "intake_result": intake_result,
            "investigation": investigation_result,
            "trace": {
                "graph": "intake_graph_v1",
                "previous_checkpoint": previous,
                "steps": trace_steps,
            },
        }

    return run_intake


def _classify_intent(intake_service: Any, *, text: str, metadata: dict[str, Any]) -> str:
    classify = getattr(intake_service, "classify_intent", None)
    if callable(classify):
        try:
            return str(classify({"text": text, "metadata": metadata}))
        except Exception:
            pass

    normalized = text.lower()
    if any(token in normalized for token in ("error", "failed", "issue", "broken", "fault")):
        return "support"
    if any(token in normalized for token in ("how", "what", "guide", "faq", "help")):
        return "faq"
    return "support"


def _run_intake_service(intake_service: Any, *, session_id: str, text: str) -> dict[str, Any]:
    run = getattr(intake_service, "run", None)
    if not callable(run):
        return {"status": "skipped", "reason": "intake_service_has_no_run"}

    try:
        result = run(session_id=session_id, message_text=text)
    except TypeError:
        result = run(session_id, text)
    except NotImplementedError:
        return {"status": "deferred", "reason": "intake_service_not_implemented"}
    except Exception as exc:
        return {"status": "error", "reason": str(exc)}

    return {"status": "ok", "result": result}


def _should_investigate(*, intent: str, metadata: dict[str, Any]) -> bool:
    if bool(metadata.get("force_investigation")):
        return True
    return intent == "support"


def _record_trace(steps: list[dict[str, Any]], step: str, details: dict[str, Any] | None = None) -> None:
    steps.append(
        {
            "step": step,
            "details": details or {},
            "at": datetime.now(UTC).isoformat(),
        }
    )

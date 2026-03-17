from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, Protocol, TypedDict, cast

from langgraph.graph import END, START, StateGraph

from core.disambiguation import DisambiguationResult
from storage.models import InboundEnvelope

if TYPE_CHECKING:
    from workflows.support_intake_workflow import SupportIntakeResult, SupportIntakeWorkflow


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


def build_intake_graph(
    intake_service: Any,
    investigation_agent: InvestigationAgentProtocol | None = None,
) -> Callable[..., dict[str, Any]]:
    """Build a minimal intake orchestration entrypoint with observable trace."""

    def run_intake(
        payload: IntakeGraphState,
        *,
        previous: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
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
        if investigation_agent is not None and _should_investigate(
            intent=intent,
            metadata=metadata,
        ):
            ticket_id = str(metadata.get("ticket_id") or session_id)
            question = str(
                metadata.get("investigation_question")
                or text
                or "Please analyze this ticket."
            )
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


def _record_trace(
    steps: list[dict[str, Any]],
    step: str,
    details: dict[str, Any] | None = None,
) -> None:
    steps.append(
        {
            "step": step,
            "details": details or {},
            "at": datetime.now(UTC).isoformat(),
        }
    )


class WorkflowIntakeGraphState(TypedDict):
    envelope: InboundEnvelope
    existing_ticket_id: str | None
    disambiguation: DisambiguationResult | None
    envelope_with_disambiguation: InboundEnvelope | None
    result: Any | None
    runtime_path: list[str]


class SupportIntakeGraphRunner:
    """Workflow 1 graph runner with legacy SupportIntakeResult compatibility."""

    GRAPH_ID = "workflow1-intake-graph-v1"

    def __init__(self, workflow: SupportIntakeWorkflow) -> None:
        self._workflow = workflow
        self._graph = self._build_graph()

    def run(
        self,
        *,
        envelope: InboundEnvelope,
        existing_ticket_id: str | None,
    ) -> SupportIntakeResult:
        initial_state: WorkflowIntakeGraphState = {
            "envelope": envelope,
            "existing_ticket_id": existing_ticket_id,
            "disambiguation": None,
            "envelope_with_disambiguation": None,
            "result": None,
            "runtime_path": [],
        }
        final_state = cast(WorkflowIntakeGraphState, self._graph.invoke(initial_state))
        result = final_state.get("result")
        if result is None:
            raise RuntimeError("intake graph finished without a SupportIntakeResult")
        runtime_path = list(final_state.get("runtime_path") or [])
        runtime_state = self._build_runtime_state(final_state, result=result)
        current_node = runtime_path[-1] if runtime_path else "emit_user_reply"
        return self._workflow._attach_runtime_graph_trace(
            result,
            runtime_graph=self.GRAPH_ID,
            runtime_current_node=current_node,
            runtime_path=runtime_path,
            runtime_state=runtime_state,
        )

    def _build_graph(self) -> Any:
        builder = StateGraph(WorkflowIntakeGraphState)
        builder.add_node("ingest_message", self._ingest_message)
        builder.add_node("classify_intent", self._classify_intent)
        builder.add_node("session_control_detect", self._session_control_detect)
        builder.add_node("customer_confirm_detect", self._customer_confirm_detect)
        builder.add_node("retrieve_context", self._retrieve_context)
        builder.add_node("faq_answer_or_ticket_open", self._faq_answer_or_ticket_open)
        builder.add_node("emit_collab_push", self._emit_collab_push)
        builder.add_node("emit_user_reply", self._emit_user_reply)

        builder.add_edge(START, "ingest_message")
        builder.add_edge("ingest_message", "classify_intent")
        builder.add_edge("classify_intent", "session_control_detect")
        builder.add_conditional_edges(
            "session_control_detect",
            self._route_after_session_control,
            {
                "emit_user_reply": "emit_user_reply",
                "customer_confirm_detect": "customer_confirm_detect",
            },
        )
        builder.add_conditional_edges(
            "customer_confirm_detect",
            self._route_after_customer_confirm,
            {
                "emit_user_reply": "emit_user_reply",
                "retrieve_context": "retrieve_context",
            },
        )
        builder.add_edge("retrieve_context", "faq_answer_or_ticket_open")
        builder.add_edge("faq_answer_or_ticket_open", "emit_collab_push")
        builder.add_edge("emit_collab_push", "emit_user_reply")
        builder.add_edge("emit_user_reply", END)
        return builder.compile()

    def _ingest_message(self, state: WorkflowIntakeGraphState) -> WorkflowIntakeGraphState:
        next_state = _wf_copy_state(state)
        next_state["runtime_path"] = _wf_append_path(state, "ingest_message")
        return next_state

    def _classify_intent(self, state: WorkflowIntakeGraphState) -> WorkflowIntakeGraphState:
        envelope = state["envelope"]
        disambiguation = self._workflow.assess_disambiguation(
            envelope,
            requested_ticket_id=None,
        )
        envelope_with_disambiguation = self._workflow._tag_disambiguation_context(
            envelope,
            disambiguation=disambiguation,
        )
        next_state = _wf_copy_state(state)
        next_state["runtime_path"] = _wf_append_path(state, "classify_intent")
        next_state["disambiguation"] = disambiguation
        next_state["envelope_with_disambiguation"] = envelope_with_disambiguation
        return next_state

    def _session_control_detect(self, state: WorkflowIntakeGraphState) -> WorkflowIntakeGraphState:
        disambiguation = state["disambiguation"]
        envelope = state["envelope_with_disambiguation"]
        if disambiguation is None or envelope is None:
            raise RuntimeError("classify_intent must run before session_control_detect")
        result = self._workflow._build_session_end_result(
            envelope=envelope,
            disambiguation=disambiguation,
        )
        if result is None:
            result = self._workflow._build_session_new_issue_result(
                envelope=envelope,
                disambiguation=disambiguation,
            )
        if result is None:
            result = self._workflow._build_session_list_tickets_result(
                envelope=envelope,
                disambiguation=disambiguation,
            )
        if result is None:
            result = self._workflow._build_view_ticket_detail_result(
                envelope=envelope,
                disambiguation=disambiguation,
                existing_ticket_id=state.get("existing_ticket_id"),
            )
        next_state = _wf_copy_state(state)
        next_state["runtime_path"] = _wf_append_path(state, "session_control_detect")
        next_state["result"] = result
        return next_state

    @staticmethod
    def _route_after_session_control(state: WorkflowIntakeGraphState) -> str:
        return "emit_user_reply" if state.get("result") is not None else "customer_confirm_detect"

    def _customer_confirm_detect(self, state: WorkflowIntakeGraphState) -> WorkflowIntakeGraphState:
        disambiguation = state["disambiguation"]
        envelope = state["envelope_with_disambiguation"]
        if disambiguation is None or envelope is None:
            raise RuntimeError("classify_intent must run before customer_confirm_detect")
        existing_ticket_id = state.get("existing_ticket_id")
        result = self._workflow._build_collab_command_result(
            envelope=envelope,
            disambiguation=disambiguation,
            existing_ticket_id=existing_ticket_id,
        )
        if result is None:
            result = self._workflow._build_customer_confirmation_result(
                envelope=envelope,
                disambiguation=disambiguation,
                existing_ticket_id=existing_ticket_id,
            )
        if result is None:
            result = self._workflow._build_collab_advice_only_result(
                envelope=envelope,
                disambiguation=disambiguation,
                existing_ticket_id=existing_ticket_id,
            )
        if result is None:
            result = self._workflow._build_clarification_result(
                envelope=envelope,
                disambiguation=disambiguation,
            )
        next_state = _wf_copy_state(state)
        next_state["runtime_path"] = _wf_append_path(state, "customer_confirm_detect")
        next_state["result"] = result
        return next_state

    @staticmethod
    def _route_after_customer_confirm(state: WorkflowIntakeGraphState) -> str:
        return "emit_user_reply" if state.get("result") is not None else "retrieve_context"

    def _retrieve_context(self, state: WorkflowIntakeGraphState) -> WorkflowIntakeGraphState:
        next_state = _wf_copy_state(state)
        next_state["runtime_path"] = _wf_append_path(state, "retrieve_context")
        return next_state

    def _faq_answer_or_ticket_open(self, state: WorkflowIntakeGraphState) -> WorkflowIntakeGraphState:
        disambiguation = state["disambiguation"]
        envelope = state["envelope_with_disambiguation"]
        if disambiguation is None or envelope is None:
            raise RuntimeError("classify_intent must run before faq_answer_or_ticket_open")
        result = self._workflow.run_standard_intake(
            envelope=envelope,
            disambiguation=disambiguation,
            existing_ticket_id=state.get("existing_ticket_id"),
        )
        next_state = _wf_copy_state(state)
        next_state["runtime_path"] = _wf_append_path(state, "faq_answer_or_ticket_open")
        next_state["result"] = result
        return next_state

    def _emit_collab_push(self, state: WorkflowIntakeGraphState) -> WorkflowIntakeGraphState:
        next_state = _wf_copy_state(state)
        next_state["runtime_path"] = _wf_append_path(state, "emit_collab_push")
        return next_state

    def _emit_user_reply(self, state: WorkflowIntakeGraphState) -> WorkflowIntakeGraphState:
        if state.get("result") is None:
            raise RuntimeError("emit_user_reply requires a result from upstream node")
        next_state = _wf_copy_state(state)
        next_state["runtime_path"] = _wf_append_path(state, "emit_user_reply")
        return next_state

    def _build_runtime_state(
        self,
        state: WorkflowIntakeGraphState,
        *,
        result: SupportIntakeResult,
    ) -> dict[str, Any]:
        disambiguation = state.get("disambiguation")
        reply_generation_type = None
        if result.outcome is not None:
            reply_generation_type = result.outcome.reply_generation_type
        return {
            "decision": disambiguation.decision if disambiguation is not None else None,
            "reason": disambiguation.reason if disambiguation is not None else None,
            "session_action": disambiguation.session_action if disambiguation is not None else None,
            "ticket_action": result.ticket_action,
            "ticket_id": result.ticket_id,
            "reply_generation_type": reply_generation_type,
            "trace_events": list(result.trace_events),
        }


def _wf_append_path(state: WorkflowIntakeGraphState, node: str) -> list[str]:
    return [*state.get("runtime_path", []), node]


def _wf_copy_state(state: WorkflowIntakeGraphState) -> WorkflowIntakeGraphState:
    return cast(WorkflowIntakeGraphState, dict(state))

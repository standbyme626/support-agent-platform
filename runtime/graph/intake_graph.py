from __future__ import annotations

from typing import TYPE_CHECKING, Any, TypedDict, cast

from langgraph.graph import END, START, StateGraph

from core.disambiguation import DisambiguationResult
from storage.models import InboundEnvelope

if TYPE_CHECKING:
    from workflows.support_intake_workflow import SupportIntakeResult, SupportIntakeWorkflow


class IntakeGraphState(TypedDict):
    envelope: InboundEnvelope
    existing_ticket_id: str | None
    disambiguation: DisambiguationResult | None
    envelope_with_disambiguation: InboundEnvelope | None
    result: Any | None
    runtime_path: list[str]


class SupportIntakeGraphRunner:
    """Workflow 1 graph runner while keeping SupportIntakeWorkflow response compatibility."""

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
        initial_state: IntakeGraphState = {
            "envelope": envelope,
            "existing_ticket_id": existing_ticket_id,
            "disambiguation": None,
            "envelope_with_disambiguation": None,
            "result": None,
            "runtime_path": [],
        }
        final_state = cast(IntakeGraphState, self._graph.invoke(initial_state))
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
        builder = StateGraph(IntakeGraphState)
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

    def _ingest_message(self, state: IntakeGraphState) -> IntakeGraphState:
        next_state = _copy_state(state)
        next_state["runtime_path"] = _append_path(state, "ingest_message")
        return next_state

    def _classify_intent(self, state: IntakeGraphState) -> IntakeGraphState:
        envelope = state["envelope"]
        disambiguation = self._workflow.assess_disambiguation(
            envelope,
            requested_ticket_id=None,
        )
        envelope_with_disambiguation = self._workflow._tag_disambiguation_context(
            envelope,
            disambiguation=disambiguation,
        )
        next_state = _copy_state(state)
        next_state["runtime_path"] = _append_path(state, "classify_intent")
        next_state["disambiguation"] = disambiguation
        next_state["envelope_with_disambiguation"] = envelope_with_disambiguation
        return next_state

    def _session_control_detect(self, state: IntakeGraphState) -> IntakeGraphState:
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
        next_state = _copy_state(state)
        next_state["runtime_path"] = _append_path(state, "session_control_detect")
        next_state["result"] = result
        return next_state

    @staticmethod
    def _route_after_session_control(state: IntakeGraphState) -> str:
        return "emit_user_reply" if state.get("result") is not None else "customer_confirm_detect"

    def _customer_confirm_detect(self, state: IntakeGraphState) -> IntakeGraphState:
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
        next_state = _copy_state(state)
        next_state["runtime_path"] = _append_path(state, "customer_confirm_detect")
        next_state["result"] = result
        return next_state

    @staticmethod
    def _route_after_customer_confirm(state: IntakeGraphState) -> str:
        return "emit_user_reply" if state.get("result") is not None else "retrieve_context"

    def _retrieve_context(self, state: IntakeGraphState) -> IntakeGraphState:
        next_state = _copy_state(state)
        next_state["runtime_path"] = _append_path(state, "retrieve_context")
        return next_state

    def _faq_answer_or_ticket_open(self, state: IntakeGraphState) -> IntakeGraphState:
        disambiguation = state["disambiguation"]
        envelope = state["envelope_with_disambiguation"]
        if disambiguation is None or envelope is None:
            raise RuntimeError("classify_intent must run before faq_answer_or_ticket_open")
        result = self._workflow.run_standard_intake(
            envelope=envelope,
            disambiguation=disambiguation,
            existing_ticket_id=state.get("existing_ticket_id"),
        )
        next_state = _copy_state(state)
        next_state["runtime_path"] = _append_path(state, "faq_answer_or_ticket_open")
        next_state["result"] = result
        return next_state

    def _emit_collab_push(self, state: IntakeGraphState) -> IntakeGraphState:
        next_state = _copy_state(state)
        next_state["runtime_path"] = _append_path(state, "emit_collab_push")
        return next_state

    def _emit_user_reply(self, state: IntakeGraphState) -> IntakeGraphState:
        if state.get("result") is None:
            raise RuntimeError("emit_user_reply requires a result from upstream node")
        next_state = _copy_state(state)
        next_state["runtime_path"] = _append_path(state, "emit_user_reply")
        return next_state

    def _build_runtime_state(
        self,
        state: IntakeGraphState,
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


def _append_path(state: IntakeGraphState, node: str) -> list[str]:
    return [*state.get("runtime_path", []), node]


def _copy_state(state: IntakeGraphState) -> IntakeGraphState:
    return cast(IntakeGraphState, dict(state))

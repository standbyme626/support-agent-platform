from __future__ import annotations

import json
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from http import HTTPStatus
from typing import Any

from app.application.collab_service import resume_collab_action_state_from_payload
from app.transport.http.routes import (
    APPROVAL_ACTION_RE,
    COPILOT_DISAMBIGUATE_PATH,
    COPILOT_TICKET_QUERY_RE,
    INTAKE_GRAPH_RUN_V2_PATH,
    KB_DOC_RE,
    SESSION_DETAIL_RE,
    SESSION_END_V2_RE,
    SESSION_NEW_ISSUE_RE,
    SESSION_REPLY_EVENTS_RE,
    SESSION_RESET_RE,
    SESSION_TICKETS_RE,
    TICKET_ACTION_RE,
    TICKET_ACTION_V2_RE,
    TICKET_ASSIST_RE,
    TICKET_DETAIL_RE,
    TICKET_DUPLICATES_RE,
    TICKET_EVENTS_RE,
    TICKET_GROUNDING_RE,
    TICKET_INVESTIGATE_V2_RE,
    TICKET_MERGE_SUGGESTION_RE,
    TICKET_PENDING_ACTIONS_RE,
    TICKET_REPLY_DRAFT_V2_RE,
    TICKET_REPLY_EVENTS_RE,
    TICKET_REPLY_SEND_V2_RE,
    TICKET_SIMILAR_RE,
    TICKET_SWITCH_ACTIVE_RE,
    TRACE_DETAIL_RE,
)

ResponseLike = Any

_VALID_KB_SOURCE_TYPES = {"faq", "sop", "history_case"}


def _normalize_kb_tags(raw_tags: Any) -> list[str]:
    if not isinstance(raw_tags, list):
        return []
    tags: list[str] = []
    for item in raw_tags:
        text = str(item).strip()
        if text:
            tags.append(text)
    return tags


def _normalize_kb_metadata(raw_metadata: Any) -> dict[str, Any]:
    if not isinstance(raw_metadata, dict):
        return {}
    try:
        normalized = json.loads(
            json.dumps(raw_metadata, ensure_ascii=False, default=str)
        )
    except TypeError:
        return {}
    if not isinstance(normalized, dict):
        return {}
    return normalized


def _normalize_kb_record(
    raw_record: dict[str, Any], *, preserve_updated_at: bool
) -> dict[str, Any]:
    updated_at_raw = raw_record.get("updated_at")
    updated_at = (
        str(updated_at_raw).strip()
        if preserve_updated_at and isinstance(updated_at_raw, str)
        else ""
    )
    if not updated_at:
        updated_at = datetime.now(UTC).isoformat()
    return {
        "doc_id": str(raw_record.get("doc_id") or "").strip(),
        "source_type": str(raw_record.get("source_type") or "").strip(),
        "title": str(raw_record.get("title") or "").strip(),
        "content": str(raw_record.get("content") or "").strip(),
        "tags": _normalize_kb_tags(raw_record.get("tags")),
        "updated_at": updated_at,
        "metadata": _normalize_kb_metadata(raw_record.get("metadata")),
    }


def try_handle_session_read_routes(
    *,
    runtime: Any,
    method: str,
    path: str,
    req_id: str,
    json_response: Callable[[str, dict[str, Any]], ResponseLike],
    error_response: Callable[..., ResponseLike],
    session_payload: Callable[[Any, str], dict[str, Any] | None],
    session_ticket_list: Callable[[Any, str], list[dict[str, Any]]],
    session_reply_events: Callable[[Any, str], list[dict[str, Any]]],
) -> ResponseLike | None:
    if method == "GET" and (match := SESSION_DETAIL_RE.match(path)):
        session_id = match.group("session_id")
        data = session_payload(runtime, session_id)
        if data is None:
            return error_response(
                req_id,
                code="session_not_found",
                message=f"session {session_id} not found",
                status=HTTPStatus.NOT_FOUND,
            )
        return json_response(req_id, {"data": data})

    if method == "GET" and (match := SESSION_TICKETS_RE.match(path)):
        session_id = match.group("session_id")
        data = session_payload(runtime, session_id)
        if data is None:
            return error_response(
                req_id,
                code="session_not_found",
                message=f"session {session_id} not found",
                status=HTTPStatus.NOT_FOUND,
            )
        return json_response(req_id, {"items": session_ticket_list(runtime, session_id)})

    if method == "GET" and (match := SESSION_REPLY_EVENTS_RE.match(path)):
        session_id = match.group("session_id")
        data = session_payload(runtime, session_id)
        if data is None:
            return error_response(
                req_id,
                code="session_not_found",
                message=f"session {session_id} not found",
                status=HTTPStatus.NOT_FOUND,
            )
        return json_response(req_id, {"items": session_reply_events(runtime, session_id)})

    return None


def try_handle_session_control_routes(
    *,
    runtime: Any,
    method: str,
    path: str,
    req_id: str,
    payload: dict[str, Any],
    json_response: Callable[[str, dict[str, Any]], ResponseLike],
    error_response: Callable[..., ResponseLike],
    session_payload: Callable[[Any, str], dict[str, Any] | None],
    run_session_new_issue: Callable[..., dict[str, Any]],
    trace_id_factory: Callable[[], str],
) -> ResponseLike | None:
    if method == "POST" and (match := SESSION_RESET_RE.match(path)):
        session_id = match.group("session_id")
        if runtime.gateway.bindings.session_mapper.get(session_id) is None:
            return error_response(
                req_id,
                code="session_not_found",
                message=f"session {session_id} not found",
                status=HTTPStatus.NOT_FOUND,
            )
        actor_id = str(payload.get("actor_id") or "ops-api").strip()
        runtime.gateway.bindings.session_mapper.reset_session_context(
            session_id,
            metadata={
                "session_mode": "awaiting_new_issue",
                "last_intent": "session_reset",
                "updated_by": actor_id,
            },
            keep_recent=True,
        )
        data = session_payload(runtime, session_id)
        if data is None:
            return error_response(
                req_id,
                code="session_not_found",
                message=f"session {session_id} not found",
                status=HTTPStatus.NOT_FOUND,
            )
        return json_response(req_id, {"data": data})

    if method == "POST" and (match := SESSION_NEW_ISSUE_RE.match(path)):
        session_id = match.group("session_id")
        try:
            action_result = run_session_new_issue(
                runtime,
                session_id=session_id,
                payload={
                    "actor_id": str(payload.get("actor_id") or "ops-api").strip() or "ops-api",
                    "reason": str(payload.get("reason") or "new_issue_requested").strip()
                    or "new_issue_requested",
                    "trace_id": str(payload.get("trace_id") or trace_id_factory()).strip(),
                },
            )
        except KeyError:
            return error_response(
                req_id,
                code="session_not_found",
                message=f"session {session_id} not found",
                status=HTTPStatus.NOT_FOUND,
            )
        data = action_result.get("session")
        if not isinstance(data, dict):
            return error_response(
                req_id,
                code="session_not_found",
                message=f"session {session_id} not found",
                status=HTTPStatus.NOT_FOUND,
            )
        return json_response(req_id, {"data": data})

    return None


def try_handle_copilot_routes(
    *,
    runtime: Any,
    method: str,
    path: str,
    req_id: str,
    payload: dict[str, Any],
    json_response: Callable[[str, dict[str, Any]], ResponseLike],
    error_response: Callable[..., ResponseLike],
    copilot_disambiguate_payload: Callable[..., dict[str, Any]],
    require_copilot_query: Callable[[str, dict[str, Any]], tuple[str | None, ResponseLike | None]],
    build_copilot_operator_payload: Callable[[Any, str], dict[str, Any]],
    build_copilot_queue_payload: Callable[[Any, str], dict[str, Any]],
    build_copilot_ticket_payload: Callable[[Any, Any, str], dict[str, Any]],
    build_copilot_dispatch_payload: Callable[[Any, str], dict[str, Any]],
) -> ResponseLike | None:
    if method == "POST" and path == COPILOT_DISAMBIGUATE_PATH:
        session_id = str(payload.get("session_id") or "").strip()
        message_text = str(payload.get("message_text") or payload.get("query") or "").strip()
        actor_id = str(payload.get("actor_id") or "ops-api").strip() or "ops-api"
        trace_id = str(payload.get("trace_id") or "").strip() or None
        if not session_id:
            return error_response(
                req_id,
                code="invalid_payload",
                message="session_id is required",
                status=HTTPStatus.BAD_REQUEST,
            )
        if not message_text:
            return error_response(
                req_id,
                code="invalid_payload",
                message="message_text is required",
                status=HTTPStatus.BAD_REQUEST,
            )
        if runtime.gateway.bindings.session_mapper.get(session_id) is None:
            return error_response(
                req_id,
                code="session_not_found",
                message=f"session {session_id} not found",
                status=HTTPStatus.NOT_FOUND,
            )
        try:
            data = copilot_disambiguate_payload(
                runtime,
                session_id=session_id,
                message_text=message_text,
                actor_id=actor_id,
                trace_id=trace_id,
            )
        except KeyError:
            return error_response(
                req_id,
                code="session_not_found",
                message=f"session {session_id} not found",
                status=HTTPStatus.NOT_FOUND,
            )
        return json_response(req_id, {"data": data})

    if method == "POST" and path == "/api/copilot/operator/query":
        query_text, error = require_copilot_query(req_id, payload)
        if error is not None:
            return error
        return json_response(
            req_id,
            {"data": build_copilot_operator_payload(runtime, query_text or "")},
        )

    if method == "POST" and path == "/api/copilot/queue/query":
        query_text, error = require_copilot_query(req_id, payload)
        if error is not None:
            return error
        queue_name = str(payload.get("queue") or "").strip() or None
        return json_response(
            req_id,
            {
                "data": build_copilot_queue_payload(
                    runtime,
                    query_text or "",
                    queue_name=queue_name,
                )
            },
        )

    if method == "POST" and (match := COPILOT_TICKET_QUERY_RE.match(path)):
        query_text, error = require_copilot_query(req_id, payload)
        if error is not None:
            return error
        ticket_id = match.group("ticket_id")
        ticket = runtime.ticket_api.require_ticket(ticket_id)
        return json_response(
            req_id,
            {"data": build_copilot_ticket_payload(runtime, ticket, query_text or "")},
        )

    if method == "POST" and path == "/api/copilot/dispatch/query":
        query_text, error = require_copilot_query(req_id, payload)
        if error is not None:
            return error
        return json_response(
            req_id,
            {"data": build_copilot_dispatch_payload(runtime, query_text or "")},
        )

    return None


def try_handle_ticket_read_routes(
    *,
    runtime: Any,
    method: str,
    path: str,
    req_id: str,
    json_response: Callable[[str, dict[str, Any]], ResponseLike],
    error_response: Callable[..., ResponseLike],
    ticket_to_dict: Callable[[Any], dict[str, Any]],
    ticket_timeline_events: Callable[[Any, str], list[dict[str, Any]]],
    ticket_reply_events: Callable[[Any, str], list[dict[str, Any]]],
    ticket_duplicate_candidates: Callable[[Any, str], list[dict[str, Any]]],
    pending_action_to_dict: Callable[[Any], dict[str, Any]],
    build_ticket_assist_payload: Callable[[Any, str], dict[str, Any]],
    extract_similar_cases: Callable[[Any, Any], list[dict[str, Any]]],
    extract_grounding_sources: Callable[[Any, Any], list[dict[str, Any]]],
) -> ResponseLike | None:
    if method == "GET" and (match := TICKET_DETAIL_RE.match(path)):
        ticket_id = match.group("ticket_id")
        ticket = runtime.ticket_api.get_ticket(ticket_id)
        if ticket is None:
            return error_response(
                req_id,
                code="ticket_not_found",
                message=f"ticket {ticket_id} not found",
                status=HTTPStatus.NOT_FOUND,
            )
        return json_response(req_id, {"data": ticket_to_dict(ticket)})

    if method == "GET" and (match := TICKET_EVENTS_RE.match(path)):
        ticket_id = match.group("ticket_id")
        return json_response(req_id, {"items": ticket_timeline_events(runtime, ticket_id)})

    if method == "GET" and (match := TICKET_REPLY_EVENTS_RE.match(path)):
        ticket_id = match.group("ticket_id")
        ticket = runtime.ticket_api.get_ticket(ticket_id)
        if ticket is None:
            return error_response(
                req_id,
                code="ticket_not_found",
                message=f"ticket {ticket_id} not found",
                status=HTTPStatus.NOT_FOUND,
            )
        return json_response(req_id, {"items": ticket_reply_events(runtime, ticket_id)})

    if method == "GET" and (match := TICKET_DUPLICATES_RE.match(path)):
        ticket_id = match.group("ticket_id")
        ticket = runtime.ticket_api.get_ticket(ticket_id)
        if ticket is None:
            return error_response(
                req_id,
                code="ticket_not_found",
                message=f"ticket {ticket_id} not found",
                status=HTTPStatus.NOT_FOUND,
            )
        return json_response(req_id, {"items": ticket_duplicate_candidates(runtime, ticket_id)})

    if method == "GET" and (match := TICKET_PENDING_ACTIONS_RE.match(path)):
        ticket_id = match.group("ticket_id")
        actions = runtime.approval_runtime.list_ticket_actions(ticket_id)
        return json_response(
            req_id,
            {"items": [pending_action_to_dict(item) for item in actions]},
        )

    if method == "GET" and (match := TICKET_ASSIST_RE.match(path)):
        ticket_id = match.group("ticket_id")
        return json_response(req_id, build_ticket_assist_payload(runtime, ticket_id))

    if method == "GET" and (match := TICKET_SIMILAR_RE.match(path)):
        ticket_id = match.group("ticket_id")
        ticket = runtime.ticket_api.require_ticket(ticket_id)
        return json_response(req_id, {"items": extract_similar_cases(ticket, runtime.retriever)})

    if method == "GET" and (match := TICKET_GROUNDING_RE.match(path)):
        ticket_id = match.group("ticket_id")
        ticket = runtime.ticket_api.require_ticket(ticket_id)
        return json_response(
            req_id,
            {"items": extract_grounding_sources(ticket, runtime.retriever)},
        )

    return None


def try_handle_retrieval_and_approval_routes(
    *,
    runtime: Any,
    method: str,
    path: str,
    req_id: str,
    payload: dict[str, Any],
    query: dict[str, str],
    json_response: Callable[[str, dict[str, Any]], ResponseLike],
    error_response: Callable[..., ResponseLike],
    parse_int: Callable[..., int],
    search_kb_tool: Callable[..., list[dict[str, Any]]],
    retrieval_health_payload: Callable[[Any], dict[str, Any]],
    pending_action_to_dict: Callable[[Any], dict[str, Any]],
    paginate_payload: Callable[..., dict[str, Any]],
) -> ResponseLike | None:
    if method == "POST" and path == "/api/retrieval/search":
        query_text = str(payload.get("query") or "").strip()
        if not query_text:
            return error_response(
                req_id,
                code="invalid_payload",
                message="query is required",
            )
        source_type = str(payload.get("source_type") or "grounded").strip().lower()
        top_k = parse_int(str(payload.get("top_k") or "5"), default=5, minimum=1, maximum=20)
        retrieval_mode = str(payload.get("retrieval_mode") or "").strip() or None
        try:
            items = search_kb_tool(
                retriever=runtime.retriever,
                source_type=source_type,
                query=query_text,
                top_k=top_k,
                retrieval_mode=retrieval_mode,
            )
        except ValueError as exc:
            return error_response(req_id, code="invalid_payload", message=str(exc))
        return json_response(
            req_id,
            {
                "items": items,
                "query": query_text,
                "source_type": source_type,
                "retrieval_mode": retrieval_mode
                or ("hybrid" if source_type in {"grounded", "hybrid"} else "lexical"),
            },
        )

    if method == "GET" and path == "/api/retrieval/health":
        return json_response(req_id, {"data": retrieval_health_payload(runtime)})

    if method == "GET" and path == "/api/approvals/pending":
        pending_items = [
            pending_action_to_dict(item) for item in runtime.approval_runtime.list_pending_actions()
        ]
        return json_response(req_id, paginate_payload(pending_items, query=query))

    return None


def try_handle_ticket_action_routes(
    *,
    runtime: Any,
    method: str,
    path: str,
    req_id: str,
    payload: dict[str, Any],
    json_response: Callable[[str, dict[str, Any]], ResponseLike],
    error_response: Callable[..., ResponseLike],
    ticket_to_dict: Callable[[Any], dict[str, Any]],
    session_payload: Callable[[Any, str], dict[str, Any] | None],
    merge_suggestion_decision: Callable[..., dict[str, Any]],
    resolve_action: Callable[..., dict[str, Any]],
    run_reply_send_v2: Callable[..., dict[str, Any]],
    run_reply_draft_v2: Callable[..., dict[str, Any]],
    run_ticket_investigation_v2: Callable[..., dict[str, Any]],
    run_intake_graph_v2: Callable[..., dict[str, Any]],
    run_session_end_v2: Callable[..., dict[str, Any]],
) -> ResponseLike | None:
    if method == "POST" and (match := TICKET_SWITCH_ACTIVE_RE.match(path)):
        ticket_id = match.group("ticket_id")
        ticket = runtime.ticket_api.require_ticket(ticket_id)
        session_id = str(payload.get("session_id") or ticket.session_id).strip()
        if not session_id:
            return error_response(
                req_id,
                code="invalid_payload",
                message="session_id is required",
                status=HTTPStatus.BAD_REQUEST,
            )
        if session_id != ticket.session_id:
            return error_response(
                req_id,
                code="invalid_payload",
                message="ticket does not belong to target session",
                status=HTTPStatus.BAD_REQUEST,
            )
        actor_id = str(payload.get("actor_id") or "ops-api").strip()
        runtime.ticket_api.switch_active_session_ticket(
            session_id,
            ticket_id,
            metadata={
                "updated_by": actor_id,
                "session_mode": "multi_issue",
            },
        )
        session_data = session_payload(runtime, session_id)
        if session_data is None:
            return error_response(
                req_id,
                code="session_not_found",
                message=f"session {session_id} not found",
                status=HTTPStatus.NOT_FOUND,
            )
        return json_response(
            req_id,
            {
                "data": {
                    "ticket": ticket_to_dict(ticket),
                    "session": session_data,
                }
            },
        )

    if method == "POST" and (match := TICKET_MERGE_SUGGESTION_RE.match(path)):
        ticket_id = match.group("ticket_id")
        decision = match.group("decision")
        result = merge_suggestion_decision(
            runtime,
            ticket_id=ticket_id,
            decision=decision,
            payload=payload,
        )
        return json_response(req_id, result)

    if method == "POST" and (match := TICKET_ACTION_V2_RE.match(path)):
        ticket_id = match.group("ticket_id")
        action = path.rsplit("/", 1)[-1]
        updated = resolve_action(runtime, ticket_id=ticket_id, action=action, body=payload)
        return json_response(req_id, {"data": updated})

    if method == "POST" and (match := TICKET_REPLY_SEND_V2_RE.match(path)):
        ticket_id = match.group("ticket_id")
        data = run_reply_send_v2(runtime, ticket_id=ticket_id, payload=payload)
        return json_response(req_id, {"data": data})

    if method == "POST" and (match := TICKET_REPLY_DRAFT_V2_RE.match(path)):
        ticket_id = match.group("ticket_id")
        data = run_reply_draft_v2(runtime, ticket_id=ticket_id, payload=payload)
        return json_response(req_id, {"data": data})

    if method == "POST" and (match := TICKET_INVESTIGATE_V2_RE.match(path)):
        ticket_id = match.group("ticket_id")
        data = run_ticket_investigation_v2(
            runtime,
            ticket_id=ticket_id,
            payload=payload,
        )
        return json_response(req_id, {"data": data})

    if method == "POST" and path == INTAKE_GRAPH_RUN_V2_PATH:
        data = run_intake_graph_v2(runtime, payload=payload)
        return json_response(req_id, {"data": data})

    if method == "POST" and (match := SESSION_END_V2_RE.match(path)):
        session_id = match.group("session_id")
        data = run_session_end_v2(runtime, session_id=session_id, payload=payload)
        return json_response(req_id, {"data": data})

    if method == "POST" and (match := TICKET_ACTION_RE.match(path)):
        ticket_id = match.group("ticket_id")
        action = path.rsplit("/", 1)[-1]
        updated = resolve_action(runtime, ticket_id=ticket_id, action=action, body=payload)
        return json_response(req_id, {"data": updated})

    return None


def try_handle_approval_action_routes(
    *,
    runtime: Any,
    method: str,
    path: str,
    req_id: str,
    payload: dict[str, Any],
    json_response: Callable[[str, dict[str, Any]], ResponseLike],
    error_response: Callable[..., ResponseLike],
    ticket_to_dict: Callable[[Any], dict[str, Any]],
    execute_action_without_approval: Callable[..., Any],
) -> ResponseLike | None:
    if method == "POST" and (match := APPROVAL_ACTION_RE.match(path)):
        approval_id = match.group("approval_id")
        decision = path.rsplit("/", 1)[-1]
        actor_id = str(payload.get("actor_id") or "").strip()
        if not actor_id:
            return error_response(
                req_id,
                code="invalid_payload",
                message="actor_id is required",
                status=HTTPStatus.BAD_REQUEST,
            )
        note = str(payload.get("note") or "").strip() or None
        trace_id = str(payload.get("trace_id") or "").strip() or None

        if decision == "approve":
            ticket, pending_action = runtime.approval_runtime.get_pending_action(approval_id)
            action_payload = dict(pending_action.payload)
            action_payload.setdefault("actor_id", pending_action.requested_by)
            executed_ticket = execute_action_without_approval(
                runtime,
                ticket_id=ticket.ticket_id,
                action=pending_action.action_type,
                payload=action_payload,
            )
            collab_graph = None
            collab_service = getattr(runtime, "collab_service", None)
            if collab_service is not None:
                collab_graph = resume_collab_action_state_from_payload(
                    collab_service,
                    pending_payload=action_payload,
                    decision="approve",
                    actor_id=actor_id,
                )
            decided = runtime.approval_runtime.mark_approved(
                approval_id,
                actor_id=actor_id,
                execution_ticket=executed_ticket,
                note=note,
                trace_id=trace_id,
            )
            response_payload = {
                "data": ticket_to_dict(decided.ticket),
                "approval": decided.pending_action.as_dict(),
            }
            if collab_graph is not None:
                response_payload["collab_graph"] = collab_graph
            return json_response(
                req_id,
                response_payload,
            )

        if decision == "reject":
            _, pending_action = runtime.approval_runtime.get_pending_action(approval_id)
            action_payload = dict(pending_action.payload)
            collab_graph = None
            collab_service = getattr(runtime, "collab_service", None)
            if collab_service is not None:
                collab_graph = resume_collab_action_state_from_payload(
                    collab_service,
                    pending_payload=action_payload,
                    decision="reject",
                    actor_id=actor_id,
                )
            decided = runtime.approval_runtime.mark_rejected(
                approval_id,
                actor_id=actor_id,
                note=note,
                trace_id=trace_id,
            )
            response_payload = {
                "data": ticket_to_dict(decided.ticket),
                "approval": decided.pending_action.as_dict(),
            }
            if collab_graph is not None:
                response_payload["collab_graph"] = collab_graph
            return json_response(
                req_id,
                response_payload,
            )

        return error_response(
            req_id,
            code="invalid_payload",
            message=f"unsupported approval decision: {decision}",
            status=HTTPStatus.BAD_REQUEST,
        )

    return None


def try_handle_trace_routes(
    *,
    runtime: Any,
    method: str,
    path: str,
    req_id: str,
    query: dict[str, str],
    json_response: Callable[[str, dict[str, Any]], ResponseLike],
    error_response: Callable[..., ResponseLike],
    parse_int: Callable[..., int],
    trace_groups: Callable[[Any], dict[str, list[dict[str, Any]]]],
    trace_summary: Callable[[Any, str, list[dict[str, Any]]], dict[str, Any]],
    parse_iso_datetime: Callable[[str], datetime | None],
    trace_detail_event_to_dict: Callable[..., dict[str, Any]],
) -> ResponseLike | None:
    if method == "GET" and path == "/api/traces":
        page = parse_int(query.get("page"), default=1, minimum=1, maximum=100000)
        page_size = parse_int(query.get("page_size"), default=20, minimum=1, maximum=200)
        summaries = [
            trace_summary(runtime, trace_id, trace_events)
            for trace_id, trace_events in trace_groups(runtime).items()
            if trace_events
        ]
        summaries.sort(
            key=lambda item: (
                parse_iso_datetime(str(item.get("created_at") or ""))
                or datetime.min.replace(tzinfo=UTC),
                str(item.get("trace_id") or ""),
            ),
            reverse=True,
        )
        filtered_traces: list[dict[str, Any]] = []
        for item in summaries:
            if query.get("trace_id") and item.get("trace_id") != query["trace_id"]:
                continue
            if query.get("ticket_id") and str(item.get("ticket_id") or "") != query["ticket_id"]:
                continue
            if query.get("session_id") and str(item.get("session_id") or "") != query["session_id"]:
                continue
            if query.get("workflow") and item.get("workflow") != query["workflow"]:
                continue
            if query.get("channel") and item.get("channel") != query["channel"]:
                continue
            if query.get("provider") and item.get("provider") != query["provider"]:
                continue
            if query.get("model") and str(item.get("model") or "") != query["model"]:
                continue
            if (
                query.get("prompt_version")
                and str(item.get("prompt_version") or "") != query["prompt_version"]
            ):
                continue
            if (
                query.get("error_only")
                and str(item.get("error_only")).lower() != str(query["error_only"]).lower()
            ):
                continue
            if (
                query.get("handoff")
                and str(item.get("handoff")).lower() != str(query["handoff"]).lower()
            ):
                continue
            filtered_traces.append(item)
        total = len(filtered_traces)
        start = (page - 1) * page_size
        end = start + page_size
        return json_response(
            req_id,
            {
                "items": filtered_traces[start:end],
                "page": page,
                "page_size": page_size,
                "total": total,
            },
        )

    if method == "GET" and (match := TRACE_DETAIL_RE.match(path)):
        trace_id = match.group("trace_id")
        trace_events = runtime.trace_logger.query_by_trace(trace_id, limit=2000)
        if not trace_events:
            return error_response(
                req_id,
                code="trace_not_found",
                message=f"trace {trace_id} not found",
                status=HTTPStatus.NOT_FOUND,
            )
        summary = trace_summary(runtime, trace_id, trace_events)
        retrieved_doc_ids: list[str] = []
        grounding_sources: list[dict[str, Any]] = []
        tool_calls: list[str] = []
        summary_text = ""
        for event in trace_events:
            event_type = str(event.get("event_type", ""))
            payload_dict = event.get("payload")
            event_payload = payload_dict if isinstance(payload_dict, dict) else {}
            if event_type == "ticket_context_retrieved":
                retrieved_doc_ids = [
                    str(item) for item in event_payload.get("doc_ids", []) if isinstance(item, str)
                ]
                payload_sources = event_payload.get("grounding_sources")
                if isinstance(payload_sources, list):
                    grounding_sources = [
                        dict(item) for item in payload_sources if isinstance(item, dict)
                    ]
            if event_type in {"tool_call_end", "tool_call"} and event_payload.get("tool"):
                tool_calls.append(str(event_payload["tool"]))
            if event_type == "recommended_actions":
                summary_text = json.dumps(event_payload.get("actions", []), ensure_ascii=False)
        return json_response(
            req_id,
            {
                "trace_id": trace_id,
                "ticket_id": summary.get("ticket_id"),
                "session_id": summary.get("session_id"),
                "workflow": summary.get("workflow"),
                "channel": summary.get("channel"),
                "provider": summary.get("provider"),
                "model": summary.get("model"),
                "prompt_key": summary.get("prompt_key"),
                "prompt_version": summary.get("prompt_version"),
                "request_id": summary.get("request_id"),
                "token_usage": summary.get("token_usage"),
                "retry_count": summary.get("retry_count"),
                "success": summary.get("success"),
                "error": summary.get("error"),
                "fallback_used": summary.get("fallback_used"),
                "degraded": summary.get("degraded"),
                "degrade_reason": summary.get("degrade_reason"),
                "generation_type": summary.get("generation_type"),
                "route_decision": summary.get("route_decision"),
                "retrieved_docs": retrieved_doc_ids,
                "grounding_sources": grounding_sources,
                "tool_calls": tool_calls,
                "summary": summary_text,
                "handoff": summary.get("handoff"),
                "handoff_reason": summary.get("handoff_reason"),
                "error_only": summary.get("error_only"),
                "latency_ms": summary.get("latency_ms"),
                "created_at": summary.get("created_at"),
                "events": [
                    trace_detail_event_to_dict(event, index=index)
                    for index, event in enumerate(trace_events)
                ],
            },
        )

    return None


def try_handle_kb_routes(
    *,
    runtime: Any,
    method: str,
    path: str,
    req_id: str,
    query: dict[str, str],
    payload: dict[str, Any],
    json_response: Callable[[str, dict[str, Any]], ResponseLike],
    error_response: Callable[..., ResponseLike],
    parse_int: Callable[..., int],
    load_kb_docs: Callable[[Any], list[dict[str, Any]]],
    write_kb_docs: Callable[[Any, list[dict[str, Any]]], None],
) -> ResponseLike | None:
    if method == "GET" and path == "/api/kb":
        kb_docs = [
            _normalize_kb_record(item, preserve_updated_at=True)
            for item in load_kb_docs(runtime.kb_store_path)
        ]
        source_type = (query.get("source_type") or "").strip()
        q = (query.get("q") or "").strip().lower()
        page = parse_int(query.get("page"), default=1, minimum=1, maximum=100000)
        page_size = parse_int(query.get("page_size"), default=20, minimum=1, maximum=200)
        filtered_kb_docs: list[dict[str, Any]] = []
        for item in kb_docs:
            if source_type and str(item.get("source_type", "")) != source_type:
                continue
            haystack = f"{item.get('title', '')} {item.get('content', '')}".lower()
            if q and q not in haystack:
                continue
            filtered_kb_docs.append(item)
        total = len(filtered_kb_docs)
        start = (page - 1) * page_size
        end = start + page_size
        return json_response(
            req_id,
            {
                "items": filtered_kb_docs[start:end],
                "page": page,
                "page_size": page_size,
                "total": total,
            },
        )

    if method == "POST" and path == "/api/kb":
        doc_id = str(payload.get("doc_id") or f"doc_{uuid.uuid4().hex[:8]}")
        source_type = str(payload.get("source_type") or "").strip()
        title = str(payload.get("title") or "").strip()
        content = str(payload.get("content") or "").strip()
        tags = _normalize_kb_tags(payload.get("tags"))
        metadata = _normalize_kb_metadata(payload.get("metadata"))
        if source_type not in _VALID_KB_SOURCE_TYPES:
            return error_response(
                req_id,
                code="invalid_source_type",
                message="source_type must be faq/sop/history_case",
            )
        if not title or not content:
            return error_response(
                req_id,
                code="invalid_payload",
                message="title and content are required",
            )

        kb_docs = [
            _normalize_kb_record(item, preserve_updated_at=True)
            for item in load_kb_docs(runtime.kb_store_path)
        ]
        if any(str(item.get("doc_id")) == doc_id for item in kb_docs):
            return error_response(
                req_id,
                code="doc_exists",
                message=f"doc {doc_id} already exists",
            )
        record = _normalize_kb_record(
            {
                "doc_id": doc_id,
                "source_type": source_type,
                "title": title,
                "content": content,
                "tags": tags,
                "metadata": metadata,
                "updated_at": datetime.now(UTC).isoformat(),
            },
            preserve_updated_at=True,
        )
        kb_docs.append(record)
        write_kb_docs(runtime.kb_store_path, kb_docs)
        return json_response(req_id, {"data": record}, status=HTTPStatus.CREATED)

    if method == "PATCH" and (match := KB_DOC_RE.match(path)):
        doc_id = match.group("doc_id")
        kb_docs = [
            _normalize_kb_record(item, preserve_updated_at=True)
            for item in load_kb_docs(runtime.kb_store_path)
        ]
        if "source_type" in payload:
            next_source_type = str(payload.get("source_type") or "").strip()
            if next_source_type not in _VALID_KB_SOURCE_TYPES:
                return error_response(
                    req_id,
                    code="invalid_source_type",
                    message="source_type must be faq/sop/history_case",
                )
        updated_doc: dict[str, Any] | None = None
        for item in kb_docs:
            if str(item.get("doc_id")) != doc_id:
                continue
            for key in ("title", "content", "source_type"):
                if key in payload:
                    item[key] = str(payload.get(key) or "").strip()
            if "tags" in payload:
                item["tags"] = _normalize_kb_tags(payload.get("tags"))
            if "metadata" in payload:
                item["metadata"] = _normalize_kb_metadata(payload.get("metadata"))
            item["updated_at"] = datetime.now(UTC).isoformat()
            normalized = _normalize_kb_record(item, preserve_updated_at=True)
            item.clear()
            item.update(normalized)
            updated_doc = item
            break
        if updated_doc is None:
            return error_response(
                req_id,
                code="doc_not_found",
                message=f"doc {doc_id} not found",
                status=HTTPStatus.NOT_FOUND,
            )
        write_kb_docs(runtime.kb_store_path, kb_docs)
        return json_response(req_id, {"data": updated_doc})

    if method == "DELETE" and (match := KB_DOC_RE.match(path)):
        doc_id = match.group("doc_id")
        kb_docs = [
            _normalize_kb_record(item, preserve_updated_at=True)
            for item in load_kb_docs(runtime.kb_store_path)
        ]
        remaining = [item for item in kb_docs if str(item.get("doc_id")) != doc_id]
        if len(remaining) == len(kb_docs):
            return error_response(
                req_id,
                code="doc_not_found",
                message=f"doc {doc_id} not found",
                status=HTTPStatus.NOT_FOUND,
            )
        write_kb_docs(runtime.kb_store_path, remaining)
        return json_response(req_id, {"deleted": True, "doc_id": doc_id})

    return None


def try_handle_channel_routes(
    *,
    runtime: Any,
    method: str,
    path: str,
    req_id: str,
    query: dict[str, str],
    json_response: Callable[[str, dict[str, Any]], ResponseLike],
    reliability_snapshot: Callable[[Any], dict[str, Any]],
    paginate_payload: Callable[..., dict[str, Any]],
    collect_openclaw_status: Callable[[Any], dict[str, Any]],
) -> ResponseLike | None:
    if method == "GET" and path == "/api/channels/health":
        recent = runtime.trace_logger.read_recent(limit=200)
        channels = runtime.gateway.bindings.channel_router.supported_channels
        reliability = reliability_snapshot(runtime)
        signature_rows = reliability.get("signature", {}).get("items", [])
        replay_rows = reliability.get("replays", {}).get("items", [])
        retry_rows = reliability.get("retries", {}).get("items", [])
        signature_by_channel = {
            str(row.get("channel")): row
            for row in signature_rows
            if isinstance(row, dict) and row.get("channel")
        }
        rows = []
        for channel in channels:
            channel_events = [
                event
                for event in recent
                if isinstance(event.get("payload"), dict)
                and str((event["payload"]).get("channel", "")) == channel
            ]
            last_event = channel_events[-1] if channel_events else None
            last_error = None
            retry_state = "idle"
            if last_event and isinstance(last_event.get("payload"), dict):
                payload_dict = last_event["payload"]
                if "error" in payload_dict:
                    last_error = payload_dict.get("error")
                    retry_state = "retry_pending"

            channel_replays = [
                row
                for row in replay_rows
                if isinstance(row, dict) and str(row.get("channel") or "") == channel
            ]
            replay_duplicates = sum(
                1 for row in channel_replays if bool(row.get("accepted", True)) is False
            )
            channel_retry_failures = [
                row
                for row in retry_rows
                if isinstance(row, dict)
                and str(row.get("channel") or "") == channel
                and str(row.get("event_type") or "") == "egress_failed"
            ]
            retry_observed = sum(
                1 for row in channel_retry_failures if isinstance(row.get("classification"), str)
            )
            retry_observability = (
                round(retry_observed / len(channel_retry_failures), 4)
                if channel_retry_failures
                else 1.0
            )
            signature_row = signature_by_channel.get(channel, {})
            signature_checked = int(signature_row.get("checked", 0)) if signature_row else 0
            signature_rejected = int(signature_row.get("rejected", 0)) if signature_row else 0
            if signature_rejected > 0:
                signature_state = "rejected"
            elif signature_checked > 0:
                signature_state = "verified"
            else:
                signature_state = "skipped"
            rows.append(
                {
                    "channel": channel,
                    "connected": True,
                    "last_event_at": (last_event or {}).get("timestamp"),
                    "last_error": last_error,
                    "retry_state": retry_state,
                    "signature_state": signature_state,
                    "replay_duplicates": replay_duplicates,
                    "retry_observability": retry_observability,
                }
            )
        return json_response(
            req_id,
            {
                "items": rows,
                "summary": {
                    "signature": reliability.get("signature", {}).get("totals", {}),
                    "replays": {
                        "total": reliability.get("replays", {}).get("total", 0),
                        "duplicate_count": reliability.get("replays", {}).get("duplicate_count", 0),
                    },
                    "retries": {
                        "failed_count": reliability.get("retries", {}).get("failed_count", 0),
                        "observability_rate": reliability.get("retries", {}).get(
                            "observability_rate", 1.0
                        ),
                    },
                },
            },
        )

    if method == "GET" and path == "/api/channels/events":
        recent_events = runtime.trace_logger.read_recent(limit=100)
        rows = []
        for event in recent_events:
            payload_dict = event.get("payload")
            payload = payload_dict if isinstance(payload_dict, dict) else {}
            channel_name = payload.get("channel")
            if not channel_name:
                continue
            rows.append(
                {
                    "timestamp": event.get("timestamp"),
                    "trace_id": event.get("trace_id"),
                    "channel": channel_name,
                    "event_type": event.get("event_type"),
                    "payload": payload,
                }
            )
        return json_response(req_id, {"items": rows[-50:]})

    if method == "GET" and path == "/api/openclaw/status":
        return json_response(req_id, {"data": collect_openclaw_status(runtime)})

    if method == "GET" and path == "/api/openclaw/routes":
        channels = runtime.gateway.bindings.channel_router.supported_channels
        return json_response(
            req_id,
            {
                "gateway": runtime.app_config.gateway.name,
                "routes": [
                    {"channel": channel, "mode": "ingress/session/routing"} for channel in channels
                ],
            },
        )

    if method == "GET" and path == "/api/openclaw/retries":
        reliability = reliability_snapshot(runtime)
        retry_items = reliability.get("retries", {}).get("items", [])
        items = [row for row in retry_items if isinstance(row, dict)]
        return json_response(
            req_id,
            {
                **paginate_payload(items, query=query),
                "observability_rate": reliability.get("retries", {}).get("observability_rate", 1.0),
            },
        )

    if method == "GET" and path == "/api/openclaw/replays":
        reliability = reliability_snapshot(runtime)
        replay_items = reliability.get("replays", {}).get("items", [])
        items = [row for row in replay_items if isinstance(row, dict)]
        return json_response(
            req_id,
            {
                **paginate_payload(items, query=query),
                "duplicate_count": reliability.get("replays", {}).get("duplicate_count", 0),
                "duplicate_ratio": reliability.get("replays", {}).get("duplicate_ratio", 0.0),
                "non_duplicate_ratio": reliability.get("replays", {}).get(
                    "non_duplicate_ratio", 1.0
                ),
            },
        )

    if method == "GET" and path == "/api/openclaw/sessions":
        reliability = reliability_snapshot(runtime)
        session_items = reliability.get("sessions", {}).get("items", [])
        items = [row for row in session_items if isinstance(row, dict)]
        return json_response(
            req_id,
            {
                **paginate_payload(items, query=query),
                "bound_to_ticket": reliability.get("sessions", {}).get("bound_to_ticket", 0),
            },
        )

    if method == "GET" and path == "/api/channels/signature-status":
        reliability = reliability_snapshot(runtime)
        signature_items = reliability.get("signature", {}).get("items", [])
        items = [row for row in signature_items if isinstance(row, dict)]
        return json_response(
            req_id,
            {
                **paginate_payload(items, query=query),
                "totals": reliability.get("signature", {}).get("totals", {}),
            },
        )

    return None

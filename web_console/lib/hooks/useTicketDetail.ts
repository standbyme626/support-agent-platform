"use client";

import { useEffect, useState } from "react";
import {
  draftTicketReply,
  endSession,
  fetchAssignees,
  fetchGroundingSources,
  fetchTicketReplyEvents,
  getTicketSessionId,
  investigateTicket,
  queryDispatchCopilot,
  queryOperatorCopilot,
  fetchSimilarCases,
  fetchTicketAssist,
  fetchTicketDetail,
  fetchTicketEvents,
  queryTicketCopilot,
  runTicketAction,
  sendTicketReply,
  type GroundingSourceItem,
  type ReplyDraftData,
  type ReplyDraftPayload,
  type ReplyEventItem,
  type ReplySendData,
  type ReplySendPayload,
  type SessionEndData,
  sortTicketEvents,
  type SimilarCaseItem,
  type TicketInvestigationData,
  type TicketActionPayload,
  type TicketActionType,
  type TicketAssistResponse,
  type TicketCopilotQueryData,
  type TicketEventItem,
  type TicketItem
} from "@/lib/api/tickets";

type State = {
  loading: boolean;
  error: string | null;
  actionLoading: TicketActionType | null;
  actionError: string | null;
  ticket: TicketItem | null;
  assist: TicketAssistResponse | null;
  copilot: TicketCopilotQueryData | null;
  operatorCopilot: TicketCopilotQueryData | null;
  dispatchCopilot: TicketCopilotQueryData | null;
  copilotLoading: boolean;
  copilotError: string | null;
  investigation: TicketInvestigationData | null;
  investigationLoading: boolean;
  investigationError: string | null;
  sessionEnd: SessionEndData | null;
  sessionEndLoading: boolean;
  sessionEndError: string | null;
  replyDraft: ReplyDraftData | null;
  replyDraftLoading: boolean;
  replyDraftError: string | null;
  replySend: ReplySendData | null;
  replySendLoading: boolean;
  replySendError: string | null;
  replyEvents: ReplyEventItem[];
  groundingSources: GroundingSourceItem[];
  similarCases: SimilarCaseItem[];
  events: TicketEventItem[];
  assignees: string[];
};

export function useTicketDetail(ticketId: string) {
  const [state, setState] = useState<State>({
    loading: true,
    error: null,
    actionLoading: null,
    actionError: null,
    ticket: null,
    assist: null,
    copilot: null,
    operatorCopilot: null,
    dispatchCopilot: null,
    copilotLoading: false,
    copilotError: null,
    investigation: null,
    investigationLoading: false,
    investigationError: null,
    sessionEnd: null,
    sessionEndLoading: false,
    sessionEndError: null,
    replyDraft: null,
    replyDraftLoading: false,
    replyDraftError: null,
    replySend: null,
    replySendLoading: false,
    replySendError: null,
    replyEvents: [],
    groundingSources: [],
    similarCases: [],
    events: [],
    assignees: []
  });

  async function load(options?: { silent?: boolean }) {
    const silent = options?.silent ?? false;
    setState((previous) => ({
      ...previous,
      loading: silent ? previous.loading : true,
      error: null
    }));
    try {
      const [detail, assist, groundingSources, similarCases, events, replyEvents, assignees] =
        await Promise.all([
        fetchTicketDetail(ticketId),
        fetchTicketAssist(ticketId),
        fetchGroundingSources(ticketId),
        fetchSimilarCases(ticketId),
        fetchTicketEvents(ticketId),
        fetchTicketReplyEvents(ticketId),
        fetchAssignees()
      ]);
      setState((previous) => ({
        ...previous,
        loading: false,
        error: null,
        ticket: detail.data,
        assist,
        groundingSources: groundingSources.items,
        similarCases: similarCases.items,
        events: sortTicketEvents(events.items),
        replyEvents: replyEvents.items,
        assignees: assignees.items
      }));
    } catch (error) {
      setState((previous) => ({
        ...previous,
        loading: silent ? previous.loading : false,
        error: error instanceof Error ? error.message : "Failed to load ticket detail"
      }));
    }
  }

  async function refreshReplyArtifacts() {
    const [events, replyEvents] = await Promise.all([
      fetchTicketEvents(ticketId),
      fetchTicketReplyEvents(ticketId)
    ]);
    setState((previous) => ({
      ...previous,
      events: sortTicketEvents(events.items),
      replyEvents: replyEvents.items
    }));
  }

  async function runAction(action: TicketActionType, payload: TicketActionPayload) {
    setState((previous) => ({ ...previous, actionLoading: action, actionError: null }));
    try {
      const actionResponse = await runTicketAction(ticketId, action, payload);
      setState((previous) => ({
        ...previous,
        ticket: actionResponse.data
      }));
      const [assist, events, replyEvents, groundingSources, similarCases] = await Promise.all([
        fetchTicketAssist(ticketId),
        fetchTicketEvents(ticketId),
        fetchTicketReplyEvents(ticketId),
        fetchGroundingSources(ticketId),
        fetchSimilarCases(ticketId)
      ]);
      setState((previous) => ({
        ...previous,
        assist,
        events: sortTicketEvents(events.items),
        replyEvents: replyEvents.items,
        groundingSources: groundingSources.items,
        similarCases: similarCases.items
      }));
    } catch (error) {
      const message = error instanceof Error ? error.message : "Failed to execute action";
      setState((previous) => ({
        ...previous,
        actionError: message
      }));
      throw error instanceof Error ? error : new Error(message);
    } finally {
      setState((previous) => ({ ...previous, actionLoading: null }));
    }
  }

  async function queryCopilot(query: string) {
    const trimmed = query.trim();
    if (!trimmed) {
      setState((previous) => ({
        ...previous,
        copilot: null,
        operatorCopilot: null,
        dispatchCopilot: null,
        copilotError: null
      }));
      return null;
    }
    setState((previous) => ({
      ...previous,
      copilotLoading: true,
      copilotError: null
    }));
    const [ticketResult, operatorResult, dispatchResult] = await Promise.allSettled([
      queryTicketCopilot(ticketId, trimmed),
      queryOperatorCopilot(trimmed),
      queryDispatchCopilot(trimmed)
    ]);

    const ticketData = ticketResult.status === "fulfilled" ? ticketResult.value.data : null;
    const operatorData = operatorResult.status === "fulfilled" ? operatorResult.value.data : null;
    const dispatchData = dispatchResult.status === "fulfilled" ? dispatchResult.value.data : null;
    const failures: string[] = [];
    if (ticketResult.status === "rejected") {
      failures.push("ticket");
    }
    if (operatorResult.status === "rejected") {
      failures.push("operator");
    }
    if (dispatchResult.status === "rejected") {
      failures.push("dispatch");
    }

    const allFailed = failures.length === 3;
    const warningMessage =
      failures.length === 0
        ? null
        : allFailed
          ? "Failed to query ticket copilot"
          : `Partial copilot degraded: ${failures.join(", ")} branch failed`;

    setState((previous) => ({
      ...previous,
      copilot: ticketData,
      operatorCopilot: operatorData,
      dispatchCopilot: dispatchData,
      copilotLoading: false,
      copilotError: warningMessage
    }));

    if (allFailed) {
      throw new Error("Failed to query ticket copilot");
    }

    return ticketData ?? operatorData ?? dispatchData;
  }

  async function runInvestigation(question: string, actorId?: string) {
    const normalizedQuestion = question.trim();
    const normalizedActor = actorId?.trim() || state.ticket?.assignee || "u_ops_01";
    setState((previous) => ({
      ...previous,
      investigationLoading: true,
      investigationError: null
    }));
    try {
      const response = await investigateTicket(ticketId, {
        actor_id: normalizedActor,
        question: normalizedQuestion || undefined
      });
      setState((previous) => ({
        ...previous,
        investigation: response.data,
        investigationLoading: false,
        investigationError: null
      }));
      return response.data;
    } catch (error) {
      const message = error instanceof Error ? error.message : "Failed to run ticket investigation";
      setState((previous) => ({
        ...previous,
        investigationLoading: false,
        investigationError: message
      }));
      throw error instanceof Error ? error : new Error(message);
    }
  }

  async function runSessionEnd(reason: string, actorId?: string) {
    const sessionId = getTicketSessionId(state.ticket);
    if (!sessionId) {
      throw new Error("session_id is required");
    }
    const normalizedReason = reason.trim() || "manual_end";
    const normalizedActor = actorId?.trim() || state.ticket?.assignee || "u_ops_01";
    setState((previous) => ({
      ...previous,
      sessionEndLoading: true,
      sessionEndError: null
    }));
    try {
      const response = await endSession(sessionId, {
        actor_id: normalizedActor,
        reason: normalizedReason
      });
      setState((previous) => ({
        ...previous,
        sessionEnd: response.data,
        sessionEndLoading: false,
        sessionEndError: null
      }));
      await load({ silent: true });
      return response.data;
    } catch (error) {
      const message = error instanceof Error ? error.message : "Failed to end session";
      setState((previous) => ({
        ...previous,
        sessionEndLoading: false,
        sessionEndError: message
      }));
      throw error instanceof Error ? error : new Error(message);
    }
  }

  async function runReplyDraft(payload: ReplyDraftPayload) {
    setState((previous) => ({
      ...previous,
      replyDraftLoading: true,
      replyDraftError: null
    }));
    try {
      const response = await draftTicketReply(ticketId, payload);
      setState((previous) => ({
        ...previous,
        replyDraft: response.data,
        replyDraftLoading: false,
        replyDraftError: null
      }));
      await refreshReplyArtifacts();
      return response.data;
    } catch (error) {
      const message = error instanceof Error ? error.message : "Failed to generate reply draft";
      setState((previous) => ({
        ...previous,
        replyDraftLoading: false,
        replyDraftError: message
      }));
      throw error instanceof Error ? error : new Error(message);
    }
  }

  async function runReplySend(payload: ReplySendPayload) {
    setState((previous) => ({
      ...previous,
      replySendLoading: true,
      replySendError: null
    }));
    try {
      const response = await sendTicketReply(ticketId, payload);
      setState((previous) => ({
        ...previous,
        replySend: response.data,
        replySendLoading: false,
        replySendError:
          response.data.delivery_status === "failed" ? response.data.error || "Send failed" : null
      }));
      await refreshReplyArtifacts();
      return response.data;
    } catch (error) {
      const message = error instanceof Error ? error.message : "Failed to send reply";
      setState((previous) => ({
        ...previous,
        replySendLoading: false,
        replySendError: message
      }));
      throw error instanceof Error ? error : new Error(message);
    }
  }

  useEffect(() => {
    if (!ticketId) {
      return;
    }
    void load();
  }, [ticketId]);

  return {
    ...state,
    refetch: load,
    runAction,
    runReplyDraft,
    runReplySend,
    queryCopilot,
    runInvestigation,
    runSessionEnd
  };
}

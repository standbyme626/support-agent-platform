"use client";

import { useEffect, useState } from "react";
import {
  endSession,
  fetchAssignees,
  fetchGroundingSources,
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
  type GroundingSourceItem,
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
    groundingSources: [],
    similarCases: [],
    events: [],
    assignees: []
  });

  async function load() {
    setState((previous) => ({ ...previous, loading: true, error: null }));
    try {
      const [detail, assist, groundingSources, similarCases, events, assignees] = await Promise.all([
        fetchTicketDetail(ticketId),
        fetchTicketAssist(ticketId),
        fetchGroundingSources(ticketId),
        fetchSimilarCases(ticketId),
        fetchTicketEvents(ticketId),
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
        assignees: assignees.items
      }));
    } catch (error) {
      setState((previous) => ({
        ...previous,
        loading: false,
        error: error instanceof Error ? error.message : "Failed to load ticket detail"
      }));
    }
  }

  async function runAction(action: TicketActionType, payload: TicketActionPayload) {
    setState((previous) => ({ ...previous, actionLoading: action, actionError: null }));
    try {
      await runTicketAction(ticketId, action, payload);
      await load();
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
    try {
      const [ticketResponse, operatorResponse, dispatchResponse] = await Promise.all([
        queryTicketCopilot(ticketId, trimmed),
        queryOperatorCopilot(trimmed),
        queryDispatchCopilot(trimmed)
      ]);
      setState((previous) => ({
        ...previous,
        copilot: ticketResponse.data,
        operatorCopilot: operatorResponse.data,
        dispatchCopilot: dispatchResponse.data,
        copilotLoading: false,
        copilotError: null
      }));
      return ticketResponse.data;
    } catch (error) {
      const message = error instanceof Error ? error.message : "Failed to query ticket copilot";
      setState((previous) => ({
        ...previous,
        copilotLoading: false,
        copilotError: message
      }));
      throw error instanceof Error ? error : new Error(message);
    }
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
      await load();
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
    queryCopilot,
    runInvestigation,
    runSessionEnd
  };
}

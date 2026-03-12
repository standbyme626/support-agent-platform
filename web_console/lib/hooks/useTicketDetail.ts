"use client";

import { useEffect, useState } from "react";
import {
  fetchAssignees,
  fetchGroundingSources,
  fetchSimilarCases,
  fetchTicketAssist,
  fetchTicketDetail,
  fetchTicketEvents,
  runTicketAction,
  type GroundingSourceItem,
  sortTicketEvents,
  type SimilarCaseItem,
  type TicketActionPayload,
  type TicketActionType,
  type TicketAssistResponse,
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

  useEffect(() => {
    if (!ticketId) {
      return;
    }
    void load();
  }, [ticketId]);

  return {
    ...state,
    refetch: load,
    runAction
  };
}

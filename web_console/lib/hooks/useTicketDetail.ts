"use client";

import { useEffect, useState } from "react";
import {
  fetchAssignees,
  fetchSimilarCases,
  fetchTicketAssist,
  fetchTicketDetail,
  fetchTicketEvents,
  runTicketAction,
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
    similarCases: [],
    events: [],
    assignees: []
  });

  async function load() {
    setState((previous) => ({ ...previous, loading: true, error: null }));
    try {
      const [detail, assist, similarCases, events, assignees] = await Promise.all([
        fetchTicketDetail(ticketId),
        fetchTicketAssist(ticketId),
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
      setState((previous) => ({
        ...previous,
        actionError: error instanceof Error ? error.message : "Failed to execute action"
      }));
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

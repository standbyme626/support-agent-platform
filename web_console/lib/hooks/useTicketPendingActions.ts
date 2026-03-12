"use client";

import { useEffect, useState } from "react";
import {
  decideApproval,
  fetchTicketPendingActions,
  type PendingApprovalItem
} from "@/lib/api/tickets";

type TicketPendingState = {
  loading: boolean;
  actionLoadingId: string | null;
  error: string | null;
  items: PendingApprovalItem[];
};

export function useTicketPendingActions(ticketId: string) {
  const [state, setState] = useState<TicketPendingState>({
    loading: true,
    actionLoadingId: null,
    error: null,
    items: []
  });

  async function load() {
    setState((previous) => ({ ...previous, loading: true, error: null }));
    try {
      const response = await fetchTicketPendingActions(ticketId);
      setState((previous) => ({
        ...previous,
        loading: false,
        error: null,
        items: response.items
      }));
    } catch (error) {
      setState((previous) => ({
        ...previous,
        loading: false,
        error: error instanceof Error ? error.message : "Failed to load ticket pending actions"
      }));
    }
  }

  async function approve(approvalId: string, note: string, actorId: string) {
    setState((previous) => ({ ...previous, actionLoadingId: approvalId, error: null }));
    try {
      await decideApproval(approvalId, "approve", { actor_id: actorId, note });
      await load();
    } catch (error) {
      setState((previous) => ({
        ...previous,
        error: error instanceof Error ? error.message : "Approval failed"
      }));
      throw error;
    } finally {
      setState((previous) => ({ ...previous, actionLoadingId: null }));
    }
  }

  async function reject(approvalId: string, note: string, actorId: string) {
    setState((previous) => ({ ...previous, actionLoadingId: approvalId, error: null }));
    try {
      await decideApproval(approvalId, "reject", { actor_id: actorId, note });
      await load();
    } catch (error) {
      setState((previous) => ({
        ...previous,
        error: error instanceof Error ? error.message : "Rejection failed"
      }));
      throw error;
    } finally {
      setState((previous) => ({ ...previous, actionLoadingId: null }));
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
    approve,
    reject
  };
}

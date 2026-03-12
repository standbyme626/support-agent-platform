"use client";

import { useEffect, useState } from "react";
import {
  decideApproval,
  fetchPendingApprovals,
  type PendingApprovalItem
} from "@/lib/api/tickets";

type PendingApprovalsState = {
  loading: boolean;
  actionLoadingId: string | null;
  error: string | null;
  items: PendingApprovalItem[];
};

export function usePendingApprovals() {
  const [state, setState] = useState<PendingApprovalsState>({
    loading: true,
    actionLoadingId: null,
    error: null,
    items: []
  });

  async function load() {
    setState((previous) => ({ ...previous, loading: true, error: null }));
    try {
      const response = await fetchPendingApprovals({ page: 1, page_size: 50 });
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
        error: error instanceof Error ? error.message : "Failed to load pending approvals"
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
    void load();
  }, []);

  return {
    ...state,
    refetch: load,
    approve,
    reject
  };
}

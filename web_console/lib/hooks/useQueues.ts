"use client";

import { useEffect, useState } from "react";
import { fetchQueues, fetchQueueSummary, type QueueSummaryItem } from "@/lib/api/queues";

type HookState = {
  loading: boolean;
  error: string | null;
  items: QueueSummaryItem[];
  summary: QueueSummaryItem[];
};

export function useQueues() {
  const [state, setState] = useState<HookState>({
    loading: true,
    error: null,
    items: [],
    summary: []
  });

  async function load() {
    setState((previous) => ({ ...previous, loading: true, error: null }));
    try {
      const [queuesResponse, summaryResponse] = await Promise.all([fetchQueues(), fetchQueueSummary()]);
      setState({
        loading: false,
        error: null,
        items: queuesResponse.items,
        summary: summaryResponse.items
      });
    } catch (error) {
      setState({
        loading: false,
        error: error instanceof Error ? error.message : "Failed to load queues",
        items: [],
        summary: []
      });
    }
  }

  useEffect(() => {
    void load();
  }, []);

  return {
    ...state,
    refetch: load
  };
}

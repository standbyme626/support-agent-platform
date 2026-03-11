"use client";

import { useEffect, useState } from "react";
import { fetchQueueSummary, type QueueSummaryItem } from "@/lib/api/queues";

type HookState = {
  loading: boolean;
  error: string | null;
  data: QueueSummaryItem[];
};

export function useQueueSummary() {
  const [state, setState] = useState<HookState>({
    loading: true,
    error: null,
    data: []
  });

  async function load() {
    setState((previous) => ({ ...previous, loading: true, error: null }));
    try {
      const response = await fetchQueueSummary();
      setState({ loading: false, error: null, data: response.items });
    } catch (error) {
      setState({
        loading: false,
        error: error instanceof Error ? error.message : "Failed to load queue summary",
        data: []
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

"use client";

import { useEffect, useState } from "react";
import { fetchTraceDetail, type TraceDetail } from "@/lib/api/traces";

type State = {
  loading: boolean;
  error: string | null;
  data: TraceDetail | null;
};

export function useTraceDetail(traceId: string) {
  const [state, setState] = useState<State>({
    loading: true,
    error: null,
    data: null
  });

  async function load() {
    setState((previous) => ({ ...previous, loading: true, error: null }));
    try {
      const response = await fetchTraceDetail(traceId);
      setState({
        loading: false,
        error: null,
        data: response
      });
    } catch (error) {
      setState({
        loading: false,
        error: error instanceof Error ? error.message : "Failed to load trace detail",
        data: null
      });
    }
  }

  useEffect(() => {
    if (!traceId) {
      return;
    }
    void load();
  }, [traceId]);

  return {
    ...state,
    refetch: load
  };
}

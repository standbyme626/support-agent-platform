"use client";

import { useEffect, useState } from "react";
import { fetchDashboardSummary, type DashboardSummary } from "@/lib/api/dashboard";

type HookState = {
  loading: boolean;
  error: string | null;
  data: DashboardSummary | null;
};

export function useDashboardSummary() {
  const [state, setState] = useState<HookState>({
    loading: true,
    error: null,
    data: null
  });

  async function load() {
    setState((previous) => ({ ...previous, loading: true, error: null }));
    try {
      const response = await fetchDashboardSummary();
      setState({ loading: false, error: null, data: response.data });
    } catch (error) {
      setState({
        loading: false,
        error: error instanceof Error ? error.message : "Failed to load dashboard summary",
        data: null
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

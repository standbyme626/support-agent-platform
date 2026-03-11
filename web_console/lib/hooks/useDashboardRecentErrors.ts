"use client";

import { useEffect, useState } from "react";
import { fetchDashboardRecentErrors, type DashboardErrorItem } from "@/lib/api/dashboard";

type HookState = {
  loading: boolean;
  error: string | null;
  data: DashboardErrorItem[];
};

export function useDashboardRecentErrors() {
  const [state, setState] = useState<HookState>({
    loading: true,
    error: null,
    data: []
  });

  async function load() {
    setState((previous) => ({ ...previous, loading: true, error: null }));
    try {
      const response = await fetchDashboardRecentErrors();
      setState({ loading: false, error: null, data: response.data });
    } catch (error) {
      setState({
        loading: false,
        error: error instanceof Error ? error.message : "Failed to load recent errors",
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

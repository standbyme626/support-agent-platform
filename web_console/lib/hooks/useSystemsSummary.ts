"use client";

import { useEffect, useState } from "react";
import { fetchSystemsSummary, type SystemSummary } from "@/lib/api/systems";

type HookState = {
  loading: boolean;
  error: string | null;
  data: SystemSummary[] | null;
  totalSystems: number;
};

export function useSystemsSummary() {
  const [state, setState] = useState<HookState>({
    loading: true,
    error: null,
    data: null,
    totalSystems: 0,
  });

  async function load() {
    setState((previous) => ({ ...previous, loading: true, error: null }));
    try {
      const response = await fetchSystemsSummary();
      setState({
        loading: false,
        error: null,
        data: response.systems || [],
        totalSystems: response.total_systems || 0,
      });
    } catch (error) {
      setState({
        loading: false,
        error: error instanceof Error ? error.message : "Failed to load systems summary",
        data: null,
        totalSystems: 0,
      });
    }
  }

  useEffect(() => {
    void load();
  }, []);

  return {
    ...state,
    refetch: load,
  };
}

"use client";

import { useEffect, useState } from "react";
import { fetchTraces, type TraceListItem, type TraceListQuery } from "@/lib/api/traces";

type TraceFilters = Omit<TraceListQuery, "page" | "page_size">;

type State = {
  loading: boolean;
  error: string | null;
  items: TraceListItem[];
  total: number;
  page: number;
  pageSize: number;
  filters: TraceFilters;
};

function buildQuery(page: number, pageSize: number, filters: TraceFilters): TraceListQuery {
  return {
    page,
    page_size: pageSize,
    ...filters
  };
}

export function useTraceList() {
  const [state, setState] = useState<State>({
    loading: true,
    error: null,
    items: [],
    total: 0,
    page: 1,
    pageSize: 20,
    filters: {}
  });

  async function load(query: TraceListQuery) {
    setState((previous) => ({ ...previous, loading: true, error: null }));
    try {
      const response = await fetchTraces(query);
      setState((previous) => ({
        ...previous,
        loading: false,
        error: null,
        items: response.items,
        total: response.total
      }));
    } catch (error) {
      setState((previous) => ({
        ...previous,
        loading: false,
        error: error instanceof Error ? error.message : "Failed to load traces"
      }));
    }
  }

  useEffect(() => {
    void load(buildQuery(state.page, state.pageSize, state.filters));
  }, [state.page, state.pageSize, JSON.stringify(state.filters)]);

  return {
    ...state,
    refetch: () => load(buildQuery(state.page, state.pageSize, state.filters)),
    setPage: (page: number) => setState((previous) => ({ ...previous, page })),
    updateFilters: (patch: Partial<TraceFilters>) =>
      setState((previous) => ({
        ...previous,
        page: 1,
        filters: { ...previous.filters, ...patch }
      })),
    clearFilters: () =>
      setState((previous) => ({
        ...previous,
        page: 1,
        filters: {}
      }))
  };
}

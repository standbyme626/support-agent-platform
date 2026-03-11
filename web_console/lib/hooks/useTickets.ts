"use client";

import { useEffect, useState } from "react";
import { fetchAssignees, fetchTickets, type TicketItem, type TicketQuery } from "@/lib/api/tickets";

const STORAGE_KEY = "ops_tickets_filters_v1";

type TicketFilters = Omit<TicketQuery, "page" | "page_size" | "sort_by" | "sort_order">;

type HookState = {
  loading: boolean;
  error: string | null;
  items: TicketItem[];
  total: number;
  assignees: string[];
  page: number;
  pageSize: number;
  sortBy: string;
  sortOrder: "asc" | "desc";
  filters: TicketFilters;
};

function initialFilters(): TicketFilters {
  if (typeof window === "undefined") {
    return {};
  }

  const params = new URLSearchParams(window.location.search);
  if (Array.from(params.keys()).length > 0) {
    return {
      q: params.get("q") ?? undefined,
      status: params.get("status") ?? undefined,
      priority: params.get("priority") ?? undefined,
      queue: params.get("queue") ?? undefined,
      assignee: params.get("assignee") ?? undefined,
      channel: params.get("channel") ?? undefined,
      handoff_state: params.get("handoff_state") ?? undefined,
      service_type: params.get("service_type") ?? undefined,
      risk_level: params.get("risk_level") ?? undefined,
      created_from: params.get("created_from") ?? undefined,
      created_to: params.get("created_to") ?? undefined,
      sla_state: params.get("sla_state") ?? undefined
    };
  }

  const fromStorage = window.localStorage.getItem(STORAGE_KEY);
  if (!fromStorage) {
    return {};
  }
  try {
    return JSON.parse(fromStorage) as TicketFilters;
  } catch {
    return {};
  }
}

function mergeQuery(state: HookState): TicketQuery {
  return {
    page: state.page,
    page_size: state.pageSize,
    sort_by: state.sortBy,
    sort_order: state.sortOrder,
    ...state.filters
  };
}

export function useTickets() {
  const [state, setState] = useState<HookState>({
    loading: true,
    error: null,
    items: [],
    total: 0,
    assignees: [],
    page: 1,
    pageSize: 20,
    sortBy: "created_at",
    sortOrder: "desc",
    filters: initialFilters()
  });

  async function load(query: TicketQuery) {
    setState((previous) => ({ ...previous, loading: true, error: null }));
    try {
      const [ticketResponse, assigneeResponse] = await Promise.all([
        fetchTickets(query),
        fetchAssignees()
      ]);
      setState((previous) => ({
        ...previous,
        loading: false,
        error: null,
        items: ticketResponse.items,
        total: ticketResponse.total,
        assignees: assigneeResponse.items
      }));
    } catch (error) {
      setState((previous) => ({
        ...previous,
        loading: false,
        error: error instanceof Error ? error.message : "Failed to load tickets"
      }));
    }
  }

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }
    const params = new URLSearchParams();
    Object.entries(state.filters).forEach(([key, value]) => {
      if (value) {
        params.set(key, value);
      }
    });
    const queryString = params.toString();
    const url = queryString.length > 0 ? `/tickets?${queryString}` : "/tickets";
    window.history.replaceState(null, "", url);
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(state.filters));
  }, [state.filters]);

  useEffect(() => {
    const query = mergeQuery(state);
    void load(query);
  }, [state.page, state.pageSize, state.sortBy, state.sortOrder, JSON.stringify(state.filters)]);

  return {
    ...state,
    refetch: () => load(mergeQuery(state)),
    setPage: (page: number) => setState((previous) => ({ ...previous, page })),
    setPageSize: (pageSize: number) => setState((previous) => ({ ...previous, pageSize, page: 1 })),
    setSort: (sortBy: string, sortOrder: "asc" | "desc") =>
      setState((previous) => ({ ...previous, sortBy, sortOrder })),
    updateFilters: (patch: Partial<TicketFilters>) =>
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

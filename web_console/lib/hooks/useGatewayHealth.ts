"use client";

import { useEffect, useState } from "react";
import {
  fetchChannelEvents,
  fetchChannelHealth,
  fetchOpenClawRoutes,
  fetchOpenClawStatus,
  type ChannelEventItem,
  type ChannelHealthItem,
  type OpenClawRoute,
  type OpenClawStatus
} from "@/lib/api/channels";

type HookState = {
  loading: boolean;
  error: string | null;
  status: OpenClawStatus | null;
  routes: OpenClawRoute[];
  channelHealth: ChannelHealthItem[];
  events: ChannelEventItem[];
};

export function useGatewayHealth() {
  const [state, setState] = useState<HookState>({
    loading: true,
    error: null,
    status: null,
    routes: [],
    channelHealth: [],
    events: []
  });

  async function load() {
    setState((previous) => ({ ...previous, loading: true, error: null }));
    try {
      const [healthResponse, eventsResponse, statusResponse, routesResponse] = await Promise.all([
        fetchChannelHealth(),
        fetchChannelEvents(),
        fetchOpenClawStatus(),
        fetchOpenClawRoutes()
      ]);
      setState({
        loading: false,
        error: null,
        status: statusResponse.data,
        routes: routesResponse.routes,
        channelHealth: healthResponse.items,
        events: eventsResponse.items
      });
    } catch (error) {
      setState({
        loading: false,
        error: error instanceof Error ? error.message : "Failed to load channels and gateway metrics",
        status: null,
        routes: [],
        channelHealth: [],
        events: []
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

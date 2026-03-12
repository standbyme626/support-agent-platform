"use client";

import { useEffect, useState } from "react";
import {
  fetchChannelEvents,
  fetchChannelHealth,
  fetchOpenClawReplays,
  fetchOpenClawRetries,
  fetchOpenClawRoutes,
  fetchOpenClawSessions,
  fetchOpenClawStatus,
  fetchSignatureStatus,
  type ChannelEventItem,
  type ChannelHealthItem,
  type OpenClawRoute,
  type OpenClawSessionItem,
  type OpenClawStatus,
  type ReplayStatusItem,
  type RetryStatusItem,
  type SignatureStatusItem
} from "@/lib/api/channels";

type HookState = {
  loading: boolean;
  error: string | null;
  status: OpenClawStatus | null;
  routes: OpenClawRoute[];
  channelHealth: ChannelHealthItem[];
  events: ChannelEventItem[];
  signatures: SignatureStatusItem[];
  replays: ReplayStatusItem[];
  retries: RetryStatusItem[];
  sessions: OpenClawSessionItem[];
  replayDuplicateRatio: number;
  retryObservabilityRate: number;
};

export function useGatewayHealth() {
  const [state, setState] = useState<HookState>({
    loading: true,
    error: null,
    status: null,
    routes: [],
    channelHealth: [],
    events: [],
    signatures: [],
    replays: [],
    retries: [],
    sessions: [],
    replayDuplicateRatio: 0,
    retryObservabilityRate: 1
  });

  async function load() {
    setState((previous) => ({ ...previous, loading: true, error: null }));
    try {
      const [
        healthResponse,
        eventsResponse,
        statusResponse,
        routesResponse,
        signatureResponse,
        replayResponse,
        retryResponse,
        sessionResponse
      ] = await Promise.all([
        fetchChannelHealth(),
        fetchChannelEvents(),
        fetchOpenClawStatus(),
        fetchOpenClawRoutes(),
        fetchSignatureStatus(),
        fetchOpenClawReplays(),
        fetchOpenClawRetries(),
        fetchOpenClawSessions()
      ]);
      setState({
        loading: false,
        error: null,
        status: statusResponse.data,
        routes: routesResponse.routes,
        channelHealth: healthResponse.items,
        events: eventsResponse.items,
        signatures: signatureResponse.items,
        replays: replayResponse.items,
        retries: retryResponse.items,
        sessions: sessionResponse.items,
        replayDuplicateRatio: replayResponse.duplicate_ratio,
        retryObservabilityRate: retryResponse.observability_rate
      });
    } catch (error) {
      setState({
        loading: false,
        error: error instanceof Error ? error.message : "Failed to load channels and gateway metrics",
        status: null,
        routes: [],
        channelHealth: [],
        events: [],
        signatures: [],
        replays: [],
        retries: [],
        sessions: [],
        replayDuplicateRatio: 0,
        retryObservabilityRate: 1
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

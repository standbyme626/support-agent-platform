import { getJson } from "@/lib/api/client";

export type ChannelHealthItem = {
  channel: string;
  connected: boolean;
  last_event_at: string | null;
  last_error: Record<string, unknown> | string | null;
  retry_state: string;
};

export type ChannelEventItem = {
  timestamp: string | null;
  trace_id: string | null;
  channel: string;
  event_type: string;
  payload: Record<string, unknown>;
};

export type OpenClawStatus = {
  environment: string;
  gateway: string;
  sqlite_path: string;
  session_bindings: number;
  log_path: string;
  recent_events: Record<string, unknown>[];
};

export type OpenClawRoute = {
  channel: string;
  mode: string;
};

type ChannelHealthResponse = {
  request_id?: string;
  items?: Array<Partial<ChannelHealthItem> & { last_error?: unknown }>;
};

type ChannelEventsResponse = {
  request_id?: string;
  items?: Array<Partial<ChannelEventItem> & { payload?: unknown }>;
};

type OpenClawStatusResponse = {
  request_id?: string;
  data?: unknown;
};

type OpenClawRoutesResponse = {
  request_id?: string;
  gateway?: unknown;
  routes?: Array<Partial<OpenClawRoute>>;
};

function toStringOrNull(value: unknown): string | null {
  if (typeof value !== "string") {
    return null;
  }
  const normalized = value.trim();
  return normalized.length > 0 ? normalized : null;
}

function toStringOrFallback(value: unknown, fallback: string): string {
  return toStringOrNull(value) ?? fallback;
}

function toBoolean(value: unknown): boolean {
  if (typeof value === "boolean") {
    return value;
  }
  if (typeof value === "string") {
    return value.toLowerCase() === "true";
  }
  return false;
}

function toNumber(value: unknown): number {
  return typeof value === "number" && Number.isFinite(value) ? value : 0;
}

function toRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" && !Array.isArray(value) ? (value as Record<string, unknown>) : {};
}

function normalizeLastError(value: unknown): ChannelHealthItem["last_error"] {
  if (value === null || value === undefined) {
    return null;
  }
  if (typeof value === "string") {
    return value;
  }
  if (value && typeof value === "object" && !Array.isArray(value)) {
    return value as Record<string, unknown>;
  }
  return String(value);
}

function normalizeChannelHealthItem(
  item: Partial<ChannelHealthItem> & { last_error?: unknown },
  index: number
): ChannelHealthItem {
  return {
    channel: toStringOrFallback(item.channel, `channel-${index}`),
    connected: toBoolean(item.connected),
    last_event_at: toStringOrNull(item.last_event_at),
    last_error: normalizeLastError(item.last_error),
    retry_state: toStringOrFallback(item.retry_state, "unknown")
  };
}

function normalizeChannelEventItem(
  item: Partial<ChannelEventItem> & { payload?: unknown },
  index: number
): ChannelEventItem {
  return {
    timestamp: toStringOrNull(item.timestamp),
    trace_id: toStringOrNull(item.trace_id),
    channel: toStringOrFallback(item.channel, `channel-${index}`),
    event_type: toStringOrFallback(item.event_type, "event"),
    payload: toRecord(item.payload)
  };
}

function normalizeOpenClawStatus(data: unknown): OpenClawStatus {
  const source = toRecord(data);
  const rawEvents = Array.isArray(source.recent_events) ? source.recent_events : [];
  return {
    environment: toStringOrFallback(source.environment, "unknown"),
    gateway: toStringOrFallback(source.gateway, "openclaw"),
    sqlite_path: toStringOrFallback(source.sqlite_path, ""),
    session_bindings: toNumber(source.session_bindings),
    log_path: toStringOrFallback(source.log_path, ""),
    recent_events: rawEvents.map((event) => toRecord(event))
  };
}

function normalizeOpenClawRoute(item: Partial<OpenClawRoute>, index: number): OpenClawRoute {
  return {
    channel: toStringOrFallback(item.channel, `channel-${index}`),
    mode: toStringOrFallback(item.mode, "ingress/session/routing")
  };
}

export async function fetchChannelHealth() {
  const response = await getJson<ChannelHealthResponse>("/api/channels/health");
  const items = Array.isArray(response.items) ? response.items : [];
  return {
    ...response,
    items: items.map((item, index) => normalizeChannelHealthItem(item, index))
  };
}

export async function fetchChannelEvents() {
  const response = await getJson<ChannelEventsResponse>("/api/channels/events");
  const items = Array.isArray(response.items) ? response.items : [];
  return {
    ...response,
    items: items.map((item, index) => normalizeChannelEventItem(item, index))
  };
}

export async function fetchOpenClawStatus() {
  const response = await getJson<OpenClawStatusResponse>("/api/openclaw/status");
  return {
    ...response,
    data: normalizeOpenClawStatus(response.data)
  };
}

export async function fetchOpenClawRoutes() {
  const response = await getJson<OpenClawRoutesResponse>("/api/openclaw/routes");
  const routes = Array.isArray(response.routes) ? response.routes : [];
  return {
    ...response,
    gateway: toStringOrFallback(response.gateway, "openclaw"),
    routes: routes.map((route, index) => normalizeOpenClawRoute(route, index))
  };
}

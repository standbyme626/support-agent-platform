import { getJson } from "@/lib/api/client";

export type ChannelHealthItem = {
  channel: string;
  connected: boolean;
  last_event_at: string | null;
  last_error: Record<string, unknown> | string | null;
  retry_state: string;
  signature_state: string;
  replay_duplicates: number;
  retry_observability: number;
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

export type SignatureStatusItem = {
  channel: string;
  checked: number;
  valid: number;
  rejected: number;
  last_checked_at: string | null;
  last_error_code: string | null;
};

export type ReplayStatusItem = {
  timestamp: string | null;
  trace_id: string | null;
  channel: string;
  session_id: string;
  idempotency_key: string | null;
  accepted: boolean;
  replay_count: number;
};

export type RetryStatusItem = {
  timestamp: string | null;
  trace_id: string | null;
  channel: string;
  session_id: string;
  event_type: string;
  attempt: number;
  classification: string | null;
  should_retry: boolean | null;
  error_code: string | null;
  error_message: string | null;
};

export type OpenClawSessionItem = {
  session_id: string;
  thread_id: string;
  ticket_id: string | null;
  updated_at: string | null;
  channel: string | null;
  last_message_id: string | null;
  replay_count: number;
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

type SignatureStatusResponse = {
  request_id?: string;
  items?: Array<Partial<SignatureStatusItem>>;
  totals?: Record<string, unknown>;
};

type ReplayStatusResponse = {
  request_id?: string;
  items?: Array<Partial<ReplayStatusItem>>;
  duplicate_count?: unknown;
  duplicate_ratio?: unknown;
  non_duplicate_ratio?: unknown;
  total?: unknown;
};

type RetryStatusResponse = {
  request_id?: string;
  items?: Array<Partial<RetryStatusItem>>;
  observability_rate?: unknown;
  total?: unknown;
};

type OpenClawSessionsResponse = {
  request_id?: string;
  items?: Array<Partial<OpenClawSessionItem>>;
  bound_to_ticket?: unknown;
  total?: unknown;
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

function toNullableString(value: unknown): string | null {
  if (value === null || value === undefined) {
    return null;
  }
  return String(value);
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
    retry_state: toStringOrFallback(item.retry_state, "unknown"),
    signature_state: toStringOrFallback(item.signature_state, "unknown"),
    replay_duplicates: toNumber(item.replay_duplicates),
    retry_observability: toNumber(item.retry_observability)
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

function normalizeSignatureStatusItem(item: Partial<SignatureStatusItem>, index: number): SignatureStatusItem {
  return {
    channel: toStringOrFallback(item.channel, `channel-${index}`),
    checked: toNumber(item.checked),
    valid: toNumber(item.valid),
    rejected: toNumber(item.rejected),
    last_checked_at: toStringOrNull(item.last_checked_at),
    last_error_code: toNullableString(item.last_error_code)
  };
}

function normalizeReplayStatusItem(item: Partial<ReplayStatusItem>, index: number): ReplayStatusItem {
  return {
    timestamp: toStringOrNull(item.timestamp),
    trace_id: toStringOrNull(item.trace_id),
    channel: toStringOrFallback(item.channel, `channel-${index}`),
    session_id: toStringOrFallback(item.session_id, ""),
    idempotency_key: toNullableString(item.idempotency_key),
    accepted: toBoolean(item.accepted),
    replay_count: toNumber(item.replay_count)
  };
}

function normalizeRetryStatusItem(item: Partial<RetryStatusItem>, index: number): RetryStatusItem {
  return {
    timestamp: toStringOrNull(item.timestamp),
    trace_id: toStringOrNull(item.trace_id),
    channel: toStringOrFallback(item.channel, `channel-${index}`),
    session_id: toStringOrFallback(item.session_id, ""),
    event_type: toStringOrFallback(item.event_type, "unknown"),
    attempt: toNumber(item.attempt),
    classification: toNullableString(item.classification),
    should_retry: typeof item.should_retry === "boolean" ? item.should_retry : null,
    error_code: toNullableString(item.error_code),
    error_message: toNullableString(item.error_message)
  };
}

function normalizeSessionItem(item: Partial<OpenClawSessionItem>, index: number): OpenClawSessionItem {
  return {
    session_id: toStringOrFallback(item.session_id, `session-${index}`),
    thread_id: toStringOrFallback(item.thread_id, ""),
    ticket_id: toNullableString(item.ticket_id),
    updated_at: toStringOrNull(item.updated_at),
    channel: toNullableString(item.channel),
    last_message_id: toNullableString(item.last_message_id),
    replay_count: toNumber(item.replay_count)
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

export async function fetchSignatureStatus() {
  const response = await getJson<SignatureStatusResponse>("/api/channels/signature-status");
  const items = Array.isArray(response.items) ? response.items : [];
  return {
    ...response,
    items: items.map((item, index) => normalizeSignatureStatusItem(item, index)),
    totals: toRecord(response.totals)
  };
}

export async function fetchOpenClawReplays() {
  const response = await getJson<ReplayStatusResponse>("/api/openclaw/replays");
  const items = Array.isArray(response.items) ? response.items : [];
  return {
    ...response,
    items: items.map((item, index) => normalizeReplayStatusItem(item, index)),
    duplicate_count: toNumber(response.duplicate_count),
    duplicate_ratio: toNumber(response.duplicate_ratio),
    non_duplicate_ratio: toNumber(response.non_duplicate_ratio),
    total: toNumber(response.total)
  };
}

export async function fetchOpenClawRetries() {
  const response = await getJson<RetryStatusResponse>("/api/openclaw/retries");
  const items = Array.isArray(response.items) ? response.items : [];
  return {
    ...response,
    items: items.map((item, index) => normalizeRetryStatusItem(item, index)),
    observability_rate: toNumber(response.observability_rate),
    total: toNumber(response.total)
  };
}

export async function fetchOpenClawSessions() {
  const response = await getJson<OpenClawSessionsResponse>("/api/openclaw/sessions");
  const items = Array.isArray(response.items) ? response.items : [];
  return {
    ...response,
    items: items.map((item, index) => normalizeSessionItem(item, index)),
    bound_to_ticket: toNumber(response.bound_to_ticket),
    total: toNumber(response.total)
  };
}

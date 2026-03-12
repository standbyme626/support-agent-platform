import { getJson } from "@/lib/api/client";

export type TraceListItem = {
  trace_id: string;
  ticket_id: string | null;
  session_id: string | null;
  workflow: string | null;
  channel: string | null;
  provider: string | null;
  model: string | null;
  prompt_key: string | null;
  prompt_version: string | null;
  request_id: string | null;
  retry_count: number | null;
  success: boolean | null;
  error: string | null;
  fallback_used: boolean;
  degraded: boolean;
  degrade_reason: string | null;
  generation_type: string | null;
  route_decision: Record<string, unknown>;
  handoff: boolean;
  handoff_reason: string | null;
  error_only: boolean;
  latency_ms: number | null;
  created_at: string | null;
};

export type TraceListQuery = {
  page: number;
  page_size: number;
  trace_id?: string;
  ticket_id?: string;
  session_id?: string;
  workflow?: string;
  channel?: string;
  provider?: string;
  model?: string;
  prompt_version?: string;
  error_only?: "true" | "false";
  handoff?: "true" | "false";
};

export type TraceListResponse = {
  request_id?: string;
  items: Array<Partial<TraceListItem>>;
  page: number;
  page_size: number;
  total: number;
};

export type TraceDetailEvent = {
  event_id: string;
  event_type: string;
  timestamp: string | null;
  ticket_id: string | null;
  session_id: string | null;
  payload: Record<string, unknown>;
};

export type TraceGroundingSource = {
  source_type: string | null;
  source_id: string | null;
  title: string | null;
  snippet: string | null;
  score: number | null;
  rank: number | null;
  reason: string | null;
  retrieval_mode: string | null;
};

export type TraceDetail = {
  trace_id: string;
  ticket_id: string | null;
  session_id: string | null;
  workflow: string | null;
  channel: string | null;
  provider: string | null;
  model: string | null;
  prompt_key: string | null;
  prompt_version: string | null;
  request_id: string | null;
  token_usage: Record<string, unknown> | null;
  retry_count: number | null;
  success: boolean | null;
  error: string | null;
  fallback_used: boolean;
  degraded: boolean;
  degrade_reason: string | null;
  generation_type: string | null;
  route_decision: Record<string, unknown>;
  retrieved_docs: string[];
  grounding_sources: TraceGroundingSource[];
  tool_calls: string[];
  summary: string;
  handoff: boolean;
  handoff_reason: string | null;
  error_only: boolean;
  latency_ms: number | null;
  created_at: string | null;
  events: TraceDetailEvent[];
};

type TraceDetailResponse = Partial<TraceDetail> & {
  request_id?: string;
  route_decision?: unknown;
  retrieved_docs?: unknown;
  grounding_sources?: unknown;
  tool_calls?: unknown;
  events?: unknown;
};

function toSearchParams(query: TraceListQuery) {
  const params = new URLSearchParams();
  Object.entries(query).forEach(([key, value]) => {
    if (value === undefined || value === null || value === "") {
      return;
    }
    params.set(key, String(value));
  });
  return params.toString();
}

function toStringOrNull(value: unknown): string | null {
  if (typeof value !== "string") {
    return null;
  }
  const normalized = value.trim();
  return normalized.length > 0 ? normalized : null;
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

function toBooleanOrNull(value: unknown): boolean | null {
  if (value === null || value === undefined) {
    return null;
  }
  return toBoolean(value);
}

function toNumberOrNull(value: unknown): number | null {
  return typeof value === "number" ? value : null;
}

function toRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" && !Array.isArray(value) ? (value as Record<string, unknown>) : {};
}

function toStringList(value: unknown): string[] {
  if (!Array.isArray(value)) {
    return [];
  }
  return value.map((item) => String(item)).filter((item) => item.length > 0);
}

function normalizeTraceListItem(item: Partial<TraceListItem>, index: number): TraceListItem {
  return {
    trace_id: toStringOrNull(item.trace_id) ?? `trace-unknown-${index}`,
    ticket_id: toStringOrNull(item.ticket_id),
    session_id: toStringOrNull(item.session_id),
    workflow: toStringOrNull(item.workflow),
    channel: toStringOrNull(item.channel),
    provider: toStringOrNull(item.provider),
    model: toStringOrNull(item.model),
    prompt_key: toStringOrNull(item.prompt_key),
    prompt_version: toStringOrNull(item.prompt_version),
    request_id: toStringOrNull(item.request_id),
    retry_count: toNumberOrNull(item.retry_count),
    success: toBooleanOrNull(item.success),
    error: toStringOrNull(item.error),
    fallback_used: toBoolean(item.fallback_used),
    degraded: toBoolean(item.degraded),
    degrade_reason: toStringOrNull(item.degrade_reason),
    generation_type: toStringOrNull(item.generation_type),
    route_decision: toRecord(item.route_decision),
    handoff: toBoolean(item.handoff),
    handoff_reason: toStringOrNull(item.handoff_reason),
    error_only: toBoolean(item.error_only),
    latency_ms: toNumberOrNull(item.latency_ms),
    created_at: toStringOrNull(item.created_at)
  };
}

function normalizeTraceEvent(item: unknown, index: number): TraceDetailEvent {
  const source = toRecord(item);
  return {
    event_id: toStringOrNull(source.event_id) ?? `trace_event_${index}`,
    event_type: toStringOrNull(source.event_type) ?? "trace_event",
    timestamp: toStringOrNull(source.timestamp),
    ticket_id: toStringOrNull(source.ticket_id),
    session_id: toStringOrNull(source.session_id),
    payload: toRecord(source.payload)
  };
}

function normalizeGroundingSource(item: unknown): TraceGroundingSource {
  const source = toRecord(item);
  return {
    source_type: toStringOrNull(source.source_type),
    source_id: toStringOrNull(source.source_id),
    title: toStringOrNull(source.title),
    snippet: toStringOrNull(source.snippet),
    score: toNumberOrNull(source.score),
    rank: toNumberOrNull(source.rank),
    reason: toStringOrNull(source.reason),
    retrieval_mode: toStringOrNull(source.retrieval_mode)
  };
}

function normalizeTraceDetail(item: TraceDetailResponse, traceId: string): TraceDetail {
  return {
    trace_id: toStringOrNull(item.trace_id) ?? traceId,
    ticket_id: toStringOrNull(item.ticket_id),
    session_id: toStringOrNull(item.session_id),
    workflow: toStringOrNull(item.workflow),
    channel: toStringOrNull(item.channel),
    provider: toStringOrNull(item.provider),
    model: toStringOrNull(item.model),
    prompt_key: toStringOrNull(item.prompt_key),
    prompt_version: toStringOrNull(item.prompt_version),
    request_id: toStringOrNull(item.request_id),
    token_usage: item.token_usage && typeof item.token_usage === "object" && !Array.isArray(item.token_usage)
      ? (item.token_usage as Record<string, unknown>)
      : null,
    retry_count: toNumberOrNull(item.retry_count),
    success: toBooleanOrNull(item.success),
    error: toStringOrNull(item.error),
    fallback_used: toBoolean(item.fallback_used),
    degraded: toBoolean(item.degraded),
    degrade_reason: toStringOrNull(item.degrade_reason),
    generation_type: toStringOrNull(item.generation_type),
    route_decision: toRecord(item.route_decision),
    retrieved_docs: toStringList(item.retrieved_docs),
    grounding_sources: Array.isArray(item.grounding_sources)
      ? item.grounding_sources.map((entry) => normalizeGroundingSource(entry))
      : [],
    tool_calls: toStringList(item.tool_calls),
    summary: typeof item.summary === "string" ? item.summary : "",
    handoff: toBoolean(item.handoff),
    handoff_reason: toStringOrNull(item.handoff_reason),
    error_only: toBoolean(item.error_only),
    latency_ms: toNumberOrNull(item.latency_ms),
    created_at: toStringOrNull(item.created_at),
    events: Array.isArray(item.events) ? item.events.map((event, index) => normalizeTraceEvent(event, index)) : []
  };
}

export async function fetchTraces(query: TraceListQuery) {
  const response = await getJson<TraceListResponse>(`/api/traces?${toSearchParams(query)}`);
  return {
    ...response,
    items: response.items.map((item, index) => normalizeTraceListItem(item, index))
  };
}

export async function fetchTraceDetail(traceId: string) {
  const response = await getJson<TraceDetailResponse>(`/api/traces/${encodeURIComponent(traceId)}`);
  return normalizeTraceDetail(response, traceId);
}

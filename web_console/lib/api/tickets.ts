import { getJson } from "@/lib/api/client";

export type TicketItem = {
  ticket_id: string;
  title: string;
  latest_message: string;
  status: string;
  priority: string;
  queue: string;
  assignee: string | null;
  channel: string;
  handoff_state: string;
  risk_level: string;
  metadata: Record<string, unknown>;
  created_at: string | null;
  updated_at: string | null;
  sla_state: "normal" | "warning" | "breached";
};

export type TicketListResponse = {
  request_id?: string;
  items: TicketItem[];
  page: number;
  page_size: number;
  total: number;
};

export type TicketQuery = {
  page: number;
  page_size: number;
  sort_by: string;
  sort_order: "asc" | "desc";
  q?: string;
  status?: string;
  priority?: string;
  queue?: string;
  assignee?: string;
  channel?: string;
  handoff_state?: string;
  service_type?: string;
  community_name?: string;
  building?: string;
  parking_lot?: string;
  approval_required?: string;
  risk_level?: string;
  created_from?: string;
  created_to?: string;
  sla_state?: string;
};

type AssigneeResponse = {
  request_id?: string;
  items: string[];
};

export type TicketDetailResponse = {
  request_id?: string;
  data: TicketItem;
};

export type TicketEventItem = {
  event_id: string;
  ticket_id: string;
  event_type: string;
  actor_type: string;
  actor_id: string;
  payload: Record<string, unknown>;
  created_at: string | null;
  source?: "ticket" | "trace" | string;
  trace_id?: string | null;
};

export type TicketEventsResponse = {
  request_id?: string;
  items: Array<Partial<TicketEventItem> & { payload?: unknown }>;
};

export type TicketAssistResponse = {
  request_id?: string;
  summary: string;
  recommended_actions: Array<Record<string, unknown>>;
  risk_flags: string[];
  latest_messages: string[];
  provider: string;
  prompt_version: string;
};

export type SimilarCaseItem = {
  doc_id?: string;
  source_type?: string;
  title?: string;
  score?: number;
};

export type SimilarCasesResponse = {
  request_id?: string;
  items: SimilarCaseItem[];
};

export type TicketActionType = "claim" | "reassign" | "escalate" | "resolve" | "close";

export type TicketActionPayload = {
  actor_id: string;
  target_queue?: string;
  target_assignee?: string;
  note?: string;
  resolution_note?: string;
  resolution_code?: string;
  close_reason?: string;
};

function toSearchParams(query: TicketQuery) {
  const params = new URLSearchParams();
  Object.entries(query).forEach(([key, value]) => {
    if (value === undefined || value === null || value === "") {
      return;
    }
    params.set(key, String(value));
  });
  return params.toString();
}

export async function fetchTickets(query: TicketQuery) {
  return getJson<TicketListResponse>(`/api/tickets?${toSearchParams(query)}`);
}

export async function fetchAssignees() {
  return getJson<AssigneeResponse>("/api/agents/assignees");
}

export async function fetchTicketDetail(ticketId: string) {
  return getJson<TicketDetailResponse>(`/api/tickets/${encodeURIComponent(ticketId)}`);
}

function toPayloadRecord(value: unknown) {
  return value && typeof value === "object" && !Array.isArray(value) ? (value as Record<string, unknown>) : {};
}

function sortTimestamp(value: string | null | undefined) {
  if (!value) {
    return Number.NEGATIVE_INFINITY;
  }
  const parsed = Date.parse(value);
  return Number.isNaN(parsed) ? Number.NEGATIVE_INFINITY : parsed;
}

export function normalizeTicketEventItem(
  item: Partial<TicketEventItem> & { payload?: unknown },
  ticketId: string,
  index: number
): TicketEventItem {
  return {
    event_id: item.event_id?.trim() || `evt_${ticketId}_${index}`,
    ticket_id: item.ticket_id?.trim() || ticketId,
    event_type: item.event_type?.trim() || "unknown",
    actor_type: item.actor_type?.trim() || "system",
    actor_id: item.actor_id?.trim() || "unknown",
    payload: toPayloadRecord(item.payload),
    created_at: item.created_at ?? null,
    source: item.source ?? "ticket",
    trace_id: item.trace_id ?? null
  };
}

export function sortTicketEvents(items: TicketEventItem[]) {
  return [...items].sort((left, right) => {
    const tsDiff = sortTimestamp(left.created_at) - sortTimestamp(right.created_at);
    if (tsDiff !== 0) {
      return tsDiff;
    }
    return left.event_id.localeCompare(right.event_id);
  });
}

export async function fetchTicketEvents(ticketId: string) {
  const response = await getJson<TicketEventsResponse>(
    `/api/tickets/${encodeURIComponent(ticketId)}/events`
  );
  return {
    ...response,
    items: sortTicketEvents(
      response.items.map((item, index) => normalizeTicketEventItem(item, ticketId, index))
    )
  };
}

export async function fetchTicketAssist(ticketId: string) {
  return getJson<TicketAssistResponse>(`/api/tickets/${encodeURIComponent(ticketId)}/assist`);
}

export async function fetchSimilarCases(ticketId: string) {
  return getJson<SimilarCasesResponse>(`/api/tickets/${encodeURIComponent(ticketId)}/similar-cases`);
}

export async function runTicketAction(
  ticketId: string,
  action: TicketActionType,
  payload: TicketActionPayload
) {
  return getJson<TicketDetailResponse>(`/api/tickets/${encodeURIComponent(ticketId)}/${action}`, {
    method: "POST",
    body: JSON.stringify(payload),
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json"
    }
  });
}

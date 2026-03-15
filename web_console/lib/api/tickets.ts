import { getJson } from "@/lib/api/client";

export type TicketItem = {
  ticket_id: string;
  session_id?: string | null;
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
  grounding_sources: GroundingSourceItem[];
  risk_flags: string[];
  latest_messages: string[];
  provider: string;
  prompt_version: string;
};

export type GroundingSourceItem = {
  source_type?: string;
  source_id?: string;
  title?: string;
  snippet?: string;
  score?: number;
  rank?: number;
  reason?: string;
  lexical_score?: number;
  vector_score?: number;
  retrieval_mode?: string;
};

export type SimilarCaseItem = {
  doc_id?: string;
  source_id?: string;
  source_type?: string;
  title?: string;
  score?: number;
  rank?: number;
  reason?: string;
  snippet?: string;
  retrieval_mode?: string;
};

export type SimilarCasesResponse = {
  request_id?: string;
  items: SimilarCaseItem[];
};

export type GroundingSourcesResponse = {
  request_id?: string;
  items: GroundingSourceItem[];
};

export type TicketActionType =
  | "claim"
  | "reassign"
  | "escalate"
  | "resolve"
  | "customer_confirm"
  | "operator_close"
  | "close_compat";

export type TicketActionPayload = {
  actor_id: string;
  target_queue?: string;
  target_assignee?: string;
  note?: string;
  resolution_note?: string;
  resolution_code?: string;
  close_reason?: string;
};

export type ApprovalDecisionType = "approve" | "reject";

export type PendingApprovalItem = {
  approval_id: string;
  ticket_id: string;
  action_type: string;
  risk_level: string;
  status: string;
  requested_by: string;
  requested_at: string | null;
  timeout_at: string | null;
  reason: string;
  payload: Record<string, unknown>;
  context: Record<string, unknown>;
  approved_by?: string | null;
  rejected_by?: string | null;
  decided_at?: string | null;
  decision_note?: string | null;
};

export type PendingApprovalsResponse = {
  request_id?: string;
  items: PendingApprovalItem[];
  page: number;
  page_size: number;
  total: number;
};

export type TicketPendingActionsResponse = {
  request_id?: string;
  items: PendingApprovalItem[];
};

export type ApprovalDecisionPayload = {
  actor_id: string;
  note?: string;
};

export type TicketCopilotQueryData = {
  scope: string;
  query: string;
  ticket_id?: string;
  answer: string;
  summary?: string;
  grounding_sources: GroundingSourceItem[];
  risk_flags: string[];
  llm_trace: Record<string, unknown>;
  runtime_trace?: Record<string, unknown> | null;
  recommended_actions?: Array<Record<string, unknown>>;
  confidence?: number | null;
  generated_at: string | null;
  advice_only: boolean;
  dashboard_summary?: Record<string, unknown>;
  queue_summary?: Array<Record<string, unknown>>;
  dispatch_priority?: Array<Record<string, unknown>>;
};

export type TicketCopilotQueryResponse = {
  request_id?: string;
  data: TicketCopilotQueryData;
};

export type TicketInvestigationPayload = {
  actor_id: string;
  question?: string;
  query?: string;
  trace_id?: string;
};

export type TicketInvestigationData = {
  ticket_id: string;
  session_id: string | null;
  question: string;
  investigation: Record<string, unknown>;
  advice_only: boolean;
  trace: Record<string, unknown>;
};

export type TicketInvestigationResponse = {
  request_id?: string;
  data: TicketInvestigationData;
};

export type SessionEndPayload = {
  actor_id: string;
  reason?: string;
  trace_id?: string;
};

export type SessionEndData = {
  session_id: string;
  event_type: string;
  trace_id: string;
  actor_id?: string;
  reason?: string;
  message?: string;
  session: Record<string, unknown> | null;
};

export type SessionEndResponse = {
  request_id?: string;
  data: SessionEndData;
};

function normalizePendingApproval(item: unknown): PendingApprovalItem {
  const record =
    item && typeof item === "object" && !Array.isArray(item) ? (item as Record<string, unknown>) : {};
  const payload = toPayloadRecord(record.payload);
  const context = toPayloadRecord(record.context);
  return {
    approval_id: String(record.approval_id ?? ""),
    ticket_id: String(record.ticket_id ?? ""),
    action_type: String(record.action_type ?? ""),
    risk_level: String(record.risk_level ?? "high"),
    status: String(record.status ?? "pending_approval"),
    requested_by: String(record.requested_by ?? ""),
    requested_at: record.requested_at ? String(record.requested_at) : null,
    timeout_at: record.timeout_at ? String(record.timeout_at) : null,
    reason: String(record.reason ?? ""),
    payload,
    context,
    approved_by: record.approved_by ? String(record.approved_by) : null,
    rejected_by: record.rejected_by ? String(record.rejected_by) : null,
    decided_at: record.decided_at ? String(record.decided_at) : null,
    decision_note: record.decision_note ? String(record.decision_note) : null
  };
}

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

function toRecord(value: unknown) {
  return toPayloadRecord(value);
}

function toStringOrNull(value: unknown): string | null {
  if (typeof value !== "string") {
    return null;
  }
  const normalized = value.trim();
  return normalized.length > 0 ? normalized : null;
}

function toNumberOrNull(value: unknown): number | null {
  return typeof value === "number" ? value : null;
}

function toBoolean(value: unknown): boolean {
  if (typeof value === "boolean") {
    return value;
  }
  if (typeof value === "string") {
    return value.trim().toLowerCase() === "true";
  }
  return false;
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

export async function fetchGroundingSources(ticketId: string) {
  return getJson<GroundingSourcesResponse>(
    `/api/tickets/${encodeURIComponent(ticketId)}/grounding-sources`
  );
}

export async function runTicketAction(
  ticketId: string,
  action: TicketActionType,
  payload: TicketActionPayload
) {
  const encodedId = encodeURIComponent(ticketId);
  let path: string;
  if (action === "resolve") {
    path = `/api/v2/tickets/${encodedId}/resolve`;
  } else if (action === "customer_confirm") {
    path = `/api/v2/tickets/${encodedId}/customer-confirm`;
  } else if (action === "operator_close") {
    path = `/api/v2/tickets/${encodedId}/operator-close`;
  } else if (action === "close_compat") {
    path = `/api/tickets/${encodedId}/close`;
  } else {
    path = `/api/tickets/${encodedId}/${action}`;
  }
  return getJson<TicketDetailResponse>(path, {
    method: "POST",
    body: JSON.stringify(payload),
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json"
    }
  });
}

export async function fetchPendingApprovals(query?: { page?: number; page_size?: number }) {
  const params = new URLSearchParams();
  if (query?.page) {
    params.set("page", String(query.page));
  }
  if (query?.page_size) {
    params.set("page_size", String(query.page_size));
  }
  const suffix = params.toString();
  const path = suffix ? `/api/approvals/pending?${suffix}` : "/api/approvals/pending";
  const response = await getJson<PendingApprovalsResponse>(path);
  return {
    ...response,
    items: response.items.map((item) => normalizePendingApproval(item))
  };
}

export async function fetchTicketPendingActions(ticketId: string) {
  const response = await getJson<TicketPendingActionsResponse>(
    `/api/tickets/${encodeURIComponent(ticketId)}/pending-actions`
  );
  return {
    ...response,
    items: response.items.map((item) => normalizePendingApproval(item))
  };
}

export async function decideApproval(
  approvalId: string,
  decision: ApprovalDecisionType,
  payload: ApprovalDecisionPayload
) {
  return getJson<TicketDetailResponse>(
    `/api/approvals/${encodeURIComponent(approvalId)}/${decision}`,
    {
      method: "POST",
      body: JSON.stringify(payload),
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json"
      }
    }
  );
}

export async function queryTicketCopilot(ticketId: string, query: string) {
  const response = await getJson<TicketCopilotQueryResponse>(
    `/api/copilot/ticket/${encodeURIComponent(ticketId)}/query`,
    {
      method: "POST",
      body: JSON.stringify({ query }),
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json"
      }
    }
  );
  return {
    ...response,
    data: normalizeCopilotQueryData(response.data)
  };
}

export async function queryOperatorCopilot(query: string) {
  const response = await getJson<TicketCopilotQueryResponse>("/api/copilot/operator/query", {
    method: "POST",
    body: JSON.stringify({ query }),
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json"
    }
  });
  return {
    ...response,
    data: normalizeCopilotQueryData(response.data)
  };
}

export async function queryDispatchCopilot(query: string) {
  const response = await getJson<TicketCopilotQueryResponse>("/api/copilot/dispatch/query", {
    method: "POST",
    body: JSON.stringify({ query }),
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json"
    }
  });
  return {
    ...response,
    data: normalizeCopilotQueryData(response.data)
  };
}

function normalizeCopilotQueryData(raw: TicketCopilotQueryData): TicketCopilotQueryData {
  const record = toRecord(raw);
  const groundingSources = Array.isArray(record.grounding_sources)
    ? (record.grounding_sources as GroundingSourceItem[])
    : [];
  const riskFlags = Array.isArray(record.risk_flags)
    ? record.risk_flags.map((item: unknown) => String(item)).filter((item) => item.length > 0)
    : [];
  const recommendedActions = Array.isArray(record.recommended_actions)
    ? record.recommended_actions
        .filter((item: unknown) => item && typeof item === "object" && !Array.isArray(item))
        .map((item: unknown) => item as Record<string, unknown>)
    : [];
  const dispatchPriority = Array.isArray(record.dispatch_priority)
    ? record.dispatch_priority
        .filter((item: unknown) => item && typeof item === "object" && !Array.isArray(item))
        .map((item: unknown) => item as Record<string, unknown>)
    : [];
  const queueSummary = Array.isArray(record.queue_summary)
    ? record.queue_summary
        .filter((item: unknown) => item && typeof item === "object" && !Array.isArray(item))
        .map((item: unknown) => item as Record<string, unknown>)
    : [];

  return {
    scope: toStringOrNull(record.scope) ?? "ticket",
    query: toStringOrNull(record.query) ?? "",
    ticket_id: toStringOrNull(record.ticket_id) ?? undefined,
    answer: toStringOrNull(record.answer) ?? "",
    summary: toStringOrNull(record.summary) ?? undefined,
    grounding_sources: groundingSources,
    risk_flags: riskFlags,
    llm_trace: toRecord(record.llm_trace),
    runtime_trace: Object.keys(toRecord(record.runtime_trace)).length ? toRecord(record.runtime_trace) : null,
    recommended_actions: recommendedActions,
    confidence: toNumberOrNull(record.confidence),
    generated_at: toStringOrNull(record.generated_at),
    advice_only: toBoolean(record.advice_only),
    dashboard_summary: Object.keys(toRecord(record.dashboard_summary)).length
      ? toRecord(record.dashboard_summary)
      : undefined,
    queue_summary: queueSummary,
    dispatch_priority: dispatchPriority
  };
}

export async function investigateTicket(ticketId: string, payload: TicketInvestigationPayload) {
  return getJson<TicketInvestigationResponse>(
    `/api/v2/tickets/${encodeURIComponent(ticketId)}/investigate`,
    {
      method: "POST",
      body: JSON.stringify(payload),
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json"
      }
    }
  );
}

export async function endSession(sessionId: string, payload: SessionEndPayload) {
  return getJson<SessionEndResponse>(`/api/v2/sessions/${encodeURIComponent(sessionId)}/end`, {
    method: "POST",
    body: JSON.stringify(payload),
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json"
    }
  });
}

export function getTicketSessionId(ticket: TicketItem | null | undefined) {
  if (!ticket) {
    return null;
  }
  if (typeof ticket.session_id === "string" && ticket.session_id.trim()) {
    return ticket.session_id.trim();
  }
  if (typeof ticket.metadata?.session_id === "string" && ticket.metadata.session_id.trim()) {
    return ticket.metadata.session_id.trim();
  }
  const fromLatestSession = ticket.metadata?.latest_session_id;
  if (typeof fromLatestSession === "string" && fromLatestSession.trim()) {
    return fromLatestSession.trim();
  }
  return null;
}

export function isAdviceOnlyResponse(
  value: { advice_only?: unknown } | null | undefined,
  fallback: boolean = true
) {
  if (!value) {
    return fallback;
  }
  if (typeof value.advice_only === "boolean") {
    return value.advice_only;
  }
  return fallback;
}

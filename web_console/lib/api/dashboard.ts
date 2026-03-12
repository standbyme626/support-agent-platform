import { getJson } from "@/lib/api/client";

export type DashboardSummary = {
  new_tickets_today: number;
  in_progress_count: number;
  handoff_pending_count: number;
  escalated_count: number;
  sla_warning_count: number;
  sla_breached_count: number;
  consulting_reuse_count: number;
  duplicate_candidates_count: number;
  merge_accept_count: number;
  merge_reject_count: number;
  merge_accept_rate: number;
};

export type DashboardSummaryResponse = {
  request_id: string;
  data: DashboardSummary;
};

export type DashboardErrorItem = {
  timestamp?: string;
  trace_id?: string;
  ticket_id?: string;
  event_type?: string;
  error?: string;
};

export type DashboardRecentErrorsResponse = {
  request_id: string;
  data: DashboardErrorItem[];
};

export async function fetchDashboardSummary() {
  return getJson<DashboardSummaryResponse>("/api/dashboard/summary");
}

export async function fetchDashboardRecentErrors() {
  return getJson<DashboardRecentErrorsResponse>("/api/dashboard/recent-errors");
}

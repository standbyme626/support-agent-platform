import { getJson } from "@/lib/api/client";

export type SystemSummary = {
  system: string;
  entity_type: string;
  id_prefix: string;
  lifecycle: string[];
  total_entities: number;
  actions: string[];
  error?: string;
};

export type SystemsSummaryResponse = {
  ok: boolean;
  total_systems: number;
  systems: SystemSummary[];
  trace_id: string;
};

export async function fetchSystemsSummary() {
  return getJson<SystemsSummaryResponse>("/api/systems/summary");
}

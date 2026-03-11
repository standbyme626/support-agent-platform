import { getJson } from "@/lib/api/client";

export type QueueSummaryItem = {
  queue_name: string;
  open_count: number;
  in_progress_count: number;
  warning_count: number;
  breached_count: number;
  escalated_count: number;
  assignee_count: number;
};

type QueueResponse = {
  request_id?: string;
  items: QueueSummaryItem[];
};

export async function fetchQueues() {
  return getJson<QueueResponse>("/api/queues");
}

export async function fetchQueueSummary() {
  return getJson<QueueResponse>("/api/queues/summary");
}

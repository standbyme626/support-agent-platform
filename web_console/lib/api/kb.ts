import { getJson } from "@/lib/api/client";

export type KbSourceType = "faq" | "sop" | "history_case";

export type KbMetadata = Record<string, unknown> & {
  source_dataset?: string;
  license?: string;
  source_url?: string;
  commercial_use?: boolean;
};

export type KbItem = {
  doc_id: string;
  source_type: KbSourceType;
  title: string;
  content: string;
  tags: string[];
  updated_at: string | null;
  metadata: KbMetadata;
};

export type KbListQuery = {
  page: number;
  page_size: number;
  source_type?: KbSourceType;
  q?: string;
};

type KbListResponse = {
  request_id?: string;
  items: Array<Partial<KbItem>>;
  page: number;
  page_size: number;
  total: number;
};

type KbDetailResponse = {
  request_id?: string;
  data: Partial<KbItem>;
};

type KbDeleteResponse = {
  request_id?: string;
  deleted: boolean;
  doc_id: string;
};

export type KbCreatePayload = {
  doc_id?: string;
  source_type: KbSourceType;
  title: string;
  content: string;
  tags: string[];
  metadata?: KbMetadata;
};

export type KbUpdatePayload = Partial<{
  source_type: KbSourceType;
  title: string;
  content: string;
  tags: string[];
  metadata: KbMetadata;
}>;

function toSearchParams(query: KbListQuery) {
  const params = new URLSearchParams();
  Object.entries(query).forEach(([key, value]) => {
    if (value === undefined || value === null || value === "") {
      return;
    }
    params.set(key, String(value));
  });
  return params.toString();
}

function toStringOrEmpty(value: unknown) {
  return typeof value === "string" ? value : "";
}

function toSourceType(value: unknown): KbSourceType {
  if (value === "faq" || value === "sop" || value === "history_case") {
    return value;
  }
  return "faq";
}

function toStringArray(value: unknown) {
  if (!Array.isArray(value)) {
    return [];
  }
  return value.map((item) => String(item)).filter((item) => item.length > 0);
}

function toMetadata(value: unknown): KbMetadata {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    return {};
  }
  return { ...(value as Record<string, unknown>) };
}

function normalizeKbItem(item: Partial<KbItem>, index: number): KbItem {
  return {
    doc_id: toStringOrEmpty(item.doc_id) || `doc_unknown_${index}`,
    source_type: toSourceType(item.source_type),
    title: toStringOrEmpty(item.title),
    content: toStringOrEmpty(item.content),
    tags: toStringArray(item.tags),
    updated_at: typeof item.updated_at === "string" ? item.updated_at : null,
    metadata: toMetadata(item.metadata)
  };
}

export async function fetchKbList(query: KbListQuery) {
  const response = await getJson<KbListResponse>(`/api/kb?${toSearchParams(query)}`);
  return {
    ...response,
    items: response.items.map((item, index) => normalizeKbItem(item, index))
  };
}

export async function createKbDoc(payload: KbCreatePayload) {
  const response = await getJson<KbDetailResponse>("/api/kb", {
    method: "POST",
    body: JSON.stringify(payload),
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json"
    }
  });
  return {
    ...response,
    data: normalizeKbItem(response.data, 0)
  };
}

export async function updateKbDoc(docId: string, payload: KbUpdatePayload) {
  const response = await getJson<KbDetailResponse>(`/api/kb/${encodeURIComponent(docId)}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json"
    }
  });
  return {
    ...response,
    data: normalizeKbItem(response.data, 0)
  };
}

export async function deleteKbDoc(docId: string) {
  return getJson<KbDeleteResponse>(`/api/kb/${encodeURIComponent(docId)}`, {
    method: "DELETE"
  });
}

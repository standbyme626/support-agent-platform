const DEFAULT_BASE_URL = "";

function opsApiBaseUrl() {
  const baseUrl = process.env.NEXT_PUBLIC_OPS_API_BASE_URL ?? DEFAULT_BASE_URL;
  return baseUrl.endsWith("/") ? baseUrl.slice(0, -1) : baseUrl;
}

export class ApiError extends Error {
  code: string;
  requestId: string;
  status: number;

  constructor({
    code,
    message,
    requestId,
    status
  }: {
    code: string;
    message: string;
    requestId: string;
    status: number;
  }) {
    super(message);
    this.code = code;
    this.requestId = requestId;
    this.status = status;
  }
}

type ErrorBody = {
  code?: string;
  message?: string;
  request_id?: string;
};

export async function getJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${opsApiBaseUrl()}${path}`, {
    ...init,
    method: init?.method ?? "GET",
    headers: {
      Accept: "application/json",
      ...(init?.headers ?? {})
    },
    cache: "no-store"
  });
  const payload = (await response.json()) as T | ErrorBody;

  if (!response.ok) {
    const errorBody = payload as ErrorBody;
    throw new ApiError({
      code: errorBody.code ?? "http_error",
      message: errorBody.message ?? "Request failed",
      requestId: errorBody.request_id ?? "n/a",
      status: response.status
    });
  }
  return payload as T;
}

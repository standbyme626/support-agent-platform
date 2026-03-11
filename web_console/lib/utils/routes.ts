type TicketListFilterValue = string | number | boolean | null | undefined;

export function buildTicketListUrl(filters: Record<string, TicketListFilterValue>) {
  const params = new URLSearchParams();
  Object.entries(filters).forEach(([key, value]) => {
    if (value === undefined || value === null || value === "") {
      return;
    }
    params.set(key, String(value));
  });
  const query = params.toString();
  return query.length > 0 ? `/tickets?${query}` : "/tickets";
}

export function buildTraceDetailUrl(traceId: string) {
  return `/traces/${encodeURIComponent(traceId)}`;
}

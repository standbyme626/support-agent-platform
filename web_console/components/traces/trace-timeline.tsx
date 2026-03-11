import type { TraceDetailEvent } from "@/lib/api/traces";

function toDateTimeText(value: string | null) {
  if (!value) {
    return "n/a";
  }
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }
  return parsed.toLocaleString();
}

function payloadPreview(payload: Record<string, unknown>) {
  const entries = Object.entries(payload).slice(0, 4);
  if (entries.length === 0) {
    return "No payload.";
  }
  return entries.map(([key, value]) => `${key}=${String(value)}`).join(" · ");
}

export function TraceTimeline({ events }: { events: TraceDetailEvent[] }) {
  return (
    <article className="card">
      <h3>Trace Timeline</h3>
      {events.length === 0 ? (
        <p style={{ color: "var(--muted)", marginTop: 10 }}>No trace events recorded.</p>
      ) : (
        <ul className="list" style={{ marginTop: 10 }}>
          {events.map((event) => (
            <li className="list-item" key={event.event_id}>
              <strong>{event.event_type}</strong>
              <div style={{ color: "var(--muted)", fontSize: 13 }}>
                {toDateTimeText(event.timestamp)} · ticket={event.ticket_id ?? "-"} · session={event.session_id ?? "-"}
              </div>
              <div style={{ color: "var(--muted)", fontSize: 13, marginTop: 4 }}>
                {payloadPreview(event.payload)}
              </div>
            </li>
          ))}
        </ul>
      )}
    </article>
  );
}

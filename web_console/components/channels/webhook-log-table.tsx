import type { ChannelEventItem } from "@/lib/api/channels";

function toDateTimeText(value: string | null) {
  if (!value) {
    return "-";
  }
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }
  return parsed.toLocaleString();
}

function payloadSummary(payload: Record<string, unknown>) {
  const serialized = JSON.stringify(payload);
  if (serialized.length <= 120) {
    return serialized;
  }
  return `${serialized.slice(0, 117)}...`;
}

export function WebhookLogTable({ rows }: { rows: ChannelEventItem[] }) {
  return (
    <article className="card">
      <h3>Webhook Event Stream</h3>
      {rows.length === 0 ? (
        <div className="hint" style={{ marginTop: 10 }}>
          No recent channel webhook events.
        </div>
      ) : (
        <div style={{ overflowX: "auto", marginTop: 10 }}>
          <table className="table">
            <thead>
              <tr>
                <th>Timestamp</th>
                <th>Channel</th>
                <th>Event</th>
                <th>Trace</th>
                <th>Payload</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={`${row.timestamp ?? "ts"}-${row.trace_id ?? "trace"}-${row.event_type}`}>
                  <td>{toDateTimeText(row.timestamp)}</td>
                  <td>{row.channel}</td>
                  <td>{row.event_type}</td>
                  <td>{row.trace_id ?? "-"}</td>
                  <td>{payloadSummary(row.payload)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </article>
  );
}

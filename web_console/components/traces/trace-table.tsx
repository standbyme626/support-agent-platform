import { buildTraceDetailUrl } from "@/lib/utils/routes";
import type { TraceListItem } from "@/lib/api/traces";

function toText(value: string | null | undefined) {
  return value && value.length > 0 ? value : "-";
}

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

export function TraceTable({
  rows,
  page,
  pageSize,
  total,
  onPageChange
}: {
  rows: TraceListItem[];
  page: number;
  pageSize: number;
  total: number;
  onPageChange: (nextPage: number) => void;
}) {
  const pageCount = Math.max(1, Math.ceil(total / pageSize));

  return (
    <section className="card">
      <h3>Traces</h3>
      <div style={{ overflowX: "auto", marginTop: 10 }}>
        <table className="table">
          <thead>
            <tr>
              <th>Trace</th>
              <th>Ticket</th>
              <th>Session</th>
              <th>Workflow</th>
              <th>Channel</th>
              <th>Provider</th>
              <th>Route</th>
              <th>Handoff</th>
              <th>Latency</th>
              <th>Created</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.trace_id}>
                <td>
                  <a href={buildTraceDetailUrl(row.trace_id)}>{row.trace_id}</a>
                </td>
                <td>{toText(row.ticket_id)}</td>
                <td>{toText(row.session_id)}</td>
                <td>{toText(row.workflow)}</td>
                <td>{toText(row.channel)}</td>
                <td>{toText(row.provider)}</td>
                <td>{toText(typeof row.route_decision.intent === "string" ? row.route_decision.intent : null)}</td>
                <td>{row.handoff ? "yes" : "no"}</td>
                <td>{row.latency_ms !== null ? `${row.latency_ms}ms` : "-"}</td>
                <td>{toDateTimeText(row.created_at)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div
        style={{
          marginTop: 10,
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center"
        }}
      >
        <small>
          page {page}/{pageCount} · total {total}
        </small>
        <div style={{ display: "flex", gap: 8 }}>
          <button
            onClick={() => onPageChange(Math.max(1, page - 1))}
            disabled={page <= 1}
            className="btn-ghost"
          >
            Prev
          </button>
          <button
            onClick={() => onPageChange(Math.min(pageCount, page + 1))}
            disabled={page >= pageCount}
            className="btn-ghost"
          >
            Next
          </button>
        </div>
      </div>
    </section>
  );
}

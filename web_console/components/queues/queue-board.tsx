import type { QueueSummaryItem } from "@/lib/api/queues";
import { buildTicketListUrl } from "@/lib/utils/routes";

function queueState(row: QueueSummaryItem) {
  if (row.breached_count > 0) {
    return "breached";
  }
  if (row.warning_count > 0 || row.escalated_count > 0) {
    return "warning";
  }
  return "normal";
}

export function QueueBoard({ rows }: { rows: QueueSummaryItem[] }) {
  if (rows.length === 0) {
    return (
      <article className="card">
        <h3>Queue Board</h3>
        <div className="hint">No queue items found.</div>
      </article>
    );
  }

  return (
    <article className="card">
      <h3>Queue Board</h3>
      <ul className="list">
        {rows.map((row) => (
          <li className="list-item" key={row.queue_name}>
            <div>
              <a href={buildTicketListUrl({ queue: row.queue_name })}>{row.queue_name}</a>
            </div>
            <small>
              open {row.open_count} · in progress {row.in_progress_count} · warning {row.warning_count} · breached{" "}
              {row.breached_count} · escalated {row.escalated_count} · state {queueState(row)}
            </small>
          </li>
        ))}
      </ul>
    </article>
  );
}

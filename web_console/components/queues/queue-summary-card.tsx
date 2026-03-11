import type { QueueSummaryItem } from "@/lib/api/queues";
import { buildTicketListUrl } from "@/lib/utils/routes";

export function QueueSummaryCard({ rows }: { rows: QueueSummaryItem[] }) {
  return (
    <article className="card">
      <h3>Queue Load Ranking</h3>
      <ul className="list">
        {rows.slice(0, 5).map((row) => (
          <li className="list-item" key={row.queue_name}>
            <div>
              <a href={buildTicketListUrl({ queue: row.queue_name })}>
                <strong>{row.queue_name}</strong>
              </a>
            </div>
            <small>
              open {row.open_count} · in progress {row.in_progress_count} · warning{" "}
              {row.warning_count} · breached {row.breached_count}
            </small>
          </li>
        ))}
      </ul>
    </article>
  );
}

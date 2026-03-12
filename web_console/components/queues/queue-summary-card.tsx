"use client";

import type { QueueSummaryItem } from "@/lib/api/queues";
import { buildTicketListUrl } from "@/lib/utils/routes";
import { useI18n } from "@/lib/i18n";

export function QueueSummaryCard({ rows }: { rows: QueueSummaryItem[] }) {
  const { t } = useI18n();

  return (
    <article className="card">
      <div className="ops-card-title-row">
        <h3>{t("队列负载排行", "Queue Load Ranking")}</h3>
        <span className="ops-chip strong">{t("Top 5", "Top 5")}</span>
      </div>
      <ul className="list">
        {rows.slice(0, 5).map((row) => (
          <li className="list-item" key={row.queue_name}>
            <div>
              <a href={buildTicketListUrl({ queue: row.queue_name })}>
                <strong>{row.queue_name}</strong>
              </a>
            </div>
            <small>
              {t("待处理", "Open")} {row.open_count} · {t("处理中", "In Progress")} {row.in_progress_count} ·{" "}
              {t("预警", "Warning")} {row.warning_count} · {t("超时", "Breached")} {row.breached_count}
            </small>
          </li>
        ))}
      </ul>
    </article>
  );
}

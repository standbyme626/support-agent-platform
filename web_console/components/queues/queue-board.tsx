"use client";

import type { QueueSummaryItem } from "@/lib/api/queues";
import { buildTicketListUrl } from "@/lib/utils/routes";
import { useI18n } from "@/lib/i18n";

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
  const { t } = useI18n();

  if (rows.length === 0) {
    return (
      <article className="card">
        <h3>{t("队列看板", "Queue Board")}</h3>
        <div className="hint">{t("未找到队列项。", "No queue items found.")}</div>
      </article>
    );
  }

  return (
    <article className="card">
      <h3>{t("队列看板", "Queue Board")}</h3>
      <ul className="list">
        {rows.map((row) => (
          <li className="list-item" key={row.queue_name}>
            <div>
              <a href={buildTicketListUrl({ queue: row.queue_name })}>{row.queue_name}</a>
            </div>
            <small>
              {t("待处理", "open")} {row.open_count} · {t("处理中", "in progress")} {row.in_progress_count} ·{" "}
              {t("预警", "warning")} {row.warning_count} · {t("超时", "breached")} {row.breached_count} ·{" "}
              {t("升级", "escalated")} {row.escalated_count} · {t("状态", "state")} {queueState(row)}
            </small>
          </li>
        ))}
      </ul>
    </article>
  );
}

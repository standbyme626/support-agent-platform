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
      <div style={{ overflowX: "auto", marginTop: 10 }}>
        <table className="table ops-table-tight">
          <thead>
            <tr>
              <th>{t("队列", "Queue")}</th>
              <th>{t("Open", "Open")}</th>
              <th>{t("In Progress", "In Progress")}</th>
              <th>{t("Warning", "Warning")}</th>
              <th>{t("Breached", "Breached")}</th>
              <th>{t("Escalated", "Escalated")}</th>
              <th>{t("Assignees", "Assignees")}</th>
              <th>{t("状态", "State")}</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => {
              const state = queueState(row);
              return (
                <tr key={row.queue_name}>
                  <td>
                    <a href={buildTicketListUrl({ queue: row.queue_name })}>{row.queue_name}</a>
                  </td>
                  <td>{row.open_count}</td>
                  <td>{row.in_progress_count}</td>
                  <td>{row.warning_count}</td>
                  <td>{row.breached_count}</td>
                  <td>{row.escalated_count}</td>
                  <td>{row.assignee_count}</td>
                  <td>
                    <span className={`pill pill-${state}`}>{state}</span>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </article>
  );
}

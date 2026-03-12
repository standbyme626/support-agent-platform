"use client";

import type { QueueSummaryItem } from "@/lib/api/queues";
import { useI18n } from "@/lib/i18n";

function computeTotals(rows: QueueSummaryItem[]) {
  return rows.reduce(
    (acc, row) => {
      acc.assigneeCount += row.assignee_count;
      acc.inProgress += row.in_progress_count;
      acc.escalated += row.escalated_count;
      return acc;
    },
    { assigneeCount: 0, inProgress: 0, escalated: 0 }
  );
}

export function AssigneeWorkloadCard({ rows }: { rows: QueueSummaryItem[] }) {
  const { t } = useI18n();
  const totals = computeTotals(rows);
  const perAssignee =
    totals.assigneeCount === 0 ? 0 : Math.round((totals.inProgress / totals.assigneeCount) * 10) / 10;
  const stateClass = totals.escalated > 0 ? "pill-warning" : "pill-normal";
  return (
    <article className="card">
      <h3>{t("处理人负载", "Assignee Workload")}</h3>
      <div className="value">{perAssignee}</div>
      <div className="hint">
        {t("每位处理人平均处理中", "avg in-progress per assignee")} · {t("已升级", "escalated")} {totals.escalated}
      </div>
      <div style={{ marginTop: 10 }}>
        <span className={`pill ${stateClass}`}>
          {totals.escalated > 0 ? t("需要人工关注", "needs human attention") : t("负载可控", "workload stable")}
        </span>
      </div>
    </article>
  );
}

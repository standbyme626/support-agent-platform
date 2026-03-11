"use client";

import { AssigneeWorkloadCard } from "@/components/queues/assignee-workload-card";
import { QueueBoard } from "@/components/queues/queue-board";
import { QueueSummaryCard } from "@/components/queues/queue-summary-card";
import { EmptyState } from "@/components/shared/empty-state";
import { ErrorState } from "@/components/shared/error-state";
import { LoadingState } from "@/components/shared/loading-state";
import { StatCard } from "@/components/shared/stat-card";
import { useI18n } from "@/lib/i18n";
import { useQueues } from "@/lib/hooks/useQueues";
import { buildTicketListUrl } from "@/lib/utils/routes";

export default function QueuesPage() {
  const { t } = useI18n();
  const queues = useQueues();

  if (queues.loading) {
    return <LoadingState title={t("队列看板同步中。", "Queue board is syncing.")} />;
  }

  if (queues.error) {
    return (
      <ErrorState title={t("加载队列看板失败。", "Failed to load queue board.")} message={queues.error} onRetry={() => void queues.refetch()} />
    );
  }

  const rows = queues.summary.length > 0 ? queues.summary : queues.items;
  if (rows.length === 0) {
    return (
      <EmptyState
        title={t("暂无队列数据。", "No queue data.")}
        message={t("暂无可用队列指标。", "No queue metrics are available yet.")}
      />
    );
  }

  const totals = rows.reduce(
    (acc, row) => {
      acc.open += row.open_count;
      acc.inProgress += row.in_progress_count;
      acc.warning += row.warning_count;
      acc.breached += row.breached_count;
      acc.escalated += row.escalated_count;
      return acc;
    },
    { open: 0, inProgress: 0, warning: 0, breached: 0, escalated: 0 }
  );

  return (
    <section>
      <h2 className="section-title">{t("队列看板", "Queue Board")}</h2>
      <div className="grid stats">
        <StatCard title={t("待处理", "Open")} value={totals.open} hint={t("待分派", "pending assignment")} href={buildTicketListUrl({ status: "open" })} />
        <StatCard
          title={t("处理中", "In Progress")}
          value={totals.inProgress}
          hint={t("pending + escalated", "pending + escalated")}
        />
        <StatCard
          title={t("SLA 风险", "SLA Risk")}
          value={totals.warning + totals.breached}
          hint={t(`预警 ${totals.warning} + 超时 ${totals.breached}`, `warning ${totals.warning} + breached ${totals.breached}`)}
          href={buildTicketListUrl({ sla_state: totals.breached > 0 ? "breached" : "warning" })}
          state={totals.breached > 0 ? "breached" : totals.warning > 0 ? "warning" : "normal"}
        />
        <StatCard
          title={t("已升级", "Escalated")}
          value={totals.escalated}
          hint={t("需要快速跟进", "requires fast follow-up")}
          href={buildTicketListUrl({ status: "escalated" })}
          state={totals.escalated > 0 ? "warning" : "normal"}
        />
      </div>

      <h2 className="section-title" style={{ marginTop: 20 }}>
        {t("队列明细", "Queue Details")}
      </h2>
      <div className="grid two-col">
        <QueueSummaryCard rows={rows} />
        <AssigneeWorkloadCard rows={rows} />
        <QueueBoard rows={rows} />
      </div>
    </section>
  );
}

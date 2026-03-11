"use client";

import { AssigneeWorkloadCard } from "@/components/queues/assignee-workload-card";
import { QueueBoard } from "@/components/queues/queue-board";
import { QueueSummaryCard } from "@/components/queues/queue-summary-card";
import { EmptyState } from "@/components/shared/empty-state";
import { ErrorState } from "@/components/shared/error-state";
import { LoadingState } from "@/components/shared/loading-state";
import { StatCard } from "@/components/shared/stat-card";
import { useQueues } from "@/lib/hooks/useQueues";
import { buildTicketListUrl } from "@/lib/utils/routes";

export default function QueuesPage() {
  const queues = useQueues();

  if (queues.loading) {
    return <LoadingState title="Queue board is syncing." />;
  }

  if (queues.error) {
    return (
      <ErrorState title="Failed to load queue board." message={queues.error} onRetry={() => void queues.refetch()} />
    );
  }

  const rows = queues.summary.length > 0 ? queues.summary : queues.items;
  if (rows.length === 0) {
    return <EmptyState title="No queue data." message="No queue metrics are available yet." />;
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
      <h2 className="section-title">Queue Board</h2>
      <div className="grid stats">
        <StatCard title="Open" value={totals.open} hint="pending assignment" href={buildTicketListUrl({ status: "open" })} />
        <StatCard
          title="In Progress"
          value={totals.inProgress}
          hint="pending + escalated"
        />
        <StatCard
          title="SLA Risk"
          value={totals.warning + totals.breached}
          hint={`warning ${totals.warning} + breached ${totals.breached}`}
          href={buildTicketListUrl({ sla_state: totals.breached > 0 ? "breached" : "warning" })}
          state={totals.breached > 0 ? "breached" : totals.warning > 0 ? "warning" : "normal"}
        />
        <StatCard
          title="Escalated"
          value={totals.escalated}
          hint="requires fast follow-up"
          href={buildTicketListUrl({ status: "escalated" })}
          state={totals.escalated > 0 ? "warning" : "normal"}
        />
      </div>

      <h2 className="section-title" style={{ marginTop: 20 }}>
        Queue Details
      </h2>
      <div className="grid two-col">
        <QueueSummaryCard rows={rows} />
        <AssigneeWorkloadCard rows={rows} />
        <QueueBoard rows={rows} />
      </div>
    </section>
  );
}

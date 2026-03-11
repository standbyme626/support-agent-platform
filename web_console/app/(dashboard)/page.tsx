"use client";

import { AssigneeWorkloadCard } from "@/components/queues/assignee-workload-card";
import { QueueSummaryCard } from "@/components/queues/queue-summary-card";
import { EmptyState } from "@/components/shared/empty-state";
import { ErrorState } from "@/components/shared/error-state";
import { LoadingState } from "@/components/shared/loading-state";
import { StatCard, type SlaSemanticState } from "@/components/shared/stat-card";
import { useDashboardRecentErrors } from "@/lib/hooks/useDashboardRecentErrors";
import { useDashboardSummary } from "@/lib/hooks/useDashboardSummary";
import { useQueueSummary } from "@/lib/hooks/useQueueSummary";
import { buildTicketListUrl, buildTraceDetailUrl } from "@/lib/utils/routes";

function determineSlaState(warning: number, breached: number): SlaSemanticState {
  if (breached > 0) {
    return "breached";
  }
  if (warning > 0) {
    return "warning";
  }
  return "normal";
}

export default function DashboardPage() {
  const summary = useDashboardSummary();
  const recentErrors = useDashboardRecentErrors();
  const queueSummary = useQueueSummary();

  if (summary.loading || recentErrors.loading || queueSummary.loading) {
    return <LoadingState title="Dashboard is syncing." />;
  }

  if (summary.error) {
    return (
      <ErrorState
        title="Failed to load dashboard summary."
        message={summary.error}
        onRetry={() => void summary.refetch()}
      />
    );
  }

  if (recentErrors.error) {
    return (
      <ErrorState
        title="Failed to load recent errors."
        message={recentErrors.error}
        onRetry={() => void recentErrors.refetch()}
      />
    );
  }

  if (queueSummary.error) {
    return (
      <ErrorState
        title="Failed to load queue summary."
        message={queueSummary.error}
        onRetry={() => void queueSummary.refetch()}
      />
    );
  }

  if (!summary.data) {
    return <EmptyState title="No dashboard data." message="No summary payload received." />;
  }

  const slaState = determineSlaState(summary.data.sla_warning_count, summary.data.sla_breached_count);
  const totalSlaRisk = summary.data.sla_warning_count + summary.data.sla_breached_count;

  return (
    <section>
      <h2 className="section-title">Overview</h2>
      <div className="grid stats">
        <StatCard
          title="New Today"
          value={summary.data.new_tickets_today}
          hint="Created in the last 24h"
          href={buildTicketListUrl({ created_from: "today" })}
        />
        <StatCard
          title="In Progress"
          value={summary.data.in_progress_count}
          hint="open + pending tickets"
          href={buildTicketListUrl({ status: "open" })}
        />
        <StatCard
          title="SLA Risk"
          value={totalSlaRisk}
          hint="warning + breached"
          href={buildTicketListUrl({ sla_state: slaState })}
          state={slaState}
        />
        <StatCard
          title="Escalated"
          value={summary.data.escalated_count}
          hint="tickets requiring higher priority"
          href={buildTicketListUrl({ status: "escalated" })}
          state={summary.data.escalated_count > 0 ? "warning" : "normal"}
        />
        <StatCard
          title="Handoff Pending"
          value={summary.data.handoff_pending_count}
          hint="requested or accepted"
          href={buildTicketListUrl({ handoff_state: "requested" })}
          state={summary.data.handoff_pending_count > 0 ? "warning" : "normal"}
        />
      </div>

      <h2 className="section-title" style={{ marginTop: 20 }}>
        Errors, Queue, and Workload
      </h2>
      <div className="grid two-col">
        <article className="card">
          <h3>Recent Trace Errors</h3>
          {recentErrors.data.length === 0 ? (
            <div className="hint" style={{ marginTop: 8 }}>
              No recent trace errors.
            </div>
          ) : (
            <ul className="list">
              {recentErrors.data.slice(0, 5).map((item, index) => (
                <li className="list-item" key={`${item.trace_id ?? "trace"}-${index}`}>
                  <div>
                    <a href={item.trace_id ? buildTraceDetailUrl(item.trace_id) : "/traces"}>
                      {(item.event_type ?? "event").toString()}
                    </a>
                  </div>
                  <small>
                    trace={item.trace_id ?? "n/a"} ticket={item.ticket_id ?? "n/a"}
                  </small>
                </li>
              ))}
            </ul>
          )}
        </article>
        <QueueSummaryCard rows={queueSummary.data} />
        <AssigneeWorkloadCard rows={queueSummary.data} />
      </div>
    </section>
  );
}

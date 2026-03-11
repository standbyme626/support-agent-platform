import type { QueueSummaryItem } from "@/lib/api/queues";

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
  const totals = computeTotals(rows);
  const perAssignee =
    totals.assigneeCount === 0 ? 0 : Math.round((totals.inProgress / totals.assigneeCount) * 10) / 10;
  return (
    <article className="card">
      <h3>Assignee Workload</h3>
      <div className="value">{perAssignee}</div>
      <div className="hint">
        avg in-progress per assignee · escalated {totals.escalated}
      </div>
    </article>
  );
}

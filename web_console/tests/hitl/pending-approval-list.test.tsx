import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { PendingApprovalList } from "@/components/hitl/pending-approval-list";
import type { PendingApprovalItem } from "@/lib/api/tickets";

const baseItem: PendingApprovalItem = {
  approval_id: "apr_001",
  ticket_id: "TCK-001",
  action_type: "escalate",
  risk_level: "high",
  status: "pending_approval",
  requested_by: "u_ops_01",
  requested_at: "2026-03-11T00:00:00+00:00",
  timeout_at: "2026-03-11T01:00:00+00:00",
  reason: "escalation_requires_manual_confirmation",
  payload: { actor_id: "u_ops_01", note: "need escalation" },
  context: {}
};

describe("PendingApprovalList", () => {
  it("renders empty state", () => {
    render(
      <PendingApprovalList
        items={[]}
        loading={false}
        actionLoadingId={null}
        error={null}
        onRefresh={vi.fn()}
        onApprove={vi.fn()}
        onReject={vi.fn()}
      />
    );
    expect(screen.getByText("当前没有待审批动作。")).toBeInTheDocument();
  });

  it("opens dialog and submits approve decision", async () => {
    const onApprove = vi.fn<(...args: [string, string]) => Promise<void>>().mockResolvedValue();
    render(
      <PendingApprovalList
        items={[baseItem]}
        loading={false}
        actionLoadingId={null}
        error={null}
        onRefresh={vi.fn()}
        onApprove={onApprove}
        onReject={vi.fn()}
      />
    );

    fireEvent.click(screen.getByRole("button", { name: "批准" }));
    expect(screen.getByText("审批确认")).toBeInTheDocument();

    fireEvent.change(screen.getByPlaceholderText("可选：填写审批意见"), {
      target: { value: "approved by supervisor" }
    });
    fireEvent.click(screen.getAllByRole("button", { name: "批准" })[1]);

    await waitFor(() => {
      expect(onApprove).toHaveBeenCalledWith("apr_001", "approved by supervisor");
    });
  });

  it("shows pending/approved/rejected/timeout branches in detail mode", () => {
    render(
      <PendingApprovalList
        showAllStatuses
        items={[
          baseItem,
          {
            ...baseItem,
            approval_id: "apr_002",
            status: "approved",
            approved_by: "u_supervisor_01",
            decided_at: "2026-03-11T00:20:00+00:00",
            decision_note: "approved"
          },
          {
            ...baseItem,
            approval_id: "apr_003",
            status: "rejected",
            rejected_by: "u_supervisor_02",
            decided_at: "2026-03-11T00:30:00+00:00",
            decision_note: "reject"
          },
          {
            ...baseItem,
            approval_id: "apr_004",
            status: "timeout",
            decided_at: "2026-03-11T00:40:00+00:00",
            decision_note: "approval_timeout"
          }
        ]}
        loading={false}
        actionLoadingId={null}
        error={null}
        onRefresh={vi.fn()}
        onApprove={vi.fn()}
        onReject={vi.fn()}
      />
    );

    expect(screen.getByText("待审批")).toBeInTheDocument();
    expect(screen.getByText("已批准")).toBeInTheDocument();
    expect(screen.getByText("已拒绝")).toBeInTheDocument();
    expect(screen.getByText("已超时")).toBeInTheDocument();
    expect(screen.getAllByText(/恢复结果/).length).toBeGreaterThan(0);
  });
});

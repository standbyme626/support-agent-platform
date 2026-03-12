import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { TicketActionsPanel } from "@/components/tickets/ticket-actions-panel";
import type { TicketActionPayload, TicketActionType, TicketItem } from "@/lib/api/tickets";

const baseTicket: TicketItem = {
  ticket_id: "TCK-DETAIL-1",
  title: "Elevator issue",
  latest_message: "elevator stopped",
  status: "pending",
  priority: "P1",
  queue: "support",
  assignee: "u_ops_01",
  channel: "wecom",
  handoff_state: "none",
  risk_level: "medium",
  metadata: {},
  created_at: "2026-03-11T00:00:00+00:00",
  updated_at: "2026-03-11T00:00:00+00:00",
  sla_state: "warning"
};

describe("TicketActionsPanel", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("shows success feedback after a successful action", async () => {
    vi.spyOn(window, "confirm").mockReturnValue(true);
    const onAction = vi
      .fn<(...args: [TicketActionType, TicketActionPayload]) => Promise<void>>()
      .mockResolvedValue(undefined);

    render(
      <TicketActionsPanel
        ticket={baseTicket}
        assignees={["u_ops_01", "u_ops_02"]}
        loadingAction={null}
        actionError={null}
        onAction={onAction}
      />
    );

    fireEvent.click(screen.getByRole("button", { name: "认领" }));

    await waitFor(() => {
      expect(onAction).toHaveBeenCalledWith("claim", { actor_id: "u_ops_01" });
    });
    expect(await screen.findByText("动作 claim 已执行。")).toBeInTheDocument();
  });

  it("does not show success feedback when action fails", async () => {
    vi.spyOn(window, "confirm").mockReturnValue(true);
    const onAction = vi
      .fn<(...args: [TicketActionType, TicketActionPayload]) => Promise<void>>()
      .mockRejectedValue(new Error("action failed"));

    render(
      <TicketActionsPanel
        ticket={baseTicket}
        assignees={["u_ops_01", "u_ops_02"]}
        loadingAction={null}
        actionError={"action failed"}
        onAction={onAction}
      />
    );

    fireEvent.click(screen.getByRole("button", { name: "认领" }));

    await waitFor(() => {
      expect(onAction).toHaveBeenCalledWith("claim", { actor_id: "u_ops_01" });
    });
    expect(screen.queryByText("动作 claim 已执行。")).not.toBeInTheDocument();
    expect(screen.getByText(/action failed/i)).toBeInTheDocument();
  });
});

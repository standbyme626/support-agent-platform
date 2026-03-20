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

  it("uses v2 customer_confirm as a primary action", async () => {
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

    fireEvent.click(screen.getByRole("button", { name: "客户确认" }));

    await waitFor(() => {
      expect(onAction).toHaveBeenCalledWith(
        "customer_confirm",
        expect.objectContaining({ actor_id: "u_ops_01" })
      );
    });
  });

  it("uses v2 operator_close as a primary action", async () => {
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

    fireEvent.click(screen.getByRole("button", { name: "运营关闭" }));

    await waitFor(() => {
      expect(onAction).toHaveBeenCalledWith(
        "operator_close",
        expect.objectContaining({ actor_id: "u_ops_01" })
      );
    });
  });

  it("enables v1 close only in compatibility mode", async () => {
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

    expect(screen.queryByRole("button", { name: "兼容关闭（v1 /close）" })).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("checkbox", { name: "兼容模式（v1 /close）" }));
    fireEvent.click(screen.getByRole("button", { name: "兼容关闭（v1 /close）" }));

    await waitFor(() => {
      expect(onAction).toHaveBeenCalledWith(
        "close_compat",
        expect.objectContaining({ actor_id: "u_ops_01" })
      );
    });
  });

  it("imports ai suggestion into manual form without auto execution", async () => {
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
        aiDraft={{
          suggested_action: "Dispatch onsite",
          note: "Dispatch onsite\nVisit within 2h",
          source: "assist.recommended_actions"
        }}
      />
    );

    expect(screen.getByLabelText("备注 / 处理说明")).toHaveValue("Dispatch onsite\nVisit within 2h");
    expect(onAction).not.toHaveBeenCalled();
  });

  it("renders transition controls as non-submit buttons", () => {
    render(
      <TicketActionsPanel
        ticket={baseTicket}
        assignees={["u_ops_01", "u_ops_02"]}
        loadingAction={null}
        actionError={null}
        onAction={vi.fn()}
      />
    );

    for (const label of ["认领", "改派", "升级", "解决", "客户确认", "运营关闭"]) {
      const button = screen.getByRole("button", { name: label });
      expect(button).toHaveAttribute("type", "button");
    }
  });
});

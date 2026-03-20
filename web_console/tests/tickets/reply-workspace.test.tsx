import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { ReplyWorkspace } from "@/components/tickets/reply-workspace";
import type { ReplyDraftData, ReplyEventItem, ReplySendData, TicketItem } from "@/lib/api/tickets";

const baseTicket: TicketItem = {
  ticket_id: "TCK-REPLY-1",
  title: "Elevator issue",
  latest_message: "elevator stopped",
  status: "pending",
  priority: "P1",
  queue: "support",
  assignee: "u_ops_01",
  session_id: "sess-001",
  channel: "wecom",
  handoff_state: "none",
  risk_level: "medium",
  metadata: {},
  created_at: "2026-03-11T00:00:00+00:00",
  updated_at: "2026-03-11T00:00:00+00:00",
  sla_state: "warning"
};

const baseDraft: ReplyDraftData = {
  ticket_id: "TCK-REPLY-1",
  session_id: "sess-001",
  draft_text: "您好，我们已经收到问题，正在处理。",
  risk_flags: [],
  grounding: {},
  advice_only: true,
  trace_id: "trace-draft-001"
};

const baseSendResult: ReplySendData = {
  reply_id: "reply_001",
  delivery_status: "queued",
  channel: "wecom",
  target: { to_user_id: "wx_user_001", session_id: "dm:wx_user_001" },
  trace_id: "trace-send-001",
  dedup_hit: false,
  attempt: 1,
  error: null
};

const baseReplyEvents: ReplyEventItem[] = [
  {
    event_id: "reply_evt_1",
    event_type: "reply_send_delivered",
    trace_id: "trace-send-001",
    ticket_id: "TCK-REPLY-1",
    session_id: "sess-001",
    created_at: "2026-03-11T10:00:00+00:00",
    source: "trace",
    payload: {},
    delivery_status: "queued",
    attempt: 1,
    actor_id: "u_ops_01",
    actor_role: "operator",
    reply_id: "reply_001",
    idempotency_key: "idem_001"
  }
];

describe("ReplyWorkspace", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("generates AI draft but does not auto-send", async () => {
    const onGenerateDraft = vi.fn().mockResolvedValue(baseDraft);
    const onSendReply = vi.fn().mockResolvedValue(baseSendResult);

    render(
      <ReplyWorkspace
        ticket={baseTicket}
        assignees={["u_ops_01", "u_ops_02"]}
        replyDraft={null}
        replyDraftLoading={false}
        replyDraftError={null}
        replySend={null}
        replySendLoading={false}
        replySendError={null}
        replyEvents={[]}
        onGenerateDraft={onGenerateDraft}
        onSendReply={onSendReply}
      />
    );

    fireEvent.click(screen.getByRole("button", { name: "生成 AI 草稿" }));

    await waitFor(() => {
      expect(onGenerateDraft).toHaveBeenCalledTimes(1);
    });
    expect(
      await screen.findByText("AI 草稿已生成，请人工编辑后再发送。")
    ).toBeInTheDocument();
    expect(onSendReply).not.toHaveBeenCalled();
  });

  it("blocks observer from sending messages", async () => {
    vi.spyOn(window, "confirm").mockReturnValue(true);
    const onGenerateDraft = vi.fn().mockResolvedValue(baseDraft);
    const onSendReply = vi.fn().mockResolvedValue(baseSendResult);

    render(
      <ReplyWorkspace
        ticket={baseTicket}
        assignees={["u_ops_01", "u_viewer_01"]}
        replyDraft={baseDraft}
        replyDraftLoading={false}
        replyDraftError={null}
        replySend={null}
        replySendLoading={false}
        replySendError={null}
        replyEvents={[]}
        onGenerateDraft={onGenerateDraft}
        onSendReply={onSendReply}
      />
    );

    fireEvent.change(screen.getByLabelText("执行角色"), { target: { value: "observer" } });
    fireEvent.change(screen.getByLabelText("人工编辑后发送内容"), {
      target: { value: "这条消息不应发送" }
    });
    fireEvent.click(screen.getByRole("button", { name: "人工确认发送" }));

    expect(onSendReply).not.toHaveBeenCalled();
    expect(await screen.findByText("当前角色为 observer，禁止发送。")).toBeInTheDocument();
  });

  it("sends manual reply with confirm and renders reply-events status", async () => {
    vi.spyOn(window, "confirm").mockReturnValue(true);
    const onGenerateDraft = vi.fn().mockResolvedValue(baseDraft);
    const onSendReply = vi.fn().mockResolvedValue(baseSendResult);

    render(
      <ReplyWorkspace
        ticket={baseTicket}
        assignees={["u_ops_01"]}
        replyDraft={null}
        replyDraftLoading={false}
        replyDraftError={null}
        replySend={baseSendResult}
        replySendLoading={false}
        replySendError={null}
        replyEvents={baseReplyEvents}
        onGenerateDraft={onGenerateDraft}
        onSendReply={onSendReply}
      />
    );

    fireEvent.change(screen.getByLabelText("人工编辑后发送内容"), {
      target: { value: "您好，我们已经安排工程师到场处理。" }
    });
    fireEvent.click(screen.getByRole("button", { name: "人工确认发送" }));

    await waitFor(() => {
      expect(onSendReply).toHaveBeenCalledTimes(1);
    });
    expect(onSendReply.mock.calls[0][0]).toEqual(
      expect.objectContaining({
        actor_id: "u_ops_01",
        actor_role: "operator",
        content: "您好，我们已经安排工程师到场处理。"
      })
    );
    expect(String(onSendReply.mock.calls[0][0].idempotency_key)).toContain("reply_TCK-REPLY-1_");
    expect(screen.getByText("reply_send_delivered")).toBeInTheDocument();
    expect(screen.getByText("消息已提交，状态=queued。")).toBeInTheDocument();
  });

  it("hides reply events when showReplyEvents is false", () => {
    render(
      <ReplyWorkspace
        ticket={baseTicket}
        assignees={["u_ops_01"]}
        replyDraft={null}
        replyDraftLoading={false}
        replyDraftError={null}
        replySend={baseSendResult}
        replySendLoading={false}
        replySendError={null}
        replyEvents={baseReplyEvents}
        showReplyEvents={false}
        onGenerateDraft={vi.fn().mockResolvedValue(baseDraft)}
        onSendReply={vi.fn().mockResolvedValue(baseSendResult)}
      />
    );

    expect(screen.queryByText("Reply Events")).not.toBeInTheDocument();
    expect(screen.queryByText("reply_send_delivered")).not.toBeInTheDocument();
  });

  it("shows suggested status transition and executes manual action with confirmation", async () => {
    const confirmSpy = vi.spyOn(window, "confirm");
    confirmSpy.mockReturnValue(true);
    const onGenerateDraft = vi.fn().mockResolvedValue(baseDraft);
    const onSendReply = vi.fn().mockResolvedValue(baseSendResult);
    const onAction = vi.fn().mockResolvedValue(undefined);

    render(
      <ReplyWorkspace
        ticket={{ ...baseTicket, handoff_state: "pending_claim" }}
        assignees={["u_ops_01"]}
        replyDraft={baseDraft}
        replyDraftLoading={false}
        replyDraftError={null}
        replySend={baseSendResult}
        replySendLoading={false}
        replySendError={null}
        actionLoading={null}
        replyEvents={baseReplyEvents}
        onGenerateDraft={onGenerateDraft}
        onSendReply={onSendReply}
        onAction={onAction}
      />
    );

    expect(
      screen.getByText("发送回复只记录 reply-events，不会自动推进工单状态；请按需要手动执行状态流转。")
    ).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "建议下一步：认领" }));

    await waitFor(() => {
      expect(onAction).toHaveBeenCalledTimes(1);
    });
    expect(onAction).toHaveBeenCalledWith("claim", expect.objectContaining({ actor_id: "u_ops_01" }));
  });
});

import { render, screen } from "@testing-library/react";
import TicketDetailPage from "@/app/(dashboard)/tickets/[ticketId]/page";
import { useTicketDetail } from "@/lib/hooks/useTicketDetail";
import { useTicketPendingActions } from "@/lib/hooks/useTicketPendingActions";
import { useParams } from "next/navigation";

vi.mock("next/navigation", () => ({
  useParams: vi.fn()
}));

vi.mock("@/lib/hooks/useTicketDetail", () => ({
  useTicketDetail: vi.fn()
}));

vi.mock("@/lib/hooks/useTicketPendingActions", () => ({
  useTicketPendingActions: vi.fn()
}));

const mockUseParams = vi.mocked(useParams);
const mockUseTicketDetail = vi.mocked(useTicketDetail);
const mockUseTicketPendingActions = vi.mocked(useTicketPendingActions);

describe("TicketDetailPage", () => {
  beforeEach(() => {
    mockUseParams.mockReturnValue({ ticketId: "TCK-DETAIL-1" });
    mockUseTicketPendingActions.mockReturnValue({
      loading: false,
      actionLoadingId: null,
      error: null,
      items: [],
      refetch: vi.fn(),
      approve: vi.fn(),
      reject: vi.fn()
    });
  });

  it("renders loading state", () => {
    mockUseTicketDetail.mockReturnValue({
      loading: true,
      error: null,
      ticket: null,
      assist: null,
      copilot: null,
      operatorCopilot: null,
      dispatchCopilot: null,
      copilotLoading: false,
      copilotError: null,
      investigation: null,
      investigationLoading: false,
      investigationError: null,
      sessionEnd: null,
      sessionEndLoading: false,
      sessionEndError: null,
      replyDraft: null,
      replyDraftLoading: false,
      replyDraftError: null,
      replySend: null,
      replySendLoading: false,
      replySendError: null,
      replyEvents: [],
      groundingSources: [],
      similarCases: [],
      events: [],
      assignees: [],
      actionLoading: null,
      actionError: null,
      runAction: vi.fn(),
      queryCopilot: vi.fn(),
      runInvestigation: vi.fn(),
      runSessionEnd: vi.fn(),
      runReplyDraft: vi.fn(),
      runReplySend: vi.fn(),
      refetch: vi.fn()
    });

    render(<TicketDetailPage />);
    expect(screen.getByText("工单详情同步中。")).toBeInTheDocument();
  });

  it("renders ticket detail layout", () => {
    mockUseTicketDetail.mockReturnValue({
      loading: false,
      error: null,
      ticket: {
        ticket_id: "TCK-DETAIL-1",
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
        metadata: {
          service_type: "repair",
          community_name: "A区",
          building: "1号楼",
          parking_lot: "B2-018",
          approval_required: "true",
          current_graph_node: "intake_router",
          graph_state_summary: "awaiting_dispatch",
          dispatch_status: "queue_balancing",
          delivery_status: "pending_vendor_ack"
        },
        created_at: "2026-03-11T00:00:00+00:00",
        updated_at: "2026-03-11T00:00:00+00:00",
        sla_state: "warning"
      },
      assist: {
        summary: "Need hardware inspection",
        recommended_actions: [{ title: "Dispatch onsite", description: "Visit within 2h" }],
        grounding_sources: [],
        risk_flags: ["safety"],
        latest_messages: ["elevator stopped"],
        provider: "openai-compatible",
        prompt_version: "workflow_engine_v1"
      },
      copilot: null,
      operatorCopilot: {
        scope: "operator",
        query: "今日优先级",
        answer: "先处理升级与SLA风险单",
        grounding_sources: [],
        risk_flags: [],
        llm_trace: {},
        generated_at: "2026-03-11T00:00:00+00:00",
        advice_only: true
      },
      dispatchCopilot: {
        scope: "dispatch",
        query: "调度建议",
        answer: "优先向support队列投放资源",
        grounding_sources: [],
        risk_flags: [],
        llm_trace: {},
        generated_at: "2026-03-11T00:00:00+00:00",
        advice_only: true
      },
      copilotLoading: false,
      copilotError: null,
      investigation: null,
      investigationLoading: false,
      investigationError: null,
      sessionEnd: null,
      sessionEndLoading: false,
      sessionEndError: null,
      replyDraft: null,
      replyDraftLoading: false,
      replyDraftError: null,
      replySend: null,
      replySendLoading: false,
      replySendError: null,
      replyEvents: [],
      groundingSources: [
        {
          source_id: "case-001",
          source_type: "history_case",
          title: "支付重复扣费案例#001",
          snippet: "先冻结通道后退款并告知用户",
          score: 0.93,
          rank: 1
        }
      ],
      similarCases: [{ doc_id: "doc-1", title: "Elevator reboot", source_type: "history_case", score: 0.92 }],
      events: [
        {
          event_id: "evt-1",
          ticket_id: "TCK-DETAIL-1",
          event_type: "ticket_assigned",
          actor_type: "agent",
          actor_id: "u_ops_01",
          payload: {},
          created_at: "2026-03-11T01:00:00+00:00"
        }
      ],
      assignees: ["u_ops_01", "u_ops_02"],
      actionLoading: null,
      actionError: null,
      runAction: vi.fn(),
      queryCopilot: vi.fn(),
      runInvestigation: vi.fn(),
      runSessionEnd: vi.fn(),
      runReplyDraft: vi.fn(),
      runReplySend: vi.fn(),
      refetch: vi.fn()
    });

    render(<TicketDetailPage />);
    expect(screen.getByText("工单详情")).toBeInTheDocument();
    expect(screen.getByText("Elevator issue")).toBeInTheDocument();
    expect(screen.getAllByText("人工动作区").length).toBeGreaterThan(0);
    expect(screen.getByText("Reply Workspace（人工接管私聊闭环）")).toBeInTheDocument();
    expect(screen.getByText("审批恢复区")).toBeInTheDocument();
    expect(screen.getByText("AI 助手区")).toBeInTheDocument();
    expect(screen.getByText("主视图区")).toBeInTheDocument();
    expect(screen.getByText("事件时间线")).toBeInTheDocument();
    expect(screen.getByText("推荐动作")).toBeInTheDocument();
    expect(screen.getByText("相似案例")).toBeInTheDocument();
    expect(screen.getByText("定制字段")).toBeInTheDocument();
    expect(screen.getByText("Runtime 视角")).toBeInTheDocument();
    expect(screen.getByText(/current graph node: intake_router/)).toBeInTheDocument();
    expect(screen.getByText(/graph state summary: awaiting_dispatch/)).toBeInTheDocument();
    expect(screen.getByText(/dispatch status: queue_balancing/)).toBeInTheDocument();
    expect(screen.getByText(/delivery status: pending_vendor_ack/)).toBeInTheDocument();
    expect(screen.getByText("Operator 建议")).toBeInTheDocument();
    expect(screen.getByText("Dispatch 建议")).toBeInTheDocument();
    expect(screen.getByText(/agent source=operator_agent/)).toBeInTheDocument();
    expect(screen.getByText(/agent source=dispatch_agent/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "运行调查" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "结束会话" })).toBeInTheDocument();
  });

  it("shows partial AI degradation warning but keeps available agent outputs", () => {
    mockUseTicketDetail.mockReturnValue({
      loading: false,
      error: null,
      ticket: {
        ticket_id: "TCK-DETAIL-1",
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
      },
      assist: {
        summary: "Need hardware inspection",
        recommended_actions: [],
        grounding_sources: [],
        risk_flags: [],
        latest_messages: [],
        provider: "openai-compatible",
        prompt_version: "workflow_engine_v1"
      },
      copilot: null,
      operatorCopilot: {
        scope: "operator",
        query: "排班建议",
        answer: "先处理升级与SLA风险单",
        grounding_sources: [],
        risk_flags: [],
        llm_trace: {},
        runtime_trace: { agent: "operator_supervisor_agent_v1" },
        generated_at: "2026-03-11T00:00:00+00:00",
        advice_only: true
      },
      dispatchCopilot: {
        scope: "dispatch",
        query: "调度建议",
        answer: "优先向support队列投放资源",
        grounding_sources: [],
        risk_flags: [],
        llm_trace: {},
        runtime_trace: { agent: "dispatch_collaboration_agent_v1" },
        queue_summary: [{ queue_name: "support" }],
        generated_at: "2026-03-11T00:00:00+00:00",
        advice_only: true
      },
      copilotLoading: false,
      copilotError: "Partial copilot degraded: ticket branch failed",
      investigation: null,
      investigationLoading: false,
      investigationError: null,
      sessionEnd: null,
      sessionEndLoading: false,
      sessionEndError: null,
      replyDraft: null,
      replyDraftLoading: false,
      replyDraftError: null,
      replySend: null,
      replySendLoading: false,
      replySendError: null,
      replyEvents: [],
      groundingSources: [],
      similarCases: [],
      events: [],
      assignees: ["u_ops_01"],
      actionLoading: null,
      actionError: null,
      runAction: vi.fn(),
      queryCopilot: vi.fn(),
      runInvestigation: vi.fn(),
      runSessionEnd: vi.fn(),
      runReplyDraft: vi.fn(),
      runReplySend: vi.fn(),
      refetch: vi.fn()
    });

    render(<TicketDetailPage />);
    expect(screen.getByText(/AI 局部降级：/)).toBeInTheDocument();
    expect(screen.getByText("Operator 建议")).toBeInTheDocument();
    expect(screen.getByText("Dispatch 建议")).toBeInTheDocument();
    expect(screen.getByText(/agent source=dispatch_agent/)).toBeInTheDocument();
  });

  it("shows approval resume path visibility in approval recovery section", () => {
    mockUseTicketPendingActions.mockReturnValue({
      loading: false,
      actionLoadingId: null,
      error: null,
      items: [
        {
          approval_id: "apr-1",
          ticket_id: "TCK-DETAIL-1",
          action_type: "escalate",
          risk_level: "high",
          status: "pending_approval",
          requested_by: "u_ops_01",
          requested_at: "2026-03-11T00:00:00+00:00",
          timeout_at: "2026-03-11T00:30:00+00:00",
          reason: "high risk",
          payload: {},
          context: {}
        },
        {
          approval_id: "apr-2",
          ticket_id: "TCK-DETAIL-1",
          action_type: "operator_close",
          risk_level: "high",
          status: "approved",
          requested_by: "u_ops_01",
          requested_at: "2026-03-10T00:00:00+00:00",
          timeout_at: "2026-03-10T00:30:00+00:00",
          reason: "history",
          payload: {},
          context: {},
          approved_by: "u_supervisor_01",
          decided_at: "2026-03-10T00:05:00+00:00",
          decision_note: "looks good"
        }
      ],
      refetch: vi.fn(),
      approve: vi.fn(),
      reject: vi.fn()
    });
    mockUseTicketDetail.mockReturnValue({
      loading: false,
      error: null,
      ticket: {
        ticket_id: "TCK-DETAIL-1",
        title: "Elevator issue",
        latest_message: "elevator stopped",
        status: "pending",
        priority: "P1",
        queue: "support",
        assignee: "u_ops_01",
        session_id: "sess-001",
        channel: "wecom",
        handoff_state: "pending_approval",
        risk_level: "high",
        metadata: {},
        created_at: "2026-03-11T00:00:00+00:00",
        updated_at: "2026-03-11T00:00:00+00:00",
        sla_state: "warning"
      },
      assist: null,
      copilot: null,
      operatorCopilot: null,
      dispatchCopilot: null,
      copilotLoading: false,
      copilotError: null,
      investigation: null,
      investigationLoading: false,
      investigationError: null,
      sessionEnd: null,
      sessionEndLoading: false,
      sessionEndError: null,
      replyDraft: null,
      replyDraftLoading: false,
      replyDraftError: null,
      replySend: null,
      replySendLoading: false,
      replySendError: null,
      replyEvents: [],
      groundingSources: [],
      similarCases: [],
      events: [],
      assignees: ["u_ops_01"],
      actionLoading: null,
      actionError: null,
      runAction: vi.fn(),
      queryCopilot: vi.fn(),
      runInvestigation: vi.fn(),
      runSessionEnd: vi.fn(),
      runReplyDraft: vi.fn(),
      runReplySend: vi.fn(),
      refetch: vi.fn()
    });

    render(<TicketDetailPage />);
    expect(screen.getByText(/pending_approval: 1/)).toBeInTheDocument();
    expect(screen.getByText(/当前审批状态/)).toBeInTheDocument();
    expect(screen.getByText(/resume 所需动作/)).toBeInTheDocument();
    expect(screen.getAllByText(/approve\/reject/).length).toBeGreaterThan(0);
    expect(screen.getByText(/审批后 graph 恢复结果/)).toBeInTheDocument();
  });

  it("renders error state", () => {
    mockUseTicketDetail.mockReturnValue({
      loading: false,
      error: "detail api timeout",
      ticket: null,
      assist: null,
      copilot: null,
      operatorCopilot: null,
      dispatchCopilot: null,
      copilotLoading: false,
      copilotError: null,
      investigation: null,
      investigationLoading: false,
      investigationError: null,
      sessionEnd: null,
      sessionEndLoading: false,
      sessionEndError: null,
      replyDraft: null,
      replyDraftLoading: false,
      replyDraftError: null,
      replySend: null,
      replySendLoading: false,
      replySendError: null,
      replyEvents: [],
      groundingSources: [],
      similarCases: [],
      events: [],
      assignees: [],
      actionLoading: null,
      actionError: null,
      runAction: vi.fn(),
      queryCopilot: vi.fn(),
      runInvestigation: vi.fn(),
      runSessionEnd: vi.fn(),
      runReplyDraft: vi.fn(),
      runReplySend: vi.fn(),
      refetch: vi.fn()
    });

    render(<TicketDetailPage />);
    expect(screen.getByText("加载工单详情失败。")).toBeInTheDocument();
    expect(screen.getByText("detail api timeout")).toBeInTheDocument();
  });
});

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
          approval_required: "true"
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
      refetch: vi.fn()
    });

    render(<TicketDetailPage />);
    expect(screen.getByText("工单详情")).toBeInTheDocument();
    expect(screen.getByText("Elevator issue")).toBeInTheDocument();
    expect(screen.getAllByText("人工动作区").length).toBeGreaterThan(0);
    expect(screen.getByText("审批恢复区")).toBeInTheDocument();
    expect(screen.getByText("AI 助手区")).toBeInTheDocument();
    expect(screen.getByText("主视图区")).toBeInTheDocument();
    expect(screen.getByText("事件时间线")).toBeInTheDocument();
    expect(screen.getByText("推荐动作")).toBeInTheDocument();
    expect(screen.getByText("相似案例")).toBeInTheDocument();
    expect(screen.getByText("定制字段")).toBeInTheDocument();
    expect(screen.getByText("Operator 建议")).toBeInTheDocument();
    expect(screen.getByText("Dispatch 建议")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "运行调查" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "结束会话" })).toBeInTheDocument();
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
      refetch: vi.fn()
    });

    render(<TicketDetailPage />);
    expect(screen.getByText("加载工单详情失败。")).toBeInTheDocument();
    expect(screen.getByText("detail api timeout")).toBeInTheDocument();
  });
});

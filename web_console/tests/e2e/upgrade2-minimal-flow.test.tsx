import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import TicketDetailPage from "@/app/(dashboard)/tickets/[ticketId]/page";
import TracesPage from "@/app/(dashboard)/traces/page";
import KbFaqPage from "@/app/(dashboard)/kb/faq/page";
import ChannelsPage from "@/app/(dashboard)/channels/page";
import { useParams } from "next/navigation";
import { useTicketDetail } from "@/lib/hooks/useTicketDetail";
import { useTraceList } from "@/lib/hooks/useTraceList";
import { useKB } from "@/lib/hooks/useKB";
import { useGatewayHealth } from "@/lib/hooks/useGatewayHealth";

vi.mock("next/navigation", () => ({
  useParams: vi.fn()
}));

vi.mock("@/lib/hooks/useTicketDetail", () => ({
  useTicketDetail: vi.fn()
}));

vi.mock("@/lib/hooks/useTraceList", () => ({
  useTraceList: vi.fn()
}));

vi.mock("@/lib/hooks/useKB", () => ({
  useKB: vi.fn()
}));

vi.mock("@/lib/hooks/useGatewayHealth", () => ({
  useGatewayHealth: vi.fn()
}));

const mockUseParams = vi.mocked(useParams);
const mockUseTicketDetail = vi.mocked(useTicketDetail);
const mockUseTraceList = vi.mocked(useTraceList);
const mockUseKB = vi.mocked(useKB);
const mockUseGatewayHealth = vi.mocked(useGatewayHealth);

describe("Upgrade2 minimal front-end flow smoke", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("covers ticket action chain", async () => {
    vi.spyOn(window, "confirm").mockReturnValue(true);
    const runAction = vi.fn().mockResolvedValue(undefined);
    mockUseParams.mockReturnValue({ ticketId: "TCK-DETAIL-1" });
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
        channel: "wecom",
        handoff_state: "none",
        risk_level: "medium",
        metadata: { service_type: "repair" },
        created_at: "2026-03-11T00:00:00+00:00",
        updated_at: "2026-03-11T00:00:00+00:00",
        sla_state: "warning"
      },
      assist: {
        summary: "Need hardware inspection",
        recommended_actions: [],
        risk_flags: [],
        latest_messages: [],
        provider: "openai-compatible",
        prompt_version: "workflow_engine_v1"
      },
      similarCases: [],
      events: [],
      assignees: ["u_ops_01", "u_ops_02"],
      actionLoading: null,
      actionError: null,
      runAction,
      refetch: vi.fn()
    });

    render(<TicketDetailPage />);

    fireEvent.click(screen.getByRole("button", { name: "认领" }));

    await waitFor(() => {
      expect(runAction).toHaveBeenCalledWith("claim", { actor_id: "u_ops_01" });
    });
    expect(await screen.findByText("动作 claim 已执行。")).toBeInTheDocument();
  });

  it("covers trace drill-down entry", () => {
    mockUseTraceList.mockReturnValue({
      loading: false,
      error: null,
      items: [
        {
          trace_id: "trace-001",
          ticket_id: "TCK-001",
          session_id: "sess-001",
          workflow: "support-intake",
          channel: "wecom",
          provider: "openai-compatible",
          route_decision: { intent: "repair" },
          handoff: false,
          handoff_reason: null,
          error_only: false,
          latency_ms: 235,
          created_at: "2026-03-11T00:00:00+00:00"
        }
      ],
      total: 1,
      page: 1,
      pageSize: 20,
      filters: {},
      setPage: vi.fn(),
      updateFilters: vi.fn(),
      clearFilters: vi.fn(),
      refetch: vi.fn()
    });

    render(<TracesPage />);

    expect(screen.getByRole("link", { name: "trace-001" })).toHaveAttribute("href", "/traces/trace-001");
  });

  it("covers kb crud entry", async () => {
    const createDoc = vi.fn().mockResolvedValue(undefined);
    mockUseKB.mockReturnValue({
      loading: false,
      error: null,
      items: [
        {
          doc_id: "doc_faq_001",
          source_type: "faq",
          title: "Elevator restart SOP",
          content: "Restart breaker and verify control panel.",
          tags: ["elevator", "safety"],
          updated_at: "2026-03-11T00:00:00+00:00"
        }
      ],
      total: 1,
      page: 1,
      pageSize: 20,
      q: "",
      actionLoading: false,
      actionError: null,
      actionSuccess: null,
      setPage: vi.fn(),
      setQuery: vi.fn(),
      clearQuery: vi.fn(),
      clearActionState: vi.fn(),
      refetch: vi.fn(),
      createDoc,
      updateDoc: vi.fn().mockResolvedValue(undefined),
      deleteDoc: vi.fn().mockResolvedValue(undefined)
    });

    render(<KbFaqPage />);

    fireEvent.click(screen.getByRole("button", { name: "kb_add_doc" }));
    fireEvent.change(screen.getByLabelText("kb_doc_id"), { target: { value: "doc_faq_002" } });
    fireEvent.change(screen.getByLabelText("kb_title"), { target: { value: "Parking entry FAQ" } });
    fireEvent.change(screen.getByLabelText("kb_content"), { target: { value: "Check camera and plate recognition." } });
    fireEvent.change(screen.getByLabelText("kb_tags"), { target: { value: "parking,camera" } });
    fireEvent.click(screen.getByRole("button", { name: "kb_submit" }));

    await waitFor(() =>
      expect(createDoc).toHaveBeenCalledWith({
        doc_id: "doc_faq_002",
        title: "Parking entry FAQ",
        content: "Check camera and plate recognition.",
        tags: ["parking", "camera"]
      })
    );
  });

  it("covers channels observation entry", () => {
    mockUseGatewayHealth.mockReturnValue({
      loading: false,
      error: null,
      status: {
        environment: "dev",
        gateway: "openclaw-dev",
        sqlite_path: "/tmp/demo.db",
        session_bindings: 3,
        log_path: "/tmp/gateway.log",
        recent_events: []
      },
      routes: [{ channel: "telegram", mode: "ingress/session/routing" }],
      channelHealth: [
        {
          channel: "telegram",
          connected: true,
          last_event_at: "2026-03-11T01:02:03+00:00",
          last_error: null,
          retry_state: "idle"
        }
      ],
      events: [
        {
          timestamp: "2026-03-11T01:02:03+00:00",
          trace_id: "trace-h-001",
          channel: "telegram",
          event_type: "ingress_normalized",
          payload: { text: "need help" }
        }
      ],
      refetch: vi.fn()
    });

    render(<ChannelsPage />);

    expect(screen.getByRole("heading", { level: 2, name: "渠道 / 网关" })).toBeInTheDocument();
    expect(screen.getByText("openclaw-dev")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "trace-h-001" })).toHaveAttribute("href", "/traces/trace-h-001");
  });
});

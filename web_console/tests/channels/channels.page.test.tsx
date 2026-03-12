import { render, screen } from "@testing-library/react";
import ChannelsPage from "@/app/(dashboard)/channels/page";
import { useGatewayHealth } from "@/lib/hooks/useGatewayHealth";

vi.mock("@/lib/hooks/useGatewayHealth", () => ({
  useGatewayHealth: vi.fn()
}));

const mockUseGatewayHealth = vi.mocked(useGatewayHealth);

describe("ChannelsPage", () => {
  it("renders loading state", () => {
    mockUseGatewayHealth.mockReturnValue({
      loading: true,
      error: null,
      status: null,
      routes: [],
      channelHealth: [],
      events: [],
      signatures: [],
      replays: [],
      retries: [],
      sessions: [],
      replayDuplicateRatio: 0,
      retryObservabilityRate: 1,
      refetch: vi.fn()
    });

    render(<ChannelsPage />);
    expect(screen.getByText("渠道与网关指标同步中。")).toBeInTheDocument();
  });

  it("renders error state", () => {
    mockUseGatewayHealth.mockReturnValue({
      loading: false,
      error: "gateway timeout",
      status: null,
      routes: [],
      channelHealth: [],
      events: [],
      signatures: [],
      replays: [],
      retries: [],
      sessions: [],
      replayDuplicateRatio: 0,
      retryObservabilityRate: 1,
      refetch: vi.fn()
    });

    render(<ChannelsPage />);
    expect(screen.getByText("加载渠道与网关指标失败。")).toBeInTheDocument();
    expect(screen.getByText("gateway timeout")).toBeInTheDocument();
  });

  it("renders gateway status, channel health, and event table", () => {
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
      routes: [
        { channel: "telegram", mode: "ingress/session/routing" },
        { channel: "wecom", mode: "ingress/session/routing" }
      ],
      channelHealth: [
        {
          channel: "telegram",
          connected: true,
          last_event_at: "2026-03-11T01:02:03+00:00",
          last_error: null,
          retry_state: "idle",
          signature_state: "verified",
          replay_duplicates: 0,
          retry_observability: 1
        }
      ],
      signatures: [
        {
          channel: "telegram",
          checked: 1,
          valid: 1,
          rejected: 0,
          last_checked_at: "2026-03-11T01:02:03+00:00",
          last_error_code: null
        }
      ],
      replays: [
        {
          timestamp: "2026-03-11T01:02:03+00:00",
          trace_id: "trace-h-001",
          channel: "telegram",
          session_id: "session-1",
          idempotency_key: "telegram:1001",
          accepted: true,
          replay_count: 0
        }
      ],
      retries: [
        {
          timestamp: "2026-03-11T01:02:03+00:00",
          trace_id: "trace-h-001",
          channel: "telegram",
          session_id: "session-1",
          event_type: "egress_failed",
          attempt: 1,
          classification: "temporary",
          should_retry: true,
          error_code: "temporary_send_failure",
          error_message: "flaky network"
        }
      ],
      sessions: [
        {
          session_id: "session-1",
          thread_id: "thread-1",
          ticket_id: "TICKET-1",
          updated_at: "2026-03-11T01:02:03+00:00",
          channel: "telegram",
          last_message_id: "telegram:1001",
          replay_count: 0
        }
      ],
      replayDuplicateRatio: 0,
      retryObservabilityRate: 1,
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
    expect(screen.getByRole("button", { name: "refresh_channels" })).toBeInTheDocument();
    expect(screen.getByText("网关状态")).toBeInTheDocument();
    expect(screen.getByText("openclaw-dev")).toBeInTheDocument();
    expect(screen.getByText("渠道健康")).toBeInTheDocument();
    expect(screen.getByText("Webhook 事件流")).toBeInTheDocument();
    expect(screen.getAllByText("签名状态").length).toBeGreaterThan(0);
    expect(screen.getByText("重放与重试")).toBeInTheDocument();
    expect(screen.getByText("ingress_normalized")).toBeInTheDocument();
    expect(screen.getByText("trace-h-001")).toBeInTheDocument();
  });
});

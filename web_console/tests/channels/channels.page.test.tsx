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
      refetch: vi.fn()
    });

    render(<ChannelsPage />);
    expect(screen.getByText("Channels and gateway metrics are syncing.")).toBeInTheDocument();
  });

  it("renders error state", () => {
    mockUseGatewayHealth.mockReturnValue({
      loading: false,
      error: "gateway timeout",
      status: null,
      routes: [],
      channelHealth: [],
      events: [],
      refetch: vi.fn()
    });

    render(<ChannelsPage />);
    expect(screen.getByText("Failed to load channels and gateway metrics.")).toBeInTheDocument();
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

    expect(screen.getByRole("heading", { level: 2, name: "Channels / Gateway" })).toBeInTheDocument();
    expect(screen.getByText("Gateway Status")).toBeInTheDocument();
    expect(screen.getByText("openclaw-dev")).toBeInTheDocument();
    expect(screen.getByText("Channel Health")).toBeInTheDocument();
    expect(screen.getByText("Webhook Event Stream")).toBeInTheDocument();
    expect(screen.getByText("ingress_normalized")).toBeInTheDocument();
    expect(screen.getByText("trace-h-001")).toBeInTheDocument();
  });
});

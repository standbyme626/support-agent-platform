import { render, screen } from "@testing-library/react";
import TracesPage from "@/app/(dashboard)/traces/page";
import { useTraceList } from "@/lib/hooks/useTraceList";

vi.mock("@/lib/hooks/useTraceList", () => ({
  useTraceList: vi.fn()
}));

const mockUseTraceList = vi.mocked(useTraceList);

describe("TracesPage", () => {
  it("renders loading state", () => {
    mockUseTraceList.mockReturnValue({
      loading: true,
      error: null,
      items: [],
      total: 0,
      page: 1,
      pageSize: 20,
      filters: {},
      setPage: vi.fn(),
      updateFilters: vi.fn(),
      clearFilters: vi.fn(),
      refetch: vi.fn()
    });

    render(<TracesPage />);
    expect(screen.getByText("Trace 列表同步中。")).toBeInTheDocument();
  });

  it("renders trace table", () => {
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
    expect(screen.getByRole("heading", { name: "Trace 列表", level: 2 })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "trace-001" })).toHaveAttribute("href", "/traces/trace-001");
    expect(screen.getByText("support-intake")).toBeInTheDocument();
  });

  it("renders error state", () => {
    mockUseTraceList.mockReturnValue({
      loading: false,
      error: "traces api timeout",
      items: [],
      total: 0,
      page: 1,
      pageSize: 20,
      filters: {},
      setPage: vi.fn(),
      updateFilters: vi.fn(),
      clearFilters: vi.fn(),
      refetch: vi.fn()
    });

    render(<TracesPage />);
    expect(screen.getByText("加载 Trace 失败。")).toBeInTheDocument();
    expect(screen.getByText("traces api timeout")).toBeInTheDocument();
  });
});

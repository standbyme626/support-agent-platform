import { render, screen } from "@testing-library/react";
import TicketsPage from "@/app/(dashboard)/tickets/page";
import { useTickets } from "@/lib/hooks/useTickets";

vi.mock("@/lib/hooks/useTickets", () => ({
  useTickets: vi.fn()
}));

const mockUseTickets = vi.mocked(useTickets);

describe("TicketsPage", () => {
  it("renders loading state", () => {
    mockUseTickets.mockReturnValue({
      loading: true,
      error: null,
      items: [],
      total: 0,
      assignees: [],
      page: 1,
      pageSize: 20,
      sortBy: "created_at",
      sortOrder: "desc",
      filters: {},
      setPage: vi.fn(),
      setPageSize: vi.fn(),
      setSort: vi.fn(),
      updateFilters: vi.fn(),
      clearFilters: vi.fn(),
      refetch: vi.fn()
    });

    render(<TicketsPage />);
    expect(screen.getByText("工单列表同步中。")).toBeInTheDocument();
  });

  it("renders table and filter controls", () => {
    const longMessage = "cannot open gate and customer is waiting for a callback ".repeat(8);
    const normalizedMessage = longMessage.replace(/\s+/g, " ").trim();
    const expectedPreview = `${normalizedMessage.slice(0, 177)}...`;

    mockUseTickets.mockReturnValue({
      loading: false,
      error: null,
      items: [
        {
          ticket_id: "t-1",
          title: "Gate issue",
          latest_message: longMessage,
          status: "open",
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
        }
      ],
      total: 1,
      assignees: ["u_ops_01"],
      page: 1,
      pageSize: 20,
      sortBy: "created_at",
      sortOrder: "desc",
      filters: {},
      setPage: vi.fn(),
      setPageSize: vi.fn(),
      setSort: vi.fn(),
      updateFilters: vi.fn(),
      clearFilters: vi.fn(),
      refetch: vi.fn()
    });

    render(<TicketsPage />);
    expect(screen.getByText("工单收件箱")).toBeInTheDocument();
    expect(screen.getByText("工单筛选")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "refresh_tickets" })).toBeInTheDocument();
    expect(screen.getByLabelText("小区")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Gate issue" })).toBeInTheDocument();
    expect(screen.getByText(expectedPreview)).toBeInTheDocument();
    expect(screen.queryByText(normalizedMessage)).not.toBeInTheDocument();
  });

  it("renders error state", () => {
    mockUseTickets.mockReturnValue({
      loading: false,
      error: "network unavailable",
      items: [],
      total: 0,
      assignees: [],
      page: 1,
      pageSize: 20,
      sortBy: "created_at",
      sortOrder: "desc",
      filters: {},
      setPage: vi.fn(),
      setPageSize: vi.fn(),
      setSort: vi.fn(),
      updateFilters: vi.fn(),
      clearFilters: vi.fn(),
      refetch: vi.fn()
    });

    render(<TicketsPage />);
    expect(screen.getByText("加载工单失败。")).toBeInTheDocument();
    expect(screen.getByText("network unavailable")).toBeInTheDocument();
  });
});

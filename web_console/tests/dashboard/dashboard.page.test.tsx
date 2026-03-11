import { render, screen } from "@testing-library/react";
import DashboardPage from "@/app/(dashboard)/page";
import { useDashboardSummary } from "@/lib/hooks/useDashboardSummary";
import { useDashboardRecentErrors } from "@/lib/hooks/useDashboardRecentErrors";
import { useQueueSummary } from "@/lib/hooks/useQueueSummary";

vi.mock("@/lib/hooks/useDashboardSummary", () => ({
  useDashboardSummary: vi.fn()
}));

vi.mock("@/lib/hooks/useDashboardRecentErrors", () => ({
  useDashboardRecentErrors: vi.fn()
}));

vi.mock("@/lib/hooks/useQueueSummary", () => ({
  useQueueSummary: vi.fn()
}));

const mockUseDashboardSummary = vi.mocked(useDashboardSummary);
const mockUseDashboardRecentErrors = vi.mocked(useDashboardRecentErrors);
const mockUseQueueSummary = vi.mocked(useQueueSummary);

describe("DashboardPage", () => {
  it("renders loading state", () => {
    mockUseDashboardSummary.mockReturnValue({
      loading: true,
      error: null,
      data: null,
      refetch: vi.fn()
    });
    mockUseDashboardRecentErrors.mockReturnValue({
      loading: false,
      error: null,
      data: [],
      refetch: vi.fn()
    });
    mockUseQueueSummary.mockReturnValue({
      loading: false,
      error: null,
      data: [],
      refetch: vi.fn()
    });

    render(<DashboardPage />);
    expect(screen.getByText("总览数据同步中。")).toBeInTheDocument();
  });

  it("renders summary cards with SLA semantic state", () => {
    mockUseDashboardSummary.mockReturnValue({
      loading: false,
      error: null,
      data: {
        new_tickets_today: 8,
        in_progress_count: 12,
        handoff_pending_count: 2,
        escalated_count: 1,
        sla_warning_count: 3,
        sla_breached_count: 1
      },
      refetch: vi.fn()
    });
    mockUseDashboardRecentErrors.mockReturnValue({
      loading: false,
      error: null,
      data: [
        {
          trace_id: "trace-001",
          ticket_id: "t-1",
          event_type: "route_failed"
        }
      ],
      refetch: vi.fn()
    });
    mockUseQueueSummary.mockReturnValue({
      loading: false,
      error: null,
      data: [
        {
          queue_name: "support",
          open_count: 2,
          in_progress_count: 5,
          warning_count: 1,
          breached_count: 0,
          escalated_count: 1,
          assignee_count: 2
        }
      ],
      refetch: vi.fn()
    });

    render(<DashboardPage />);

    expect(screen.getByText("今日新建")).toBeInTheDocument();
    expect(screen.getByText("SLA 风险")).toBeInTheDocument();
    expect(screen.getByText("近期 Trace 错误")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "打开 SLA 风险" })).toHaveAttribute(
      "href",
      "/tickets?sla_state=breached"
    );
  });

  it("renders error state", () => {
    mockUseDashboardSummary.mockReturnValue({
      loading: false,
      error: "network timeout",
      data: null,
      refetch: vi.fn()
    });
    mockUseDashboardRecentErrors.mockReturnValue({
      loading: false,
      error: null,
      data: [],
      refetch: vi.fn()
    });
    mockUseQueueSummary.mockReturnValue({
      loading: false,
      error: null,
      data: [],
      refetch: vi.fn()
    });

    render(<DashboardPage />);
    expect(screen.getByText("加载总览摘要失败。")).toBeInTheDocument();
    expect(screen.getByText("network timeout")).toBeInTheDocument();
  });
});

import { render, screen } from "@testing-library/react";
import QueuesPage from "@/app/(dashboard)/queues/page";
import { useQueues } from "@/lib/hooks/useQueues";

vi.mock("@/lib/hooks/useQueues", () => ({
  useQueues: vi.fn()
}));

const mockUseQueues = vi.mocked(useQueues);

describe("QueuesPage", () => {
  it("renders loading state", () => {
    mockUseQueues.mockReturnValue({
      loading: true,
      error: null,
      items: [],
      summary: [],
      refetch: vi.fn()
    });

    render(<QueuesPage />);
    expect(screen.getByText("Queue board is syncing.")).toBeInTheDocument();
  });

  it("renders error state", () => {
    mockUseQueues.mockReturnValue({
      loading: false,
      error: "network timeout",
      items: [],
      summary: [],
      refetch: vi.fn()
    });

    render(<QueuesPage />);
    expect(screen.getByText("Failed to load queue board.")).toBeInTheDocument();
    expect(screen.getByText("network timeout")).toBeInTheDocument();
  });

  it("renders queue metrics and jump links", () => {
    mockUseQueues.mockReturnValue({
      loading: false,
      error: null,
      items: [],
      summary: [
        {
          queue_name: "support",
          open_count: 2,
          in_progress_count: 4,
          warning_count: 1,
          breached_count: 0,
          escalated_count: 1,
          assignee_count: 2
        },
        {
          queue_name: "billing",
          open_count: 1,
          in_progress_count: 1,
          warning_count: 0,
          breached_count: 1,
          escalated_count: 0,
          assignee_count: 1
        }
      ],
      refetch: vi.fn()
    });

    render(<QueuesPage />);

    expect(screen.getByRole("heading", { level: 2, name: "Queue Board" })).toBeInTheDocument();
    expect(screen.getByText("Queue Details")).toBeInTheDocument();
    const queueLinks = screen
      .getAllByRole("link")
      .map((element) => element.getAttribute("href"))
      .filter((href): href is string => Boolean(href));
    expect(queueLinks).toContain("/tickets?queue=support");
    expect(queueLinks).toContain("/tickets?queue=billing");
  });
});

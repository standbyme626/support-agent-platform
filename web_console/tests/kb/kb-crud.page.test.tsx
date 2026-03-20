import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import KbFaqPage from "@/app/(dashboard)/kb/faq/page";
import { useKB } from "@/lib/hooks/useKB";

vi.mock("@/lib/hooks/useKB", () => ({
  useKB: vi.fn()
}));

const mockUseKB = vi.mocked(useKB);

function baseHookState() {
  return {
    loading: false,
    error: null,
    items: [
      {
        doc_id: "doc_faq_001",
        source_type: "faq" as const,
        title: "Elevator restart SOP",
        content: "Restart breaker and verify control panel.",
        tags: ["elevator", "safety"],
        updated_at: "2026-03-11T00:00:00+00:00",
        metadata: {}
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
    createDoc: vi.fn().mockResolvedValue(undefined),
    updateDoc: vi.fn().mockResolvedValue(undefined),
    deleteDoc: vi.fn().mockResolvedValue(undefined)
  };
}

describe("KbFaqPage", () => {
  it("renders loading state", () => {
    mockUseKB.mockReturnValue({
      ...baseHookState(),
      loading: true
    });

    render(<KbFaqPage />);
    expect(screen.getByText("知识库列表同步中。")).toBeInTheDocument();
  });

  it("renders KB table and source tabs", () => {
    mockUseKB.mockReturnValue(baseHookState());

    render(<KbFaqPage />);
    expect(screen.getByRole("heading", { name: "知识库 FAQ", level: 2 })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "知识库 SOP" })).toHaveAttribute("href", "/kb/sop");
    expect(screen.getByRole("button", { name: /edit_doc_faq_001/i })).toBeInTheDocument();
  });

  it("supports create, edit and delete actions", async () => {
    const state = baseHookState();
    mockUseKB.mockReturnValue(state);

    render(<KbFaqPage />);

    fireEvent.click(screen.getByRole("button", { name: "kb_add_doc" }));
    fireEvent.change(screen.getByLabelText("kb_doc_id"), { target: { value: "doc_faq_002" } });
    fireEvent.change(screen.getByLabelText("kb_title"), { target: { value: "Parking entry FAQ" } });
    fireEvent.change(screen.getByLabelText("kb_content"), { target: { value: "Check camera and plate recognition." } });
    fireEvent.change(screen.getByLabelText("kb_tags"), { target: { value: "parking,camera" } });
    fireEvent.click(screen.getByRole("button", { name: "kb_submit" }));

    await waitFor(() =>
      expect(state.createDoc).toHaveBeenCalledWith({
        doc_id: "doc_faq_002",
        title: "Parking entry FAQ",
        content: "Check camera and plate recognition.",
        tags: ["parking", "camera"]
      })
    );

    fireEvent.click(screen.getByRole("button", { name: "edit_doc_faq_001" }));
    fireEvent.change(screen.getByLabelText("kb_title"), { target: { value: "Elevator reboot SOP" } });
    fireEvent.click(screen.getByRole("button", { name: "kb_submit" }));

    await waitFor(() =>
      expect(state.updateDoc).toHaveBeenCalledWith("doc_faq_001", {
        title: "Elevator reboot SOP",
        content: "Restart breaker and verify control panel.",
        tags: ["elevator", "safety"]
      })
    );

    fireEvent.click(screen.getByRole("button", { name: "delete_doc_faq_001" }));
    fireEvent.click(screen.getByRole("button", { name: "确认删除" }));

    await waitFor(() => expect(state.deleteDoc).toHaveBeenCalledWith("doc_faq_001"));
  });
});

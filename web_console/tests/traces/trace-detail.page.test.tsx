import { render, screen } from "@testing-library/react";
import { useParams } from "next/navigation";
import TraceDetailPage from "@/app/(dashboard)/traces/[traceId]/page";
import { useTraceDetail } from "@/lib/hooks/useTraceDetail";

vi.mock("next/navigation", () => ({
  useParams: vi.fn()
}));

vi.mock("@/lib/hooks/useTraceDetail", () => ({
  useTraceDetail: vi.fn()
}));

const mockUseParams = vi.mocked(useParams);
const mockUseTraceDetail = vi.mocked(useTraceDetail);

describe("TraceDetailPage", () => {
  beforeEach(() => {
    mockUseParams.mockReturnValue({ traceId: "trace-001" });
  });

  it("renders loading state", () => {
    mockUseTraceDetail.mockReturnValue({
      loading: true,
      error: null,
      data: null,
      refetch: vi.fn()
    });

    render(<TraceDetailPage />);
    expect(screen.getByText("Trace 详情同步中。")).toBeInTheDocument();
  });

  it("renders trace detail sections", () => {
    mockUseTraceDetail.mockReturnValue({
      loading: false,
      error: null,
      data: {
        trace_id: "trace-001",
        ticket_id: "TCK-001",
        session_id: "sess-001",
        workflow: "support-intake",
        channel: "wecom",
        provider: "openai-compatible",
        model: "qwen3.5-27b",
        prompt_key: "case_summary",
        prompt_version: "v2",
        request_id: "req-trace-001",
        token_usage: { total_tokens: 88 },
        retry_count: 1,
        success: true,
        error: null,
        fallback_used: false,
        degraded: false,
        degrade_reason: null,
        generation_type: "progress",
        route_decision: { intent: "repair", confidence: 0.93 },
        retrieved_docs: ["doc-001"],
        grounding_sources: [
          {
            source_id: "doc-001",
            source_type: "history_case",
            title: "电梯停运应急案例",
            snippet: "先断电复位并通知值班工程师",
            score: 0.91,
            rank: 1,
            reason: "rerank:title_match",
            retrieval_mode: "hybrid"
          }
        ],
        tool_calls: ["search_kb"],
        summary: "action recommendations generated",
        handoff: false,
        handoff_reason: null,
        error_only: false,
        latency_ms: 250,
        created_at: "2026-03-11T00:00:00+00:00",
        events: [
          {
            event_id: "trace_evt_1",
            event_type: "route_decision",
            timestamp: "2026-03-11T00:00:01+00:00",
            ticket_id: "TCK-001",
            session_id: "sess-001",
            payload: {
              intent: "repair",
              node: "router",
              from_node: "ingress",
              to_node: "dispatch",
              summary: "agent suggested dispatch"
            }
          }
        ]
      },
      refetch: vi.fn()
    });

    render(<TraceDetailPage />);
    expect(screen.getByText("Trace 详情")).toBeInTheDocument();
    expect(screen.getByText("Trace 路由")).toBeInTheDocument();
    expect(screen.getByText("工具调用")).toBeInTheDocument();
    expect(screen.getByText("Grounding 与摘要")).toBeInTheDocument();
    expect(screen.getByText("Trace 时间线")).toBeInTheDocument();
    expect(screen.getByText("Graph Execution Drilldown")).toBeInTheDocument();
    expect(screen.getByText(/ingress -> dispatch/)).toBeInTheDocument();
    expect(screen.getByText(/route_decision: agent suggested dispatch/)).toBeInTheDocument();
    expect(screen.getAllByText("search_kb").length).toBeGreaterThan(0);
  });

  it("renders error state", () => {
    mockUseTraceDetail.mockReturnValue({
      loading: false,
      error: "trace detail timeout",
      data: null,
      refetch: vi.fn()
    });

    render(<TraceDetailPage />);
    expect(screen.getByText("加载 Trace 详情失败。")).toBeInTheDocument();
    expect(screen.getByText("trace detail timeout")).toBeInTheDocument();
  });
});

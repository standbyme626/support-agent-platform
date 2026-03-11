import { fireEvent, render, screen } from "@testing-library/react";
import { TicketTimeline } from "@/components/tickets/ticket-timeline";
import type { TicketEventItem } from "@/lib/api/tickets";

function buildEvent(
  event_type: string,
  payload: Record<string, unknown>,
  created_at: string
): TicketEventItem {
  return {
    event_id: `evt-${event_type}`,
    ticket_id: "TCK-TIMELINE-1",
    event_type,
    actor_type: "trace",
    actor_id: "sess-1",
    payload,
    created_at,
    source: "trace",
    trace_id: "trace-1"
  };
}

describe("TicketTimeline", () => {
  it("renders empty state", () => {
    render(<TicketTimeline events={[]} />);
    expect(screen.getByText("暂无事件。")).toBeInTheDocument();
  });

  it("renders key observability events", () => {
    const events = [
      buildEvent(
        "ingress_normalized",
        { channel: "wecom", inbox: "wecom", session_id: "sess-1", idempotency_key: "mid-1" },
        "2026-03-11T01:00:00+00:00"
      ),
      buildEvent(
        "route_decision",
        { intent: "repair", confidence: 0.91, is_low_confidence: false, reason: "keyword_match" },
        "2026-03-11T01:00:02+00:00"
      ),
      buildEvent(
        "sla_evaluated",
        { matched_rule_id: "rule-repair-p2", used_fallback: false },
        "2026-03-11T01:00:03+00:00"
      ),
      buildEvent(
        "handoff_decision",
        { should_handoff: false, reason: "none", policy_version: "handoff_policy_v1" },
        "2026-03-11T01:00:04+00:00"
      )
    ];
    render(<TicketTimeline events={events} />);
    expect(screen.getByText("ingress_normalized")).toBeInTheDocument();
    expect(screen.getByText("route_decision")).toBeInTheDocument();
    expect(screen.getByText("sla_evaluated")).toBeInTheDocument();
    expect(screen.getByText("handoff_decision")).toBeInTheDocument();
    expect(screen.getAllByText("可观测")).toHaveLength(4);
  });

  it("shows hover summary for selected node", () => {
    const events = [
      buildEvent(
        "route_decision",
        { intent: "repair", confidence: 0.87, is_low_confidence: false, reason: "router_v1" },
        "2026-03-11T01:00:02+00:00"
      ),
      buildEvent(
        "handoff_decision",
        { should_handoff: true, reason: "high_risk", policy_version: "handoff_policy_v1" },
        "2026-03-11T01:00:03+00:00"
      )
    ];
    render(<TicketTimeline events={events} />);

    const routeNode = screen.getByRole("button", { name: "timeline-event-route_decision" });
    fireEvent.mouseEnter(routeNode);

    expect(screen.getByText(/route_decision:/)).toBeInTheDocument();
    expect(screen.getByText(/intent=repair/)).toBeInTheDocument();
    expect(screen.getByText(/confidence=0.87/)).toBeInTheDocument();
  });
});

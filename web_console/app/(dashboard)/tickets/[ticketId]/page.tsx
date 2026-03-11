"use client";

import { useParams } from "next/navigation";
import { TicketActionsPanel } from "@/components/tickets/ticket-actions-panel";
import { TicketDetailHeader } from "@/components/tickets/ticket-detail-header";
import { TicketSummaryCard } from "@/components/tickets/ticket-summary-card";
import { TicketTimeline } from "@/components/tickets/ticket-timeline";
import { EmptyState } from "@/components/shared/empty-state";
import { ErrorState } from "@/components/shared/error-state";
import { LoadingState } from "@/components/shared/loading-state";
import { useTicketDetail } from "@/lib/hooks/useTicketDetail";
import type { TicketActionPayload, TicketActionType } from "@/lib/api/tickets";

function toText(value: unknown) {
  if (value === null || value === undefined || value === "") {
    return "-";
  }
  return String(value);
}

export default function TicketDetailPage() {
  const params = useParams<{ ticketId: string }>();
  const ticketId = params?.ticketId;
  if (!ticketId) {
    return <ErrorState title="Invalid ticket id." message="Cannot resolve ticket from route." />;
  }

  const { loading, error, ticket, assist, similarCases, events, assignees, actionLoading, actionError, runAction, refetch } =
    useTicketDetail(ticketId);

  if (loading) {
    return <LoadingState title="Ticket detail is syncing." />;
  }

  if (error) {
    return (
      <ErrorState title="Failed to load ticket detail." message={error} onRetry={() => void refetch()} />
    );
  }

  if (!ticket) {
    return <EmptyState title="Ticket not found." message={`No ticket payload for ${ticketId}.`} />;
  }

  return (
    <section>
      <h2 className="section-title">Ticket Detail</h2>
      <TicketDetailHeader ticket={ticket} />
      <div className="detail-grid" style={{ marginTop: 12 }}>
        <div className="detail-col">
          <TicketSummaryCard ticket={ticket} assist={assist} />
          <article className="card" style={{ marginTop: 12 }}>
            <h3>Core Fields</h3>
            <ul style={{ marginTop: 10, marginBottom: 0, paddingLeft: 18 }}>
              <li>queue: {ticket.queue}</li>
              <li>assignee: {ticket.assignee ?? "-"}</li>
              <li>channel: {ticket.channel}</li>
              <li>handoff_state: {ticket.handoff_state}</li>
              <li>service_type: {toText(ticket.metadata?.service_type)}</li>
              <li>community_name: {toText(ticket.metadata?.community_name)}</li>
              <li>building: {toText(ticket.metadata?.building)}</li>
              <li>parking: {toText(ticket.metadata?.parking_lot)}</li>
              <li>approval_required: {toText(ticket.metadata?.approval_required)}</li>
              <li>risk_level: {ticket.risk_level}</li>
            </ul>
          </article>
        </div>

        <div className="detail-col">
          <TicketActionsPanel
            ticket={ticket}
            assignees={assignees}
            loadingAction={actionLoading}
            actionError={actionError}
            onAction={(action: TicketActionType, payload: TicketActionPayload) =>
              runAction(action, payload)
            }
          />
          <article className="card" style={{ marginTop: 12 }}>
            <h3>Event Timeline</h3>
            <TicketTimeline events={events} />
          </article>
        </div>

        <div className="detail-col">
          <article className="card">
            <h3>Recommended Actions</h3>
            {assist?.recommended_actions?.length ? (
              <ul className="list">
                {assist.recommended_actions.map((action, index) => (
                  <li className="list-item" key={`action-${index}`}>
                    <strong>{toText(action.title ?? action.action)}</strong>
                    <div style={{ color: "var(--muted)", fontSize: 13 }}>
                      {toText(action.description ?? action.reason)}
                    </div>
                  </li>
                ))}
              </ul>
            ) : (
              <p style={{ color: "var(--muted)" }}>No recommended actions available.</p>
            )}
          </article>
          <article className="card" style={{ marginTop: 12 }}>
            <h3>Similar Cases</h3>
            {similarCases.length ? (
              <ul className="list">
                {similarCases.map((item, index) => (
                  <li className="list-item" key={`${item.doc_id ?? "doc"}-${index}`}>
                    <strong>{item.title ?? "Untitled case"}</strong>
                    <div style={{ color: "var(--muted)", fontSize: 13 }}>
                      source={item.source_type ?? "unknown"} · score={item.score ?? "-"}
                    </div>
                  </li>
                ))}
              </ul>
            ) : (
              <p style={{ color: "var(--muted)" }}>No similar cases.</p>
            )}
          </article>
        </div>
      </div>
    </section>
  );
}

import type { TicketItem } from "@/lib/api/tickets";

export function TicketDetailHeader({ ticket }: { ticket: TicketItem }) {
  return (
    <header className="card">
      <h3 style={{ fontSize: 18, margin: 0 }}>{ticket.title}</h3>
      <div style={{ marginTop: 8, color: "var(--muted)" }}>
        {ticket.ticket_id} · {ticket.channel} · queue {ticket.queue}
      </div>
      <div style={{ marginTop: 10, display: "flex", gap: 8, flexWrap: "wrap" }}>
        <span className={`pill pill-${ticket.sla_state}`}>status {ticket.status}</span>
        <span className="pill pill-normal">priority {ticket.priority}</span>
        <span className="pill pill-normal">handoff {ticket.handoff_state}</span>
        <span className="pill pill-normal">risk {ticket.risk_level}</span>
      </div>
    </header>
  );
}

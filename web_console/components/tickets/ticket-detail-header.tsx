"use client";

import { useI18n } from "@/lib/i18n";
import type { TicketItem } from "@/lib/api/tickets";

export function TicketDetailHeader({ ticket }: { ticket: TicketItem }) {
  const { t } = useI18n();

  return (
    <header className="card">
      <div className="ops-card-title-row">
        <h3 style={{ fontSize: 18, margin: 0, color: "var(--text)" }}>{ticket.title}</h3>
        <span className="ops-chip">{ticket.ticket_id}</span>
      </div>
      <div style={{ marginTop: 8, color: "var(--muted)" }}>
        {ticket.channel} · {t("队列", "queue")} {ticket.queue}
      </div>
      <div style={{ marginTop: 10, display: "flex", gap: 8, flexWrap: "wrap" }}>
        <span className={`pill pill-${ticket.sla_state}`}>{t("状态", "status")} {ticket.status}</span>
        <span className="pill pill-normal">{t("优先级", "priority")} {ticket.priority}</span>
        <span className="pill pill-normal">{t("接管", "handoff")} {ticket.handoff_state}</span>
        <span className="pill pill-normal">{t("风险", "risk")} {ticket.risk_level}</span>
      </div>
    </header>
  );
}

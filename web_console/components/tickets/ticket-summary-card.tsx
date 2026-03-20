"use client";

import { useI18n } from "@/lib/i18n";
import type { TicketAssistResponse, TicketItem } from "@/lib/api/tickets";

function toInlineValue(raw: unknown) {
  if (raw === null || raw === undefined || raw === "") {
    return "-";
  }
  if (typeof raw === "string" || typeof raw === "number" || typeof raw === "boolean") {
    return String(raw);
  }
  try {
    const serialized = JSON.stringify(raw);
    return serialized.length > 120 ? `${serialized.slice(0, 117)}...` : serialized;
  } catch {
    return String(raw);
  }
}

function buildContextRows(ticket: TicketItem, t: (zh: string, en: string) => string) {
  const rows = [
    { key: "service_type", label: t("服务类型", "Service"), value: ticket.metadata?.service_type },
    { key: "community_name", label: t("小区", "Community"), value: ticket.metadata?.community_name },
    { key: "building", label: t("楼栋", "Building"), value: ticket.metadata?.building },
    { key: "parking_lot", label: t("停车位", "Parking Lot"), value: ticket.metadata?.parking_lot },
    { key: "approval_required", label: t("审批要求", "Approval Required"), value: ticket.metadata?.approval_required }
  ];
  return rows.filter((row) => row.value !== undefined && row.value !== null && row.value !== "");
}

export function TicketSummaryCard({
  ticket,
  assist
}: {
  ticket: TicketItem;
  assist: TicketAssistResponse | null;
}) {
  const { t } = useI18n();
  const contextRows = buildContextRows(ticket, t);
  const riskFlags = Array.isArray(assist?.risk_flags) ? assist.risk_flags : [];
  return (
    <article className="card">
      <div className="ops-card-title-row">
        <h3>{t("AI 摘要", "AI Summary")}</h3>
        <span className="ops-chip strong">{assist?.provider ?? "agent"}</span>
      </div>
      <p style={{ marginTop: 10, marginBottom: 0 }}>
        {assist?.summary || t("暂无摘要。", "No summary available yet.")}
      </p>
      <div style={{ marginTop: 12, color: "var(--muted)", fontSize: 13 }}>
        {t("最新消息", "Latest message")}: {ticket.latest_message}
      </div>
      <div style={{ marginTop: 10 }}>
        <strong>{t("风险标签", "Risk flags")}:</strong> {riskFlags.join(", ") || "-"}
      </div>
      {contextRows.length > 0 ? (
        <ul className="ops-inline-list" style={{ marginTop: 10, marginBottom: 0 }}>
          {contextRows.map((row) => (
            <li key={row.key}>
              <strong>{row.label}:</strong> {toInlineValue(row.value)}
            </li>
          ))}
        </ul>
      ) : null}
    </article>
  );
}

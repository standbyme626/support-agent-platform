"use client";

import { useI18n } from "@/lib/i18n";
import type { TicketAssistResponse, TicketItem } from "@/lib/api/tickets";

function renderMetadata(ticket: TicketItem) {
  const targetKeys = [
    "service_type",
    "community_name",
    "building",
    "parking_lot",
    "approval_required",
    "risk_level"
  ];

  return targetKeys
    .map((key) => {
      const raw = ticket.metadata?.[key];
      if (raw === undefined || raw === null || raw === "") {
        return null;
      }
      return (
        <li key={key}>
          <strong>{key}:</strong> {String(raw)}
        </li>
      );
    })
    .filter(Boolean);
}

export function TicketSummaryCard({
  ticket,
  assist
}: {
  ticket: TicketItem;
  assist: TicketAssistResponse | null;
}) {
  const { t } = useI18n();
  const metadataRows = renderMetadata(ticket);
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
        <strong>{t("风险标签", "Risk flags")}:</strong> {assist?.risk_flags?.join(", ") || "-"}
      </div>
      <div style={{ marginTop: 6, color: "var(--muted)", fontSize: 12 }}>
        {t("提示词版本", "Prompt version")}: {assist?.prompt_version ?? "-"}
      </div>
      {metadataRows.length > 0 ? (
        <ul className="ops-inline-list" style={{ marginTop: 10, marginBottom: 0 }}>{metadataRows}</ul>
      ) : null}
    </article>
  );
}

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
  const metadataRows = renderMetadata(ticket);
  return (
    <article className="card">
      <h3>AI Summary</h3>
      <p style={{ marginTop: 10, marginBottom: 0 }}>
        {assist?.summary || "No summary available yet."}
      </p>
      <div style={{ marginTop: 12, color: "var(--muted)", fontSize: 13 }}>
        Latest message: {ticket.latest_message}
      </div>
      <div style={{ marginTop: 10 }}>
        <strong>Risk flags:</strong> {assist?.risk_flags?.join(", ") || "-"}
      </div>
      {metadataRows.length > 0 ? (
        <ul style={{ marginTop: 10, marginBottom: 0, paddingLeft: 18 }}>{metadataRows}</ul>
      ) : null}
    </article>
  );
}

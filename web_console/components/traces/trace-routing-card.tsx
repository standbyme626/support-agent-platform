function toText(value: unknown) {
  if (value === null || value === undefined || value === "") {
    return "-";
  }
  if (typeof value === "string" || typeof value === "number" || typeof value === "boolean") {
    return String(value);
  }
  return JSON.stringify(value);
}

export function TraceRoutingCard({
  routeDecision,
  handoff,
  handoffReason,
  errorOnly
}: {
  routeDecision: Record<string, unknown>;
  handoff: boolean;
  handoffReason: string | null;
  errorOnly: boolean;
}) {
  const rows = Object.entries(routeDecision).slice(0, 8);
  return (
    <article className="card">
      <h3>Trace Routing</h3>
      <ul className="list" style={{ marginTop: 10 }}>
        <li className="list-item">
          <strong>handoff</strong>
          <div style={{ color: "var(--muted)", fontSize: 13 }}>
            {handoff ? "true" : "false"} · reason={handoffReason ?? "-"}
          </div>
        </li>
        <li className="list-item">
          <strong>error_only</strong>
          <div style={{ color: "var(--muted)", fontSize: 13 }}>{errorOnly ? "true" : "false"}</div>
        </li>
        {rows.length === 0 ? (
          <li className="list-item">
            <strong>route_decision</strong>
            <div style={{ color: "var(--muted)", fontSize: 13 }}>No route payload.</div>
          </li>
        ) : (
          rows.map(([key, value]) => (
            <li className="list-item" key={key}>
              <strong>{key}</strong>
              <div style={{ color: "var(--muted)", fontSize: 13 }}>{toText(value)}</div>
            </li>
          ))
        )}
      </ul>
    </article>
  );
}

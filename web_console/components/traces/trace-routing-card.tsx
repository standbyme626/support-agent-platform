"use client";

import { useI18n } from "@/lib/i18n";

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
  const { t } = useI18n();
  const rows = Object.entries(routeDecision).slice(0, 8);
  return (
    <article className="card">
      <h3>{t("Trace 路由", "Trace Routing")}</h3>
      <ul className="list" style={{ marginTop: 10 }}>
        <li className="list-item">
          <strong>{t("接管", "Handoff")}</strong>
          <div style={{ color: "var(--muted)", fontSize: 13 }}>
            {handoff ? "true" : "false"} · {t("原因", "Reason")}={handoffReason ?? "-"}
          </div>
        </li>
        <li className="list-item">
          <strong>{t("仅错误", "Error Only")}</strong>
          <div style={{ color: "var(--muted)", fontSize: 13 }}>{errorOnly ? "true" : "false"}</div>
        </li>
        {rows.length === 0 ? (
          <li className="list-item">
            <strong>{t("路由决策", "Route Decision")}</strong>
            <div style={{ color: "var(--muted)", fontSize: 13 }}>{t("暂无路由载荷。", "No route payload.")}</div>
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

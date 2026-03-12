"use client";

import { useI18n } from "@/lib/i18n";
import type { TraceDetailEvent } from "@/lib/api/traces";

function toDateTimeText(value: string | null, locale: string) {
  if (!value) {
    return "n/a";
  }
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }
  return parsed.toLocaleString(locale);
}

function payloadPreview(payload: Record<string, unknown>, emptyText: string) {
  const entries = Object.entries(payload).slice(0, 4);
  if (entries.length === 0) {
    return emptyText;
  }
  return entries.map(([key, value]) => `${key}=${String(value)}`).join(" · ");
}

export function TraceTimeline({ events }: { events: TraceDetailEvent[] }) {
  const { t, language } = useI18n();

  return (
    <article className="card">
      <h3>{t("Trace 时间线", "Trace Timeline")}</h3>
      {events.length === 0 ? (
        <p style={{ color: "var(--muted)", marginTop: 10 }}>{t("暂无 Trace 事件。", "No trace events recorded.")}</p>
      ) : (
        <ul className="ops-timeline" style={{ marginTop: 10 }}>
          {events.map((event) => (
            <li className={`ops-timeline-item ${event.event_type.includes("route") ? "is-observable" : ""}`} key={event.event_id}>
              <strong>{event.event_type}</strong>
              <div style={{ color: "var(--muted)", fontSize: 13 }}>
                {toDateTimeText(event.timestamp, language === "en" ? "en-US" : "zh-CN")} · ticket={event.ticket_id ?? "-"} ·{" "}
                session={event.session_id ?? "-"}
              </div>
              <div style={{ color: "var(--muted)", fontSize: 13, marginTop: 4 }}>
                {payloadPreview(event.payload, t("无载荷。", "No payload."))}
              </div>
            </li>
          ))}
        </ul>
      )}
    </article>
  );
}

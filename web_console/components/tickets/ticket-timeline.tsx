"use client";

import { useMemo, useState } from "react";
import type { TicketEventItem } from "@/lib/api/tickets";
import { useI18n } from "@/lib/i18n";

const OBSERVABILITY_EVENTS = new Set([
  "ingress_normalized",
  "route_decision",
  "sla_evaluated",
  "handoff_decision"
]);

const EVENT_SUMMARY_FIELDS: Record<string, string[]> = {
  ingress_normalized: ["channel", "inbox", "session_id", "idempotency_key"],
  route_decision: ["intent", "confidence", "is_low_confidence", "reason"],
  sla_evaluated: ["matched_rule_id", "matched_rule_path", "used_fallback", "resolution_due_at"],
  handoff_decision: ["should_handoff", "reason", "policy_version"]
};

const INLINE_TEXT_MAX = 180;

function formatTimestamp(value: string | null, locale: string) {
  if (!value) {
    return "n/a";
  }
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }
  return parsed.toLocaleString(locale, { hour12: false });
}

function truncateInlineText(value: string) {
  if (value.length <= INLINE_TEXT_MAX) {
    return value;
  }
  return `${value.slice(0, INLINE_TEXT_MAX - 1)}…`;
}

function toInlineValue(value: unknown): string {
  if (value === null || value === undefined || value === "") {
    return "-";
  }
  if (typeof value === "string" || typeof value === "number" || typeof value === "boolean") {
    return truncateInlineText(String(value));
  }
  if (Array.isArray(value)) {
    return truncateInlineText(value.map((item) => toInlineValue(item)).join(","));
  }
  return truncateInlineText(JSON.stringify(value));
}

function buildEventSummary(event: TicketEventItem, emptyText: string) {
  const payload = event.payload ?? {};
  const preferredFields = EVENT_SUMMARY_FIELDS[event.event_type] ?? [];
  const preferredSummary = preferredFields
    .filter((field) => payload[field] !== undefined)
    .map((field) => `${field}=${toInlineValue(payload[field])}`);
  if (preferredSummary.length > 0) {
    return preferredSummary.join(" · ");
  }

  const genericSummary = Object.entries(payload)
    .slice(0, 4)
    .map(([key, value]) => `${key}=${toInlineValue(value)}`);
  if (genericSummary.length > 0) {
    return genericSummary.join(" · ");
  }
  return emptyText;
}

function extractContextMessage(event: TicketEventItem) {
  const payload = event.payload ?? {};
  const candidates = ["message_text", "latest_message", "note", "resolution_note", "reason"];
  for (const key of candidates) {
    if (payload[key] !== undefined && payload[key] !== null && payload[key] !== "") {
      return `${key}=${toInlineValue(payload[key])}`;
    }
  }
  return null;
}

export function TicketTimeline({ events }: { events: TicketEventItem[] }) {
  const { t, language } = useI18n();
  const normalizedEvents = useMemo(
    () =>
      events.map((event, index) => ({
        ...event,
        event_id: event.event_id || `evt_fallback_${index}`
      })),
    [events]
  );
  const [activeEventId, setActiveEventId] = useState<string | null>(null);

  if (normalizedEvents.length === 0) {
    return <p style={{ color: "var(--muted)" }}>{t("暂无事件。", "No events yet.")}</p>;
  }

  const activeEvent =
    normalizedEvents.find((event) => event.event_id === activeEventId) ??
    normalizedEvents[normalizedEvents.length - 1];

  return (
    <div>
      <ul className="ops-timeline" style={{ marginTop: 10 }}>
        {normalizedEvents.map((event) => {
          const isObservabilityEvent = OBSERVABILITY_EVENTS.has(event.event_type);
          const summary = buildEventSummary(event, t("无载荷摘要。", "No payload summary."));
          const contextMessage = extractContextMessage(event);
          return (
            <li
              key={event.event_id}
              className={`ops-timeline-item ${isObservabilityEvent ? "is-observable" : ""}`}
            >
              <button
                type="button"
                onMouseEnter={() => setActiveEventId(event.event_id)}
                onFocus={() => setActiveEventId(event.event_id)}
                onMouseLeave={() => setActiveEventId(null)}
                onBlur={() => setActiveEventId(null)}
                title={summary}
                style={{
                  width: "100%",
                  textAlign: "left",
                  border: 0,
                  background: "transparent",
                  color: "inherit",
                  padding: 0,
                  cursor: "pointer"
                }}
                aria-label={`timeline-event-${event.event_type}`}
              >
                <div style={{ display: "flex", justifyContent: "space-between", gap: 8, alignItems: "center" }}>
                  <strong>{event.event_type}</strong>
                  {isObservabilityEvent ? (
                    <span className="ops-chip strong">
                      {t("可观测", "observable")}
                    </span>
                  ) : null}
                </div>
                <small>
                  actor={event.actor_id} · source={event.source ?? "ticket"} ·{" "}
                  trace={event.trace_id ?? "-"} ·{" "}
                  {formatTimestamp(event.created_at, language === "en" ? "en-US" : "zh-CN")}
                </small>
                {contextMessage ? (
                  <div style={{ marginTop: 4, color: "var(--muted)", fontSize: 12 }}>{contextMessage}</div>
                ) : null}
              </button>
            </li>
          );
        })}
      </ul>

      <div
        role="status"
        aria-live="polite"
        style={{
          marginTop: 10,
          border: "1px solid var(--border)",
          borderRadius: 10,
          padding: "8px 10px",
          background: "rgba(15, 111, 133, 0.06)"
        }}
      >
        <strong style={{ display: "block", fontSize: 12, color: "var(--muted)" }}>
          {t("悬停摘要", "Hover Summary")}
        </strong>
        <div style={{ marginTop: 4, fontSize: 13 }}>
          {activeEvent
            ? `${activeEvent.event_type}: ${buildEventSummary(activeEvent, t("无载荷摘要。", "No payload summary."))}`
            : t("悬停时间线节点查看摘要。", "Hover a timeline node.")}
        </div>
      </div>
    </div>
  );
}

"use client";

import { useMemo, useState } from "react";
import type { TicketEventItem } from "@/lib/api/tickets";

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

function formatTimestamp(value: string | null) {
  if (!value) {
    return "n/a";
  }
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }
  return parsed.toLocaleString("zh-CN", { hour12: false });
}

function toInlineValue(value: unknown): string {
  if (value === null || value === undefined || value === "") {
    return "-";
  }
  if (typeof value === "string" || typeof value === "number" || typeof value === "boolean") {
    return String(value);
  }
  if (Array.isArray(value)) {
    return value.map((item) => toInlineValue(item)).join(",");
  }
  return JSON.stringify(value);
}

function buildEventSummary(event: TicketEventItem) {
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
  return "No payload summary.";
}

export function TicketTimeline({ events }: { events: TicketEventItem[] }) {
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
    return <p style={{ color: "var(--muted)" }}>No events yet.</p>;
  }

  const activeEvent =
    normalizedEvents.find((event) => event.event_id === activeEventId) ??
    normalizedEvents[normalizedEvents.length - 1];

  return (
    <div>
      <ul className="list" style={{ marginTop: 10 }}>
        {normalizedEvents.map((event) => {
          const isObservabilityEvent = OBSERVABILITY_EVENTS.has(event.event_type);
          const summary = buildEventSummary(event);
          return (
            <li
              key={event.event_id}
              className="list-item"
              style={{ borderLeft: `3px solid ${isObservabilityEvent ? "var(--accent)" : "var(--border)"}` }}
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
                    <span
                      style={{
                        border: "1px solid var(--accent)",
                        color: "var(--accent)",
                        borderRadius: 999,
                        padding: "1px 8px",
                        fontSize: 11,
                        whiteSpace: "nowrap"
                      }}
                    >
                      observable
                    </span>
                  ) : null}
                </div>
                <small>
                  actor={event.actor_id} · source={event.source ?? "ticket"} · {formatTimestamp(event.created_at)}
                </small>
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
          background: "rgba(31, 111, 235, 0.06)"
        }}
      >
        <strong style={{ display: "block", fontSize: 12, color: "var(--muted)" }}>Hover Summary</strong>
        <div style={{ marginTop: 4, fontSize: 13 }}>
          {activeEvent ? `${activeEvent.event_type}: ${buildEventSummary(activeEvent)}` : "Hover a timeline node."}
        </div>
      </div>
    </div>
  );
}

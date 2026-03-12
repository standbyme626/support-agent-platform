"use client";

import type { ChannelEventItem } from "@/lib/api/channels";
import { useI18n } from "@/lib/i18n";

function toDateTimeText(value: string | null) {
  if (!value) {
    return "-";
  }
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }
  return parsed.toLocaleString();
}

function payloadSummary(payload: Record<string, unknown>) {
  const serialized = JSON.stringify(payload);
  if (serialized.length <= 120) {
    return serialized;
  }
  return `${serialized.slice(0, 117)}...`;
}

export function WebhookLogTable({ rows }: { rows: ChannelEventItem[] }) {
  const { t } = useI18n();

  return (
    <article className="card">
      <h3>{t("Webhook 事件流", "Webhook Event Stream")}</h3>
      {rows.length === 0 ? (
        <div className="hint" style={{ marginTop: 10 }}>
          {t("暂无近期渠道 Webhook 事件。", "No recent channel webhook events.")}
        </div>
      ) : (
        <div style={{ overflowX: "auto", marginTop: 10 }}>
          <table className="table">
            <thead>
              <tr>
                <th>{t("时间戳", "Timestamp")}</th>
                <th>{t("渠道", "Channel")}</th>
                <th>{t("事件", "Event")}</th>
                <th>{t("Trace", "Trace")}</th>
                <th>{t("载荷", "Payload")}</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={`${row.timestamp ?? "ts"}-${row.trace_id ?? "trace"}-${row.event_type}`}>
                  <td>{toDateTimeText(row.timestamp)}</td>
                  <td>{row.channel}</td>
                  <td>
                    <span className={`pill ${row.event_type.includes("error") ? "pill-breached" : "pill-normal"}`}>
                      {row.event_type}
                    </span>
                  </td>
                  <td>{row.trace_id ? <a href={`/traces/${encodeURIComponent(row.trace_id)}`}>{row.trace_id}</a> : "-"}</td>
                  <td>{payloadSummary(row.payload)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </article>
  );
}

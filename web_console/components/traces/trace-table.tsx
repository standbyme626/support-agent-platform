"use client";

import { buildTraceDetailUrl } from "@/lib/utils/routes";
import { useI18n } from "@/lib/i18n";
import type { TraceListItem } from "@/lib/api/traces";

function toText(value: string | null | undefined) {
  return value && value.length > 0 ? value : "-";
}

function toDateTimeText(value: string | null, locale: string) {
  if (!value) {
    return "-";
  }
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }
  return parsed.toLocaleString(locale);
}

export function TraceTable({
  rows,
  page,
  pageSize,
  total,
  onPageChange
}: {
  rows: TraceListItem[];
  page: number;
  pageSize: number;
  total: number;
  onPageChange: (nextPage: number) => void;
}) {
  const { t, language } = useI18n();
  const pageCount = Math.max(1, Math.ceil(total / pageSize));

  return (
    <section className="card">
      <h3>{t("Trace 列表", "Traces")}</h3>
      <div style={{ overflowX: "auto", marginTop: 10 }}>
        <table className="table">
          <thead>
            <tr>
              <th>{t("Trace", "Trace")}</th>
              <th>{t("工单", "Ticket")}</th>
              <th>{t("会话", "Session")}</th>
              <th>{t("工作流", "Workflow")}</th>
              <th>{t("渠道", "Channel")}</th>
              <th>{t("模型提供方", "Provider")}</th>
              <th>{t("路由", "Route")}</th>
              <th>{t("接管", "Handoff")}</th>
              <th>{t("延迟", "Latency")}</th>
              <th>{t("创建时间", "Created")}</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.trace_id}>
                <td>
                  <a href={buildTraceDetailUrl(row.trace_id)}>{row.trace_id}</a>
                </td>
                <td>{toText(row.ticket_id)}</td>
                <td>{toText(row.session_id)}</td>
                <td>{toText(row.workflow)}</td>
                <td>{toText(row.channel)}</td>
                <td>{toText(row.provider)}</td>
                <td>{toText(typeof row.route_decision.intent === "string" ? row.route_decision.intent : null)}</td>
                <td>{row.handoff ? t("是", "yes") : t("否", "no")}</td>
                <td>{row.latency_ms !== null ? `${row.latency_ms}ms` : "-"}</td>
                <td>{toDateTimeText(row.created_at, language === "en" ? "en-US" : "zh-CN")}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div
        style={{
          marginTop: 10,
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center"
        }}
      >
        <small>
          {t("页", "page")} {page}/{pageCount} · {t("总计", "total")} {total}
        </small>
        <div style={{ display: "flex", gap: 8 }}>
          <button
            onClick={() => onPageChange(Math.max(1, page - 1))}
            disabled={page <= 1}
            className="btn-ghost"
          >
            {t("上一页", "Prev")}
          </button>
          <button
            onClick={() => onPageChange(Math.min(pageCount, page + 1))}
            disabled={page >= pageCount}
            className="btn-ghost"
          >
            {t("下一页", "Next")}
          </button>
        </div>
      </div>
    </section>
  );
}

"use client";

import type { ChannelHealthItem } from "@/lib/api/channels";
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

function toErrorText(value: ChannelHealthItem["last_error"]) {
  if (!value) {
    return "-";
  }
  if (typeof value === "string") {
    return value;
  }
  const code = typeof value.code === "string" ? value.code : "";
  const message = typeof value.message === "string" ? value.message : "";
  if (code && message) {
    return `${code}: ${message}`;
  }
  if (code) {
    return code;
  }
  return JSON.stringify(value);
}

export function ChannelHealthCard({ rows }: { rows: ChannelHealthItem[] }) {
  const { t } = useI18n();

  return (
    <article className="card">
      <h3>{t("渠道健康", "Channel Health")}</h3>
      {rows.length === 0 ? (
        <div className="hint" style={{ marginTop: 10 }}>
          {t("暂无渠道健康数据。", "No channel health rows found.")}
        </div>
      ) : (
        <div style={{ overflowX: "auto", marginTop: 10 }}>
          <table className="table">
            <thead>
              <tr>
                <th>{t("渠道", "Channel")}</th>
                <th>{t("已连接", "Connected")}</th>
                <th>{t("最近事件", "Last Event")}</th>
                <th>{t("重试状态", "Retry State")}</th>
                <th>{t("最近错误", "Last Error")}</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.channel}>
                  <td>{row.channel}</td>
                  <td>{row.connected ? t("是", "Yes") : t("否", "No")}</td>
                  <td>{toDateTimeText(row.last_event_at)}</td>
                  <td>{row.retry_state}</td>
                  <td>{toErrorText(row.last_error)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </article>
  );
}

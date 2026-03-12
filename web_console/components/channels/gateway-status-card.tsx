"use client";

import type { OpenClawRoute, OpenClawStatus } from "@/lib/api/channels";
import { useI18n } from "@/lib/i18n";

export function GatewayStatusCard({
  status,
  routes
}: {
  status: OpenClawStatus | null;
  routes: OpenClawRoute[];
}) {
  const { t } = useI18n();

  if (!status) {
    return (
      <article className="card">
        <h3>{t("网关状态", "Gateway Status")}</h3>
        <div className="hint" style={{ marginTop: 10 }}>
          {t("未返回网关状态数据。", "No gateway status payload was returned.")}
        </div>
      </article>
    );
  }

  return (
    <article className="card">
      <h3>{t("网关状态", "Gateway Status")}</h3>
      <p className="hint" style={{ marginTop: 8 }}>
        {t("职责：ingress / session / routing", "Scope: ingress / session / routing")}
      </p>
      <ul className="list" style={{ marginTop: 10 }}>
        <li className="list-item">
          <div>
            <strong>{status.gateway}</strong>
          </div>
          <small>{t("环境", "environment")} {status.environment}</small>
        </li>
        <li className="list-item">
          <div>
            <strong>{t("会话绑定数", "Session Bindings")}</strong>
          </div>
          <small>{status.session_bindings}</small>
        </li>
        <li className="list-item">
          <div>
            <strong>{t("已注册路由", "Registered Routes")}</strong>
          </div>
          <small>{routes.length}</small>
        </li>
        <li className="list-item">
          <div>
            <strong>{t("网关日志", "Gateway Log")}</strong>
          </div>
          <small>{status.log_path}</small>
        </li>
      </ul>
      {routes.length > 0 ? (
        <div style={{ marginTop: 10, overflowX: "auto" }}>
          <table className="table ops-table-tight">
            <thead>
              <tr>
                <th>{t("Channel", "Channel")}</th>
                <th>{t("Mode", "Mode")}</th>
              </tr>
            </thead>
            <tbody>
              {routes.map((route) => (
                <tr key={`${route.channel}-${route.mode}`}>
                  <td>{route.channel}</td>
                  <td>{route.mode}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
    </article>
  );
}

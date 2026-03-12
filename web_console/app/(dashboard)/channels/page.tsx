"use client";

import { ChannelHealthCard } from "@/components/channels/channel-health-card";
import { GatewayStatusCard } from "@/components/channels/gateway-status-card";
import { WebhookLogTable } from "@/components/channels/webhook-log-table";
import { EmptyState } from "@/components/shared/empty-state";
import { ErrorState } from "@/components/shared/error-state";
import { LoadingState } from "@/components/shared/loading-state";
import { useI18n } from "@/lib/i18n";
import { useGatewayHealth } from "@/lib/hooks/useGatewayHealth";

export default function ChannelsPage() {
  const { t } = useI18n();
  const gateway = useGatewayHealth();

  if (gateway.loading) {
    return <LoadingState title={t("渠道与网关指标同步中。", "Channels and gateway metrics are syncing.")} />;
  }

  if (gateway.error) {
    return (
      <ErrorState
        title={t("加载渠道与网关指标失败。", "Failed to load channels and gateway metrics.")}
        message={gateway.error}
        onRetry={() => void gateway.refetch()}
      />
    );
  }

  const hasAnyData =
    gateway.status !== null ||
    gateway.routes.length > 0 ||
    gateway.channelHealth.length > 0 ||
    gateway.events.length > 0 ||
    gateway.signatures.length > 0 ||
    gateway.replays.length > 0 ||
    gateway.retries.length > 0 ||
    gateway.sessions.length > 0;

  if (!hasAnyData) {
    return (
      <EmptyState
        title={t("暂无渠道数据。", "No channels data.")}
        message={t("暂无渠道健康或网关事件数据。", "No channel health or gateway event data is available yet.")}
      />
    );
  }

  return (
    <section className="ops-page-stack">
      <div className="ops-card-title-row">
        <h2 className="section-title">{t("渠道 / 网关", "Channels / Gateway")}</h2>
        <button className="btn-ghost" onClick={() => void gateway.refetch()} aria-label="refresh_channels">
          {t("刷新", "Refresh")}
        </button>
      </div>
      <p className="ops-kicker">
        {t(
          "仅展示 OpenClaw ingress/session/routing 与 channel health，不承载 CRM/工单业务流程。",
          "OpenClaw boundary only: ingress/session/routing/channel health, not business CRM workflows."
        )}
      </p>
      <div className="grid two-col">
        <GatewayStatusCard status={gateway.status} routes={gateway.routes} />
        <ChannelHealthCard rows={gateway.channelHealth} />
      </div>
      <div className="grid two-col">
        <article className="card">
          <h3>{t("防重放命中", "Replay Guard")}</h3>
          <p className="hint" style={{ marginTop: 8 }}>
            {t("重复 webhook 不重复建单比例", "Duplicate webhook non-create ratio")}
          </p>
          <strong style={{ fontSize: 22 }}>{((1 - gateway.replayDuplicateRatio) * 100).toFixed(1)}%</strong>
        </article>
        <article className="card">
          <h3>{t("重试可观测", "Retry Observability")}</h3>
          <p className="hint" style={{ marginTop: 8 }}>
            {t("outbound 重试链路可观测率", "Outbound retry observability rate")}
          </p>
          <strong style={{ fontSize: 22 }}>{(gateway.retryObservabilityRate * 100).toFixed(1)}%</strong>
        </article>
      </div>

      <h2 className="section-title" style={{ marginTop: 20 }}>
        {t("签名状态", "Signature Status")}
      </h2>
      <article className="card">
        <div style={{ overflowX: "auto" }}>
          <table className="table">
            <thead>
              <tr>
                <th>{t("渠道", "Channel")}</th>
                <th>{t("已校验", "Checked")}</th>
                <th>{t("通过", "Valid")}</th>
                <th>{t("拒绝", "Rejected")}</th>
                <th>{t("最后错误码", "Last Error")}</th>
              </tr>
            </thead>
            <tbody>
              {gateway.signatures.length === 0 ? (
                <tr>
                  <td colSpan={5}>{t("暂无签名数据", "No signature data yet")}</td>
                </tr>
              ) : (
                gateway.signatures.map((row) => (
                  <tr key={row.channel}>
                    <td>{row.channel}</td>
                    <td>{row.checked}</td>
                    <td>{row.valid}</td>
                    <td>{row.rejected}</td>
                    <td>{row.last_error_code ?? "-"}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </article>

      <h2 className="section-title" style={{ marginTop: 20 }}>
        {t("近期 Webhook 事件", "Recent Webhook Events")}
      </h2>
      <WebhookLogTable rows={gateway.events} />

      <h2 className="section-title" style={{ marginTop: 20 }}>
        {t("重放与重试", "Replays and Retries")}
      </h2>
      <div className="grid two-col">
        <article className="card">
          <h3>{t("重放记录", "Replay Records")}</h3>
          <div style={{ overflowX: "auto", marginTop: 10 }}>
            <table className="table ops-table-tight">
              <thead>
                <tr>
                  <th>{t("渠道", "Channel")}</th>
                  <th>{t("Session", "Session")}</th>
                  <th>{t("幂等键", "Idempotency Key")}</th>
                  <th>{t("状态", "Status")}</th>
                </tr>
              </thead>
              <tbody>
                {gateway.replays.length === 0 ? (
                  <tr>
                    <td colSpan={4}>{t("暂无重放记录", "No replay records")}</td>
                  </tr>
                ) : (
                  gateway.replays.slice(0, 10).map((row) => (
                    <tr key={`${row.channel}-${row.session_id}-${row.idempotency_key ?? "none"}`}>
                      <td>{row.channel}</td>
                      <td>{row.session_id}</td>
                      <td>{row.idempotency_key ?? "-"}</td>
                      <td>{row.accepted ? t("accepted", "accepted") : t("duplicate", "duplicate")}</td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </article>
        <article className="card">
          <h3>{t("重试记录", "Retry Records")}</h3>
          <div style={{ overflowX: "auto", marginTop: 10 }}>
            <table className="table ops-table-tight">
              <thead>
                <tr>
                  <th>{t("事件", "Event")}</th>
                  <th>{t("渠道", "Channel")}</th>
                  <th>{t("attempt", "attempt")}</th>
                  <th>{t("分级", "Classification")}</th>
                </tr>
              </thead>
              <tbody>
                {gateway.retries.length === 0 ? (
                  <tr>
                    <td colSpan={4}>{t("暂无重试记录", "No retry records")}</td>
                  </tr>
                ) : (
                  gateway.retries.slice(0, 10).map((row, index) => (
                    <tr key={`${row.event_type}-${row.channel}-${row.attempt}-${index}`}>
                      <td>{row.event_type}</td>
                      <td>{row.channel}</td>
                      <td>{row.attempt}</td>
                      <td>{row.classification ?? "-"}</td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </article>
      </div>

      <h2 className="section-title" style={{ marginTop: 20 }}>
        {t("Sessions", "Sessions")}
      </h2>
      <article className="card">
        <div style={{ overflowX: "auto" }}>
          <table className="table ops-table-tight">
            <thead>
              <tr>
                <th>{t("session_id", "session_id")}</th>
                <th>{t("ticket_id", "ticket_id")}</th>
                <th>{t("channel", "channel")}</th>
                <th>{t("replay_count", "replay_count")}</th>
              </tr>
            </thead>
            <tbody>
              {gateway.sessions.length === 0 ? (
                <tr>
                  <td colSpan={4}>{t("暂无会话记录", "No session records")}</td>
                </tr>
              ) : (
                gateway.sessions.slice(0, 10).map((row) => (
                  <tr key={row.session_id}>
                    <td>{row.session_id}</td>
                    <td>{row.ticket_id ?? "-"}</td>
                    <td>{row.channel ?? "-"}</td>
                    <td>{row.replay_count}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </article>
    </section>
  );
}

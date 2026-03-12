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
    gateway.events.length > 0;

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

      <h2 className="section-title" style={{ marginTop: 20 }}>
        {t("近期 Webhook 事件", "Recent Webhook Events")}
      </h2>
      <WebhookLogTable rows={gateway.events} />
    </section>
  );
}

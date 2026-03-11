"use client";

import { ChannelHealthCard } from "@/components/channels/channel-health-card";
import { GatewayStatusCard } from "@/components/channels/gateway-status-card";
import { WebhookLogTable } from "@/components/channels/webhook-log-table";
import { EmptyState } from "@/components/shared/empty-state";
import { ErrorState } from "@/components/shared/error-state";
import { LoadingState } from "@/components/shared/loading-state";
import { useGatewayHealth } from "@/lib/hooks/useGatewayHealth";

export default function ChannelsPage() {
  const gateway = useGatewayHealth();

  if (gateway.loading) {
    return <LoadingState title="Channels and gateway metrics are syncing." />;
  }

  if (gateway.error) {
    return (
      <ErrorState title="Failed to load channels and gateway metrics." message={gateway.error} onRetry={() => void gateway.refetch()} />
    );
  }

  const hasAnyData =
    gateway.status !== null ||
    gateway.routes.length > 0 ||
    gateway.channelHealth.length > 0 ||
    gateway.events.length > 0;

  if (!hasAnyData) {
    return <EmptyState title="No channels data." message="No channel health or gateway event data is available yet." />;
  }

  return (
    <section>
      <h2 className="section-title">Channels / Gateway</h2>
      <div className="grid two-col">
        <GatewayStatusCard status={gateway.status} routes={gateway.routes} />
        <ChannelHealthCard rows={gateway.channelHealth} />
      </div>

      <h2 className="section-title" style={{ marginTop: 20 }}>
        Recent Webhook Events
      </h2>
      <WebhookLogTable rows={gateway.events} />
    </section>
  );
}

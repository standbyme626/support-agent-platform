"use client";

import { useGatewayHealth } from "@/lib/hooks/useGatewayHealth";
import { AssigneeWorkloadCard } from "@/components/queues/assignee-workload-card";
import { QueueSummaryCard } from "@/components/queues/queue-summary-card";
import { EmptyState } from "@/components/shared/empty-state";
import { ErrorState } from "@/components/shared/error-state";
import { LoadingState } from "@/components/shared/loading-state";
import { StatCard, type SlaSemanticState } from "@/components/shared/stat-card";
import { useDashboardRecentErrors } from "@/lib/hooks/useDashboardRecentErrors";
import { useDashboardSummary } from "@/lib/hooks/useDashboardSummary";
import { useI18n } from "@/lib/i18n";
import { useQueueSummary } from "@/lib/hooks/useQueueSummary";
import { buildTicketListUrl, buildTraceDetailUrl } from "@/lib/utils/routes";

function determineSlaState(warning: number, breached: number): SlaSemanticState {
  if (breached > 0) {
    return "breached";
  }
  if (warning > 0) {
    return "warning";
  }
  return "normal";
}

export default function DashboardPage() {
  const { t } = useI18n();
  const summary = useDashboardSummary();
  const recentErrors = useDashboardRecentErrors();
  const queueSummary = useQueueSummary();
  const gateway = useGatewayHealth();

  if (summary.loading || recentErrors.loading || queueSummary.loading) {
    return <LoadingState title={t("总览数据同步中。", "Dashboard is syncing.")} />;
  }

  if (summary.error) {
    return (
      <ErrorState
        title={t("加载总览摘要失败。", "Failed to load dashboard summary.")}
        message={summary.error}
        onRetry={() => void summary.refetch()}
      />
    );
  }

  if (recentErrors.error) {
    return (
      <ErrorState
        title={t("加载近期错误失败。", "Failed to load recent errors.")}
        message={recentErrors.error}
        onRetry={() => void recentErrors.refetch()}
      />
    );
  }

  if (queueSummary.error) {
    return (
      <ErrorState
        title={t("加载队列摘要失败。", "Failed to load queue summary.")}
        message={queueSummary.error}
        onRetry={() => void queueSummary.refetch()}
      />
    );
  }

  if (!summary.data) {
    return (
      <EmptyState
        title={t("暂无总览数据。", "No dashboard data.")}
        message={t("未收到摘要数据。", "No summary payload received.")}
      />
    );
  }

  const slaState = determineSlaState(summary.data.sla_warning_count, summary.data.sla_breached_count);
  const totalSlaRisk = summary.data.sla_warning_count + summary.data.sla_breached_count;
  const traceErrorCount = recentErrors.data.length;
  const channelConnected = gateway.channelHealth.filter((row) => row.connected).length;
  const channelTotal = gateway.channelHealth.length;
  const gatewayStateLabel = gateway.status ? gateway.status.gateway : t("未连接", "disconnected");
  const gatewayRouteCount = gateway.routes.length;

  return (
    <section className="ops-page-stack">
      <h2 className="section-title">{t("概览", "Overview")}</h2>
      <p className="ops-kicker">
        {t(
          "workflow-first，agent-assisted 运营工作台。聚合 SLA / Trace / Channel 风险并直达处理页面。",
          "Workflow-first, agent-assisted operations console with SLA / Trace / Channel risk pivots."
        )}
      </p>
      <div className="grid stats">
        <StatCard
          title={t("今日新建", "New Today")}
          value={summary.data.new_tickets_today}
          hint={t("最近 24 小时创建", "Created in the last 24h")}
          href={buildTicketListUrl({ created_from: "today" })}
        />
        <StatCard
          title={t("处理中", "In Progress")}
          value={summary.data.in_progress_count}
          hint={t("open + pending 工单", "open + pending tickets")}
          href={buildTicketListUrl({ status: "open" })}
        />
        <StatCard
          title={t("SLA 风险", "SLA Risk")}
          value={totalSlaRisk}
          hint={t("预警 + 超时", "warning + breached")}
          href={buildTicketListUrl({ sla_state: slaState })}
          state={slaState}
        />
        <StatCard
          title={t("已升级", "Escalated")}
          value={summary.data.escalated_count}
          hint={t("需要更高优先级处理", "tickets requiring higher priority")}
          href={buildTicketListUrl({ status: "escalated" })}
          state={summary.data.escalated_count > 0 ? "warning" : "normal"}
        />
        <StatCard
          title={t("待接管", "Handoff Pending")}
          value={summary.data.handoff_pending_count}
          hint={t("requested 或 accepted", "requested or accepted")}
          href={buildTicketListUrl({ handoff_state: "requested" })}
          state={summary.data.handoff_pending_count > 0 ? "warning" : "normal"}
        />
        <StatCard
          title={t("Trace 错误", "Trace Errors")}
          value={traceErrorCount}
          hint={t("最近错误事件", "Recent error events")}
          href="/traces?error_only=true"
          state={traceErrorCount > 0 ? "warning" : "normal"}
        />
      </div>

      <h2 className="section-title" style={{ marginTop: 20 }}>
        {t("SLA / Trace / Channel 状态块", "SLA / Trace / Channel Blocks")}
      </h2>
      <div className="grid two-col">
        <article className="card">
          <h3>{t("SLA 状态块", "SLA Status Block")}</h3>
          <ul className="list" style={{ marginTop: 10 }}>
            <li className="list-item">
              <div className="ops-card-title-row">
                <strong>{t("预警中", "Warning")}</strong>
                <span className={`pill ${summary.data.sla_warning_count > 0 ? "pill-warning" : "pill-normal"}`}>
                  {summary.data.sla_warning_count}
                </span>
              </div>
            </li>
            <li className="list-item">
              <div className="ops-card-title-row">
                <strong>{t("已超时", "Breached")}</strong>
                <span className={`pill ${summary.data.sla_breached_count > 0 ? "pill-breached" : "pill-normal"}`}>
                  {summary.data.sla_breached_count}
                </span>
              </div>
            </li>
            <li className="list-item">
              <a href={buildTicketListUrl({ sla_state: slaState })} className="ops-muted">
                {t("打开 SLA 风险列表", "Open SLA risk list")}
              </a>
            </li>
          </ul>
        </article>
        <article className="card">
          <h3>{t("近期 Trace 错误", "Recent Trace Errors")}</h3>
          {traceErrorCount === 0 ? (
            <div className="hint" style={{ marginTop: 8 }}>
              {t("暂无近期 Trace 错误。", "No recent trace errors.")}
            </div>
          ) : (
            <ul className="list">
              {recentErrors.data.slice(0, 5).map((item, index) => (
                <li className="list-item" key={`${item.trace_id ?? "trace"}-${index}`}>
                  <div>
                    <a href={item.trace_id ? buildTraceDetailUrl(item.trace_id) : "/traces"}>
                      {(item.event_type ?? "event").toString()}
                    </a>
                  </div>
                  <small>
                    trace={item.trace_id ?? "n/a"} ticket={item.ticket_id ?? "n/a"}
                  </small>
                </li>
              ))}
            </ul>
          )}
        </article>
        <article className="card">
          <h3>{t("Channel / Gateway 状态块", "Channel / Gateway Block")}</h3>
          {gateway.loading ? (
            <p className="hint" style={{ marginTop: 10 }}>
              {t("渠道指标同步中...", "Syncing channel metrics...")}
            </p>
          ) : gateway.error ? (
            <div className="hint" style={{ marginTop: 10 }}>
              {gateway.error}
              <div style={{ marginTop: 8 }}>
                <button className="btn-ghost" onClick={() => void gateway.refetch()}>
                  {t("重试", "Retry")}
                </button>
              </div>
            </div>
          ) : (
            <ul className="list" style={{ marginTop: 10 }}>
              <li className="list-item">
                <strong>{t("Gateway", "Gateway")}</strong>
                <div className="ops-muted" style={{ fontSize: 13 }}>
                  {gatewayStateLabel} · {t("路由", "routes")}={gatewayRouteCount}
                </div>
              </li>
              <li className="list-item">
                <strong>{t("Channel Health", "Channel Health")}</strong>
                <div className="ops-muted" style={{ fontSize: 13 }}>
                  {t("已连接", "connected")}={channelConnected}/{channelTotal}
                </div>
              </li>
              <li className="list-item">
                <a href="/channels" className="ops-muted">
                  {t("打开 Channels / Gateway 页面", "Open Channels / Gateway page")}
                </a>
              </li>
            </ul>
          )}
        </article>
        <QueueSummaryCard rows={queueSummary.data} />
        <AssigneeWorkloadCard rows={queueSummary.data} />
      </div>
    </section>
  );
}

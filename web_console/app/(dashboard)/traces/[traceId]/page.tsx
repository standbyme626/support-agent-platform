"use client";

import { useParams } from "next/navigation";
import { TraceGroundingCard } from "@/components/traces/trace-grounding-card";
import { TraceRoutingCard } from "@/components/traces/trace-routing-card";
import { TraceTimeline } from "@/components/traces/trace-timeline";
import { TraceToolCallsCard } from "@/components/traces/trace-tool-calls-card";
import { EmptyState } from "@/components/shared/empty-state";
import { ErrorState } from "@/components/shared/error-state";
import { LoadingState } from "@/components/shared/loading-state";
import { useI18n } from "@/lib/i18n";
import { useTraceDetail } from "@/lib/hooks/useTraceDetail";

function toText(value: string | null | undefined) {
  return value && value.length > 0 ? value : "-";
}

export default function TraceDetailPage() {
  const { t } = useI18n();
  const params = useParams<{ traceId: string }>();
  const traceId = params?.traceId;

  if (!traceId) {
    return (
      <ErrorState
        title={t("无效 Trace ID。", "Invalid trace id.")}
        message={t("无法从路由中解析 Trace。", "Cannot resolve trace from route.")}
      />
    );
  }

  const { loading, error, data, refetch } = useTraceDetail(traceId);

  if (loading) {
    return <LoadingState title={t("Trace 详情同步中。", "Trace detail is syncing.")} />;
  }

  if (error) {
    return <ErrorState title={t("加载 Trace 详情失败。", "Failed to load trace detail.")} message={error} onRetry={() => void refetch()} />;
  }

  if (!data) {
    return (
      <EmptyState
        title={t("未找到 Trace。", "Trace not found.")}
        message={t(`未找到 ${traceId} 的 Trace 数据。`, `No trace payload for ${traceId}.`)}
      />
    );
  }

  return (
    <section className="ops-page-stack">
      <h2 className="section-title">{t("Trace 详情", "Trace Detail")}</h2>
      <p className="ops-kicker">
        {t(
          "自实现 Trace 工作台：route decision / retrieved docs / tool calls / summary / handoff reason。",
          "Custom trace workspace: route decision / retrieved docs / tool calls / summary / handoff reason."
        )}
      </p>
      <article className="card">
        <h3>{data.trace_id}</h3>
        <div style={{ color: "var(--muted)", marginTop: 8 }}>
          {t("工单", "Ticket")}={toText(data.ticket_id)} · {t("会话", "Session")}={toText(data.session_id)}
        </div>
        <div style={{ color: "var(--muted)", marginTop: 4 }}>
          {t("工作流", "Workflow")}={toText(data.workflow)} · {t("渠道", "Channel")}={toText(data.channel)} ·{" "}
          {t("模型提供方", "Provider")}={toText(data.provider)}
        </div>
        <div style={{ color: "var(--muted)", marginTop: 4 }}>
          {t("模型", "Model")}={toText(data.model)} · {t("Prompt", "Prompt")}={toText(data.prompt_key)}@
          {toText(data.prompt_version)}
        </div>
        <div style={{ color: "var(--muted)", marginTop: 4 }}>
          {t("重试次数", "Retry")}={data.retry_count !== null ? data.retry_count : "-"} ·{" "}
          {t("成功", "Success")}={data.success === null ? "-" : data.success ? "true" : "false"} ·{" "}
          {t("错误", "Error")}={toText(data.error)}
        </div>
        <div style={{ color: "var(--muted)", marginTop: 4 }}>
          {t("延迟", "Latency")}={data.latency_ms !== null ? `${data.latency_ms}ms` : "-"} ·{" "}
          request_id={toText(data.request_id)} ·{" "}
          {t("创建时间", "Created At")}={toText(data.created_at)}
        </div>
        {data.degraded ? (
          <div style={{ marginTop: 8 }}>
            <span className="pill pill-breached">
              {t("已降级", "Degraded")} {toText(data.degrade_reason)}
            </span>
          </div>
        ) : null}
      </article>

      <div
        style={{
          marginTop: 12,
          display: "grid",
          gap: 12,
          gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))"
        }}
      >
        <TraceRoutingCard
          routeDecision={data.route_decision}
          handoff={data.handoff}
          handoffReason={data.handoff_reason}
          errorOnly={data.error_only}
        />
        <TraceToolCallsCard toolCalls={data.tool_calls} />
        <TraceGroundingCard
          retrievedDocs={data.retrieved_docs}
          groundingSources={data.grounding_sources}
          summary={data.summary}
        />
        <article className="card">
          <h3>{t("Handoff Reason", "Handoff Reason")}</h3>
          <div style={{ marginTop: 10, color: "var(--muted)", fontSize: 13 }}>
            {data.handoff ? t("已触发接管。", "Handoff was triggered.") : t("未触发接管。", "No handoff triggered.")}
          </div>
          <div style={{ marginTop: 6 }}>
            <strong>{toText(data.handoff_reason)}</strong>
          </div>
          <div style={{ marginTop: 10 }}>
            <span className={`pill ${data.error_only ? "pill-breached" : "pill-normal"}`}>
              error_only={data.error_only ? "true" : "false"}
            </span>
          </div>
        </article>
      </div>

      <div style={{ marginTop: 12 }}>
        <TraceTimeline events={data.events} />
      </div>
    </section>
  );
}

"use client";

import { TraceTable } from "@/components/traces/trace-table";
import { EmptyState } from "@/components/shared/empty-state";
import { ErrorState } from "@/components/shared/error-state";
import { LoadingState } from "@/components/shared/loading-state";
import { useI18n } from "@/lib/i18n";
import { useTraceList } from "@/lib/hooks/useTraceList";

export default function TracesPage() {
  const { t } = useI18n();
  const { loading, error, items, total, page, pageSize, filters, setPage, updateFilters, clearFilters, refetch } =
    useTraceList();

  if (loading) {
    return <LoadingState title={t("Trace 列表同步中。", "Trace list is syncing.")} />;
  }

  if (error) {
    return <ErrorState title={t("加载 Trace 失败。", "Failed to load traces.")} message={error} onRetry={() => void refetch()} />;
  }

  return (
    <section className="ops-page-stack">
      <div className="ops-card-title-row">
        <h2 className="section-title">{t("Trace 列表", "Trace List")}</h2>
        <button className="btn-ghost" onClick={() => void refetch()} aria-label="refresh_traces">
          {t("刷新", "Refresh")}
        </button>
      </div>
      <p className="ops-kicker">
        {t(
          "自定义可观测追踪页：按 trace/ticket/session/workflow 检索，不引入 helpdesk 业务模型。",
          "Custom observability trace list using admin-table patterns, without helpdesk business coupling."
        )}
      </p>
      <article className="card">
        <div className="ops-card-title-row">
          <h3>{t("筛选", "Filters")}</h3>
          <span className="ops-chip">{t("Admin Table", "Admin Table")}</span>
        </div>
        <div className="ops-filter-grid">
          <input
            className="ops-input"
            aria-label={t("Trace ID", "Trace ID")}
            placeholder={t("Trace ID", "Trace ID")}
            value={filters.trace_id ?? ""}
            onChange={(event) => updateFilters({ trace_id: event.target.value || undefined })}
          />
          <input
            className="ops-input"
            aria-label={t("工单 ID", "Ticket ID")}
            placeholder={t("工单 ID", "Ticket ID")}
            value={filters.ticket_id ?? ""}
            onChange={(event) => updateFilters({ ticket_id: event.target.value || undefined })}
          />
          <input
            className="ops-input"
            aria-label={t("会话 ID", "Session ID")}
            placeholder={t("会话 ID", "Session ID")}
            value={filters.session_id ?? ""}
            onChange={(event) => updateFilters({ session_id: event.target.value || undefined })}
          />
          <input
            className="ops-input"
            aria-label={t("工作流", "Workflow")}
            placeholder={t("工作流", "Workflow")}
            value={filters.workflow ?? ""}
            onChange={(event) => updateFilters({ workflow: event.target.value || undefined })}
          />
          <input
            className="ops-input"
            aria-label={t("渠道", "Channel")}
            placeholder={t("渠道", "Channel")}
            value={filters.channel ?? ""}
            onChange={(event) => updateFilters({ channel: event.target.value || undefined })}
          />
          <input
            className="ops-input"
            aria-label={t("模型提供方", "Provider")}
            placeholder={t("模型提供方", "Provider")}
            value={filters.provider ?? ""}
            onChange={(event) => updateFilters({ provider: event.target.value || undefined })}
          />
          <select
            className="ops-select"
            aria-label="error_only"
            value={filters.error_only ?? ""}
            onChange={(event) =>
              updateFilters({ error_only: (event.target.value || undefined) as "true" | "false" | undefined })
            }
          >
            <option value="">{t("仅错误：全部", "Error Only: All")}</option>
            <option value="true">{t("仅错误=true", "Error Only = true")}</option>
            <option value="false">{t("仅错误=false", "Error Only = false")}</option>
          </select>
          <select
            className="ops-select"
            aria-label="handoff"
            value={filters.handoff ?? ""}
            onChange={(event) =>
              updateFilters({ handoff: (event.target.value || undefined) as "true" | "false" | undefined })
            }
          >
            <option value="">{t("接管：全部", "Handoff: All")}</option>
            <option value="true">{t("接管=true", "Handoff = true")}</option>
            <option value="false">{t("接管=false", "Handoff = false")}</option>
          </select>
        </div>
        <button
          onClick={clearFilters}
          className="btn-ghost"
          style={{ marginTop: 10 }}
          aria-label="clear_trace_filters"
        >
          {t("清空筛选", "Clear Filters")}
        </button>
      </article>

      <div style={{ marginTop: 12 }}>
        {items.length === 0 ? (
          <EmptyState
            title={t("未匹配到 Trace。", "No traces matched.")}
            message={t("请调整筛选条件后重试。", "Adjust filters to find related traces.")}
          />
        ) : (
          <TraceTable rows={items} page={page} pageSize={pageSize} total={total} onPageChange={setPage} />
        )}
      </div>
    </section>
  );
}

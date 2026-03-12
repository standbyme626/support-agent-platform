"use client";

import { TicketFilters } from "@/components/tickets/ticket-filters";
import { TicketTable } from "@/components/tickets/ticket-table";
import { EmptyState } from "@/components/shared/empty-state";
import { ErrorState } from "@/components/shared/error-state";
import { LoadingState } from "@/components/shared/loading-state";
import { useI18n } from "@/lib/i18n";
import { useTickets } from "@/lib/hooks/useTickets";

export default function TicketsPage() {
  const { t } = useI18n();
  const {
    loading,
    error,
    items,
    total,
    assignees,
    page,
    pageSize,
    sortBy,
    sortOrder,
    filters,
    setPage,
    setSort,
    updateFilters,
    clearFilters,
    refetch
  } = useTickets();

  if (loading) {
    return <LoadingState title={t("工单列表同步中。", "Ticket list is syncing.")} />;
  }

  if (error) {
    return (
      <ErrorState
        title={t("加载工单失败。", "Failed to load tickets.")}
        message={error}
        onRetry={() => void refetch()}
      />
    );
  }

  return (
    <section className="ops-page-stack">
      <div className="ops-card-title-row">
        <h2 className="section-title">{t("工单收件箱", "Ticket Inbox")}</h2>
        <button className="btn-ghost" onClick={() => void refetch()} aria-label="refresh_tickets">
          {t("刷新", "Refresh")}
        </button>
      </div>
      <p className="ops-kicker">
        {t(
          "参考工单中心信息架构：在高密度列表中快速检索风险/SLA/接管状态并进入处置。",
          "Ticket-center density: triage by risk/SLA/handoff quickly and drill into detail."
        )}
      </p>
      <div className="ops-two-pane">
        <aside>
          {filters.queue ? <p className="hint">{t("队列筛选：", "Queue filter:")} {filters.queue}</p> : null}
          <TicketFilters
            value={filters}
            assignees={assignees}
            onChange={updateFilters}
            onClear={clearFilters}
          />
        </aside>
        <div>
          {items.length === 0 ? (
            <EmptyState
              title={t("未匹配到工单。", "No tickets matched.")}
              message={t("请调整筛选条件后重试。", "Adjust filters to find related cases.")}
            />
          ) : (
            <TicketTable
              items={items}
              page={page}
              pageSize={pageSize}
              total={total}
              sortBy={sortBy}
              sortOrder={sortOrder}
              onSort={setSort}
              onPageChange={setPage}
            />
          )}
        </div>
      </div>
    </section>
  );
}

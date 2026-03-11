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
    <section>
      <h2 className="section-title">{t("工单收件箱", "Ticket Inbox")}</h2>
      {filters.queue ? <p className="hint">{t("队列筛选：", "Queue filter:")} {filters.queue}</p> : null}
      <TicketFilters
        value={filters}
        assignees={assignees}
        onChange={updateFilters}
        onClear={clearFilters}
      />
      <div style={{ marginTop: 12 }}>
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
    </section>
  );
}

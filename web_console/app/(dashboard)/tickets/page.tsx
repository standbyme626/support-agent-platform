"use client";

import { TicketFilters } from "@/components/tickets/ticket-filters";
import { TicketTable } from "@/components/tickets/ticket-table";
import { EmptyState } from "@/components/shared/empty-state";
import { ErrorState } from "@/components/shared/error-state";
import { LoadingState } from "@/components/shared/loading-state";
import { useTickets } from "@/lib/hooks/useTickets";

export default function TicketsPage() {
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
    return <LoadingState title="Ticket list is syncing." />;
  }

  if (error) {
    return (
      <ErrorState
        title="Failed to load tickets."
        message={error}
        onRetry={() => void refetch()}
      />
    );
  }

  return (
    <section>
      <h2 className="section-title">Ticket Inbox</h2>
      {filters.queue ? <p className="hint">Queue filter: {filters.queue}</p> : null}
      <TicketFilters
        value={filters}
        assignees={assignees}
        onChange={updateFilters}
        onClear={clearFilters}
      />
      <div style={{ marginTop: 12 }}>
        {items.length === 0 ? (
          <EmptyState
            title="No tickets matched."
            message="Adjust filters to find related cases."
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

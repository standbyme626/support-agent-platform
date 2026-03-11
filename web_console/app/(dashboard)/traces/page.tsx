"use client";

import { TraceTable } from "@/components/traces/trace-table";
import { EmptyState } from "@/components/shared/empty-state";
import { ErrorState } from "@/components/shared/error-state";
import { LoadingState } from "@/components/shared/loading-state";
import { useTraceList } from "@/lib/hooks/useTraceList";

export default function TracesPage() {
  const { loading, error, items, total, page, pageSize, filters, setPage, updateFilters, clearFilters, refetch } =
    useTraceList();

  if (loading) {
    return <LoadingState title="Trace list is syncing." />;
  }

  if (error) {
    return <ErrorState title="Failed to load traces." message={error} onRetry={() => void refetch()} />;
  }

  return (
    <section>
      <h2 className="section-title">Trace List</h2>
      <article className="card">
        <h3>Filters</h3>
        <div
          style={{
            marginTop: 10,
            display: "grid",
            gap: 8,
            gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))"
          }}
        >
          <input
            aria-label="trace_id"
            placeholder="trace_id"
            value={filters.trace_id ?? ""}
            onChange={(event) => updateFilters({ trace_id: event.target.value || undefined })}
            style={{ height: 34, borderRadius: 8, border: "1px solid var(--border)", padding: "0 10px" }}
          />
          <input
            aria-label="ticket_id"
            placeholder="ticket_id"
            value={filters.ticket_id ?? ""}
            onChange={(event) => updateFilters({ ticket_id: event.target.value || undefined })}
            style={{ height: 34, borderRadius: 8, border: "1px solid var(--border)", padding: "0 10px" }}
          />
          <input
            aria-label="session_id"
            placeholder="session_id"
            value={filters.session_id ?? ""}
            onChange={(event) => updateFilters({ session_id: event.target.value || undefined })}
            style={{ height: 34, borderRadius: 8, border: "1px solid var(--border)", padding: "0 10px" }}
          />
          <input
            aria-label="workflow"
            placeholder="workflow"
            value={filters.workflow ?? ""}
            onChange={(event) => updateFilters({ workflow: event.target.value || undefined })}
            style={{ height: 34, borderRadius: 8, border: "1px solid var(--border)", padding: "0 10px" }}
          />
          <input
            aria-label="channel"
            placeholder="channel"
            value={filters.channel ?? ""}
            onChange={(event) => updateFilters({ channel: event.target.value || undefined })}
            style={{ height: 34, borderRadius: 8, border: "1px solid var(--border)", padding: "0 10px" }}
          />
          <input
            aria-label="provider"
            placeholder="provider"
            value={filters.provider ?? ""}
            onChange={(event) => updateFilters({ provider: event.target.value || undefined })}
            style={{ height: 34, borderRadius: 8, border: "1px solid var(--border)", padding: "0 10px" }}
          />
          <select
            aria-label="error_only"
            value={filters.error_only ?? ""}
            onChange={(event) =>
              updateFilters({ error_only: (event.target.value || undefined) as "true" | "false" | undefined })
            }
            style={{ height: 34, borderRadius: 8, border: "1px solid var(--border)", padding: "0 10px" }}
          >
            <option value="">error_only: all</option>
            <option value="true">error_only=true</option>
            <option value="false">error_only=false</option>
          </select>
          <select
            aria-label="handoff"
            value={filters.handoff ?? ""}
            onChange={(event) =>
              updateFilters({ handoff: (event.target.value || undefined) as "true" | "false" | undefined })
            }
            style={{ height: 34, borderRadius: 8, border: "1px solid var(--border)", padding: "0 10px" }}
          >
            <option value="">handoff: all</option>
            <option value="true">handoff=true</option>
            <option value="false">handoff=false</option>
          </select>
        </div>
        <button
          onClick={clearFilters}
          className="btn-ghost"
          style={{ marginTop: 10 }}
          aria-label="clear_trace_filters"
        >
          Clear Filters
        </button>
      </article>

      <div style={{ marginTop: 12 }}>
        {items.length === 0 ? (
          <EmptyState title="No traces matched." message="Adjust filters to find related traces." />
        ) : (
          <TraceTable rows={items} page={page} pageSize={pageSize} total={total} onPageChange={setPage} />
        )}
      </div>
    </section>
  );
}

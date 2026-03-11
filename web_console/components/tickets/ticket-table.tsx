import type { TicketItem } from "@/lib/api/tickets";

function SortButton({
  label,
  sortBy,
  activeSortBy,
  activeSortOrder,
  onSort
}: {
  label: string;
  sortBy: string;
  activeSortBy: string;
  activeSortOrder: "asc" | "desc";
  onSort: (sortBy: string, sortOrder: "asc" | "desc") => void;
}) {
  const isActive = activeSortBy === sortBy;
  return (
    <button
      onClick={() => onSort(sortBy, isActive && activeSortOrder === "asc" ? "desc" : "asc")}
      style={{
        border: "none",
        background: "transparent",
        color: "inherit",
        cursor: "pointer",
        fontWeight: 600,
        padding: 0
      }}
    >
      {label} {isActive ? (activeSortOrder === "asc" ? "↑" : "↓") : ""}
    </button>
  );
}

export function TicketTable({
  items,
  page,
  pageSize,
  total,
  sortBy,
  sortOrder,
  onSort,
  onPageChange
}: {
  items: TicketItem[];
  page: number;
  pageSize: number;
  total: number;
  sortBy: string;
  sortOrder: "asc" | "desc";
  onSort: (sortBy: string, sortOrder: "asc" | "desc") => void;
  onPageChange: (nextPage: number) => void;
}) {
  const pageCount = Math.max(1, Math.ceil(total / pageSize));

  return (
    <section className="card">
      <h3>Tickets</h3>
      <div style={{ overflowX: "auto", marginTop: 10 }}>
        <table className="table">
          <thead>
            <tr>
              <th>Ticket</th>
              <th>
                <SortButton
                  label="Priority"
                  sortBy="priority"
                  activeSortBy={sortBy}
                  activeSortOrder={sortOrder}
                  onSort={onSort}
                />
              </th>
              <th>
                <SortButton
                  label="Status"
                  sortBy="status"
                  activeSortBy={sortBy}
                  activeSortOrder={sortOrder}
                  onSort={onSort}
                />
              </th>
              <th>Queue</th>
              <th>Assignee</th>
              <th>Channel</th>
              <th>
                <SortButton
                  label="Created"
                  sortBy="created_at"
                  activeSortBy={sortBy}
                  activeSortOrder={sortOrder}
                  onSort={onSort}
                />
              </th>
            </tr>
          </thead>
          <tbody>
            {items.map((ticket) => (
              <tr key={ticket.ticket_id}>
                <td>
                  <a href={`/tickets/${ticket.ticket_id}`}>{ticket.title}</a>
                  <div style={{ color: "var(--muted)", fontSize: 12 }}>{ticket.latest_message}</div>
                </td>
                <td>{ticket.priority}</td>
                <td>
                  <span className={`pill pill-${ticket.sla_state}`}>{ticket.status}</span>
                </td>
                <td>{ticket.queue}</td>
                <td>{ticket.assignee ?? "-"}</td>
                <td>{ticket.channel}</td>
                <td>{ticket.created_at ? new Date(ticket.created_at).toLocaleString() : "-"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div
        style={{
          marginTop: 10,
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center"
        }}
      >
        <small>
          page {page}/{pageCount} · total {total}
        </small>
        <div style={{ display: "flex", gap: 8 }}>
          <button
            onClick={() => onPageChange(Math.max(1, page - 1))}
            disabled={page <= 1}
            className="btn-ghost"
          >
            Prev
          </button>
          <button
            onClick={() => onPageChange(Math.min(pageCount, page + 1))}
            disabled={page >= pageCount}
            className="btn-ghost"
          >
            Next
          </button>
        </div>
      </div>
    </section>
  );
}

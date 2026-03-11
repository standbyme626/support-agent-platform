"use client";

import { useI18n } from "@/lib/i18n";
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
  const { t } = useI18n();
  const pageCount = Math.max(1, Math.ceil(total / pageSize));

  return (
    <section className="card">
      <h3>{t("工单列表", "Tickets")}</h3>
      <div style={{ overflowX: "auto", marginTop: 10 }}>
        <table className="table">
          <thead>
            <tr>
              <th>{t("工单", "Ticket")}</th>
              <th>
                <SortButton
                  label={t("优先级", "Priority")}
                  sortBy="priority"
                  activeSortBy={sortBy}
                  activeSortOrder={sortOrder}
                  onSort={onSort}
                />
              </th>
              <th>
                <SortButton
                  label={t("状态", "Status")}
                  sortBy="status"
                  activeSortBy={sortBy}
                  activeSortOrder={sortOrder}
                  onSort={onSort}
                />
              </th>
              <th>{t("队列", "Queue")}</th>
              <th>{t("处理人", "Assignee")}</th>
              <th>{t("渠道", "Channel")}</th>
              <th>
                <SortButton
                  label={t("创建时间", "Created")}
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
          {t("页", "page")} {page}/{pageCount} · {t("总计", "total")} {total}
        </small>
        <div style={{ display: "flex", gap: 8 }}>
          <button
            onClick={() => onPageChange(Math.max(1, page - 1))}
            disabled={page <= 1}
            className="btn-ghost"
          >
            {t("上一页", "Prev")}
          </button>
          <button
            onClick={() => onPageChange(Math.min(pageCount, page + 1))}
            disabled={page >= pageCount}
            className="btn-ghost"
          >
            {t("下一页", "Next")}
          </button>
        </div>
      </div>
    </section>
  );
}

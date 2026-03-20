"use client";

import { useI18n } from "@/lib/i18n";
import type { TicketItem } from "@/lib/api/tickets";

const MESSAGE_PREVIEW_MAX_CHARS = 180;

function buildMessagePreview(message: string | null | undefined) {
  const normalized = String(message ?? "")
    .replace(/\s+/g, " ")
    .trim();
  if (!normalized) {
    return "-";
  }
  if (normalized.length <= MESSAGE_PREVIEW_MAX_CHARS) {
    return normalized;
  }
  return `${normalized.slice(0, MESSAGE_PREVIEW_MAX_CHARS - 3)}...`;
}

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
      <div className="ops-card-title-row">
        <h3>{t("工单列表", "Tickets")}</h3>
        <span className="ops-chip strong">
          {t("总计", "total")} {total}
        </span>
      </div>
      <div style={{ overflowX: "auto", marginTop: 10 }}>
        <table className="table ops-table-tight">
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
              <th>{t("服务类型", "Service Type")}</th>
              <th>{t("小区", "Community")}</th>
              <th>{t("楼栋", "Building")}</th>
              <th>{t("停车位", "Parking Lot")}</th>
              <th>{t("审批", "Approval")}</th>
              <th>{t("接管", "Handoff")}</th>
              <th>{t("风险", "Risk")}</th>
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
            {items.map((ticket) => {
              const latestMessagePreview = buildMessagePreview(ticket.latest_message);
              return (
                <tr key={ticket.ticket_id}>
                  <td>
                    <div className="ops-ticket-row-title">
                      <a href={`/tickets/${ticket.ticket_id}`}>{ticket.title}</a>
                      <span className="ops-chip">{ticket.ticket_id}</span>
                    </div>
                    <div className="ops-ticket-row-meta" title={latestMessagePreview === "-" ? undefined : ticket.latest_message}>
                      {latestMessagePreview}
                    </div>
                  </td>
                  <td>{ticket.priority}</td>
                  <td>
                    <span className={`pill pill-${ticket.sla_state}`}>{ticket.status}</span>{" "}
                    <span className={`pill pill-${ticket.sla_state}`}>SLA:{ticket.sla_state}</span>
                  </td>
                  <td>{ticket.queue}</td>
                  <td>{ticket.assignee ?? "-"}</td>
                  <td>{ticket.channel}</td>
                  <td>{String(ticket.metadata?.service_type ?? "-")}</td>
                  <td>{String(ticket.metadata?.community_name ?? "-")}</td>
                  <td>{String(ticket.metadata?.building ?? "-")}</td>
                  <td>{String(ticket.metadata?.parking_lot ?? "-")}</td>
                  <td>{String(ticket.metadata?.approval_required ?? "-")}</td>
                  <td>{ticket.handoff_state}</td>
                  <td>{ticket.risk_level}</td>
                  <td>{ticket.created_at ? new Date(ticket.created_at).toLocaleString() : "-"}</td>
                </tr>
              );
            })}
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

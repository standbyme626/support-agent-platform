"use client";

import { useParams } from "next/navigation";
import { TicketActionsPanel } from "@/components/tickets/ticket-actions-panel";
import { TicketDetailHeader } from "@/components/tickets/ticket-detail-header";
import { TicketSummaryCard } from "@/components/tickets/ticket-summary-card";
import { TicketTimeline } from "@/components/tickets/ticket-timeline";
import { EmptyState } from "@/components/shared/empty-state";
import { ErrorState } from "@/components/shared/error-state";
import { LoadingState } from "@/components/shared/loading-state";
import { useTicketDetail } from "@/lib/hooks/useTicketDetail";
import { useI18n } from "@/lib/i18n";
import type { TicketActionPayload, TicketActionType } from "@/lib/api/tickets";

function toText(value: unknown) {
  if (value === null || value === undefined || value === "") {
    return "-";
  }
  return String(value);
}

export default function TicketDetailPage() {
  const { t } = useI18n();
  const params = useParams<{ ticketId: string }>();
  const ticketId = params?.ticketId;
  if (!ticketId) {
    return (
      <ErrorState
        title={t("无效工单 ID。", "Invalid ticket id.")}
        message={t("无法从路由中解析工单。", "Cannot resolve ticket from route.")}
      />
    );
  }

  const { loading, error, ticket, assist, similarCases, events, assignees, actionLoading, actionError, runAction, refetch } =
    useTicketDetail(ticketId);

  if (loading) {
    return <LoadingState title={t("工单详情同步中。", "Ticket detail is syncing.")} />;
  }

  if (error) {
    return (
      <ErrorState title={t("加载工单详情失败。", "Failed to load ticket detail.")} message={error} onRetry={() => void refetch()} />
    );
  }

  if (!ticket) {
    return (
      <EmptyState
        title={t("未找到工单。", "Ticket not found.")}
        message={t(`未找到 ${ticketId} 的工单数据。`, `No ticket payload for ${ticketId}.`)}
      />
    );
  }

  return (
    <section>
      <h2 className="section-title">{t("工单详情", "Ticket Detail")}</h2>
      <TicketDetailHeader ticket={ticket} />
      <div className="detail-grid" style={{ marginTop: 12 }}>
        <div className="detail-col">
          <TicketSummaryCard ticket={ticket} assist={assist} />
          <article className="card" style={{ marginTop: 12 }}>
            <h3>{t("核心字段", "Core Fields")}</h3>
            <ul style={{ marginTop: 10, marginBottom: 0, paddingLeft: 18 }}>
              <li>{t("队列", "Queue")}: {ticket.queue}</li>
              <li>{t("处理人", "Assignee")}: {ticket.assignee ?? "-"}</li>
              <li>{t("渠道", "Channel")}: {ticket.channel}</li>
              <li>{t("接管状态", "Handoff State")}: {ticket.handoff_state}</li>
              <li>{t("服务类型", "Service Type")}: {toText(ticket.metadata?.service_type)}</li>
              <li>{t("小区", "Community Name")}: {toText(ticket.metadata?.community_name)}</li>
              <li>{t("楼栋", "Building")}: {toText(ticket.metadata?.building)}</li>
              <li>{t("停车位", "Parking Lot")}: {toText(ticket.metadata?.parking_lot)}</li>
              <li>{t("是否需审批", "Approval Required")}: {toText(ticket.metadata?.approval_required)}</li>
              <li>{t("风险等级", "Risk Level")}: {ticket.risk_level}</li>
            </ul>
          </article>
        </div>

        <div className="detail-col">
          <TicketActionsPanel
            ticket={ticket}
            assignees={assignees}
            loadingAction={actionLoading}
            actionError={actionError}
            onAction={(action: TicketActionType, payload: TicketActionPayload) =>
              runAction(action, payload)
            }
          />
          <article className="card" style={{ marginTop: 12 }}>
            <h3>{t("事件时间线", "Event Timeline")}</h3>
            <TicketTimeline events={events} />
          </article>
        </div>

        <div className="detail-col">
          <article className="card">
            <h3>{t("推荐动作", "Recommended Actions")}</h3>
            {assist?.recommended_actions?.length ? (
              <ul className="list">
                {assist.recommended_actions.map((action, index) => (
                  <li className="list-item" key={`action-${index}`}>
                    <strong>{toText(action.title ?? action.action)}</strong>
                    <div style={{ color: "var(--muted)", fontSize: 13 }}>
                      {toText(action.description ?? action.reason)}
                    </div>
                  </li>
                ))}
              </ul>
            ) : (
              <p style={{ color: "var(--muted)" }}>{t("暂无推荐动作。", "No recommended actions available.")}</p>
            )}
          </article>
          <article className="card" style={{ marginTop: 12 }}>
            <h3>{t("相似案例", "Similar Cases")}</h3>
            {similarCases.length ? (
              <ul className="list">
                {similarCases.map((item, index) => (
                  <li className="list-item" key={`${item.doc_id ?? "doc"}-${index}`}>
                    <strong>{item.title ?? t("未命名案例", "Untitled case")}</strong>
                    <div style={{ color: "var(--muted)", fontSize: 13 }}>
                      {t("来源", "Source")}={item.source_type ?? t("未知", "Unknown")} · {t("评分", "Score")}=
                      {item.score ?? "-"}
                    </div>
                  </li>
                ))}
              </ul>
            ) : (
              <p style={{ color: "var(--muted)" }}>{t("暂无相似案例。", "No similar cases.")}</p>
            )}
          </article>
        </div>
      </div>
    </section>
  );
}

"use client";

import { type FormEvent, useState } from "react";
import { useParams } from "next/navigation";
import { PendingApprovalList } from "@/components/hitl/pending-approval-list";
import { TicketActionsPanel, type TicketActionDraft } from "@/components/tickets/ticket-actions-panel";
import { TicketDetailHeader } from "@/components/tickets/ticket-detail-header";
import { TicketSummaryCard } from "@/components/tickets/ticket-summary-card";
import { TicketTimeline } from "@/components/tickets/ticket-timeline";
import { EmptyState } from "@/components/shared/empty-state";
import { ErrorState } from "@/components/shared/error-state";
import { LoadingState } from "@/components/shared/loading-state";
import { useTicketDetail } from "@/lib/hooks/useTicketDetail";
import { useTicketPendingActions } from "@/lib/hooks/useTicketPendingActions";
import { useI18n } from "@/lib/i18n";
import { getTicketSessionId, type TicketActionPayload, type TicketActionType } from "@/lib/api/tickets";

function toText(value: unknown) {
  if (value === null || value === undefined || value === "") {
    return "-";
  }
  return String(value);
}

function toBriefJson(value: unknown) {
  if (value === null || value === undefined) {
    return "-";
  }
  if (typeof value === "string" || typeof value === "number" || typeof value === "boolean") {
    return String(value);
  }
  try {
    const serialized = JSON.stringify(value);
    return serialized.length > 140 ? `${serialized.slice(0, 137)}...` : serialized;
  } catch {
    return String(value);
  }
}

function recommendationLabel(action: Record<string, unknown>) {
  return String(action.title ?? action.action ?? "recommendation");
}

function recommendationDescription(action: Record<string, unknown>) {
  return String(action.description ?? action.reason ?? "");
}

export default function TicketDetailPage() {
  const { t } = useI18n();
  const params = useParams<{ ticketId: string }>();
  const ticketId = params?.ticketId;
  const [copilotQueryText, setCopilotQueryText] = useState("");
  const [investigationQuestion, setInvestigationQuestion] = useState("");
  const [sessionEndReason, setSessionEndReason] = useState("");
  const [actionDraft, setActionDraft] = useState<TicketActionDraft | null>(null);

  if (!ticketId) {
    return (
      <ErrorState
        title={t("无效工单 ID。", "Invalid ticket id.")}
        message={t("无法从路由中解析工单。", "Cannot resolve ticket from route.")}
      />
    );
  }

  const {
    loading,
    error,
    ticket,
    assist,
    copilot,
    operatorCopilot,
    dispatchCopilot,
    copilotLoading,
    copilotError,
    investigation,
    investigationLoading,
    investigationError,
    sessionEnd,
    sessionEndLoading,
    sessionEndError,
    groundingSources,
    similarCases,
    events,
    assignees,
    actionLoading,
    actionError,
    runAction,
    queryCopilot,
    runInvestigation,
    runSessionEnd,
    refetch
  } = useTicketDetail(ticketId);
  const pendingApprovals = useTicketPendingActions(ticketId);

  if (loading || pendingApprovals.loading) {
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

  const lastHandoffEvent = [...events].reverse().find((item) => item.event_type.includes("handoff"));
  const sessionId = getTicketSessionId(ticket);
  const metadataEntries = Object.entries(ticket.metadata ?? {})
    .filter(([, value]) => value !== null && value !== undefined && value !== "")
    .sort(([left], [right]) => left.localeCompare(right));
  const approvalCounts = {
    pending: pendingApprovals.items.filter((item) => item.status === "pending_approval").length,
    approved: pendingApprovals.items.filter((item) => item.status === "approved").length,
    rejected: pendingApprovals.items.filter((item) => item.status === "rejected").length,
    timeout: pendingApprovals.items.filter((item) => item.status === "timeout").length
  };

  async function submitCopilotQuery(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!copilotQueryText.trim()) {
      return;
    }
    try {
      await queryCopilot(copilotQueryText);
    } catch {
      // Error state is surfaced through copilotError.
    }
  }

  async function submitInvestigation() {
    try {
      await runInvestigation(investigationQuestion, ticket.assignee ?? undefined);
    } catch {
      // Error state is surfaced through investigationError.
    }
  }

  async function submitSessionEnd() {
    if (!sessionId) {
      return;
    }
    try {
      await runSessionEnd(sessionEndReason, ticket.assignee ?? undefined);
    } catch {
      // Error state is surfaced through sessionEndError.
    }
  }

  return (
    <section className="ops-page-stack">
      <h2 className="section-title">{t("工单详情", "Ticket Detail")}</h2>
      <p className="ops-kicker">
        {t(
          "四区工作台：主视图、AI助手区、人工动作区、审批恢复区，同步同一 ticket/trace 主线。",
          "Four-zone workspace: main view, AI assistant, manual actions, and approval recovery on one ticket/trace line."
        )}
      </p>
      <TicketDetailHeader ticket={ticket} />

      <div className="detail-grid" style={{ marginTop: 12 }}>
        <div className="detail-col">
          <p className="ops-kicker">{t("主视图区", "Main View")}</p>
          <article className="card">
            <h3>{t("事件时间线", "Event Timeline")}</h3>
            <TicketTimeline events={events} />
            <h4 style={{ marginTop: 12, marginBottom: 6, fontSize: 13 }}>
              {t("来源消息 / 上下文", "Source Messages / Context")}
            </h4>
            <ul className="list">
              <li className="list-item">
                <small>{t("当前消息", "Current message")}: {ticket.latest_message || "-"}</small>
              </li>
              {(assist?.latest_messages ?? []).slice(0, 3).map((line, index) => (
                <li className="list-item" key={`source-msg-${index}`}>
                  <small>{line}</small>
                </li>
              ))}
            </ul>
          </article>
          <article className="card" style={{ marginTop: 12 }}>
            <h3>{t("核心字段", "Core Fields")}</h3>
            <ul className="ops-inline-list" style={{ marginTop: 10 }}>
              <li>{t("队列", "Queue")}: {ticket.queue}</li>
              <li>{t("处理人", "Assignee")}: {ticket.assignee ?? "-"}</li>
              <li>{t("渠道", "Channel")}: {ticket.channel}</li>
              <li>{t("接管状态", "Handoff State")}: {ticket.handoff_state}</li>
              <li>{t("风险等级", "Risk Level")}: {ticket.risk_level}</li>
              <li>{t("优先级", "Priority")}: {ticket.priority}</li>
              <li>{t("状态", "Status")}: {ticket.status}</li>
              <li>
                {t("最新接管事件", "Latest handoff event")}:{" "}
                {lastHandoffEvent ? `${lastHandoffEvent.event_type} · ${toText(lastHandoffEvent.created_at)}` : t("无", "none")}
              </li>
              <li>{t("接管载荷", "Handoff payload")}: {lastHandoffEvent ? toBriefJson(lastHandoffEvent.payload) : "-"}</li>
            </ul>
          </article>
          <article className="card" style={{ marginTop: 12 }}>
            <h3>{t("定制字段", "Custom Fields")}</h3>
            {metadataEntries.length > 0 ? (
              <ul className="ops-inline-list" style={{ marginTop: 10 }}>
                {metadataEntries.map(([key, value]) => (
                  <li key={key}>
                    <strong>{key}</strong>: {toText(value)}
                  </li>
                ))}
              </ul>
            ) : (
              <p style={{ color: "var(--muted)" }}>{t("暂无定制字段。", "No custom fields.")}</p>
            )}
          </article>
        </div>

        <div className="detail-col">
          <p className="ops-kicker">{t("AI 助手区", "AI Assistant")}</p>
          <TicketSummaryCard ticket={ticket} assist={assist} />
          <article className="card" style={{ marginTop: 12 }}>
            <h3>{t("Grounding", "Grounding")}</h3>
            <ul className="ops-inline-list" style={{ marginTop: 10 }}>
              <li>{t("服务类型", "Service Type")}: {toText(ticket.metadata?.service_type)}</li>
              <li>{t("小区", "Community Name")}: {toText(ticket.metadata?.community_name)}</li>
              <li>{t("楼栋", "Building")}: {toText(ticket.metadata?.building)}</li>
              <li>{t("停车位", "Parking Lot")}: {toText(ticket.metadata?.parking_lot)}</li>
              <li>{t("审批要求", "Approval Required")}: {toText(ticket.metadata?.approval_required)}</li>
            </ul>
            {groundingSources.length ? (
              <ul className="list" style={{ marginTop: 10 }}>
                {groundingSources.map((item, index) => (
                  <li className="list-item" key={`${item.source_id ?? "source"}-${index}`}>
                    <strong>{item.title ?? t("未命名来源", "Untitled source")}</strong>
                    <div style={{ color: "var(--muted)", fontSize: 13 }}>
                      {t("来源", "Source")}={item.source_type ?? "-"} · {t("排名", "Rank")}={item.rank ?? "-"} ·{" "}
                      {t("分数", "Score")}={item.score ?? "-"}
                    </div>
                  </li>
                ))}
              </ul>
            ) : null}
          </article>
          <article className="card" style={{ marginTop: 12 }}>
            <h3>{t("推荐动作", "Recommended Actions")}</h3>
            {assist?.recommended_actions?.length ? (
              <ul className="list" style={{ marginTop: 10 }}>
                {assist.recommended_actions.map((action, index) => (
                  <li className="list-item" key={`action-${index}`}>
                    <strong>{recommendationLabel(action)}</strong>
                    <div style={{ color: "var(--muted)", fontSize: 13, marginTop: 2 }}>
                      {recommendationDescription(action)}
                    </div>
                    <button
                      className="btn-ghost"
                      style={{ marginTop: 8 }}
                      onClick={() =>
                        setActionDraft({
                          suggested_action: recommendationLabel(action),
                          note: [recommendationLabel(action), recommendationDescription(action)].filter(Boolean).join("\n"),
                          source: "assist.recommended_actions"
                        })
                      }
                    >
                      {t("带入人工动作表单", "Copy to Manual Action Form")}
                    </button>
                  </li>
                ))}
              </ul>
            ) : (
              <p style={{ color: "var(--muted)" }}>{t("暂无推荐动作。", "No recommended actions available.")}</p>
            )}
          </article>
          <article className="card" style={{ marginTop: 12 }}>
            <h3>{t("Copilot 查询（advice_only）", "Copilot Query (advice_only)")}</h3>
            <form className="ops-kb-search-row" onSubmit={(event) => void submitCopilotQuery(event)}>
              <input
                className="ops-input"
                placeholder={t("例如：下一步如何推进？", "Example: What should I do next?")}
                value={copilotQueryText}
                onChange={(event) => setCopilotQueryText(event.target.value)}
              />
              <button className="btn-primary" type="submit" disabled={copilotLoading}>
                {t("询问 AI", "Ask AI")}
              </button>
            </form>
            <p className="hint" style={{ marginTop: 8 }}>
              {t("AI 输出仅为建议，不会直接执行动作。", "AI output is advice only and never executes actions directly.")}
            </p>
            {copilotLoading ? (
              <p style={{ color: "var(--muted)", marginTop: 8 }}>{t("AI 正在生成建议...", "AI is generating advice...")}</p>
            ) : null}
            {copilotError ? (
              <p style={{ color: "var(--danger)", marginTop: 8 }}>
                {t("Copilot 查询失败：", "Copilot query failed: ")}
                {copilotError}
              </p>
            ) : null}
            {copilot ? (
              <div style={{ marginTop: 8 }}>
                <div className="ops-card-title-row">
                  <strong>{copilot.scope}</strong>
                  <span className="ops-chip strong">advice_only=true</span>
                </div>
                <p style={{ marginTop: 8 }}>{copilot.answer || copilot.summary}</p>
                <div className="ops-muted" style={{ fontSize: 13 }}>
                  {t("风险标签", "Risk flags")}: {copilot.risk_flags.join(", ") || "-"}
                </div>
                <button
                  className="btn-ghost"
                  style={{ marginTop: 8 }}
                  onClick={() =>
                    setActionDraft({
                      suggested_action: t("Copilot 建议", "Copilot suggestion"),
                      note: [copilot.summary, copilot.answer].filter(Boolean).join("\n"),
                      source: "copilot.ticket.query"
                    })
                  }
                >
                  {t("带入人工动作表单", "Copy to Manual Action Form")}
                </button>
              </div>
            ) : null}
            {operatorCopilot ? (
              <div style={{ marginTop: 10 }}>
                <div className="ops-card-title-row">
                  <strong>{t("Operator 建议", "Operator Advice")}</strong>
                  <span className="ops-chip strong">advice_only=true</span>
                </div>
                <p style={{ marginTop: 6 }}>{operatorCopilot.answer}</p>
              </div>
            ) : null}
            {dispatchCopilot ? (
              <div style={{ marginTop: 10 }}>
                <div className="ops-card-title-row">
                  <strong>{t("Dispatch 建议", "Dispatch Advice")}</strong>
                  <span className="ops-chip strong">advice_only=true</span>
                </div>
                <p style={{ marginTop: 6 }}>{dispatchCopilot.answer}</p>
              </div>
            ) : null}
            <div style={{ marginTop: 12, display: "grid", gap: 8 }}>
              <label className="ops-label">
                <span>{t("调查问题（v2 investigate）", "Investigation Question (v2 investigate)")}</span>
                <input
                  className="ops-input"
                  value={investigationQuestion}
                  onChange={(event) => setInvestigationQuestion(event.target.value)}
                  placeholder={t("例如：请给出根因分析建议", "Example: Please suggest root cause analysis")}
                />
              </label>
              <button
                className="btn-ghost"
                type="button"
                disabled={investigationLoading}
                onClick={() => void submitInvestigation()}
              >
                {t("运行调查", "Run Investigation")}
              </button>
              {investigationLoading ? (
                <p className="hint">{t("调查进行中...", "Investigation in progress...")}</p>
              ) : null}
              {investigationError ? (
                <p style={{ color: "var(--danger)" }}>
                  {t("调查失败：", "Investigation failed: ")}
                  {investigationError}
                </p>
              ) : null}
              {investigation ? (
                <p className="hint">
                  {t("调查结果已返回（advice_only）", "Investigation completed (advice_only)")} · trace=
                  {String(investigation.trace?.trace_id ?? "-")}
                </p>
              ) : null}
            </div>
            <div style={{ marginTop: 12, display: "grid", gap: 8 }}>
              <label className="ops-label">
                <span>{t("会话结束原因（v2 session end）", "Session End Reason (v2 session end)")}</span>
                <input
                  className="ops-input"
                  value={sessionEndReason}
                  onChange={(event) => setSessionEndReason(event.target.value)}
                  placeholder={t("例如：manual_end", "Example: manual_end")}
                />
              </label>
              <button
                className="btn-ghost"
                type="button"
                disabled={sessionEndLoading || !sessionId}
                onClick={() => void submitSessionEnd()}
              >
                {t("结束会话", "End Session")}
              </button>
              <p className="hint">{t("当前 session_id", "Current session_id")}: {sessionId ?? "-"}</p>
              {sessionEndLoading ? (
                <p className="hint">{t("会话结束处理中...", "Ending session...")}</p>
              ) : null}
              {sessionEndError ? (
                <p style={{ color: "var(--danger)" }}>
                  {t("会话结束失败：", "Session end failed: ")}
                  {sessionEndError}
                </p>
              ) : null}
              {sessionEnd ? (
                <p className="hint">
                  {t("会话已结束", "Session ended")} · event={sessionEnd.event_type} · trace={sessionEnd.trace_id}
                </p>
              ) : null}
            </div>
          </article>
          <article className="card" style={{ marginTop: 12 }}>
            <h3>{t("相似案例", "Similar Cases")}</h3>
            {similarCases.length ? (
              <ul className="list" style={{ marginTop: 10 }}>
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

        <div className="detail-col">
          <p className="ops-kicker">{t("人工动作区", "Manual Actions")}</p>
          <TicketActionsPanel
            ticket={ticket}
            assignees={assignees}
            loadingAction={actionLoading}
            actionError={actionError}
            aiDraft={actionDraft}
            onAction={(action: TicketActionType, payload: TicketActionPayload) =>
              runAction(action, payload)
            }
          />

          <p className="ops-kicker" style={{ marginTop: 12 }}>
            {t("审批恢复区", "Approval Recovery")}
          </p>
          <article className="card">
            <h3>{t("审批分支总览", "Approval Branch Overview")}</h3>
            <ul className="ops-inline-list" style={{ marginTop: 10 }}>
              <li>pending_approval: {approvalCounts.pending}</li>
              <li>approved: {approvalCounts.approved}</li>
              <li>rejected: {approvalCounts.rejected}</li>
              <li>timeout: {approvalCounts.timeout}</li>
            </ul>
          </article>
          <div style={{ marginTop: 12 }}>
            <PendingApprovalList
              title={t("工单审批 / 恢复记录", "Ticket Approval / Recovery Records")}
              showAllStatuses
              items={pendingApprovals.items}
              loading={pendingApprovals.loading}
              actionLoadingId={pendingApprovals.actionLoadingId}
              error={pendingApprovals.error}
              onRefresh={() => void pendingApprovals.refetch()}
              onApprove={async (approvalId, note) => {
                await pendingApprovals.approve(approvalId, note, ticket.assignee ?? "u_supervisor_01");
                await refetch();
              }}
              onReject={async (approvalId, note) => {
                await pendingApprovals.reject(approvalId, note, ticket.assignee ?? "u_supervisor_01");
                await refetch();
              }}
            />
          </div>
        </div>
      </div>
    </section>
  );
}

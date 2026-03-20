"use client";

import { type FormEvent, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { PendingApprovalList } from "@/components/hitl/pending-approval-list";
import { ReplyWorkspace } from "@/components/tickets/reply-workspace";
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
  if (typeof value === "object") {
    return toBriefJson(value);
  }
  const text = String(value);
  return text.length > 140 ? `${text.slice(0, 137)}...` : text;
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

function toRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : {};
}

function toBooleanFlag(value: unknown): boolean {
  if (typeof value === "boolean") {
    return value;
  }
  if (typeof value === "number") {
    return value > 0;
  }
  if (typeof value === "string") {
    const normalized = value.trim().toLowerCase();
    return ["1", "true", "yes", "pending"].includes(normalized);
  }
  return false;
}

function firstNonEmptyString(...values: unknown[]): string | null {
  for (const value of values) {
    if (typeof value === "string" && value.trim()) {
      return value;
    }
    if (typeof value === "number" || typeof value === "boolean") {
      return String(value);
    }
  }
  return null;
}

function recommendationLabel(action: Record<string, unknown>) {
  return String(action.title ?? action.action ?? "recommendation");
}

function recommendationDescription(action: Record<string, unknown>) {
  return String(action.description ?? action.reason ?? "");
}

function formatTimestamp(value: string | null | undefined) {
  if (!value) {
    return "-";
  }
  const timestamp = Date.parse(value);
  if (Number.isNaN(timestamp)) {
    return value;
  }
  return new Date(timestamp).toLocaleString();
}

export default function TicketDetailPage() {
  const { t } = useI18n();
  const params = useParams<{ ticketId: string }>();
  const ticketId = params?.ticketId;
  const [copilotQueryText, setCopilotQueryText] = useState("");
  const [investigationQuestion, setInvestigationQuestion] = useState("");
  const [sessionEndReason, setSessionEndReason] = useState("");
  const [actionDraft, setActionDraft] = useState<TicketActionDraft | null>(null);
  const backLink = (
    <div>
      <Link href="/tickets" className="btn-ghost" data-testid="back-to-tickets-link">
        {t("返回工单列表", "Back to Tickets")}
      </Link>
    </div>
  );

  if (!ticketId) {
    return (
      <section className="ops-page-stack">
        {backLink}
        <ErrorState
          title={t("无效工单 ID。", "Invalid ticket id.")}
          message={t("无法从路由中解析工单。", "Cannot resolve ticket from route.")}
        />
      </section>
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
    replyDraft,
    replyDraftLoading,
    replyDraftError,
    replySend,
    replySendLoading,
    replySendError,
    replyEvents,
    groundingSources,
    similarCases,
    events,
    assignees,
    actionLoading,
    actionError,
    runAction,
    runReplyDraft,
    runReplySend,
    queryCopilot,
    runInvestigation,
    runSessionEnd,
    refetch
  } = useTicketDetail(ticketId);
  const pendingApprovals = useTicketPendingActions(ticketId);

  if (loading) {
    return (
      <section className="ops-page-stack">
        {backLink}
        <LoadingState title={t("工单详情同步中。", "Ticket detail is syncing.")} />
      </section>
    );
  }

  if (error) {
    return (
      <section className="ops-page-stack">
        {backLink}
        <ErrorState
          title={t("加载工单详情失败。", "Failed to load ticket detail.")}
          message={error}
          onRetry={() => void refetch()}
        />
      </section>
    );
  }

  if (!ticket) {
    return (
      <section className="ops-page-stack">
        {backLink}
        <EmptyState
          title={t("未找到工单。", "Ticket not found.")}
          message={t(`未找到 ${ticketId} 的工单数据。`, `No ticket payload for ${ticketId}.`)}
        />
      </section>
    );
  }

  const lastHandoffEvent = [...events].reverse().find((item) => item.event_type.includes("handoff"));
  const sessionId = getTicketSessionId(ticket);
  const assigneeForAction = ticket.assignee ?? undefined;
  const metadataEntries = Object.entries(ticket.metadata ?? {})
    .filter(([, value]) => value !== null && value !== undefined && value !== "")
    .sort(([left], [right]) => left.localeCompare(right));
  const metadataPreviewEntries = metadataEntries.slice(0, 16);
  const metadataRemainingEntries = metadataEntries.slice(16);
  const approvalCounts = {
    pending: pendingApprovals.items.filter((item) => item.status === "pending_approval").length,
    approved: pendingApprovals.items.filter((item) => item.status === "approved").length,
    rejected: pendingApprovals.items.filter((item) => item.status === "rejected").length,
    timeout: pendingApprovals.items.filter((item) => item.status === "timeout").length
  };
  const metadata = toRecord(ticket.metadata);
  const ticketRuntimeTrace = toRecord(copilot?.runtime_trace);
  const operatorRuntimeTrace = toRecord(operatorCopilot?.runtime_trace);
  const dispatchRuntimeTrace = toRecord(dispatchCopilot?.runtime_trace);
  const activeRuntimeTrace = Object.keys(ticketRuntimeTrace).length
    ? ticketRuntimeTrace
    : Object.keys(operatorRuntimeTrace).length
      ? operatorRuntimeTrace
      : dispatchRuntimeTrace;
  const currentGraphNode =
    firstNonEmptyString(
      metadata.current_graph_node,
      metadata.graph_node,
      metadata.runtime_node,
      metadata.current_node,
      activeRuntimeTrace.current_node,
      activeRuntimeTrace.node
    ) ?? "-";
  const graphStateSummary =
    firstNonEmptyString(
      metadata.graph_state_summary,
      metadata.graph_state,
      metadata.lifecycle_stage,
      metadata.runtime_state,
      activeRuntimeTrace.state,
      activeRuntimeTrace.mode
    ) ??
    toBriefJson({
      status: ticket.status,
      handoff_state: ticket.handoff_state,
      lifecycle_stage: metadata.lifecycle_stage ?? "unknown"
    });
  const pendingApproval = approvalCounts.pending > 0 || ticket.handoff_state === "pending_approval";
  const pendingCustomer = ticket.handoff_state === "waiting_customer" || toBooleanFlag(metadata.pending_customer);
  const pendingHandoff =
    ["requested", "accepted", "pending_claim", "pending_handoff"].includes(ticket.handoff_state) ||
    toBooleanFlag(metadata.pending_handoff);
  const topDispatchQueue = toRecord(dispatchCopilot?.queue_summary?.[0]).queue_name;
  const dispatchStatus =
    firstNonEmptyString(metadata.dispatch_status, metadata.dispatch_state, topDispatchQueue) ?? "not_available";
  const deliveryStatus =
    firstNonEmptyString(metadata.delivery_status, metadata.delivery_state, metadata.message_delivery_status) ??
    "not_available";
  const latestApprovalDecision = [...pendingApprovals.items]
    .reverse()
    .find((item) => item.status === "approved" || item.status === "rejected" || item.status === "timeout");
  const resumeRequiredAction =
    approvalCounts.pending > 0
      ? t(
          "需要审批人执行 approve/reject，随后由 runtime 自动恢复到 resume_handoff_state。",
          "Approver must execute approve/reject; runtime then resumes to resume_handoff_state."
        )
      : ticket.handoff_state === "waiting_customer"
        ? t(
            "进入 waiting_customer，可在人工动作区执行 customer_confirm / operator_close。",
            "Ticket is in waiting_customer; continue with customer_confirm / operator_close in Manual Actions."
          )
        : t("当前无待审批恢复动作。", "No pending approval resume action now.");
  const approvalResumeResult = latestApprovalDecision
    ? [
        latestApprovalDecision.status,
        latestApprovalDecision.decided_at ?? "-",
        latestApprovalDecision.decision_note ?? ""
      ]
        .filter((item) => String(item).trim().length > 0)
        .join(" · ")
    : t("暂无审批后的恢复记录。", "No post-approval resume record yet.");
  const recentReplyEvents = [...(Array.isArray(replyEvents) ? replyEvents : [])].reverse().slice(0, 8);
  const latestMessages = Array.isArray(assist?.latest_messages) ? assist.latest_messages : [];
  const recommendedActions = Array.isArray(assist?.recommended_actions) ? assist.recommended_actions : [];
  const copilotRiskFlags = Array.isArray(copilot?.risk_flags) ? copilot.risk_flags : [];
  const copilotRecommendedActions = Array.isArray(copilot?.recommended_actions) ? copilot.recommended_actions : [];
  const operatorGroundingSources = Array.isArray(operatorCopilot?.grounding_sources)
    ? operatorCopilot.grounding_sources
    : [];
  const operatorRecommendedActions = Array.isArray(operatorCopilot?.recommended_actions)
    ? operatorCopilot.recommended_actions
    : [];
  const dispatchGroundingSources = Array.isArray(dispatchCopilot?.grounding_sources)
    ? dispatchCopilot.grounding_sources
    : [];
  const dispatchRecommendedActions = Array.isArray(dispatchCopilot?.recommended_actions)
    ? dispatchCopilot.recommended_actions
    : [];

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
      await runInvestigation(investigationQuestion, assigneeForAction);
    } catch {
      // Error state is surfaced through investigationError.
    }
  }

  async function submitSessionEnd() {
    if (!sessionId) {
      return;
    }
    try {
      await runSessionEnd(sessionEndReason, assigneeForAction);
    } catch {
      // Error state is surfaced through sessionEndError.
    }
  }

  return (
    <section className="ops-page-stack">
      {backLink}
      <h2 className="section-title">{t("工单详情", "Ticket Detail")}</h2>
      <p className="ops-kicker">
        {t(
          "summary-first：首屏聚焦客户上下文、AI摘要、推荐动作、人工回复与审批状态；技术细节按需展开。",
          "Summary-first: keep context, AI summary, recommended actions, manual reply, and approvals on first screen; open technical details on demand."
        )}
      </p>
      <TicketDetailHeader ticket={ticket} />

      <div className="ticket-detail-primary-grid" style={{ marginTop: 12 }} data-testid="ticket-primary-sections">
        <div className="ticket-detail-primary-main">
          <article className="card">
            <h3>{t("客户上下文 / 来源消息", "Customer Context / Source Messages")}</h3>
            <ul className="list" style={{ marginTop: 10 }}>
              <li className="list-item">
                <small>{t("当前消息", "Current message")}: {ticket.latest_message || "-"}</small>
              </li>
              <li className="list-item">
                <small>{t("队列", "Queue")}: {ticket.queue} · {t("处理人", "Assignee")}: {ticket.assignee ?? "-"}</small>
              </li>
              <li className="list-item">
                <small>{t("渠道", "Channel")}: {ticket.channel} · {t("接管状态", "Handoff State")}: {ticket.handoff_state}</small>
              </li>
              {latestMessages.slice(0, 3).map((line, index) => (
                <li className="list-item" key={`source-msg-${index}`}>
                  <small>{line}</small>
                </li>
              ))}
            </ul>
          </article>

          <TicketSummaryCard ticket={ticket} assist={assist} />

          <article className="card">
            <h3>{t("推荐动作", "Recommended Actions")}</h3>
            {recommendedActions.length ? (
              <ul className="list" style={{ marginTop: 10 }}>
                {recommendedActions.map((action, index) => (
                  <li className="list-item" key={`action-${index}`}>
                    <strong>{recommendationLabel(action)}</strong>
                    <div style={{ color: "var(--muted)", fontSize: 13, marginTop: 2 }}>
                      {recommendationDescription(action)}
                    </div>
                    <button
                      type="button"
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
        </div>

        <div className="ticket-detail-primary-side">
          <p className="ops-kicker">{t("人工动作区", "Manual Actions")}</p>
          <ReplyWorkspace
            ticket={ticket}
            assignees={assignees}
            replyDraft={replyDraft}
            replyDraftLoading={replyDraftLoading}
            replyDraftError={replyDraftError}
            replySend={replySend}
            replySendLoading={replySendLoading}
            replySendError={replySendError}
            actionLoading={actionLoading}
            replyEvents={replyEvents}
            showReplyEvents={false}
            onGenerateDraft={(payload) => runReplyDraft(payload)}
            onSendReply={(payload) => runReplySend(payload)}
            onAction={(action: TicketActionType, payload: TicketActionPayload) =>
              runAction(action, payload)
            }
          />
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
            <div style={{ marginTop: 10 }}>
              <div style={{ color: "var(--muted)", fontSize: 13 }}>
                {t("当前审批状态", "Current approval state")}: {" "}
                {approvalCounts.pending > 0 ? "pending_approval" : t("无进行中审批", "no pending approval")}
              </div>
              <div style={{ color: "var(--muted)", fontSize: 13, marginTop: 4 }}>
                {t("resume 所需动作", "Resume required action")}: {resumeRequiredAction}
              </div>
              <div style={{ color: "var(--muted)", fontSize: 13, marginTop: 4 }}>
                {t("审批后 graph 恢复结果", "Post-approval graph resume result")}: {approvalResumeResult}
              </div>
            </div>
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

      <div className="ticket-detail-secondary-stack" data-testid="ticket-secondary-sections">
        <details className="ticket-detail-disclosure">
          <summary>{t("二级详情：时间线", "Details: Timeline")}</summary>
          <article className="card" style={{ marginTop: 10 }}>
            <h3>{t("事件时间线", "Event Timeline")}</h3>
            <TicketTimeline events={events} />
          </article>
        </details>

        <details className="ticket-detail-disclosure">
          <summary>{t("二级详情：Runtime 视角", "Details: Runtime View")}</summary>
          <article className="card" style={{ marginTop: 10 }}>
            <h3>{t("Runtime 视角", "Runtime View")}</h3>
            <ul className="ops-inline-list" style={{ marginTop: 10 }}>
              <li>current graph node: {currentGraphNode}</li>
              <li>graph state summary: {toBriefJson(graphStateSummary)}</li>
              <li>pending approval: {pendingApproval ? "true" : "false"}</li>
              <li>pending customer: {pendingCustomer ? "true" : "false"}</li>
              <li>pending handoff: {pendingHandoff ? "true" : "false"}</li>
              <li>dispatch status: {dispatchStatus}</li>
              <li>delivery status: {deliveryStatus}</li>
            </ul>
            <p className="hint" style={{ marginTop: 8, marginBottom: 0 }}>
              {t(
                "该卡片聚焦 graph/runtime 关键态，不再仅依赖旧 workflow 字段。",
                "This card focuses on graph/runtime states instead of only legacy workflow fields."
              )}
            </p>
          </article>
        </details>

        <details className="ticket-detail-disclosure">
          <summary>{t("二级详情：Trace / Reply Events", "Details: Trace / Reply Events")}</summary>
          <article className="card" style={{ marginTop: 10 }}>
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
              <p style={{ color: copilotError.startsWith("Partial copilot degraded") ? "var(--muted)" : "var(--danger)", marginTop: 8 }}>
                {copilotError.startsWith("Partial copilot degraded")
                  ? t("AI 局部降级：", "AI partial degradation: ")
                  : t("Copilot 查询失败：", "Copilot query failed: ")}
                {copilotError}
              </p>
            ) : null}
            {copilot ? (
              <div style={{ marginTop: 8 }}>
                <div className="ops-card-title-row">
                  <strong>{t("Ticket Copilot", "Ticket Copilot")}</strong>
                  <span className="ops-chip strong">advice_only=true</span>
                </div>
                <p style={{ marginTop: 8 }}>{copilot.answer || copilot.summary}</p>
                <div className="ops-muted" style={{ fontSize: 13 }}>
                  {t("风险标签", "Risk flags")}: {copilotRiskFlags.join(", ") || "-"}
                </div>
                <div className="ops-muted" style={{ fontSize: 13, marginTop: 2 }}>
                  agent source=ticket_copilot · grounding={Array.isArray(copilot.grounding_sources) ? copilot.grounding_sources.length : 0} · recommended_actions=
                  {copilotRecommendedActions.length}
                </div>
                <div className="ops-muted" style={{ fontSize: 13, marginTop: 2 }}>
                  runtime_trace={toBriefJson(copilot.runtime_trace ?? copilot.llm_trace)}
                </div>
                <button
                  type="button"
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
                <div className="ops-muted" style={{ fontSize: 13 }}>
                  agent source=operator_agent · grounding={operatorGroundingSources.length} · recommended_actions=
                  {operatorRecommendedActions.length} · confidence=
                  {operatorCopilot.confidence ?? "-"}
                </div>
                <div className="ops-muted" style={{ fontSize: 13, marginTop: 2 }}>
                  runtime_trace={toBriefJson(operatorCopilot.runtime_trace ?? operatorCopilot.llm_trace)}
                </div>
              </div>
            ) : null}
            {dispatchCopilot ? (
              <div style={{ marginTop: 10 }}>
                <div className="ops-card-title-row">
                  <strong>{t("Dispatch 建议", "Dispatch Advice")}</strong>
                  <span className="ops-chip strong">advice_only=true</span>
                </div>
                <p style={{ marginTop: 6 }}>{dispatchCopilot.answer}</p>
                <div className="ops-muted" style={{ fontSize: 13 }}>
                  agent source=dispatch_agent · grounding={dispatchGroundingSources.length} · recommended_actions=
                  {dispatchRecommendedActions.length} · top_queue=
                  {toText(toRecord(dispatchCopilot.queue_summary?.[0]).queue_name)}
                </div>
                <div className="ops-muted" style={{ fontSize: 13, marginTop: 2 }}>
                  runtime_trace={toBriefJson(dispatchCopilot.runtime_trace ?? dispatchCopilot.llm_trace)}
                </div>
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

          <article className="card" style={{ marginTop: 10 }}>
            <h3>{t("Reply Events", "Reply Events")}</h3>
            {recentReplyEvents.length ? (
              <ul className="list" style={{ marginTop: 10 }}>
                {recentReplyEvents.map((item) => (
                  <li className="list-item" key={item.event_id}>
                    <strong>{item.event_type}</strong>
                    <div style={{ color: "var(--muted)", fontSize: 13 }}>
                      {t("时间", "Time")}={formatTimestamp(item.created_at)} · {t("状态", "Status")}=
                      {item.delivery_status ?? "-"} · attempt={item.attempt ?? "-"}
                    </div>
                    <div style={{ color: "var(--muted)", fontSize: 13 }}>
                      trace={item.trace_id ?? "-"} · actor={item.actor_id ?? "-"} · source={item.source}
                    </div>
                    {item.trace_id ? (
                      <a href={`/traces/${encodeURIComponent(item.trace_id)}`} style={{ fontSize: 13 }}>
                        {t("查看 trace 详情", "View Trace Detail")}
                      </a>
                    ) : null}
                  </li>
                ))}
              </ul>
            ) : (
              <p className="hint">{t("暂无 reply-events。", "No reply events yet.")}</p>
            )}
          </article>
        </details>

        <details className="ticket-detail-disclosure">
          <summary>{t("二级详情：技术字段 / 定制字段", "Details: Technical / Custom Fields")}</summary>
          <article className="card" style={{ marginTop: 10 }}>
            <h3>{t("核心字段", "Core Fields")}</h3>
            <ul className="ops-inline-list" style={{ marginTop: 10 }}>
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

          <article className="card" style={{ marginTop: 10 }}>
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

          <article className="card" style={{ marginTop: 10 }}>
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

          <article className="card" style={{ marginTop: 10 }}>
            <h3>{t("定制字段", "Custom Fields")}</h3>
            {metadataEntries.length > 0 ? (
              <>
                <ul className="ops-inline-list" style={{ marginTop: 10 }}>
                  {metadataPreviewEntries.map(([key, value]) => (
                    <li key={key} style={{ overflowWrap: "anywhere" }}>
                      <strong>{key}</strong>: {toText(value)}
                    </li>
                  ))}
                </ul>
                {metadataRemainingEntries.length > 0 ? (
                  <details style={{ marginTop: 8 }}>
                    <summary style={{ color: "var(--muted)", cursor: "pointer", fontSize: 13 }}>
                      {t("展开更多字段", "Show more fields")} ({metadataRemainingEntries.length})
                    </summary>
                    <div style={{ maxHeight: 260, overflowY: "auto", marginTop: 8 }}>
                      <ul className="ops-inline-list" style={{ marginTop: 0 }}>
                        {metadataRemainingEntries.map(([key, value]) => (
                          <li key={key} style={{ overflowWrap: "anywhere" }}>
                            <strong>{key}</strong>: {toText(value)}
                          </li>
                        ))}
                      </ul>
                    </div>
                  </details>
                ) : null}
              </>
            ) : (
              <p style={{ color: "var(--muted)" }}>{t("暂无定制字段。", "No custom fields.")}</p>
            )}
          </article>
        </details>
      </div>
    </section>
  );
}

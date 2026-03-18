"use client";

import { useEffect, useMemo, useState } from "react";
import { ActionFeedback } from "@/components/shared/action-feedback";
import {
  type TicketActionPayload,
  type TicketActionType,
  type ReplyDraftData,
  type ReplyDraftPayload,
  type ReplyEventItem,
  type ReplySendData,
  type ReplySendPayload,
  type TicketItem
} from "@/lib/api/tickets";
import { useI18n } from "@/lib/i18n";

function buildIdempotencyKey(ticketId: string) {
  const now = Date.now().toString(36);
  const nonce = Math.random().toString(36).slice(2, 10);
  return `reply_${ticketId}_${now}_${nonce}`;
}

function isObserverActor(actorId: string) {
  const normalized = actorId.trim().toLowerCase();
  return normalized.startsWith("u_viewer") || normalized.includes("observer");
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

function suggestNextAction(handoffState: string): TicketActionType | null {
  const normalized = handoffState.trim().toLowerCase();
  if (["pending_claim", "requested", "accepted", "pending_handoff"].includes(normalized)) {
    return "claim";
  }
  if (["claimed", "in_progress", "waiting_internal", "none"].includes(normalized)) {
    return "resolve";
  }
  if (normalized === "waiting_customer") {
    return "customer_confirm";
  }
  return null;
}

export function ReplyWorkspace({
  ticket,
  assignees,
  replyDraft,
  replyDraftLoading,
  replyDraftError,
  replySend,
  replySendLoading,
  replySendError,
  actionLoading,
  replyEvents,
  onGenerateDraft,
  onSendReply,
  onAction
}: {
  ticket: TicketItem;
  assignees: string[];
  replyDraft: ReplyDraftData | null;
  replyDraftLoading: boolean;
  replyDraftError: string | null;
  replySend: ReplySendData | null;
  replySendLoading: boolean;
  replySendError: string | null;
  actionLoading?: TicketActionType | null;
  replyEvents: ReplyEventItem[];
  onGenerateDraft: (payload: ReplyDraftPayload) => Promise<ReplyDraftData>;
  onSendReply: (payload: ReplySendPayload) => Promise<ReplySendData>;
  onAction?: (action: TicketActionType, payload: TicketActionPayload) => Promise<void>;
}) {
  const { t } = useI18n();
  const defaultActorId = useMemo(
    () => ticket.assignee || assignees[0] || "u_ops_01",
    [assignees, ticket.assignee]
  );
  const [actorId, setActorId] = useState(defaultActorId);
  const [actorRole, setActorRole] = useState<"operator" | "observer">(
    isObserverActor(defaultActorId) ? "observer" : "operator"
  );
  const [replyStyle, setReplyStyle] = useState("说明");
  const [draftText, setDraftText] = useState("");
  const [editorText, setEditorText] = useState("");
  const [idempotencyKey, setIdempotencyKey] = useState(() => buildIdempotencyKey(ticket.ticket_id));
  const [feedback, setFeedback] = useState<string | null>(null);
  const [localError, setLocalError] = useState<string | null>(null);
  const [lastReplyId, setLastReplyId] = useState<string | null>(null);
  const [lastSentContent, setLastSentContent] = useState("");

  useEffect(() => {
    setActorId(defaultActorId);
    setActorRole(isObserverActor(defaultActorId) ? "observer" : "operator");
  }, [defaultActorId]);

  useEffect(() => {
    if (!replyDraft?.draft_text) {
      return;
    }
    setDraftText(replyDraft.draft_text);
    setEditorText(replyDraft.draft_text);
  }, [replyDraft?.trace_id, replyDraft?.draft_text]);

  useEffect(() => {
    if (!replySend || replySend.delivery_status === "failed") {
      return;
    }
    if (lastReplyId === replySend.reply_id) {
      return;
    }
    setLastReplyId(replySend.reply_id);
    setLastSentContent(editorText.trim());
    setIdempotencyKey(buildIdempotencyKey(ticket.ticket_id));
  }, [editorText, lastReplyId, replySend, ticket.ticket_id]);

  const isObserver = actorRole === "observer" || isObserverActor(actorId);
  const trimmedContent = editorText.trim();
  const unchangedAfterSuccess =
    !!replySend &&
    replySend.delivery_status !== "failed" &&
    trimmedContent.length > 0 &&
    trimmedContent === lastSentContent;
  const sortedReplyEvents = useMemo(
    () => [...(Array.isArray(replyEvents) ? replyEvents : [])].reverse().slice(0, 8),
    [replyEvents]
  );
  const suggestedAction = useMemo(() => suggestNextAction(ticket.handoff_state), [ticket.handoff_state]);
  const actionButtonLoading =
    !!actionLoading &&
    ((suggestedAction === "claim" && actionLoading === "claim") ||
      (suggestedAction === "resolve" && actionLoading === "resolve") ||
      (suggestedAction === "customer_confirm" && actionLoading === "customer_confirm"));

  async function handleGenerateDraft() {
    setFeedback(null);
    setLocalError(null);
    try {
      const data = await onGenerateDraft({
        actor_id: actorId,
        actor_role: actorRole,
        style: replyStyle,
        max_length: 280
      });
      setDraftText(data.draft_text);
      setEditorText(data.draft_text);
      setFeedback(t("AI 草稿已生成，请人工编辑后再发送。", "AI draft generated. Please edit before sending."));
    } catch (error) {
      setLocalError(error instanceof Error ? error.message : "Failed to generate draft");
    }
  }

  async function handleSendReply() {
    if (!trimmedContent) {
      return;
    }
    if (isObserver) {
      setLocalError(t("观察者角色不可发送消息。", "Observer role cannot send messages."));
      return;
    }
    const confirmText = t(
      `确认发送给用户？\n工单=${ticket.ticket_id}\n幂等键=${idempotencyKey}`,
      `Confirm send to user?\nTicket=${ticket.ticket_id}\nIdempotency=${idempotencyKey}`
    );
    if (!window.confirm(confirmText)) {
      return;
    }
    setFeedback(null);
    setLocalError(null);
    try {
      const result = await onSendReply({
        actor_id: actorId,
        actor_role: actorRole,
        content: trimmedContent,
        idempotency_key: idempotencyKey,
        draft_source: draftText ? "ai_draft_edited" : "manual"
      });
      if (result.delivery_status === "failed") {
        setFeedback(t("发送失败，可直接重试（沿用相同幂等键）。", "Send failed. You can retry with same idempotency key."));
      } else if (result.dedup_hit) {
        setFeedback(t("检测到重复发送请求，已命中幂等去重。", "Duplicate send detected and deduplicated."));
      } else {
        setFeedback(
          t(
            `消息已提交，状态=${result.delivery_status}。`,
            `Reply submitted with status=${result.delivery_status}.`
          )
        );
      }
    } catch (error) {
      setLocalError(error instanceof Error ? error.message : "Failed to send reply");
    }
  }

  async function handleSuggestedTransition() {
    if (!onAction || !suggestedAction) {
      return;
    }
    const actionLabel =
      suggestedAction === "claim"
        ? t("认领", "Claim")
        : suggestedAction === "resolve"
          ? t("解决（进入待客户确认）", "Resolve (to waiting_customer)")
          : t("客户确认", "Customer Confirm");
    const confirmText = t(
      `发送不会自动改变工单状态。\n确认执行状态流转：${actionLabel} ？`,
      `Reply sending will not change ticket state automatically.\nConfirm transition: ${actionLabel}?`
    );
    if (!window.confirm(confirmText)) {
      return;
    }
    const payload: TicketActionPayload =
      suggestedAction === "claim"
        ? { actor_id: actorId }
        : suggestedAction === "resolve"
          ? {
              actor_id: actorId,
              resolution_note:
                trimmedContent ||
                t("人工回复已发送，推进至待客户确认。", "Manual reply sent; moved to waiting customer."),
              resolution_code: "manual_reply_sent"
            }
          : {
              actor_id: actorId,
              note:
                trimmedContent ||
                t("客户确认后闭环。", "Closed after customer confirmation."),
              resolution_note:
                trimmedContent ||
                t("客户确认后闭环。", "Closed after customer confirmation."),
              resolution_code: "customer_confirmed"
            };
    try {
      await onAction(suggestedAction, payload);
      setFeedback(
        t(
          `状态已流转：${actionLabel}。`,
          `Ticket transition executed: ${actionLabel}.`
        )
      );
    } catch (error) {
      setLocalError(error instanceof Error ? error.message : "Failed to transition ticket status");
    }
  }

  return (
    <article className="card" style={{ marginBottom: 12 }}>
      <h3>{t("Reply Workspace（人工接管私聊闭环）", "Reply Workspace (Manual DM Loop)")}</h3>
      <p className="hint" style={{ marginTop: 8 }}>
        {t(
          "流程：AI 草稿 -> 人工编辑 -> 人工确认发送。advice_only 仅提供建议，不允许自动外发。",
          "Flow: AI draft -> human edit -> human-confirmed send. advice_only provides suggestions only and never auto-sends."
        )}
      </p>

      <div style={{ marginTop: 10, display: "grid", gap: 8 }}>
        <label className="ops-label">
          <span>{t("执行人", "Actor")}</span>
          <select className="ops-select" value={actorId} onChange={(event) => setActorId(event.target.value)}>
            {[...new Set([actorId, ...assignees])].map((assignee) => (
              <option key={assignee} value={assignee}>
                {assignee}
              </option>
            ))}
          </select>
        </label>

        <label className="ops-label">
          <span>{t("执行角色", "Actor Role")}</span>
          <select
            className="ops-select"
            value={actorRole}
            onChange={(event) => setActorRole(event.target.value as "operator" | "observer")}
          >
            <option value="operator">{t("operator（可发送）", "operator (can send)")}</option>
            <option value="observer">{t("observer（只读）", "observer (read-only)")}</option>
          </select>
        </label>

        <label className="ops-label">
          <span>{t("草稿风格", "Draft Style")}</span>
          <input className="ops-input" value={replyStyle} onChange={(event) => setReplyStyle(event.target.value)} />
        </label>

        <button className="btn-ghost" type="button" disabled={replyDraftLoading} onClick={() => void handleGenerateDraft()}>
          {replyDraftLoading ? t("草稿生成中...", "Generating draft...") : t("生成 AI 草稿", "Generate AI Draft")}
        </button>
      </div>

      <label className="ops-label" style={{ marginTop: 10 }}>
        <span>{t("AI 草稿", "AI Draft")}</span>
        <textarea className="ops-textarea" rows={3} value={draftText} readOnly />
      </label>

      <label className="ops-label" style={{ marginTop: 10 }}>
        <span>{t("人工编辑后发送内容", "Edited Reply Content")}</span>
        <textarea
          className="ops-textarea"
          rows={5}
          value={editorText}
          onChange={(event) => setEditorText(event.target.value)}
          placeholder={t("请人工确认并编辑消息后发送。", "Please edit and confirm before sending.")}
        />
      </label>

      <label className="ops-label" style={{ marginTop: 10 }}>
        <span>{t("幂等键", "Idempotency Key")}</span>
        <input className="ops-input" value={idempotencyKey} onChange={(event) => setIdempotencyKey(event.target.value)} />
      </label>

      <div style={{ display: "grid", gap: 8, marginTop: 10 }}>
        <button
          className="btn-primary"
          type="button"
          disabled={replySendLoading || !trimmedContent || isObserver || unchangedAfterSuccess}
          onClick={() => void handleSendReply()}
        >
          {replySendLoading
            ? t("发送中...", "Sending...")
            : replySend?.delivery_status === "failed"
              ? t("重试发送", "Retry Send")
              : t("人工确认发送", "Confirm & Send")}
        </button>
        {isObserver ? (
          <p className="hint">{t("当前角色为 observer，禁止发送。", "Current role is observer; sending is blocked.")}</p>
        ) : null}
        {unchangedAfterSuccess ? (
          <p className="hint">
            {t(
              "当前内容已发送成功；如需再次发送请先修改内容。",
              "This content has already been sent successfully; edit content before sending again."
            )}
          </p>
        ) : null}
        <p className="hint" style={{ margin: 0 }}>
          {t(
            "发送回复只记录 reply-events，不会自动推进工单状态；请按需要手动执行状态流转。",
            "Reply send only records reply-events and does not auto-transition ticket state; run transition manually when needed."
          )}
        </p>
        {onAction && suggestedAction ? (
          <button
            className="btn-ghost"
            type="button"
            disabled={actionButtonLoading || replySendLoading}
            onClick={() => void handleSuggestedTransition()}
          >
            {suggestedAction === "claim"
              ? t("建议下一步：认领", "Suggested next step: Claim")
              : suggestedAction === "resolve"
                ? t("建议下一步：解决（待客户确认）", "Suggested next step: Resolve")
                : t("建议下一步：客户确认", "Suggested next step: Customer Confirm")}
          </button>
        ) : null}
      </div>

      <ActionFeedback variant="success" message={feedback} />
      <ActionFeedback
        variant="error"
        message={localError || replyDraftError || replySendError ? (localError || replyDraftError || replySendError) : null}
      />

      <div style={{ marginTop: 12 }}>
        <h4 style={{ marginBottom: 6 }}>{t("Reply Events", "Reply Events")}</h4>
        {sortedReplyEvents.length ? (
          <ul className="list">
            {sortedReplyEvents.map((item) => (
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
      </div>
    </article>
  );
}

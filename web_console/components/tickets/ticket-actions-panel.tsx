"use client";

import { useEffect, useMemo, useState } from "react";
import type { TicketActionPayload, TicketActionType, TicketItem } from "@/lib/api/tickets";
import { useI18n } from "@/lib/i18n";
import { ActionFeedback } from "@/components/shared/action-feedback";

const HIGH_RISK_ACTIONS = new Set<TicketActionType>(["escalate", "operator_close"]);

export type TicketActionDraft = {
  note?: string;
  resolution_code?: string;
  close_reason?: string;
  suggested_action?: string;
  source?: string;
};

function actionDisplayName(action: TicketActionType, t: (zh: string, en: string) => string) {
  if (action === "customer_confirm") {
    return t("客户确认", "Customer Confirm");
  }
  if (action === "operator_close") {
    return t("运营关闭", "Operator Close");
  }
  if (action === "close_compat") {
    return t("兼容关闭", "Compat Close");
  }
  return action;
}

export function TicketActionsPanel({
  ticket,
  assignees,
  loadingAction,
  actionError,
  onAction,
  aiDraft
}: {
  ticket: TicketItem;
  assignees: string[];
  loadingAction: TicketActionType | null;
  actionError: string | null;
  onAction: (action: TicketActionType, payload: TicketActionPayload) => Promise<void>;
  aiDraft?: TicketActionDraft | null;
}) {
  const { t } = useI18n();
  const defaultActor = useMemo(() => ticket.assignee ?? assignees[0] ?? "u_ops_01", [
    ticket.assignee,
    assignees
  ]);
  const [actorId, setActorId] = useState(defaultActor);
  const [targetQueue, setTargetQueue] = useState(ticket.queue);
  const [targetAssignee, setTargetAssignee] = useState(ticket.assignee ?? "");
  const [note, setNote] = useState("");
  const [resolutionCode, setResolutionCode] = useState("resolved");
  const [closeReason, setCloseReason] = useState("customer_confirmed");
  const [compatMode, setCompatMode] = useState(false);
  const [feedback, setFeedback] = useState<string | null>(null);

  useEffect(() => {
    if (!aiDraft) {
      return;
    }
    if (typeof aiDraft.note === "string" && aiDraft.note.trim()) {
      setNote(aiDraft.note);
    }
    if (typeof aiDraft.resolution_code === "string" && aiDraft.resolution_code.trim()) {
      setResolutionCode(aiDraft.resolution_code);
    }
    if (typeof aiDraft.close_reason === "string" && aiDraft.close_reason.trim()) {
      setCloseReason(aiDraft.close_reason);
    }
    setFeedback(
      t(
        "已将 AI 建议带入人工动作表单，请人工确认后执行。",
        "AI suggestion has been copied into the manual action form. Please confirm before execution."
      )
    );
  }, [aiDraft, t]);

  async function submit(action: TicketActionType, payload: TicketActionPayload) {
    const summary = actionDisplayName(action, t);
    const promptLines = [
      t(
        `确认对工单 ${ticket.ticket_id} 执行 ${summary}？`,
        `Confirm ${summary} for ticket ${ticket.ticket_id}?`
      )
    ];
    if (HIGH_RISK_ACTIONS.has(action)) {
      promptLines.push(
        t("该动作为高风险动作，提交后将进入审批链路。", "This is a high-risk action and will enter approval flow.")
      );
    }
    if (action === "close_compat") {
      promptLines.push(
        t(
          "兼容模式：本次将调用 v1 /api/tickets/:ticketId/close。",
          "Compat mode: this call will use v1 /api/tickets/:ticketId/close."
        )
      );
    }
    const confirmed = window.confirm(promptLines.join("\n"));
    if (!confirmed) {
      return;
    }
    setFeedback(null);
    try {
      await onAction(action, payload);
      setFeedback(t(`动作 ${summary} 已执行。`, `Action ${summary} executed.`));
    } catch {
      // Errors are surfaced by actionError from useTicketDetail.
    }
  }

  const transitionGuide = [
    {
      action: "claim" as const,
      label: t("认领", "Claim"),
      from: "pending_claim",
      to: "claimed",
      description: t("进入人工处理起点。", "Enter the human-handled runtime path.")
    },
    {
      action: "reassign" as const,
      label: t("改派", "Reassign"),
      from: "claimed",
      to: "waiting_internal",
      description: t("改派到目标队列/处理人。", "Move ticket to another queue or assignee.")
    },
    {
      action: "escalate" as const,
      label: t("升级", "Escalate"),
      from: "claimed|waiting_internal",
      to: "pending_approval",
      description: t("触发审批链路（人工接入/HITL）。", "Trigger HITL approval flow.")
    },
    {
      action: "resolve" as const,
      label: t("解决", "Resolve"),
      from: "claimed|waiting_internal",
      to: "waiting_customer",
      description: t("待客户确认恢复。", "Move to customer confirmation stage.")
    },
    {
      action: "customer_confirm" as const,
      label: t("客户确认", "Customer Confirm"),
      from: "waiting_customer",
      to: "completed",
      description: t("客户确认后闭环。", "Close loop after customer confirmation.")
    },
    {
      action: "operator_close" as const,
      label: t("运营关闭", "Operator Close"),
      from: "waiting_customer|escalated",
      to: "completed",
      description: t("高风险终态动作，进入审批后执行。", "High-risk terminal action; execute after approval.")
    }
  ];

  const resumePathHint =
    ticket.handoff_state === "pending_approval"
      ? t(
          "当前处于 pending_approval：请在审批恢复区完成 approve/reject，再继续图状态迁移。",
          "Current state is pending_approval: complete approve/reject in Approval Recovery before next transition."
        )
      : ticket.handoff_state === "waiting_customer"
        ? t(
            "当前处于 waiting_customer：优先执行客户确认(customer_confirm)或运营关闭(operator_close)。",
            "Current state is waiting_customer: use customer_confirm or operator_close as next transition."
          )
        : ticket.handoff_state === "waiting_internal"
          ? t(
              "当前处于 waiting_internal：可继续改派(reassign)或升级(escalate)。",
              "Current state is waiting_internal: continue with reassign or escalate."
            )
          : t(
              "可按下方 transition controls 推进图状态；高风险动作会进入审批链路。",
              "Use transition controls below to move graph state; high-risk actions enter approval flow."
            );

  return (
    <section className="card">
      <h3>{t("人工动作区（Graph Transition Controls）", "Manual Actions (Graph Transition Controls)")}</h3>
      <p className="hint" style={{ marginTop: 8 }}>
        {t(
          "以下动作按状态机迁移组织，不再是散乱按钮集合。每次执行都需要人工确认。",
          "Actions are organized by state-machine transitions, not a loose button list. Every action requires human confirmation."
        )}
      </p>
      <article style={{ marginTop: 10, border: "1px solid var(--line)", borderRadius: 10, padding: 10 }}>
        <div style={{ fontSize: 13, color: "var(--muted)", marginBottom: 6 }}>
          {t("当前 handoff_state", "Current handoff_state")}: <strong>{ticket.handoff_state}</strong>
        </div>
        <ul className="list">
          {transitionGuide.map((item) => (
            <li className="list-item" key={item.action}>
              <strong>{item.label}</strong>
              <div style={{ color: "var(--muted)", fontSize: 13 }}>
                {item.from} {"->"} {item.to}
              </div>
              <div style={{ color: "var(--muted)", fontSize: 13 }}>{item.description}</div>
            </li>
          ))}
        </ul>
        <p className="hint" style={{ marginTop: 8, marginBottom: 0 }}>
          {resumePathHint}
        </p>
      </article>
      <div style={{ marginTop: 10, display: "grid", gap: 8 }}>
        <label className="ops-label">
          <span>{t("执行人", "Actor")}</span>
          <select
            className="ops-select"
            value={actorId}
            onChange={(event) => setActorId(event.target.value)}
          >
            {[...new Set([actorId, ...assignees])].map((assignee) => (
              <option key={assignee} value={assignee}>
                {assignee}
              </option>
            ))}
          </select>
        </label>

        <label className="ops-label">
          <span>{t("目标队列（改派）", "Target Queue (reassign)")}</span>
          <input
            className="ops-input"
            value={targetQueue}
            onChange={(event) => setTargetQueue(event.target.value)}
          />
        </label>

        <label className="ops-label">
          <span>{t("目标处理人（改派）", "Target Assignee (reassign)")}</span>
          <input
            className="ops-input"
            value={targetAssignee}
            onChange={(event) => setTargetAssignee(event.target.value)}
          />
        </label>

        <label className="ops-label">
          <span>{t("备注 / 处理说明", "Note / Resolution")}</span>
          <textarea
            className="ops-textarea"
            value={note}
            onChange={(event) => setNote(event.target.value)}
            rows={3}
          />
        </label>

        <div className="ops-split">
          <label className="ops-label">
            <span>{t("处理结果代码", "Resolution Code")}</span>
            <input
              className="ops-input"
              value={resolutionCode}
              onChange={(event) => setResolutionCode(event.target.value)}
            />
          </label>
          <label className="ops-label">
            <span>{t("关闭原因", "Close Reason")}</span>
            <input
              className="ops-input"
              value={closeReason}
              onChange={(event) => setCloseReason(event.target.value)}
            />
          </label>
        </div>

        <label
          style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 2 }}
          aria-label={t("兼容模式（v1 /close）", "Compatibility Mode (v1 /close)")}
        >
          <input
            type="checkbox"
            checked={compatMode}
            onChange={(event) => setCompatMode(event.target.checked)}
          />
          <span>{t("兼容模式（v1 /close）", "Compatibility Mode (v1 /close)")}</span>
        </label>
        <p className="hint" style={{ margin: 0 }}>
          {compatMode
            ? t(
                "已启用兼容模式：仅在回滚/灰度时使用 v1 /close。",
                "Compatibility mode enabled: use v1 /close for fallback only."
              )
            : t("默认使用 v2 动作语义。", "v2 action semantics are used by default.")}
        </p>
        <p className="hint" style={{ margin: 0 }}>
          {t(
            "高风险动作（升级、运营关闭）提交后将进入审批链路。",
            "High-risk actions (escalate, operator close) will enter approval workflow."
          )}
        </p>
        {aiDraft?.suggested_action ? (
          <p className="hint" style={{ margin: 0 }}>
            {t("当前带入建议", "Current imported suggestion")}: {aiDraft.suggested_action}
          </p>
        ) : null}
      </div>

      <div className="ops-action-grid">
        <button type="button" className="btn-primary" disabled={loadingAction !== null} onClick={() => submit("claim", { actor_id: actorId })}>
          {t("认领", "Claim")}
        </button>
        <button
          type="button"
          className="btn-primary"
          disabled={loadingAction !== null}
          onClick={() =>
            submit("reassign", {
              actor_id: actorId,
              target_queue: targetQueue,
              target_assignee: targetAssignee
            })
          }
        >
          {t("改派", "Reassign")}
        </button>
        <button
          type="button"
          className="btn-primary"
          disabled={loadingAction !== null}
          onClick={() => submit("escalate", { actor_id: actorId, note: note || t("运营升级处理", "Escalated by ops") })}
        >
          {t("升级", "Escalate")}
        </button>
        <button
          type="button"
          className="btn-primary"
          disabled={loadingAction !== null}
          onClick={() =>
            submit("resolve", {
              actor_id: actorId,
              resolution_note: note || t("运营已处理", "Resolved by ops"),
              resolution_code: resolutionCode
            })
          }
        >
          {t("解决", "Resolve")}
        </button>
        <button
          type="button"
          className="btn-primary"
          disabled={loadingAction !== null}
          onClick={() =>
            submit("customer_confirm", {
              actor_id: actorId,
              note: note || t("客户已确认恢复", "Customer confirmed recovery"),
              resolution_note: note || t("客户已确认恢复", "Customer confirmed recovery"),
              resolution_code: resolutionCode
            })
          }
        >
          {t("客户确认", "Customer Confirm")}
        </button>
        <button
          type="button"
          className="btn-primary"
          disabled={loadingAction !== null}
          onClick={() =>
            submit("operator_close", {
              actor_id: actorId,
              note: note || t("运营执行强制关闭", "Operator forced close"),
              resolution_note: note || t("运营执行强制关闭", "Operator forced close"),
              close_reason: closeReason,
              resolution_code: resolutionCode
            })
          }
        >
          {t("运营关闭", "Operator Close")}
        </button>
        {compatMode ? (
          <button
            type="button"
            className="btn-ghost"
            disabled={loadingAction !== null}
            onClick={() =>
              submit("close_compat", {
                actor_id: actorId,
                resolution_note: note || t("兼容模式关闭", "Closed by compatibility mode"),
                close_reason: closeReason,
                resolution_code: resolutionCode
              })
            }
            style={{ gridColumn: "1 / -1" }}
          >
            {t("兼容关闭（v1 /close）", "Compat Close (v1 /close)")}
          </button>
        ) : null}
      </div>

      {loadingAction ? (
        <p style={{ marginTop: 10, color: "var(--muted)" }}>
          {t(`正在执行 ${loadingAction}...`, `Executing ${loadingAction}...`)}
        </p>
      ) : null}
      <ActionFeedback variant="success" message={feedback} />
      <ActionFeedback
        variant="error"
        message={actionError ? t("动作执行失败：", "Action failed: ") + actionError : null}
      />
    </section>
  );
}

"use client";

import { useMemo, useState } from "react";
import type { TicketActionPayload, TicketActionType, TicketItem } from "@/lib/api/tickets";
import { useI18n } from "@/lib/i18n";
import { ActionFeedback } from "@/components/shared/action-feedback";

export function TicketActionsPanel({
  ticket,
  assignees,
  loadingAction,
  actionError,
  onAction
}: {
  ticket: TicketItem;
  assignees: string[];
  loadingAction: TicketActionType | null;
  actionError: string | null;
  onAction: (action: TicketActionType, payload: TicketActionPayload) => Promise<void>;
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
  const [feedback, setFeedback] = useState<string | null>(null);

  async function submit(action: TicketActionType, payload: TicketActionPayload) {
    const confirmed = window.confirm(
      t(`确认对工单 ${ticket.ticket_id} 执行 ${action}？`, `Confirm ${action} for ticket ${ticket.ticket_id}?`)
    );
    if (!confirmed) {
      return;
    }
    setFeedback(null);
    try {
      await onAction(action, payload);
      setFeedback(t(`动作 ${action} 已执行。`, `Action ${action} executed.`));
    } catch {
      // Errors are surfaced by actionError from useTicketDetail.
    }
  }

  return (
    <section className="card">
      <h3>{t("动作面板", "Actions Panel")}</h3>
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
      </div>

      <div className="ops-action-grid">
        <button className="btn-primary" disabled={loadingAction !== null} onClick={() => submit("claim", { actor_id: actorId })}>
          {t("认领", "Claim")}
        </button>
        <button
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
          className="btn-primary"
          disabled={loadingAction !== null}
          onClick={() => submit("escalate", { actor_id: actorId, note: note || t("运营升级处理", "Escalated by ops") })}
        >
          {t("升级", "Escalate")}
        </button>
        <button
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
          className="btn-primary"
          disabled={loadingAction !== null}
          onClick={() =>
            submit("close", {
              actor_id: actorId,
              resolution_note: note || t("运营已关闭", "Closed by ops"),
              close_reason: closeReason,
              resolution_code: resolutionCode
            })
          }
          style={{ gridColumn: "1 / -1" }}
        >
          {t("关闭", "Close")}
        </button>
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

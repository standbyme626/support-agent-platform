"use client";

import { useMemo, useState } from "react";
import type { TicketActionPayload, TicketActionType, TicketItem } from "@/lib/api/tickets";

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
    const confirmed = window.confirm(`Confirm ${action} for ticket ${ticket.ticket_id}?`);
    if (!confirmed) {
      return;
    }
    await onAction(action, payload);
    setFeedback(`Action ${action} executed.`);
  }

  return (
    <section className="card">
      <h3>Actions Panel</h3>
      <div style={{ marginTop: 10, display: "grid", gap: 8 }}>
        <label style={{ display: "grid", gap: 4 }}>
          <span style={{ color: "var(--muted)", fontSize: 12 }}>Actor</span>
          <select
            value={actorId}
            onChange={(event) => setActorId(event.target.value)}
            style={{ height: 36, borderRadius: 8, border: "1px solid var(--border)", padding: "0 10px" }}
          >
            {[...new Set([actorId, ...assignees])].map((assignee) => (
              <option key={assignee} value={assignee}>
                {assignee}
              </option>
            ))}
          </select>
        </label>

        <label style={{ display: "grid", gap: 4 }}>
          <span style={{ color: "var(--muted)", fontSize: 12 }}>Target Queue (reassign)</span>
          <input
            value={targetQueue}
            onChange={(event) => setTargetQueue(event.target.value)}
            style={{ height: 36, borderRadius: 8, border: "1px solid var(--border)", padding: "0 10px" }}
          />
        </label>

        <label style={{ display: "grid", gap: 4 }}>
          <span style={{ color: "var(--muted)", fontSize: 12 }}>Target Assignee (reassign)</span>
          <input
            value={targetAssignee}
            onChange={(event) => setTargetAssignee(event.target.value)}
            style={{ height: 36, borderRadius: 8, border: "1px solid var(--border)", padding: "0 10px" }}
          />
        </label>

        <label style={{ display: "grid", gap: 4 }}>
          <span style={{ color: "var(--muted)", fontSize: 12 }}>Note / Resolution</span>
          <textarea
            value={note}
            onChange={(event) => setNote(event.target.value)}
            rows={3}
            style={{ borderRadius: 8, border: "1px solid var(--border)", padding: "8px 10px", resize: "vertical" }}
          />
        </label>

        <div style={{ display: "grid", gap: 8, gridTemplateColumns: "1fr 1fr" }}>
          <label style={{ display: "grid", gap: 4 }}>
            <span style={{ color: "var(--muted)", fontSize: 12 }}>Resolution Code</span>
            <input
              value={resolutionCode}
              onChange={(event) => setResolutionCode(event.target.value)}
              style={{ height: 34, borderRadius: 8, border: "1px solid var(--border)", padding: "0 10px" }}
            />
          </label>
          <label style={{ display: "grid", gap: 4 }}>
            <span style={{ color: "var(--muted)", fontSize: 12 }}>Close Reason</span>
            <input
              value={closeReason}
              onChange={(event) => setCloseReason(event.target.value)}
              style={{ height: 34, borderRadius: 8, border: "1px solid var(--border)", padding: "0 10px" }}
            />
          </label>
        </div>
      </div>

      <div style={{ marginTop: 12, display: "grid", gap: 8, gridTemplateColumns: "1fr 1fr" }}>
        <button className="btn-primary" disabled={loadingAction !== null} onClick={() => submit("claim", { actor_id: actorId })}>
          Claim
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
          Reassign
        </button>
        <button
          className="btn-primary"
          disabled={loadingAction !== null}
          onClick={() => submit("escalate", { actor_id: actorId, note: note || "Escalated by ops" })}
        >
          Escalate
        </button>
        <button
          className="btn-primary"
          disabled={loadingAction !== null}
          onClick={() =>
            submit("resolve", {
              actor_id: actorId,
              resolution_note: note || "Resolved by ops",
              resolution_code: resolutionCode
            })
          }
        >
          Resolve
        </button>
        <button
          className="btn-primary"
          disabled={loadingAction !== null}
          onClick={() =>
            submit("close", {
              actor_id: actorId,
              resolution_note: note || "Closed by ops",
              close_reason: closeReason,
              resolution_code: resolutionCode
            })
          }
          style={{ gridColumn: "1 / -1" }}
        >
          Close
        </button>
      </div>

      {loadingAction ? (
        <p style={{ marginTop: 10, color: "var(--muted)" }}>Executing {loadingAction}...</p>
      ) : null}
      {feedback ? <p style={{ marginTop: 10, color: "var(--ok)" }}>{feedback}</p> : null}
      {actionError ? <p style={{ marginTop: 10, color: "var(--bad)" }}>{actionError}</p> : null}
    </section>
  );
}

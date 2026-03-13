"use client";

import { useMemo, useState } from "react";
import type { PendingApprovalItem } from "@/lib/api/tickets";
import { useI18n } from "@/lib/i18n";
import {
  ApprovalActionDialog,
  type ApprovalDialogAction
} from "@/components/hitl/approval-action-dialog";

const APPROVAL_STATUS_ORDER = ["pending_approval", "approved", "rejected", "timeout"] as const;

function formatTime(value: string | null | undefined) {
  if (!value) {
    return "-";
  }
  const parsed = Date.parse(value);
  if (Number.isNaN(parsed)) {
    return value;
  }
  return new Date(parsed).toLocaleString();
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
    return serialized.length > 120 ? `${serialized.slice(0, 117)}...` : serialized;
  } catch {
    return String(value);
  }
}

function statusLabel(status: string, t: (zh: string, en: string) => string) {
  if (status === "pending_approval") {
    return t("待审批", "Pending Approval");
  }
  if (status === "approved") {
    return t("已批准", "Approved");
  }
  if (status === "rejected") {
    return t("已拒绝", "Rejected");
  }
  if (status === "timeout") {
    return t("已超时", "Timed Out");
  }
  return status;
}

export function PendingApprovalList({
  items,
  loading,
  actionLoadingId,
  error,
  onRefresh,
  onApprove,
  onReject,
  title,
  showAllStatuses = false
}: {
  items: PendingApprovalItem[];
  loading: boolean;
  actionLoadingId: string | null;
  error: string | null;
  onRefresh: () => void;
  onApprove: (approvalId: string, note: string) => Promise<void>;
  onReject: (approvalId: string, note: string) => Promise<void>;
  title?: string;
  showAllStatuses?: boolean;
}) {
  const { t } = useI18n();
  const [dialogOpen, setDialogOpen] = useState(false);
  const [dialogAction, setDialogAction] = useState<ApprovalDialogAction>("approve");
  const [dialogApprovalId, setDialogApprovalId] = useState<string | null>(null);
  const [dialogError, setDialogError] = useState<string | null>(null);
  const sections = useMemo(
    () =>
      (showAllStatuses
        ? APPROVAL_STATUS_ORDER.map((status) => ({
            status,
            items: items.filter((item) => item.status === status)
          }))
        : [
            {
              status: "pending_approval",
              items
            }
          ]),
    [items, showAllStatuses]
  );

  const currentApproval = useMemo(
    () => items.find((item) => item.approval_id === dialogApprovalId) ?? null,
    [items, dialogApprovalId]
  );

  function openDialog(action: ApprovalDialogAction, approvalId: string) {
    setDialogAction(action);
    setDialogApprovalId(approvalId);
    setDialogError(null);
    setDialogOpen(true);
  }

  function closeDialog() {
    setDialogOpen(false);
    setDialogApprovalId(null);
    setDialogError(null);
  }

  async function confirmDecision(note: string) {
    if (!currentApproval) {
      return;
    }
    try {
      if (dialogAction === "approve") {
        await onApprove(currentApproval.approval_id, note);
      } else {
        await onReject(currentApproval.approval_id, note);
      }
      closeDialog();
    } catch (error) {
      setDialogError(error instanceof Error ? error.message : "decision failed");
    }
  }

  return (
    <article className="card">
      <div className="ops-card-title-row">
        <h3>{title ?? t("待审批动作", "Pending Approvals")}</h3>
        <button className="btn-ghost" onClick={onRefresh}>
          {t("刷新", "Refresh")}
        </button>
      </div>

      {loading ? (
        <p className="hint" style={{ marginTop: 8 }}>
          {t("待审批数据同步中...", "Syncing pending approvals...")}
        </p>
      ) : null}

      {!loading && !items.length && !showAllStatuses ? (
        <p className="hint" style={{ marginTop: 8 }}>
          {t("当前没有待审批动作。", "No pending approvals right now.")}
        </p>
      ) : null}

      {sections.map((section) => (
        <section key={section.status} style={{ marginTop: 10 }}>
          {showAllStatuses ? (
            <div className="ops-card-title-row" style={{ marginBottom: 6 }}>
              <strong>{statusLabel(section.status, t)}</strong>
              <span className="ops-chip">{section.items.length}</span>
            </div>
          ) : null}
          {section.items.length === 0 ? (
            showAllStatuses ? (
              <p className="hint" style={{ marginTop: 6 }}>
                {t("暂无记录。", "No records.")}
              </p>
            ) : null
          ) : (
            <ul className="list">
              {section.items.map((item) => (
                <li className="list-item" key={item.approval_id}>
                  <div className="ops-card-title-row">
                    <strong>{item.action_type}</strong>
                    <span className="pill pill-warning">{item.risk_level}</span>
                  </div>
                  <div className="ops-muted" style={{ marginTop: 4, fontSize: 13 }}>
                    approval={item.approval_id} · ticket={item.ticket_id} · {statusLabel(item.status, t)}
                  </div>
                  <div className="ops-muted" style={{ marginTop: 4, fontSize: 13 }}>
                    {t("发起人", "Requested by")}: {item.requested_by} · {t("截止", "Timeout")}=
                    {formatTime(item.timeout_at)}
                  </div>
                  <div className="ops-muted" style={{ marginTop: 4, fontSize: 13 }}>
                    {t("上下文", "Context")}: {toBriefJson(item.context)}
                  </div>
                  {item.status === "pending_approval" ? (
                    <div style={{ marginTop: 8, display: "flex", gap: 8 }}>
                      <button
                        className="btn-primary"
                        disabled={actionLoadingId === item.approval_id}
                        onClick={() => openDialog("approve", item.approval_id)}
                      >
                        {t("批准", "Approve")}
                      </button>
                      <button
                        className="btn-ghost"
                        disabled={actionLoadingId === item.approval_id}
                        onClick={() => openDialog("reject", item.approval_id)}
                      >
                        {t("拒绝", "Reject")}
                      </button>
                    </div>
                  ) : (
                    <div className="ops-muted" style={{ marginTop: 6, fontSize: 13 }}>
                      {t("恢复结果", "Recovery result")}: {statusLabel(item.status, t)} ·{" "}
                      {t("处理人", "Actor")}={item.approved_by ?? item.rejected_by ?? "-"} ·{" "}
                      {t("处理时间", "Decided at")}={formatTime(item.decided_at)}
                      {item.decision_note ? ` · ${t("意见", "Note")}=${item.decision_note}` : ""}
                    </div>
                  )}
                </li>
              ))}
            </ul>
          )}
        </section>
      ))}

      {error ? (
        <p style={{ color: "var(--danger)", marginTop: 8 }}>
          {t("审批数据加载失败：", "Failed to load approvals: ")}
          {error}
        </p>
      ) : null}

      <ApprovalActionDialog
        open={dialogOpen}
        action={dialogAction}
        approval={currentApproval}
        loading={actionLoadingId !== null}
        error={dialogError}
        onCancel={closeDialog}
        onConfirm={confirmDecision}
      />
    </article>
  );
}

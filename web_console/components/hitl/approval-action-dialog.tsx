"use client";

import { useEffect, useState } from "react";
import type { PendingApprovalItem } from "@/lib/api/tickets";
import { useI18n } from "@/lib/i18n";

export type ApprovalDialogAction = "approve" | "reject";

export function ApprovalActionDialog({
  open,
  action,
  approval,
  loading,
  error,
  onCancel,
  onConfirm
}: {
  open: boolean;
  action: ApprovalDialogAction;
  approval: PendingApprovalItem | null;
  loading: boolean;
  error: string | null;
  onCancel: () => void;
  onConfirm: (note: string) => Promise<void>;
}) {
  const { t } = useI18n();
  const [note, setNote] = useState("");

  useEffect(() => {
    if (!open) {
      setNote("");
    }
  }, [open]);

  if (!open || !approval) {
    return null;
  }

  const actionLabel = action === "approve" ? t("批准", "Approve") : t("拒绝", "Reject");

  return (
    <section className="card" style={{ marginTop: 12, borderColor: "var(--accent)" }}>
      <h4>{t("审批确认", "Approval Confirmation")}</h4>
      <p className="hint" style={{ marginTop: 8 }}>
        {t("动作", "Action")}: {approval.action_type} · ticket={approval.ticket_id}
      </p>
      <label className="ops-label" style={{ marginTop: 10 }}>
        <span>{t("审批备注", "Decision Note")}</span>
        <textarea
          className="ops-textarea"
          rows={3}
          value={note}
          onChange={(event) => setNote(event.target.value)}
          placeholder={t("可选：填写审批意见", "Optional note")}
        />
      </label>
      <div className="ops-split" style={{ marginTop: 10 }}>
        <button className="btn-primary" disabled={loading} onClick={() => void onConfirm(note)}>
          {loading ? t("处理中...", "Processing...") : actionLabel}
        </button>
        <button className="btn-ghost" disabled={loading} onClick={onCancel}>
          {t("取消", "Cancel")}
        </button>
      </div>
      {error ? (
        <p style={{ color: "var(--danger)", marginTop: 8 }}>
          {t("审批失败：", "Approval failed: ")}
          {error}
        </p>
      ) : null}
    </section>
  );
}

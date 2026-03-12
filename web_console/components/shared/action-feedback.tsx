"use client";

import { useI18n } from "@/lib/i18n";

export function ActionFeedback({
  variant,
  message
}: {
  variant: "success" | "error";
  message: string | null;
}) {
  const { t } = useI18n();
  if (!message) {
    return null;
  }

  return (
    <section
      className={`ops-feedback ops-feedback-${variant}`}
      role={variant === "error" ? "alert" : "status"}
      aria-live={variant === "error" ? "assertive" : "polite"}
    >
      <strong>{variant === "success" ? t("操作成功", "Operation Succeeded") : t("操作失败", "Operation Failed")}</strong>
      <p>{message}</p>
    </section>
  );
}

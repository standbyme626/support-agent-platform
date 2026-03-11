"use client";

import { useI18n } from "@/lib/i18n";
import type { KbSourceType } from "@/lib/api/kb";

export function SourceTypeBadge({ sourceType }: { sourceType: KbSourceType }) {
  const { t } = useI18n();
  const labels: Record<KbSourceType, string> = {
    faq: "FAQ",
    sop: "SOP",
    history_case: t("历史案例", "History Case")
  };

  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        height: 22,
        padding: "0 8px",
        borderRadius: 999,
        border: "1px solid var(--border)",
        color: "var(--muted)",
        fontSize: 12,
        fontWeight: 600
      }}
    >
      {labels[sourceType]}
    </span>
  );
}

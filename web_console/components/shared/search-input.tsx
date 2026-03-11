"use client";

import { useI18n } from "@/lib/i18n";

export function SearchInput({
  value,
  onChange,
  placeholder
}: {
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
}) {
  const { t } = useI18n();

  return (
    <input
      aria-label={t("搜索工单", "Search tickets")}
      value={value}
      placeholder={placeholder ?? t("搜索...", "Search...")}
      onChange={(event) => onChange(event.target.value)}
      style={{
        width: "100%",
        padding: "10px 12px",
        borderRadius: 8,
        border: "1px solid var(--border)",
        background: "#fff"
      }}
    />
  );
}

import type { KbSourceType } from "@/lib/api/kb";

const LABELS: Record<KbSourceType, string> = {
  faq: "FAQ",
  sop: "SOP",
  history_case: "History Case"
};

export function SourceTypeBadge({ sourceType }: { sourceType: KbSourceType }) {
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
      {LABELS[sourceType]}
    </span>
  );
}

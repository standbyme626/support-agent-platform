"use client";

import { useI18n } from "@/lib/i18n";

export type SlaSemanticState = "normal" | "warning" | "breached";

export function StatCard({
  title,
  value,
  hint,
  href,
  state = "normal"
}: {
  title: string;
  value: string | number;
  hint?: string;
  href?: string;
  state?: SlaSemanticState;
}) {
  const { t } = useI18n();
  const content = (
    <article className={`card state-${state}`}>
      <h3>{title}</h3>
      <div className="value">{value}</div>
      {hint ? <div className="hint">{hint}</div> : null}
    </article>
  );

  if (!href) {
    return content;
  }
  return (
    <a href={href} aria-label={`${t("打开", "Open")} ${title}`}>
      {content}
    </a>
  );
}

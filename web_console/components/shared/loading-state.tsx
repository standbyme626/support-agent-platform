"use client";

import { useI18n } from "@/lib/i18n";

export function LoadingState({ title }: { title: string }) {
  const { t } = useI18n();

  return (
    <section className="state-banner" role="status" aria-live="polite">
      <p>{title}</p>
      <p>{t("正在加载最新数据...", "Loading latest metrics...")}</p>
    </section>
  );
}

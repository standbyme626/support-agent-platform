"use client";

import { useI18n } from "@/lib/i18n";

export function ErrorState({
  title,
  message,
  onRetry
}: {
  title: string;
  message: string;
  onRetry?: () => void;
}) {
  const { t } = useI18n();

  return (
    <section className="state-banner" role="alert">
      <p>{title}</p>
      <p>{message}</p>
      {onRetry ? <button onClick={onRetry}>{t("重试", "Retry")}</button> : null}
    </section>
  );
}

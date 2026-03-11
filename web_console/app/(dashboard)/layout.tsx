"use client";

import { I18nProvider, useI18n, type Language } from "@/lib/i18n";

function DashboardShell({ children }: { children: React.ReactNode }) {
  const { language, setLanguage, t } = useI18n();

  return (
    <div className="app-shell">
      <header className="topbar">
        <h1>{t("客服运营控制台", "Support Ops Console")}</h1>
        <div className="topbar-actions">
          <nav>
            <a href="/">{t("总览", "Dashboard")}</a>
            <a href="/tickets">{t("工单", "Tickets")}</a>
            <a href="/traces">{t("链路", "Traces")}</a>
            <a href="/queues">{t("队列", "Queues")}</a>
            <a href="/kb/faq">{t("知识库", "Knowledge Base")}</a>
            <a href="/channels">{t("渠道", "Channels")}</a>
          </nav>
          <label className="lang-switch" htmlFor="language-switch">
            <span>{t("语言", "Language")}</span>
            <select
              id="language-switch"
              aria-label={t("切换语言", "Switch language")}
              value={language}
              onChange={(event) => setLanguage(event.target.value as Language)}
            >
              <option value="zh">{t("中文", "Chinese")}</option>
              <option value="en">{t("英文", "English")}</option>
            </select>
          </label>
        </div>
      </header>
      <main className="main-content">{children}</main>
    </div>
  );
}

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  return (
    <I18nProvider>
      <DashboardShell>{children}</DashboardShell>
    </I18nProvider>
  );
}

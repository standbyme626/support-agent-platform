"use client";

import { useSystemsSummary } from "@/lib/hooks/useSystemsSummary";
import { SystemCard } from "@/components/systems/system-card";
import { EmptyState } from "@/components/shared/empty-state";
import { ErrorState } from "@/components/shared/error-state";
import { LoadingState } from "@/components/shared/loading-state";
import { useI18n } from "@/lib/i18n";

export default function SystemsPage() {
  const { t } = useI18n();
  const { loading, error, data, totalSystems, refetch } = useSystemsSummary();

  if (loading) {
    return <LoadingState title={t("正在加载十系统概览...", "Loading ten systems overview...")} />;
  }

  if (error) {
    return (
      <ErrorState
        title={t("加载系统概览失败", "Failed to load systems overview")}
        message={error}
        onRetry={() => void refetch()}
      />
    );
  }

  if (!data || data.length === 0) {
    return (
      <EmptyState
        title={t("暂无系统数据", "No system data")}
        message={t("未检测到已注册的系统", "No registered systems detected")}
      />
    );
  }

  return (
    <section className="ops-page-stack">
      <h2 className="section-title">{t("十系统总览", "Ten Systems Overview")}</h2>
      <p className="ops-kicker">
        {t(
          "统一协议层下的十业务系统生命周期管理。点击查看系统详情与列表。",
          "Ten business systems with unified protocol layer. Click to view details."
        )}
      </p>
      <div className="stats-summary">
        <span className="stat-badge">
          {t("共", "Total")} {totalSystems} {t("个系统", "systems")}
        </span>
        <span className="stat-badge">
          {t("实体总数", "Total entities")}: {data.reduce((sum, s) => sum + s.total_entities, 0)}
        </span>
      </div>
      <div className="systems-grid">
        {data.map((system) => (
          <SystemCard key={system.system} system={system} />
        ))}
      </div>
    </section>
  );
}

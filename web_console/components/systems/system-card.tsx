"use client";

import type { SystemSummary } from "@/lib/api/systems";
import { useI18n } from "@/lib/i18n";

const SYSTEM_LABELS: Record<string, { name: string; desc: string }> = {
  ticket: { name: "工单系统", desc: "故障上报与处理" },
  procurement: { name: "采购系统", desc: "采购申请与审批" },
  finance: { name: "财务系统", desc: "发票与付款" },
  approval: { name: "审批系统", desc: "通用审批流程" },
  hr: { name: "HR系统", desc: "员工入职管理" },
  asset: { name: "资产系统", desc: "IT资产全生命周期" },
  kb: { name: "知识库", desc: "文档与SOP管理" },
  crm: { name: "CRM系统", desc: "客户关系管理" },
  project: { name: "项目系统", desc: "项目进度跟踪" },
  supply_chain: { name: "供应链", desc: "订单与物流" },
};

const STATUS_COLORS: Record<string, string> = {
  inventory: "pill-info",
  assigned: "pill-success",
  maintenance: "pill-warning",
  retired: "pill-muted",
  disposed: "pill-muted",
  draft: "pill-info",
  review: "pill-warning",
  published: "pill-success",
  archived: "pill-muted",
  new: "pill-info",
  in_progress: "pill-warning",
  resolved: "pill-success",
  closed: "pill-muted",
  pending_approval: "pill-warning",
  planning: "pill-info",
  active: "pill-warning",
  on_hold: "pill-warning",
  completed: "pill-success",
  cancelled: "pill-muted",
  pending: "pill-info",
  confirmed: "pill-info",
  shipped: "pill-warning",
  in_transit: "pill-warning",
  delivered: "pill-success",
};

export function SystemCard({ system }: { system: SystemSummary }) {
  const { t } = useI18n();
  const meta = SYSTEM_LABELS[system.system] || { name: system.system, desc: system.entity_type };

  return (
    <article className="card system-card">
      <header className="card-header">
        <div className="system-title">
          <span className="system-key">{system.system.toUpperCase()}</span>
          <h3>{meta.name}</h3>
        </div>
        <span className="entity-count">{system.total_entities}</span>
      </header>
      <div className="card-body">
        <p className="system-desc">{meta.desc}</p>
        <div className="system-meta">
          <span className="meta-label">ID前缀:</span>
          <code>{system.id_prefix}</code>
        </div>
        <div className="system-meta">
          <span className="meta-label">生命周期:</span>
        </div>
        <div className="lifecycle-flow">
          {system.lifecycle.map((status, idx) => (
            <span key={status} className={`lifecycle-step ${STATUS_COLORS[status] || "pill-normal"}`}>
              {status}
              {idx < system.lifecycle.length - 1 && <span className="arrow">→</span>}
            </span>
          ))}
        </div>
        {system.actions.length > 0 && (
          <div className="system-meta" style={{ marginTop: 8 }}>
            <span className="meta-label">支持动作:</span>
            <div className="action-tags">
              {system.actions.map((action) => (
                <span key={action} className="action-tag">
                  {action}
                </span>
              ))}
            </div>
          </div>
        )}
        {system.error && (
          <div className="system-error">
            <span className="pill-breached">加载失败</span>
          </div>
        )}
      </div>
      <footer className="card-footer">
        <a href={`/api/systems/${system.system}`} className="btn-ghost">
          {t("查看列表", "View List")}
        </a>
      </footer>
    </article>
  );
}

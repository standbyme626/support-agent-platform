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
  open: "pill-info",
  pending: "pill-warning",
  in_progress: "pill-warning",
  resolved: "pill-success",
  closed: "pill-muted",
  escalated: "pill-warning",
  pending_approval: "pill-warning",
  approved: "pill-success",
  rejected: "pill-muted",
  planning: "pill-info",
  active: "pill-warning",
  on_hold: "pill-warning",
  completed: "pill-success",
  cancelled: "pill-muted",
  confirmed: "pill-info",
  shipped: "pill-warning",
  in_transit: "pill-warning",
  delivered: "pill-success",
};

const STATUS_LABELS: Record<string, { zh: string; en: string }> = {
  inventory: { zh: "库存", en: "Inventory" },
  assigned: { zh: "已分配", en: "Assigned" },
  maintenance: { zh: "维护中", en: "Maintenance" },
  retired: { zh: "已退役", en: "Retired" },
  disposed: { zh: "已处置", en: "Disposed" },
  draft: { zh: "草稿", en: "Draft" },
  review: { zh: "审核中", en: "Review" },
  published: { zh: "已发布", en: "Published" },
  archived: { zh: "已归档", en: "Archived" },
  new: { zh: "新建", en: "New" },
  open: { zh: "待处理", en: "Open" },
  pending: { zh: "等待中", en: "Pending" },
  in_progress: { zh: "处理中", en: "In Progress" },
  resolved: { zh: "已解决", en: "Resolved" },
  closed: { zh: "已关闭", en: "Closed" },
  escalated: { zh: "已升级", en: "Escalated" },
  pending_approval: { zh: "待审批", en: "Pending Approval" },
  approved: { zh: "已批准", en: "Approved" },
  rejected: { zh: "已拒绝", en: "Rejected" },
  planning: { zh: "规划中", en: "Planning" },
  active: { zh: "进行中", en: "Active" },
  on_hold: { zh: "暂停", en: "On Hold" },
  completed: { zh: "已完成", en: "Completed" },
  cancelled: { zh: "已取消", en: "Cancelled" },
  confirmed: { zh: "已确认", en: "Confirmed" },
  shipped: { zh: "已发货", en: "Shipped" },
  in_transit: { zh: "运输中", en: "In Transit" },
  delivered: { zh: "已送达", en: "Delivered" },
};

const ACTION_LABELS: Record<string, { zh: string; en: string }> = {
  assign: { zh: "分配", en: "Assign" },
  return: { zh: "归还", en: "Return" },
  maintenance: { zh: "维护", en: "Maintenance" },
  retire: { zh: "退役", en: "Retire" },
  dispose: { zh: "处置", en: "Dispose" },
  submit: { zh: "提交", en: "Submit" },
  approve: { zh: "批准", en: "Approve" },
  reject: { zh: "拒绝", en: "Reject" },
  publish: { zh: "发布", en: "Publish" },
  archive: { zh: "归档", en: "Archive" },
  start: { zh: "开始", en: "Start" },
  pause: { zh: "暂停", en: "Pause" },
  complete: { zh: "完成", en: "Complete" },
  cancel: { zh: "取消", en: "Cancel" },
  ship: { zh: "发货", en: "Ship" },
  deliver: { zh: "送达", en: "Deliver" },
};

function getStatusLabel(status: string, lang: string): string {
  const labels = STATUS_LABELS[status];
  if (!labels) return status;
  return lang === "zh" ? `${labels.zh} (${status})` : `${labels.en} (${status})`;
}

function getActionLabel(action: string, lang: string): string {
  const labels = ACTION_LABELS[action];
  if (!labels) return action;
  return lang === "zh" ? labels.zh : labels.en;
}

export function SystemCard({ system }: { system: SystemSummary }) {
  const { t, language } = useI18n();
  const meta = SYSTEM_LABELS[system.system] || { name: system.system, desc: system.entity_type };
  const lang = language || "zh";

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
          <span className="meta-label">{t("ID前缀", "ID Prefix")}:</span>
          <code>{system.id_prefix}</code>
        </div>
        <div className="system-meta">
          <span className="meta-label">{t("生命周期", "Lifecycle")}:</span>
        </div>
        <div className="lifecycle-flow">
          {system.lifecycle.map((status, idx) => (
            <span key={status} className={`lifecycle-step ${STATUS_COLORS[status] || "pill-normal"}`}>
              {getStatusLabel(status, lang)}
              {idx < system.lifecycle.length - 1 && <span className="arrow">→</span>}
            </span>
          ))}
        </div>
        {system.actions.length > 0 && (
          <div className="system-meta" style={{ marginTop: 8 }}>
            <span className="meta-label">{t("支持动作", "Actions")}:</span>
            <div className="action-tags">
              {system.actions.map((action) => (
                <span key={action} className="action-tag">
                  {getActionLabel(action, lang)}
                </span>
              ))}
            </div>
          </div>
        )}
        {system.error && (
          <div className="system-error">
            <span className="pill-breached">{t("加载失败", "Load Failed")}</span>
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

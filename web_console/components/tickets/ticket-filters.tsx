"use client";

import { useI18n } from "@/lib/i18n";
import { SearchInput } from "@/components/shared/search-input";

export type TicketFiltersValue = {
  q?: string;
  status?: string;
  priority?: string;
  queue?: string;
  assignee?: string;
  channel?: string;
  handoff_state?: string;
  service_type?: string;
  risk_level?: string;
  created_from?: string;
  created_to?: string;
  sla_state?: string;
};

function SelectField({
  label,
  allLabel,
  value,
  options,
  onChange
}: {
  label: string;
  allLabel?: string;
  value?: string;
  options: Array<{ label: string; value: string }>;
  onChange: (value: string) => void;
}) {
  return (
    <label style={{ display: "flex", flexDirection: "column", gap: 4 }}>
      <span style={{ color: "var(--muted)", fontSize: 12 }}>{label}</span>
      <select
        value={value ?? ""}
        onChange={(event) => onChange(event.target.value)}
        style={{
          height: 36,
          borderRadius: 8,
          border: "1px solid var(--border)",
          background: "#fff",
          padding: "0 10px"
        }}
      >
        <option value="">{allLabel ?? "All"}</option>
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
    </label>
  );
}

export function TicketFilters({
  value,
  assignees,
  onChange,
  onClear
}: {
  value: TicketFiltersValue;
  assignees: string[];
  onChange: (patch: Partial<TicketFiltersValue>) => void;
  onClear: () => void;
}) {
  const { t } = useI18n();

  return (
    <section className="card">
      <h3>{t("工单筛选", "Ticket Filters")}</h3>
      <div style={{ marginTop: 10 }}>
        <SearchInput
          value={value.q ?? ""}
          placeholder={t("搜索标题和最新消息", "Search title and latest message")}
          onChange={(q) => onChange({ q })}
        />
      </div>
      <div
        style={{
          marginTop: 10,
          display: "grid",
          gridTemplateColumns: "repeat(auto-fill, minmax(170px, 1fr))",
          gap: 10
        }}
      >
        <SelectField
          label={t("状态", "Status")}
          allLabel={t("全部", "All")}
          value={value.status}
          onChange={(status) => onChange({ status })}
          options={[
            { label: t("待处理", "Open"), value: "open" },
            { label: t("处理中", "Pending"), value: "pending" },
            { label: t("已升级", "Escalated"), value: "escalated" },
            { label: t("已解决", "Resolved"), value: "resolved" },
            { label: t("已关闭", "Closed"), value: "closed" }
          ]}
        />
        <SelectField
          label={t("优先级", "Priority")}
          allLabel={t("全部", "All")}
          value={value.priority}
          onChange={(priority) => onChange({ priority })}
          options={[
            { label: "P0", value: "P0" },
            { label: "P1", value: "P1" },
            { label: "P2", value: "P2" },
            { label: "P3", value: "P3" }
          ]}
        />
        <SelectField
          label={t("队列", "Queue")}
          allLabel={t("全部", "All")}
          value={value.queue}
          onChange={(queue) => onChange({ queue })}
          options={[
            { label: "support", value: "support" },
            { label: "billing", value: "billing" },
            { label: "complaints", value: "complaints" }
          ]}
        />
        <SelectField
          label={t("处理人", "Assignee")}
          allLabel={t("全部", "All")}
          value={value.assignee}
          onChange={(assignee) => onChange({ assignee })}
          options={assignees.map((item) => ({ label: item, value: item }))}
        />
        <SelectField
          label={t("渠道", "Channel")}
          allLabel={t("全部", "All")}
          value={value.channel}
          onChange={(channel) => onChange({ channel })}
          options={[
            { label: "wecom", value: "wecom" },
            { label: "telegram", value: "telegram" },
            { label: "feishu", value: "feishu" }
          ]}
        />
        <SelectField
          label={t("接管", "Handoff")}
          allLabel={t("全部", "All")}
          value={value.handoff_state}
          onChange={(handoff_state) => onChange({ handoff_state })}
          options={[
            { label: t("无", "none"), value: "none" },
            { label: t("已请求", "requested"), value: "requested" },
            { label: t("已接受", "accepted"), value: "accepted" }
          ]}
        />
        <SelectField
          label={t("服务类型", "Service Type")}
          allLabel={t("全部", "All")}
          value={value.service_type}
          onChange={(service_type) => onChange({ service_type })}
          options={[
            { label: t("报修", "repair"), value: "repair" },
            { label: t("停车", "parking"), value: "parking" },
            { label: t("投诉", "complaint"), value: "complaint" },
            { label: t("账单", "billing"), value: "billing" }
          ]}
        />
        <SelectField
          label={t("风险", "Risk")}
          allLabel={t("全部", "All")}
          value={value.risk_level}
          onChange={(risk_level) => onChange({ risk_level })}
          options={[
            { label: t("低", "low"), value: "low" },
            { label: t("中", "medium"), value: "medium" },
            { label: t("高", "high"), value: "high" },
            { label: t("紧急", "critical"), value: "critical" }
          ]}
        />
        <SelectField
          label="SLA"
          allLabel={t("全部", "All")}
          value={value.sla_state}
          onChange={(sla_state) => onChange({ sla_state })}
          options={[
            { label: t("正常", "normal"), value: "normal" },
            { label: t("预警", "warning"), value: "warning" },
            { label: t("超时", "breached"), value: "breached" }
          ]}
        />
        <label style={{ display: "flex", flexDirection: "column", gap: 4 }}>
          <span style={{ color: "var(--muted)", fontSize: 12 }}>{t("创建起始", "Created From")}</span>
          <input
            type="date"
            value={value.created_from ?? ""}
            onChange={(event) => onChange({ created_from: event.target.value })}
            style={{ height: 36, borderRadius: 8, border: "1px solid var(--border)", padding: "0 10px" }}
          />
        </label>
        <label style={{ display: "flex", flexDirection: "column", gap: 4 }}>
          <span style={{ color: "var(--muted)", fontSize: 12 }}>{t("创建截止", "Created To")}</span>
          <input
            type="date"
            value={value.created_to ?? ""}
            onChange={(event) => onChange({ created_to: event.target.value })}
            style={{ height: 36, borderRadius: 8, border: "1px solid var(--border)", padding: "0 10px" }}
          />
        </label>
      </div>
      <div style={{ marginTop: 10 }}>
        <button
          onClick={onClear}
          style={{
            height: 34,
            borderRadius: 8,
            border: "1px solid var(--border)",
            background: "#fff",
            padding: "0 12px",
            cursor: "pointer"
          }}
        >
          {t("清空筛选", "Clear Filters")}
        </button>
      </div>
    </section>
  );
}

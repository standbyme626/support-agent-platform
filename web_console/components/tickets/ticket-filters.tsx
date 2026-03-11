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
  value,
  options,
  onChange
}: {
  label: string;
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
        <option value="">All</option>
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
  return (
    <section className="card">
      <h3>Ticket Filters</h3>
      <div style={{ marginTop: 10 }}>
        <SearchInput
          value={value.q ?? ""}
          placeholder="Search title and latest message"
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
          label="Status"
          value={value.status}
          onChange={(status) => onChange({ status })}
          options={[
            { label: "Open", value: "open" },
            { label: "Pending", value: "pending" },
            { label: "Escalated", value: "escalated" },
            { label: "Resolved", value: "resolved" },
            { label: "Closed", value: "closed" }
          ]}
        />
        <SelectField
          label="Priority"
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
          label="Queue"
          value={value.queue}
          onChange={(queue) => onChange({ queue })}
          options={[
            { label: "support", value: "support" },
            { label: "billing", value: "billing" },
            { label: "complaints", value: "complaints" }
          ]}
        />
        <SelectField
          label="Assignee"
          value={value.assignee}
          onChange={(assignee) => onChange({ assignee })}
          options={assignees.map((item) => ({ label: item, value: item }))}
        />
        <SelectField
          label="Channel"
          value={value.channel}
          onChange={(channel) => onChange({ channel })}
          options={[
            { label: "wecom", value: "wecom" },
            { label: "telegram", value: "telegram" },
            { label: "feishu", value: "feishu" }
          ]}
        />
        <SelectField
          label="Handoff"
          value={value.handoff_state}
          onChange={(handoff_state) => onChange({ handoff_state })}
          options={[
            { label: "none", value: "none" },
            { label: "requested", value: "requested" },
            { label: "accepted", value: "accepted" }
          ]}
        />
        <SelectField
          label="Service Type"
          value={value.service_type}
          onChange={(service_type) => onChange({ service_type })}
          options={[
            { label: "repair", value: "repair" },
            { label: "parking", value: "parking" },
            { label: "complaint", value: "complaint" },
            { label: "billing", value: "billing" }
          ]}
        />
        <SelectField
          label="Risk"
          value={value.risk_level}
          onChange={(risk_level) => onChange({ risk_level })}
          options={[
            { label: "low", value: "low" },
            { label: "medium", value: "medium" },
            { label: "high", value: "high" },
            { label: "critical", value: "critical" }
          ]}
        />
        <SelectField
          label="SLA"
          value={value.sla_state}
          onChange={(sla_state) => onChange({ sla_state })}
          options={[
            { label: "normal", value: "normal" },
            { label: "warning", value: "warning" },
            { label: "breached", value: "breached" }
          ]}
        />
        <label style={{ display: "flex", flexDirection: "column", gap: 4 }}>
          <span style={{ color: "var(--muted)", fontSize: 12 }}>Created From</span>
          <input
            type="date"
            value={value.created_from ?? ""}
            onChange={(event) => onChange({ created_from: event.target.value })}
            style={{ height: 36, borderRadius: 8, border: "1px solid var(--border)", padding: "0 10px" }}
          />
        </label>
        <label style={{ display: "flex", flexDirection: "column", gap: 4 }}>
          <span style={{ color: "var(--muted)", fontSize: 12 }}>Created To</span>
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
          Clear Filters
        </button>
      </div>
    </section>
  );
}

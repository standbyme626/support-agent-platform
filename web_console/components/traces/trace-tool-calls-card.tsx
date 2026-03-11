"use client";

import { useI18n } from "@/lib/i18n";

export function TraceToolCallsCard({ toolCalls }: { toolCalls: string[] }) {
  const { t } = useI18n();

  return (
    <article className="card">
      <h3>{t("工具调用", "Tool Calls")}</h3>
      {toolCalls.length === 0 ? (
        <p style={{ color: "var(--muted)", marginTop: 10 }}>{t("暂无工具调用记录。", "No tool calls recorded.")}</p>
      ) : (
        <ul className="list" style={{ marginTop: 10 }}>
          {toolCalls.map((toolName, index) => (
            <li className="list-item" key={`${toolName}-${index}`}>
              <strong>{toolName}</strong>
            </li>
          ))}
        </ul>
      )}
    </article>
  );
}

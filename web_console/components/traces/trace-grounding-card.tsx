"use client";

import { useI18n } from "@/lib/i18n";

export function TraceGroundingCard({
  retrievedDocs,
  summary
}: {
  retrievedDocs: string[];
  summary: string;
}) {
  const { t } = useI18n();

  return (
    <article className="card">
      <h3>{t("Grounding 与摘要", "Grounding & Summary")}</h3>
      <div style={{ marginTop: 10, color: "var(--muted)", fontSize: 13 }}>
        {summary || t("暂无摘要输出。", "No summary output.")}
      </div>
      <h4 style={{ marginTop: 12, marginBottom: 6, fontSize: 14 }}>{t("召回文档", "Retrieved Docs")}</h4>
      {retrievedDocs.length === 0 ? (
        <p style={{ color: "var(--muted)", marginTop: 0 }}>{t("该 Trace 暂无 grounding 文档。", "No grounding docs in trace.")}</p>
      ) : (
        <ul className="list">
          {retrievedDocs.map((docId, index) => (
            <li className="list-item" key={`${docId}-${index}`}>
              <strong>{docId}</strong>
            </li>
          ))}
        </ul>
      )}
    </article>
  );
}

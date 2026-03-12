"use client";

import { useI18n } from "@/lib/i18n";
import type { TraceGroundingSource } from "@/lib/api/traces";

export function TraceGroundingCard({
  retrievedDocs,
  groundingSources,
  summary
}: {
  retrievedDocs: string[];
  groundingSources: TraceGroundingSource[];
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
      {groundingSources.length > 0 ? (
        <ul className="list">
          {groundingSources.map((item, index) => (
            <li className="list-item" key={`${item.source_id ?? "source"}-${index}`}>
              <strong>{item.title ?? item.source_id ?? t("未命名来源", "Untitled source")}</strong>
              <div style={{ color: "var(--muted)", fontSize: 13 }}>
                {t("来源", "Source")}={item.source_type ?? "-"} · {t("排名", "Rank")}={item.rank ?? "-"} ·{" "}
                {t("分数", "Score")}={item.score ?? "-"}
              </div>
              {item.reason ? (
                <div style={{ color: "var(--muted)", fontSize: 12 }}>{item.reason}</div>
              ) : null}
              {item.snippet ? (
                <div style={{ color: "var(--muted)", fontSize: 12 }}>{item.snippet}</div>
              ) : null}
            </li>
          ))}
        </ul>
      ) : retrievedDocs.length === 0 ? (
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

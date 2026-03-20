"use client";

import type { KbItem } from "@/lib/api/kb";
import { SourceTypeBadge } from "@/components/kb/source-type-badge";
import { useI18n } from "@/lib/i18n";

function toDateTimeText(value: string | null) {
  if (!value) {
    return "-";
  }
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }
  return parsed.toLocaleString();
}

function toMetadataString(metadata: Record<string, unknown>, key: string) {
  const value = metadata[key];
  return typeof value === "string" && value.trim().length > 0 ? value.trim() : "";
}

export function KbTable({
  rows,
  page,
  pageSize,
  total,
  actionLoading,
  onPageChange,
  onEdit,
  onDelete
}: {
  rows: KbItem[];
  page: number;
  pageSize: number;
  total: number;
  actionLoading: boolean;
  onPageChange: (nextPage: number) => void;
  onEdit: (item: KbItem) => void;
  onDelete: (item: KbItem) => void;
}) {
  const { t } = useI18n();
  const pageCount = Math.max(1, Math.ceil(total / pageSize));

  return (
    <section className="card">
      <h3>{t("知识库文档", "KB Documents")}</h3>
      <div style={{ overflowX: "auto", marginTop: 10 }}>
        <table className="table">
          <thead>
              <tr>
                <th>{t("文档 ID", "Doc ID")}</th>
                <th>{t("类型", "Type")}</th>
                <th>{t("标题", "Title")}</th>
                <th>{t("来源", "Source")}</th>
                <th>{t("标签", "Tags")}</th>
                <th>{t("更新时间", "Updated")}</th>
                <th>{t("操作", "Actions")}</th>
              </tr>
          </thead>
          <tbody>
            {rows.map((item) => (
              <tr key={item.doc_id}>
                <td>{item.doc_id}</td>
                <td>
                  <SourceTypeBadge sourceType={item.source_type} />
                </td>
                <td>
                  <div style={{ fontWeight: 600 }}>{item.title}</div>
                  <div style={{ color: "var(--muted)", fontSize: 12 }}>{item.content}</div>
                </td>
                <td>
                  {(() => {
                    const source = toMetadataString(item.metadata, "source_dataset");
                    const license = toMetadataString(item.metadata, "license");
                    const sourceUrl = toMetadataString(item.metadata, "source_url");
                    const sourceText = [source, license].filter((text) => text.length > 0).join(" · ");
                    if (!sourceText && !sourceUrl) {
                      return "-";
                    }
                    return (
                      <div style={{ fontSize: 12, color: "var(--muted)" }}>
                        <div>{sourceText || "-"}</div>
                        {sourceUrl ? (
                          <a href={sourceUrl} target="_blank" rel="noreferrer">
                            {t("数据来源链接", "Source Link")}
                          </a>
                        ) : null}
                      </div>
                    );
                  })()}
                </td>
                <td>{item.tags.join(", ") || "-"}</td>
                <td>{toDateTimeText(item.updated_at)}</td>
                <td>
                  <div style={{ display: "flex", gap: 8 }}>
                    <button
                      className="btn-ghost"
                      onClick={() => onEdit(item)}
                      aria-label={`edit_${item.doc_id}`}
                      disabled={actionLoading}
                    >
                      {t("编辑", "Edit")}
                    </button>
                    <button
                      className="btn-ghost"
                      onClick={() => onDelete(item)}
                      aria-label={`delete_${item.doc_id}`}
                      disabled={actionLoading}
                    >
                      {t("删除", "Delete")}
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div
        style={{
          marginTop: 10,
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center"
        }}
      >
        <small>
          {t("页", "page")} {page}/{pageCount} · {t("总计", "total")} {total}
        </small>
        <div style={{ display: "flex", gap: 8 }}>
          <button
            className="btn-ghost"
            onClick={() => onPageChange(Math.max(1, page - 1))}
            disabled={page <= 1}
          >
            {t("上一页", "Prev")}
          </button>
          <button
            className="btn-ghost"
            onClick={() => onPageChange(Math.min(pageCount, page + 1))}
            disabled={page >= pageCount}
          >
            {t("下一页", "Next")}
          </button>
        </div>
      </div>
    </section>
  );
}

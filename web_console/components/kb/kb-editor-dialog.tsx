"use client";

import { useEffect, useState } from "react";
import type { KbItem, KbSourceType } from "@/lib/api/kb";
import { SourceTypeBadge } from "@/components/kb/source-type-badge";
import { useI18n } from "@/lib/i18n";

type EditorSubmitPayload = {
  doc_id?: string;
  title: string;
  content: string;
  tags: string[];
};

export function KbEditorDialog({
  open,
  sourceType,
  initialValue,
  submitting,
  error,
  onCancel,
  onSubmit
}: {
  open: boolean;
  sourceType: KbSourceType;
  initialValue: KbItem | null;
  submitting: boolean;
  error: string | null;
  onCancel: () => void;
  onSubmit: (payload: EditorSubmitPayload) => void;
}) {
  const { t } = useI18n();
  const [docId, setDocId] = useState("");
  const [title, setTitle] = useState("");
  const [content, setContent] = useState("");
  const [tagsText, setTagsText] = useState("");
  const isEditMode = Boolean(initialValue);

  useEffect(() => {
    if (!open) {
      return;
    }
    setDocId(initialValue?.doc_id ?? "");
    setTitle(initialValue?.title ?? "");
    setContent(initialValue?.content ?? "");
    setTagsText(initialValue?.tags.join(", ") ?? "");
  }, [open, initialValue]);

  if (!open) {
    return null;
  }

  return (
    <section className="card" style={{ marginTop: 12 }}>
      <h3>{isEditMode ? t("编辑知识库文档", "Edit KB Document") : t("新建知识库文档", "Create KB Document")}</h3>
      <div style={{ marginTop: 8 }}>
        <SourceTypeBadge sourceType={sourceType} />
      </div>
      <div
        style={{
          marginTop: 10,
          display: "grid",
          gap: 10,
          gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))"
        }}
      >
        <label style={{ display: "flex", flexDirection: "column", gap: 4 }}>
          <span style={{ color: "var(--muted)", fontSize: 12 }}>{t("文档 ID", "Doc ID")}</span>
          <input
            value={docId}
            onChange={(event) => setDocId(event.target.value)}
            disabled={isEditMode || submitting}
            placeholder={isEditMode ? initialValue?.doc_id : "doc_custom_001"}
            style={{ height: 34, borderRadius: 8, border: "1px solid var(--border)", padding: "0 10px" }}
            aria-label="kb_doc_id"
          />
        </label>
        <label style={{ display: "flex", flexDirection: "column", gap: 4 }}>
          <span style={{ color: "var(--muted)", fontSize: 12 }}>{t("标题", "Title")}</span>
          <input
            value={title}
            onChange={(event) => setTitle(event.target.value)}
            disabled={submitting}
            style={{ height: 34, borderRadius: 8, border: "1px solid var(--border)", padding: "0 10px" }}
            aria-label="kb_title"
          />
        </label>
      </div>
      <label style={{ display: "flex", flexDirection: "column", gap: 4, marginTop: 10 }}>
        <span style={{ color: "var(--muted)", fontSize: 12 }}>{t("内容", "Content")}</span>
        <textarea
          value={content}
          onChange={(event) => setContent(event.target.value)}
          disabled={submitting}
          rows={4}
          style={{ borderRadius: 8, border: "1px solid var(--border)", padding: "8px 10px", resize: "vertical" }}
          aria-label="kb_content"
        />
      </label>
      <label style={{ display: "flex", flexDirection: "column", gap: 4, marginTop: 10 }}>
        <span style={{ color: "var(--muted)", fontSize: 12 }}>{t("标签（逗号分隔）", "Tags (comma separated)")}</span>
        <input
          value={tagsText}
          onChange={(event) => setTagsText(event.target.value)}
          disabled={submitting}
          style={{ height: 34, borderRadius: 8, border: "1px solid var(--border)", padding: "0 10px" }}
          aria-label="kb_tags"
        />
      </label>
      {error ? (
        <div role="alert" style={{ marginTop: 10, color: "var(--danger)" }}>
          {error}
        </div>
      ) : null}
      <div style={{ marginTop: 12, display: "flex", gap: 8 }}>
        <button
          className="btn-primary"
          onClick={() =>
            onSubmit({
              doc_id: docId.trim() || undefined,
              title: title.trim(),
              content: content.trim(),
              tags: tagsText
                .split(",")
                .map((item) => item.trim())
                .filter((item) => item.length > 0)
            })
          }
          disabled={submitting}
          aria-label="kb_submit"
        >
          {submitting
            ? t("提交中...", "Submitting...")
            : isEditMode
              ? t("保存修改", "Save Changes")
              : t("创建文档", "Create Document")}
        </button>
        <button className="btn-ghost" onClick={onCancel} disabled={submitting} aria-label="kb_cancel">
          {t("取消", "Cancel")}
        </button>
      </div>
    </section>
  );
}

"use client";

import { useState } from "react";
import { KbEditorDialog } from "@/components/kb/kb-editor-dialog";
import { KbTable } from "@/components/kb/kb-table";
import { EmptyState } from "@/components/shared/empty-state";
import { ErrorState } from "@/components/shared/error-state";
import { LoadingState } from "@/components/shared/loading-state";
import { useKB } from "@/lib/hooks/useKB";
import type { KbItem, KbSourceType } from "@/lib/api/kb";

const KB_NAV_ITEMS: Array<{ href: string; label: string; sourceType: KbSourceType }> = [
  { href: "/kb/faq", label: "FAQ", sourceType: "faq" },
  { href: "/kb/sop", label: "SOP", sourceType: "sop" },
  { href: "/kb/cases", label: "History Cases", sourceType: "history_case" }
];

function sourceTypeTitle(sourceType: KbSourceType) {
  if (sourceType === "faq") {
    return "KB FAQ";
  }
  if (sourceType === "sop") {
    return "KB SOP";
  }
  return "KB History Cases";
}

export function KbWorkspacePage({ sourceType }: { sourceType: KbSourceType }) {
  const kb = useKB(sourceType);
  const [editorOpen, setEditorOpen] = useState(false);
  const [editingItem, setEditingItem] = useState<KbItem | null>(null);
  const [deleteCandidate, setDeleteCandidate] = useState<KbItem | null>(null);

  function openCreateDialog() {
    kb.clearActionState();
    setEditingItem(null);
    setEditorOpen(true);
  }

  function openEditDialog(item: KbItem) {
    kb.clearActionState();
    setEditingItem(item);
    setEditorOpen(true);
  }

  async function handleEditorSubmit(payload: {
    doc_id?: string;
    title: string;
    content: string;
    tags: string[];
  }) {
    if (editingItem) {
      await kb.updateDoc(editingItem.doc_id, {
        title: payload.title,
        content: payload.content,
        tags: payload.tags
      });
    } else {
      await kb.createDoc(payload);
    }
    setEditorOpen(false);
    setEditingItem(null);
  }

  async function confirmDelete() {
    if (!deleteCandidate) {
      return;
    }
    await kb.deleteDoc(deleteCandidate.doc_id);
    setDeleteCandidate(null);
  }

  if (kb.loading) {
    return <LoadingState title="KB list is syncing." />;
  }

  if (kb.error) {
    return <ErrorState title="Failed to load KB documents." message={kb.error} onRetry={() => void kb.refetch()} />;
  }

  return (
    <section>
      <h2 className="section-title">{sourceTypeTitle(sourceType)}</h2>
      <nav style={{ display: "flex", gap: 10, marginTop: 8, flexWrap: "wrap" }}>
        {KB_NAV_ITEMS.map((item) => (
          <a
            key={item.href}
            href={item.href}
            className={item.sourceType === sourceType ? "btn-primary" : "btn-ghost"}
            aria-current={item.sourceType === sourceType ? "page" : undefined}
          >
            {item.label}
          </a>
        ))}
      </nav>

      <article className="card" style={{ marginTop: 12 }}>
        <h3>Filters & Actions</h3>
        <div
          style={{
            marginTop: 10,
            display: "grid",
            gap: 8,
            gridTemplateColumns: "minmax(220px, 2fr) auto auto"
          }}
        >
          <input
            value={kb.q}
            onChange={(event) => kb.setQuery(event.target.value)}
            placeholder="Search in title/content"
            aria-label="kb_search"
            style={{ height: 34, borderRadius: 8, border: "1px solid var(--border)", padding: "0 10px" }}
          />
          <button className="btn-ghost" onClick={kb.clearQuery}>
            Clear
          </button>
          <button className="btn-primary" onClick={openCreateDialog} aria-label="kb_add_doc">
            Add Document
          </button>
        </div>
      </article>

      {kb.actionSuccess ? (
        <section className="state-banner" role="status" style={{ marginTop: 12 }}>
          <p>{kb.actionSuccess}</p>
        </section>
      ) : null}
      {kb.actionError && !editorOpen ? (
        <section className="state-banner" role="alert" style={{ marginTop: 12 }}>
          <p>{kb.actionError}</p>
        </section>
      ) : null}

      <KbEditorDialog
        open={editorOpen}
        sourceType={sourceType}
        initialValue={editingItem}
        submitting={kb.actionLoading}
        error={kb.actionError}
        onCancel={() => {
          setEditorOpen(false);
          setEditingItem(null);
          kb.clearActionState();
        }}
        onSubmit={(payload) => void handleEditorSubmit(payload)}
      />

      {deleteCandidate ? (
        <article className="card" style={{ marginTop: 12 }}>
          <h3>Confirm Delete</h3>
          <p style={{ marginTop: 8 }}>
            Delete <strong>{deleteCandidate.doc_id}</strong>?
          </p>
          <div style={{ marginTop: 10, display: "flex", gap: 8 }}>
            <button className="btn-primary" onClick={() => void confirmDelete()} disabled={kb.actionLoading}>
              Confirm Delete
            </button>
            <button
              className="btn-ghost"
              onClick={() => {
                setDeleteCandidate(null);
                kb.clearActionState();
              }}
              disabled={kb.actionLoading}
            >
              Cancel
            </button>
          </div>
        </article>
      ) : null}

      <div style={{ marginTop: 12 }}>
        {kb.items.length === 0 ? (
          <EmptyState
            title="No KB documents matched."
            message="Try another keyword or create a new KB document."
          />
        ) : (
          <KbTable
            rows={kb.items}
            page={kb.page}
            pageSize={kb.pageSize}
            total={kb.total}
            actionLoading={kb.actionLoading}
            onPageChange={kb.setPage}
            onEdit={openEditDialog}
            onDelete={(item) => setDeleteCandidate(item)}
          />
        )}
      </div>
    </section>
  );
}

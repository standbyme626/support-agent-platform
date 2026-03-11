import type { KbItem } from "@/lib/api/kb";
import { SourceTypeBadge } from "@/components/kb/source-type-badge";

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
  const pageCount = Math.max(1, Math.ceil(total / pageSize));

  return (
    <section className="card">
      <h3>KB Documents</h3>
      <div style={{ overflowX: "auto", marginTop: 10 }}>
        <table className="table">
          <thead>
            <tr>
              <th>Doc ID</th>
              <th>Type</th>
              <th>Title</th>
              <th>Tags</th>
              <th>Updated</th>
              <th>Actions</th>
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
                      Edit
                    </button>
                    <button
                      className="btn-ghost"
                      onClick={() => onDelete(item)}
                      aria-label={`delete_${item.doc_id}`}
                      disabled={actionLoading}
                    >
                      Delete
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
          page {page}/{pageCount} · total {total}
        </small>
        <div style={{ display: "flex", gap: 8 }}>
          <button
            className="btn-ghost"
            onClick={() => onPageChange(Math.max(1, page - 1))}
            disabled={page <= 1}
          >
            Prev
          </button>
          <button
            className="btn-ghost"
            onClick={() => onPageChange(Math.min(pageCount, page + 1))}
            disabled={page >= pageCount}
          >
            Next
          </button>
        </div>
      </div>
    </section>
  );
}

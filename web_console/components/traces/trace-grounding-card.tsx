export function TraceGroundingCard({
  retrievedDocs,
  summary
}: {
  retrievedDocs: string[];
  summary: string;
}) {
  return (
    <article className="card">
      <h3>Grounding & Summary</h3>
      <div style={{ marginTop: 10, color: "var(--muted)", fontSize: 13 }}>
        {summary || "No summary output."}
      </div>
      <h4 style={{ marginTop: 12, marginBottom: 6, fontSize: 14 }}>Retrieved Docs</h4>
      {retrievedDocs.length === 0 ? (
        <p style={{ color: "var(--muted)", marginTop: 0 }}>No grounding docs in trace.</p>
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

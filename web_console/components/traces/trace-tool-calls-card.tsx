export function TraceToolCallsCard({ toolCalls }: { toolCalls: string[] }) {
  return (
    <article className="card">
      <h3>Tool Calls</h3>
      {toolCalls.length === 0 ? (
        <p style={{ color: "var(--muted)", marginTop: 10 }}>No tool calls recorded.</p>
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

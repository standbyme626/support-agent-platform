import type { OpenClawRoute, OpenClawStatus } from "@/lib/api/channels";

export function GatewayStatusCard({
  status,
  routes
}: {
  status: OpenClawStatus | null;
  routes: OpenClawRoute[];
}) {
  if (!status) {
    return (
      <article className="card">
        <h3>Gateway Status</h3>
        <div className="hint" style={{ marginTop: 10 }}>
          No gateway status payload was returned.
        </div>
      </article>
    );
  }

  return (
    <article className="card">
      <h3>Gateway Status</h3>
      <ul className="list" style={{ marginTop: 10 }}>
        <li className="list-item">
          <div>
            <strong>{status.gateway}</strong>
          </div>
          <small>environment {status.environment}</small>
        </li>
        <li className="list-item">
          <div>
            <strong>Session Bindings</strong>
          </div>
          <small>{status.session_bindings}</small>
        </li>
        <li className="list-item">
          <div>
            <strong>Registered Routes</strong>
          </div>
          <small>{routes.length}</small>
        </li>
        <li className="list-item">
          <div>
            <strong>Gateway Log</strong>
          </div>
          <small>{status.log_path}</small>
        </li>
      </ul>
    </article>
  );
}

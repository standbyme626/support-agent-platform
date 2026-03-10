CREATE TABLE IF NOT EXISTS tickets (
  ticket_id TEXT PRIMARY KEY,
  channel TEXT NOT NULL,
  session_id TEXT NOT NULL,
  thread_id TEXT NOT NULL,
  customer_id TEXT,
  title TEXT NOT NULL,
  latest_message TEXT NOT NULL,
  intent TEXT NOT NULL,
  priority TEXT NOT NULL,
  status TEXT NOT NULL,
  queue TEXT NOT NULL,
  assignee TEXT,
  needs_handoff INTEGER NOT NULL DEFAULT 0,
  metadata_json TEXT NOT NULL DEFAULT '{}',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_tickets_status ON tickets(status);
CREATE INDEX IF NOT EXISTS idx_tickets_session ON tickets(session_id);

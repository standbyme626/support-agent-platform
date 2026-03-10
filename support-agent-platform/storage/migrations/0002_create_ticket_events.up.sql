CREATE TABLE IF NOT EXISTS ticket_events (
  event_id TEXT PRIMARY KEY,
  ticket_id TEXT NOT NULL,
  event_type TEXT NOT NULL,
  actor_type TEXT NOT NULL,
  actor_id TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  created_at TEXT NOT NULL,
  FOREIGN KEY(ticket_id) REFERENCES tickets(ticket_id)
);

CREATE INDEX IF NOT EXISTS idx_ticket_events_ticket_id ON ticket_events(ticket_id);
CREATE INDEX IF NOT EXISTS idx_ticket_events_created_at ON ticket_events(created_at);

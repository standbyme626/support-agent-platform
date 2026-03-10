ALTER TABLE tickets ADD COLUMN inbox TEXT NOT NULL DEFAULT 'default';
ALTER TABLE tickets ADD COLUMN lifecycle_stage TEXT NOT NULL DEFAULT 'intake';
ALTER TABLE tickets ADD COLUMN first_response_due_at TEXT;
ALTER TABLE tickets ADD COLUMN resolution_due_at TEXT;
ALTER TABLE tickets ADD COLUMN escalated_at TEXT;
ALTER TABLE tickets ADD COLUMN resolved_at TEXT;
ALTER TABLE tickets ADD COLUMN closed_at TEXT;
ALTER TABLE tickets ADD COLUMN resolution_note TEXT;

CREATE INDEX IF NOT EXISTS idx_tickets_queue_status ON tickets(queue, status);
CREATE INDEX IF NOT EXISTS idx_tickets_lifecycle_stage ON tickets(lifecycle_stage);

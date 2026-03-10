ALTER TABLE tickets ADD COLUMN source_channel TEXT NOT NULL DEFAULT '';
ALTER TABLE tickets ADD COLUMN resolution_code TEXT;
ALTER TABLE tickets ADD COLUMN close_reason TEXT;
ALTER TABLE tickets ADD COLUMN handoff_state TEXT NOT NULL DEFAULT 'none';
ALTER TABLE tickets ADD COLUMN last_agent_action TEXT;
ALTER TABLE tickets ADD COLUMN risk_level TEXT NOT NULL DEFAULT 'medium';

CREATE INDEX IF NOT EXISTS idx_tickets_source_channel ON tickets(source_channel);
CREATE INDEX IF NOT EXISTS idx_tickets_handoff_state ON tickets(handoff_state);
CREATE INDEX IF NOT EXISTS idx_tickets_risk_level ON tickets(risk_level);

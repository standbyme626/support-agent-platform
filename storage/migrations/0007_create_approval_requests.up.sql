CREATE TABLE IF NOT EXISTS approval_requests (
  id TEXT PRIMARY KEY,
  status TEXT NOT NULL DEFAULT 'submitted',
  request_type TEXT,
  requester_id TEXT,
  title TEXT,
  content TEXT,
  attachments_json TEXT DEFAULT '[]',
  approver_chain_json TEXT DEFAULT '[]',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_approval_status ON approval_requests(status);
CREATE INDEX IF NOT EXISTS idx_approval_requester ON approval_requests(requester_id);

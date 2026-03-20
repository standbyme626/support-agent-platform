CREATE TABLE IF NOT EXISTS procurement_requests (
  id TEXT PRIMARY KEY,
  status TEXT NOT NULL DEFAULT 'draft',
  requester_id TEXT,
  item_name TEXT,
  category TEXT,
  quantity INTEGER,
  budget REAL,
  business_reason TEXT,
  urgency TEXT DEFAULT 'normal',
  approver_id TEXT,
  supplier_id TEXT,
  po_no TEXT,
  received_qty INTEGER,
  invoice_ref TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_procurement_status ON procurement_requests(status);
CREATE INDEX IF NOT EXISTS idx_procurement_requester ON procurement_requests(requester_id);

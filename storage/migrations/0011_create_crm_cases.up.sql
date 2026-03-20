CREATE TABLE IF NOT EXISTS crm_cases (
  id TEXT PRIMARY KEY,
  status TEXT NOT NULL DEFAULT 'new',
  case_type TEXT,
  customer_id TEXT,
  customer_name TEXT,
  contact_email TEXT,
  contact_phone TEXT,
  subject TEXT,
  description TEXT,
  priority TEXT DEFAULT 'medium',
  assigned_to TEXT,
  resolution TEXT,
  closed_at TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_crm_status ON crm_cases(status);
CREATE INDEX IF NOT EXISTS idx_crm_customer ON crm_cases(customer_id);
CREATE INDEX IF NOT EXISTS idx_crm_assigned_to ON crm_cases(assigned_to);

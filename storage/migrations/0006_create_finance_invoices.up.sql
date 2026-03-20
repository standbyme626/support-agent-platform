CREATE TABLE IF NOT EXISTS finance_invoices (
  id TEXT PRIMARY KEY,
  status TEXT NOT NULL DEFAULT 'invoice_received',
  vendor_id TEXT,
  invoice_no TEXT,
  po_no TEXT,
  receipt_no TEXT,
  amount REAL,
  currency TEXT DEFAULT 'CNY',
  invoice_date TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_finance_status ON finance_invoices(status);
CREATE INDEX IF NOT EXISTS idx_finance_vendor ON finance_invoices(vendor_id);

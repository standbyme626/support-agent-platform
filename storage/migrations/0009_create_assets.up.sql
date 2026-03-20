CREATE TABLE IF NOT EXISTS assets (
  id TEXT PRIMARY KEY,
  status TEXT NOT NULL DEFAULT 'inventory',
  asset_tag TEXT,
  name TEXT,
  category TEXT,
  model TEXT,
  serial_number TEXT,
  location TEXT,
  assigned_to TEXT,
  assigned_at TEXT,
  purchase_date TEXT,
  warranty_expires TEXT,
  value REAL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_assets_status ON assets(status);
CREATE INDEX IF NOT EXISTS idx_assets_category ON assets(category);
CREATE INDEX IF NOT EXISTS idx_assets_assigned_to ON assets(assigned_to);

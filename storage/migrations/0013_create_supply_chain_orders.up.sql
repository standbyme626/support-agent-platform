CREATE TABLE IF NOT EXISTS supply_chain_orders (
  id TEXT PRIMARY KEY,
  status TEXT NOT NULL DEFAULT 'pending',
  order_type TEXT,
  supplier_id TEXT,
  items_json TEXT DEFAULT '[]',
  total_amount REAL,
  expected_delivery TEXT,
  received_at TEXT,
  notes TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_supply_chain_status ON supply_chain_orders(status);
CREATE INDEX IF NOT EXISTS idx_supply_chain_supplier ON supply_chain_orders(supplier_id);

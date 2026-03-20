CREATE TABLE IF NOT EXISTS hr_onboardings (
  id TEXT PRIMARY KEY,
  status TEXT NOT NULL DEFAULT 'submitted',
  candidate_name TEXT,
  department TEXT,
  position TEXT,
  manager_id TEXT,
  start_date TEXT,
  employee_id TEXT,
  accounts_json TEXT DEFAULT '[]',
  devices_json TEXT DEFAULT '[]',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_hr_status ON hr_onboardings(status);
CREATE INDEX IF NOT EXISTS idx_hr_manager ON hr_onboardings(manager_id);

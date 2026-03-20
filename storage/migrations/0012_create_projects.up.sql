CREATE TABLE IF NOT EXISTS projects (
  id TEXT PRIMARY KEY,
  status TEXT NOT NULL DEFAULT 'planning',
  name TEXT,
  description TEXT,
  owner_id TEXT,
  start_date TEXT,
  end_date TEXT,
  milestones_json TEXT DEFAULT '[]',
  resources_json TEXT DEFAULT '[]',
  budget REAL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_projects_status ON projects(status);
CREATE INDEX IF NOT EXISTS idx_projects_owner ON projects(owner_id);

CREATE TABLE IF NOT EXISTS kb_articles (
  id TEXT PRIMARY KEY,
  status TEXT NOT NULL DEFAULT 'draft',
  title TEXT,
  content TEXT,
  category TEXT,
  tags_json TEXT DEFAULT '[]',
  author_id TEXT,
  version INTEGER DEFAULT 1,
  views INTEGER DEFAULT 0,
  helpful INTEGER DEFAULT 0,
  not_helpful INTEGER DEFAULT 0,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  published_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_kb_status ON kb_articles(status);
CREATE INDEX IF NOT EXISTS idx_kb_category ON kb_articles(category);

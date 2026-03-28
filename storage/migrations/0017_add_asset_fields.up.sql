-- 补充资产系统缺失字段
ALTER TABLE assets ADD COLUMN supplier_id TEXT;
ALTER TABLE assets ADD COLUMN custodian TEXT;
ALTER TABLE assets ADD COLUMN depreciation TEXT;

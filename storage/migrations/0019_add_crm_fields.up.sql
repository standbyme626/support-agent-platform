-- 补充CRM系统缺失字段
ALTER TABLE crm_cases ADD COLUMN opportunity_value REAL DEFAULT 0;
ALTER TABLE crm_cases ADD COLUMN sales_stage TEXT;
ALTER TABLE crm_cases ADD COLUMN expected_close TEXT;

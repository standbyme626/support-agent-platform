-- 回滚CRM系统补充字段
ALTER TABLE crm_cases DROP COLUMN opportunity_value;
ALTER TABLE crm_cases DROP COLUMN sales_stage;
ALTER TABLE crm_cases DROP COLUMN expected_close;

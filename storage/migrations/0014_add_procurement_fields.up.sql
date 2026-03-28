-- 补充采购系统缺失字段
ALTER TABLE procurement_requests ADD COLUMN supplier_name TEXT;
ALTER TABLE procurement_requests ADD COLUMN contact_email TEXT;
ALTER TABLE procurement_requests ADD COLUMN expected_date TEXT;
ALTER TABLE procurement_requests ADD COLUMN priority TEXT DEFAULT 'normal';

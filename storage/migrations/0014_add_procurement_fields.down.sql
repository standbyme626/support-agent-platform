-- 回滚采购系统补充字段
ALTER TABLE procurement_requests DROP COLUMN supplier_name;
ALTER TABLE procurement_requests DROP COLUMN contact_email;
ALTER TABLE procurement_requests DROP COLUMN expected_date;
ALTER TABLE procurement_requests DROP COLUMN priority;

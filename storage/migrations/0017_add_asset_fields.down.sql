-- 回滚资产系统补充字段
ALTER TABLE assets DROP COLUMN supplier_id;
ALTER TABLE assets DROP COLUMN custodian;
ALTER TABLE assets DROP COLUMN depreciation;

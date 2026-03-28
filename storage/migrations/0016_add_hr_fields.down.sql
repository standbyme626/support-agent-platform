-- 回滚HR系统补充字段
ALTER TABLE hr_onboardings DROP COLUMN email;
ALTER TABLE hr_onboardings DROP COLUMN hire_date;
ALTER TABLE hr_onboardings DROP COLUMN contract_type;

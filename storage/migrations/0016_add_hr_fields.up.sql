-- 补充HR系统缺失字段
ALTER TABLE hr_onboardings ADD COLUMN email TEXT;
ALTER TABLE hr_onboardings ADD COLUMN hire_date TEXT;
ALTER TABLE hr_onboardings ADD COLUMN contract_type TEXT DEFAULT 'full_time';

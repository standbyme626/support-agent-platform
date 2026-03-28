-- 回滚财务系统补充字段
ALTER TABLE finance_invoices DROP COLUMN tax_amount;
ALTER TABLE finance_invoices DROP COLUMN total_amount;
ALTER TABLE finance_invoices DROP COLUMN payment_terms;
ALTER TABLE finance_invoices DROP COLUMN due_date;
ALTER TABLE finance_invoices DROP COLUMN payment_method;
ALTER TABLE finance_invoices DROP COLUMN account_id;

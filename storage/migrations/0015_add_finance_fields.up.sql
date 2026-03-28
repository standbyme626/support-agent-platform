-- 补充财务系统缺失字段
ALTER TABLE finance_invoices ADD COLUMN tax_amount REAL DEFAULT 0;
ALTER TABLE finance_invoices ADD COLUMN total_amount REAL;
ALTER TABLE finance_invoices ADD COLUMN payment_terms TEXT;
ALTER TABLE finance_invoices ADD COLUMN due_date TEXT;
ALTER TABLE finance_invoices ADD COLUMN payment_method TEXT;
ALTER TABLE finance_invoices ADD COLUMN account_id TEXT;

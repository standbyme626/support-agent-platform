-- 回滚供应链系统补充字段
ALTER TABLE supply_chain_orders DROP COLUMN warehouse;
ALTER TABLE supply_chain_orders DROP COLUMN batch_no;
ALTER TABLE supply_chain_orders DROP COLUMN shipment_no;

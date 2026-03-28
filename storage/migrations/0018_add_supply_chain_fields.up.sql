-- 补充供应链系统缺失字段
ALTER TABLE supply_chain_orders ADD COLUMN warehouse TEXT;
ALTER TABLE supply_chain_orders ADD COLUMN batch_no TEXT;
ALTER TABLE supply_chain_orders ADD COLUMN shipment_no TEXT;

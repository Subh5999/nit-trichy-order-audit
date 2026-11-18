-- Supabase PostgreSQL schema for Order-to-Audit.
-- Stock balances are derived from stock_movements, never written directly.
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    username TEXT NOT NULL UNIQUE,
    display_name TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('Salesman','Admin','Production Supervisor','Accountant/Auditor','Owner')),
    password_hash TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS customers (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    customer_type TEXT NOT NULL,
    address TEXT NOT NULL,
    state TEXT NOT NULL,
    state_code TEXT NOT NULL,
    gstin TEXT NOT NULL DEFAULT '',
    phone TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS products (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    sku TEXT NOT NULL UNIQUE,
    unit TEXT NOT NULL,
    hsn TEXT NOT NULL,
    gst_rate NUMERIC(5,2) NOT NULL CHECK (gst_rate >= 0)
);
CREATE TABLE IF NOT EXISTS bom_lines (
    id TEXT PRIMARY KEY,
    product_id TEXT NOT NULL REFERENCES products(id),
    ingredient TEXT NOT NULL,
    item_code TEXT NOT NULL,
    quantity_per_packet NUMERIC(14,3) NOT NULL CHECK (quantity_per_packet > 0),
    unit TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS orders (
    id TEXT PRIMARY KEY,
    order_number TEXT NOT NULL UNIQUE,
    customer_id TEXT NOT NULL REFERENCES customers(id),
    product_id TEXT NOT NULL REFERENCES products(id),
    quantity INTEGER NOT NULL CHECK (quantity > 0),
    unit_price NUMERIC(14,2) NOT NULL CHECK (unit_price > 0),
    gst_rate NUMERIC(5,2) NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('pending_review','approved','rejected','dispatched','cancelled')),
    note TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_by TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS production_runs (
    id TEXT PRIMARY KEY,
    product_id TEXT NOT NULL REFERENCES products(id),
    run_number TEXT NOT NULL UNIQUE,
    expected_packets INTEGER NOT NULL CHECK (expected_packets > 0),
    actual_good_packets INTEGER NOT NULL CHECK (actual_good_packets > 0),
    damaged_pouches INTEGER NOT NULL DEFAULT 0 CHECK (damaged_pouches >= 0),
    cartons_used INTEGER NOT NULL DEFAULT 0 CHECK (cartons_used >= 0),
    flour_kg NUMERIC(14,3) NOT NULL,
    oil_litres NUMERIC(14,3) NOT NULL,
    spice_kg NUMERIC(14,3) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_by TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS invoices (
    id TEXT PRIMARY KEY,
    invoice_number TEXT NOT NULL UNIQUE,
    order_id TEXT NOT NULL UNIQUE REFERENCES orders(id),
    taxable_amount NUMERIC(14,2) NOT NULL,
    cgst NUMERIC(14,2) NOT NULL,
    sgst NUMERIC(14,2) NOT NULL,
    igst NUMERIC(14,2) NOT NULL,
    total NUMERIC(14,2) NOT NULL,
    paid NUMERIC(14,2) NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'posted' CHECK (status IN ('posted','cancelled')),
    credit_note_number TEXT,
    cancellation_reason TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS purchases (
    id TEXT PRIMARY KEY,
    item_code TEXT NOT NULL,
    item_name TEXT NOT NULL,
    quantity NUMERIC(16,3) NOT NULL CHECK (quantity > 0),
    unit TEXT NOT NULL,
    unit_price NUMERIC(14,2) NOT NULL CHECK (unit_price > 0),
    total NUMERIC(14,2) NOT NULL CHECK (total > 0),
    supplier TEXT NOT NULL,
    reference TEXT NOT NULL DEFAULT '',
    purchase_date DATE NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_by TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS payments (
    id TEXT PRIMARY KEY,
    invoice_id TEXT NOT NULL REFERENCES invoices(id),
    amount NUMERIC(14,2) NOT NULL CHECK (amount > 0),
    method TEXT NOT NULL,
    reference TEXT NOT NULL DEFAULT '',
    received_by TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS stock_movements (
    id TEXT PRIMARY KEY,
    item_code TEXT NOT NULL,
    item_name TEXT NOT NULL,
    category TEXT NOT NULL,
    quantity NUMERIC(16,3) NOT NULL CHECK (quantity <> 0),
    unit TEXT NOT NULL,
    movement_type TEXT NOT NULL,
    source_type TEXT NOT NULL,
    source_id TEXT NOT NULL,
    note TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    actor TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_stock_movements_item ON stock_movements(item_code);
CREATE INDEX IF NOT EXISTS idx_stock_movements_source ON stock_movements(source_type, source_id);
CREATE TABLE IF NOT EXISTS audit_logs (
    id TEXT PRIMARY KEY,
    actor TEXT NOT NULL,
    role TEXT NOT NULL,
    action TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    details TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE OR REPLACE FUNCTION prevent_stock_movement_mutation()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'Stock ledger is append-only; post a reversing movement instead.';
END;
$$;
DROP TRIGGER IF EXISTS stock_movements_immutable ON stock_movements;
CREATE TRIGGER stock_movements_immutable
BEFORE UPDATE OR DELETE ON stock_movements
FOR EACH ROW EXECUTE FUNCTION prevent_stock_movement_mutation();

-- Fictional benchmark data only. Passwords are demo-only and should not be used in production.
INSERT INTO users (id,username,display_name,role,password_hash) VALUES
('demo-sales','sales','Demo Sales Rep','Salesman','62617463686c696e652d64656d6f2121:1a7ee62731d08dbfca3b42eb5763607c2024c4f220f1c67ca40a220f1dbcd759'),
('demo-admin','admin','Demo Admin','Admin','62617463686c696e652d64656d6f2121:1a7ee62731d08dbfca3b42eb5763607c2024c4f220f1c67ca40a220f1dbcd759'),
('demo-production','production','Demo Production Supervisor','Production Supervisor','62617463686c696e652d64656d6f2121:1a7ee62731d08dbfca3b42eb5763607c2024c4f220f1c67ca40a220f1dbcd759'),
('demo-audit','auditor','Demo Accountant / Auditor','Accountant/Auditor','62617463686c696e652d64656d6f2121:1a7ee62731d08dbfca3b42eb5763607c2024c4f220f1c67ca40a220f1dbcd759'),
('demo-owner','owner','Demo Owner','Owner','62617463686c696e652d64656d6f2121:1a7ee62731d08dbfca3b42eb5763607c2024c4f220f1c67ca40a220f1dbcd759')
ON CONFLICT (id) DO NOTHING;
INSERT INTO customers (id,name,customer_type,address,state,state_code,gstin,phone) VALUES
('retailer-a','Retailer A','Retailer','Demo market, Tiruchirappalli','Tamil Nadu','33','33DEMO0000A1Z5','00000 00001'),
('distributor-b','Distributor B','Distributor','Demo wholesale, Bengaluru','Karnataka','29','29DEMO0000B1Z4','00000 00002')
ON CONFLICT (id) DO NOTHING;
INSERT INTO products (id,name,sku,unit,hsn,gst_rate) VALUES
('murukku-200','Murukku 200 g','MUR-200','packet','210690',5.00)
ON CONFLICT (id) DO NOTHING;
INSERT INTO bom_lines (id,product_id,ingredient,item_code,quantity_per_packet,unit) VALUES
('bom-flour','murukku-200','Flour','RM-FLOUR',0.200,'kg'),
('bom-oil','murukku-200','Oil','RM-OIL',0.050,'litre'),
('bom-spice','murukku-200','Spice mix','RM-SPICE',0.005,'kg'),
('bom-pouch','murukku-200','Pouch','PK-POUCH',1.000,'piece'),
('bom-carton','murukku-200','Carton','PK-CARTON',0.045,'piece')
ON CONFLICT (id) DO NOTHING;
INSERT INTO production_runs (id,product_id,run_number,expected_packets,actual_good_packets,damaged_pouches,cartons_used,flour_kg,oil_litres,spice_kg,created_by) VALUES
('run-benchmark-001','murukku-200','RUN-2026-001',200,188,6,9,40,10.5,1.2,'demo-production')
ON CONFLICT (id) DO NOTHING;
INSERT INTO orders (id,order_number,customer_id,product_id,quantity,unit_price,gst_rate,status,note,created_by) VALUES
('order-retailer-a','ORD-2026-001','retailer-a','murukku-200',150,50,5,'dispatched','Benchmark intrastate sale','demo-sales'),
('order-distributor-b','ORD-2026-002','distributor-b','murukku-200',120,50,5,'pending_review','Short by 32 packets; interstate supply uses IGST if invoiced.','demo-sales')
ON CONFLICT (id) DO NOTHING;
INSERT INTO invoices (id,invoice_number,order_id,taxable_amount,cgst,sgst,igst,total,paid,status) VALUES
('invoice-retailer-a','INV-2026-001','order-retailer-a',7500,187.50,187.50,0,7875,4000,'posted')
ON CONFLICT (id) DO NOTHING;
INSERT INTO purchases (id,item_code,item_name,quantity,unit,unit_price,total,supplier,reference,purchase_date,created_by) VALUES
('purchase-flour-60','RM-FLOUR','Flour',60,'kg',45,2700,'Demo supplier','DEMO-BILL-001','2026-11-18','demo-admin')
ON CONFLICT (id) DO NOTHING;
INSERT INTO payments (id,invoice_id,amount,method,reference,received_by) VALUES
('payment-retailer-a','invoice-retailer-a',4000,'Bank transfer','DEMO-RECEIPT-001','demo-audit')
ON CONFLICT (id) DO NOTHING;
INSERT INTO stock_movements (id,item_code,item_name,category,quantity,unit,movement_type,source_type,source_id,note,actor) VALUES
('seed-open-flour','RM-FLOUR','Flour','Raw material',100,'kg','opening','opening_balance','opening-2026','Benchmark opening stock','System seed'),
('seed-open-oil','RM-OIL','Oil','Raw material',30,'litre','opening','opening_balance','opening-2026','Benchmark opening stock','System seed'),
('seed-open-spice','RM-SPICE','Spice mix','Raw material',5,'kg','opening','opening_balance','opening-2026','Benchmark opening stock','System seed'),
('seed-open-pouch','PK-POUCH','Pouches','Packaging',500,'piece','opening','opening_balance','opening-2026','Benchmark opening stock','System seed'),
('seed-open-carton','PK-CARTON','Cartons','Packaging',30,'piece','opening','opening_balance','opening-2026','Benchmark opening stock','System seed'),
('seed-open-fg','FG-MUR-200','Murukku 200 g','Finished goods',50,'packet','opening','opening_balance','opening-2026','Benchmark opening stock','System seed'),
('seed-purchase-flour','RM-FLOUR','Flour','Raw material',60,'kg','purchase_in','purchase','purchase-flour-60','60 kg × Rs. 45/kg','System seed'),
('seed-run-flour','RM-FLOUR','Flour','Raw material',-40,'kg','production','production_run','run-benchmark-001','Benchmark production','Demo Production Supervisor'),
('seed-run-oil','RM-OIL','Oil','Raw material',-10.5,'litre','production','production_run','run-benchmark-001','Benchmark production','Demo Production Supervisor'),
('seed-run-spice','RM-SPICE','Spice mix','Raw material',-1.2,'kg','production','production_run','run-benchmark-001','Benchmark production','Demo Production Supervisor'),
('seed-run-pouch','PK-POUCH','Pouches','Packaging',-194,'piece','production','production_run','run-benchmark-001','188 good packets and 6 damaged pouches','Demo Production Supervisor'),
('seed-run-carton','PK-CARTON','Cartons','Packaging',-9,'piece','production','production_run','run-benchmark-001','Benchmark production','Demo Production Supervisor'),
('seed-run-fg','FG-MUR-200','Murukku 200 g','Finished goods',188,'packet','production_output','production_run','run-benchmark-001','Benchmark good output','Demo Production Supervisor'),
('seed-dispatch-a','FG-MUR-200','Murukku 200 g','Finished goods',-150,'packet','dispatch','order','order-retailer-a','Benchmark dispatch','Demo Admin')
ON CONFLICT (id) DO NOTHING;

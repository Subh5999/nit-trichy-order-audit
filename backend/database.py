from __future__ import annotations

import os
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from backend.auth import hash_password

ROOT = Path(__file__).resolve().parent
DATABASE_PATH = Path(os.getenv("DEMO_DATABASE_PATH", ROOT / "data" / "demo.sqlite3"))
DATABASE_URL = os.getenv("DATABASE_URL", "")

SCHEMA = """
PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY, username TEXT NOT NULL UNIQUE, display_name TEXT NOT NULL,
    role TEXT NOT NULL, password_hash TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS customers (
    id TEXT PRIMARY KEY, name TEXT NOT NULL, customer_type TEXT NOT NULL,
    address TEXT NOT NULL, state TEXT NOT NULL, state_code TEXT NOT NULL,
    gstin TEXT NOT NULL DEFAULT '', phone TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS products (
    id TEXT PRIMARY KEY, name TEXT NOT NULL, sku TEXT NOT NULL UNIQUE,
    unit TEXT NOT NULL, hsn TEXT NOT NULL, gst_rate TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS bom_lines (
    id TEXT PRIMARY KEY, product_id TEXT NOT NULL REFERENCES products(id),
    ingredient TEXT NOT NULL, item_code TEXT NOT NULL, quantity_per_packet TEXT NOT NULL,
    unit TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS orders (
    id TEXT PRIMARY KEY, order_number TEXT NOT NULL UNIQUE,
    customer_id TEXT NOT NULL REFERENCES customers(id), product_id TEXT NOT NULL REFERENCES products(id),
    quantity INTEGER NOT NULL CHECK(quantity > 0), unit_price TEXT NOT NULL, gst_rate TEXT NOT NULL,
    status TEXT NOT NULL, note TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL, created_by TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS production_runs (
    id TEXT PRIMARY KEY, product_id TEXT NOT NULL REFERENCES products(id), run_number TEXT NOT NULL UNIQUE,
    expected_packets INTEGER NOT NULL, actual_good_packets INTEGER NOT NULL, damaged_pouches INTEGER NOT NULL,
    cartons_used INTEGER NOT NULL, flour_kg TEXT NOT NULL, oil_litres TEXT NOT NULL,
    spice_kg TEXT NOT NULL, created_at TEXT NOT NULL, created_by TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS invoices (
    id TEXT PRIMARY KEY, invoice_number TEXT NOT NULL UNIQUE, order_id TEXT NOT NULL UNIQUE REFERENCES orders(id),
    taxable_amount TEXT NOT NULL, cgst TEXT NOT NULL, sgst TEXT NOT NULL, igst TEXT NOT NULL,
    total TEXT NOT NULL, paid TEXT NOT NULL DEFAULT '0.00', status TEXT NOT NULL DEFAULT 'posted',
    credit_note_number TEXT, cancellation_reason TEXT, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS purchases (
    id TEXT PRIMARY KEY, item_code TEXT NOT NULL, item_name TEXT NOT NULL,
    quantity TEXT NOT NULL, unit TEXT NOT NULL, unit_price TEXT NOT NULL,
    total TEXT NOT NULL, supplier TEXT NOT NULL, reference TEXT NOT NULL,
    purchase_date TEXT NOT NULL, created_at TEXT NOT NULL, created_by TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS payments (
    id TEXT PRIMARY KEY, invoice_id TEXT NOT NULL REFERENCES invoices(id), amount TEXT NOT NULL,
    method TEXT NOT NULL, reference TEXT NOT NULL, received_by TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS stock_movements (
    id TEXT PRIMARY KEY, item_code TEXT NOT NULL, item_name TEXT NOT NULL,
    category TEXT NOT NULL, quantity TEXT NOT NULL, unit TEXT NOT NULL,
    movement_type TEXT NOT NULL, source_type TEXT NOT NULL, source_id TEXT NOT NULL,
    note TEXT NOT NULL, created_at TEXT NOT NULL, actor TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_stock_item ON stock_movements(item_code);
CREATE INDEX IF NOT EXISTS idx_stock_source ON stock_movements(source_type, source_id);
CREATE TABLE IF NOT EXISTS audit_logs (
    id TEXT PRIMARY KEY, actor TEXT NOT NULL, role TEXT NOT NULL, action TEXT NOT NULL,
    entity_type TEXT NOT NULL, entity_id TEXT NOT NULL, details TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE TRIGGER IF NOT EXISTS stock_movements_no_update
BEFORE UPDATE ON stock_movements BEGIN SELECT RAISE(ABORT, 'Stock ledger is append-only'); END;
CREATE TRIGGER IF NOT EXISTS stock_movements_no_delete
BEFORE DELETE ON stock_movements BEGIN SELECT RAISE(ABORT, 'Stock ledger is append-only'); END;
"""

NOW = datetime.now(timezone.utc).isoformat(timespec="seconds")


@contextmanager
def connect() -> Iterator[Any]:
    if DATABASE_URL:
        import psycopg
        from psycopg.rows import dict_row

        connection = psycopg.connect(DATABASE_URL, row_factory=dict_row)
        database = PostgresConnection(connection)
        try:
            yield database
        except Exception:
            connection.rollback()
            raise
        else:
            connection.commit()
        finally:
            connection.close()
        return
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(DATABASE_PATH, timeout=15, isolation_level=None)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")
    db.execute("PRAGMA busy_timeout = 15000")
    try:
        yield db
    except Exception:
        if db.in_transaction:
            db.rollback()
        raise
    else:
        if db.in_transaction:
            db.commit()
    finally:
        db.close()


class PostgresConnection:
    def __init__(self, connection: Any) -> None:
        self.connection = connection

    def execute(self, query: str, parameters: tuple = ()) -> Any:
        if query.strip().upper() == "BEGIN IMMEDIATE":
            query = "SELECT pg_advisory_xact_lock(49281736)"
        else:
            query = query.replace("?", "%s")
        return self.connection.execute(query, parameters)

    def executemany(self, query: str, parameters: list[tuple]) -> Any:
        query = query.replace("?", "%s")
        with self.connection.cursor() as cursor:
            return cursor.executemany(query, parameters)


def _insert_movement(
    db: sqlite3.Connection,
    code: str,
    name: str,
    category: str,
    quantity: str,
    unit: str,
    movement_type: str,
    source_type: str,
    source_id: str,
    note: str,
    actor: str = "System seed",
) -> None:
    db.execute(
        """INSERT INTO stock_movements
           (id,item_code,item_name,category,quantity,unit,movement_type,source_type,source_id,note,created_at,actor)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
        (str(uuid.uuid4()), code, name, category, quantity, unit, movement_type, source_type, source_id, note, NOW, actor),
    )


def initialize() -> None:
    if DATABASE_URL:
        # PostgreSQL schema and demo rows are provisioned by the Supabase migration.
        return
    with connect() as db:
        db.executescript(SCHEMA)
        if db.execute("SELECT COUNT(*) FROM users").fetchone()[0]:
            return
        db.execute("BEGIN IMMEDIATE")
        users = [
            ("demo-sales", "sales", "Demo Sales Rep", "Salesman"),
            ("demo-admin", "admin", "Demo Admin", "Admin"),
            ("demo-production", "production", "Demo Production Supervisor", "Production Supervisor"),
            ("demo-audit", "auditor", "Demo Accountant / Auditor", "Accountant/Auditor"),
            ("demo-owner", "owner", "Demo Owner", "Owner"),
        ]
        for user_id, username, display, role in users:
            db.execute(
                "INSERT INTO users VALUES (?,?,?,?,?,?)",
                (user_id, username, display, role, hash_password("demo123"), NOW),
            )
        db.execute(
            "INSERT INTO products VALUES (?,?,?,?,?,?)",
            ("murukku-200", "Murukku 200 g", "MUR-200", "packet", "210690", "5.00"),
        )
        customers = [
            ("retailer-a", "Retailer A", "Retailer", "Demo market, Tiruchirappalli", "Tamil Nadu", "33", "33DEMO0000A1Z5", "00000 00001"),
            ("distributor-b", "Distributor B", "Distributor", "Demo wholesale, Bengaluru", "Karnataka", "29", "29DEMO0000B1Z4", "00000 00002"),
        ]
        db.executemany("INSERT INTO customers VALUES (?,?,?,?,?,?,?,?)", customers)
        bom_rows = [
            ("bom-flour", "Flour", "RM-FLOUR", "0.200", "kg"),
            ("bom-oil", "Oil", "RM-OIL", "0.050", "litre"),
            ("bom-spice", "Spice mix", "RM-SPICE", "0.005", "kg"),
            ("bom-pouch", "Pouch", "PK-POUCH", "1.000", "piece"),
            ("bom-carton", "Carton", "PK-CARTON", "0.045", "piece"),
        ]
        db.executemany(
            "INSERT INTO bom_lines (id,product_id,ingredient,item_code,quantity_per_packet,unit) VALUES (?,?,?,?,?,?)",
            [(key, "murukku-200", name, code, qty, unit) for key, name, code, qty, unit in bom_rows],
        )

        # The opening, purchase, production and dispatch below are immutable source-referenced ledger entries.
        for code, name, category, qty, unit in [
            ("RM-FLOUR", "Flour", "Raw material", "100", "kg"),
            ("RM-OIL", "Oil", "Raw material", "30", "litre"),
            ("RM-SPICE", "Spice mix", "Raw material", "5", "kg"),
            ("PK-POUCH", "Pouches", "Packaging", "500", "piece"),
            ("PK-CARTON", "Cartons", "Packaging", "30", "piece"),
            ("FG-MUR-200", "Murukku 200 g", "Finished goods", "50", "packet"),
        ]:
            _insert_movement(db, code, name, category, qty, unit, "opening", "opening_balance", "opening-2026", "Seeded benchmark opening stock")
        _insert_movement(db, "RM-FLOUR", "Flour", "Raw material", "60", "kg", "purchase_in", "purchase", "purchase-flour-60", "60 kg × Rs. 45/kg")
        db.execute(
            "INSERT INTO purchases VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            ("purchase-flour-60", "RM-FLOUR", "Flour", "60", "kg", "45.00", "2700.00", "Demo supplier", "DEMO-BILL-001", "2026-11-18", NOW, "demo-admin"),
        )

        db.execute(
            """INSERT INTO production_runs VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            ("run-benchmark-001", "murukku-200", "RUN-2026-001", 200, 188, 6, 9, "40", "10.5", "1.2", NOW, "demo-production"),
        )
        for code, name, category, quantity, unit in [
            ("RM-FLOUR", "Flour", "Raw material", "-40", "kg"),
            ("RM-OIL", "Oil", "Raw material", "-10.5", "litre"),
            ("RM-SPICE", "Spice mix", "Raw material", "-1.2", "kg"),
            ("PK-POUCH", "Pouches", "Packaging", "-194", "piece"),
            ("PK-CARTON", "Cartons", "Packaging", "-9", "piece"),
            ("FG-MUR-200", "Murukku 200 g", "Finished goods", "188", "packet"),
        ]:
            _insert_movement(db, code, name, category, quantity, unit, "production", "production_run", "run-benchmark-001", "Benchmark production RUN-2026-001", "demo-production")

        db.execute(
            """INSERT INTO orders VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            ("order-retailer-a", "ORD-2026-001", "retailer-a", "murukku-200", 150, "50.00", "5.00", "dispatched", "Benchmark intrastate sale", NOW, "demo-sales"),
        )
        db.execute(
            """INSERT INTO invoices VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            ("invoice-retailer-a", "INV-2026-001", "order-retailer-a", "7500.00", "187.50", "187.50", "0.00", "7875.00", "4000.00", "posted", None, None, NOW),
        )
        db.execute(
            "INSERT INTO payments VALUES (?,?,?,?,?,?,?)",
            ("payment-retailer-a", "invoice-retailer-a", "4000.00", "Bank transfer", "DEMO-RECEIPT-001", "demo-audit", NOW),
        )
        _insert_movement(db, "FG-MUR-200", "Murukku 200 g", "Finished goods", "-150", "packet", "dispatch", "order", "order-retailer-a", "Dispatch against ORD-2026-001", "demo-admin")
        db.execute(
            """INSERT INTO orders VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            ("order-distributor-b", "ORD-2026-002", "distributor-b", "murukku-200", 120, "50.00", "5.00", "pending_review", "Short by 32 packets; interstate supply uses IGST if invoiced.", NOW, "demo-sales"),
        )
        for actor, role, action, entity, entity_id, details in [
            ("System seed", "System", "seeded_benchmark", "inventory", "opening-2026", "Loaded the benchmark opening stock and stock ledger."),
            ("Demo Production Supervisor", "Production Supervisor", "recorded_production", "production_run", "run-benchmark-001", "40 kg flour, 10.5 L oil, 1.2 kg spice; 188 good packets, 6 damaged pouches."),
            ("Demo Admin", "Admin", "dispatched_order", "order", "order-retailer-a", "150 packets dispatched. Local GST split into CGST and SGST."),
        ]:
            db.execute(
                "INSERT INTO audit_logs VALUES (?,?,?,?,?,?,?,?)",
                (str(uuid.uuid4()), actor, role, action, entity, entity_id, details, NOW),
            )

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from fastapi import HTTPException

from backend.database import connect

CENT = Decimal("0.01")


def money(value: Decimal) -> str:
    return str(value.quantize(CENT, rounding=ROUND_HALF_UP))


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def audit(db: sqlite3.Connection, user: dict[str, str], action: str, entity: str, entity_id: str, details: str) -> None:
    db.execute(
        "INSERT INTO audit_logs VALUES (?,?,?,?,?,?,?,?)",
        (str(uuid.uuid4()), user["display_name"], user["role"], action, entity, entity_id, details, now()),
    )


def balance(db: sqlite3.Connection, code: str) -> Decimal:
    row = db.execute(
        "SELECT quantity FROM stock_movements WHERE item_code = ?", (code,)
    ).fetchall()
    return sum((Decimal(item["quantity"]) for item in row), Decimal(0))


def add_movement(
    db: sqlite3.Connection,
    item_code: str,
    item_name: str,
    category: str,
    quantity: Decimal,
    unit: str,
    movement_type: str,
    source_type: str,
    source_id: str,
    note: str,
    user: dict[str, str],
) -> None:
    if not source_id:
        raise ValueError("Every stock movement must reference its source.")
    db.execute(
        """INSERT INTO stock_movements
        (id,item_code,item_name,category,quantity,unit,movement_type,source_type,source_id,note,created_at,actor)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
        (str(uuid.uuid4()), item_code, item_name, category, str(quantity), unit, movement_type, source_type, source_id, note, now(), user["display_name"]),
    )


def create_order(payload: dict[str, Any], user: dict[str, str]) -> dict[str, Any]:
    order_id = str(uuid.uuid4())
    with connect() as db:
        db.execute("BEGIN IMMEDIATE")
        customer = db.execute("SELECT id FROM customers WHERE id=?", (payload["customer_id"],)).fetchone()
        if customer is None:
            raise HTTPException(status_code=404, detail="Customer not found.")
        product = db.execute("SELECT id, gst_rate FROM products WHERE id='murukku-200'").fetchone()
        if product is None:
            raise HTTPException(status_code=503, detail="The benchmark product master is not configured.")
        order_number = f"ORD-{datetime.now():%y%m%d}-{order_id[:6].upper()}"
        db.execute(
            "INSERT INTO orders VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (order_id, order_number, payload["customer_id"], product["id"], payload["quantity"], money(payload["unit_price"]), str(product["gst_rate"]), "pending_review", "", now(), user["id"]),
        )
        audit(db, user, "created_order", "order", order_id, f"{payload['quantity']} packets at Rs. {money(payload['unit_price'])}.")
        return {"id": order_id, "order_number": order_number, "status": "pending_review"}


def approve_order(order_id: str, user: dict[str, str]) -> dict[str, Any]:
    with connect() as db:
        db.execute("BEGIN IMMEDIATE")
        order = db.execute("SELECT * FROM orders WHERE id=?", (order_id,)).fetchone()
        if order is None:
            raise HTTPException(status_code=404, detail="Order not found.")
        if order["status"] != "pending_review":
            raise HTTPException(status_code=409, detail="Only orders awaiting review can be approved.")
        available = balance(db, "FG-MUR-200")
        shortage = max(0, order["quantity"] - int(available))
        if shortage:
            raise HTTPException(status_code=409, detail=f"Insufficient finished stock: {shortage} packet shortage.")
        db.execute("UPDATE orders SET status='approved' WHERE id=?", (order_id,))
        audit(db, user, "approved_order", "order", order_id, "Order passed stock availability check.")
        return {"id": order_id, "status": "approved"}


def reject_order(order_id: str, reason: str, user: dict[str, str]) -> dict[str, Any]:
    with connect() as db:
        db.execute("BEGIN IMMEDIATE")
        order = db.execute("SELECT * FROM orders WHERE id=?", (order_id,)).fetchone()
        if order is None:
            raise HTTPException(status_code=404, detail="Order not found.")
        if order["status"] != "pending_review":
            raise HTTPException(status_code=409, detail="Only orders awaiting review can be rejected.")
        db.execute("UPDATE orders SET status='rejected', note=? WHERE id=?", (reason, order_id))
        audit(db, user, "rejected_order", "order", order_id, reason)
        return {"id": order_id, "status": "rejected", "reason": reason}


def run_production(payload: dict[str, Any], user: dict[str, str]) -> dict[str, Any]:
    run_id = str(uuid.uuid4())
    with connect() as db:
        db.execute("BEGIN IMMEDIATE")
        if payload["actual_good_packets"] > payload["expected_packets"]:
            raise HTTPException(status_code=422, detail="Good output cannot exceed the expected batch output.")
        required = [
            ("RM-FLOUR", Decimal(payload["flour_kg"]), "Flour"),
            ("RM-OIL", Decimal(payload["oil_litres"]), "Oil"),
            ("RM-SPICE", Decimal(payload["spice_kg"]), "Spice mix"),
            ("PK-POUCH", Decimal(payload["actual_good_packets"] + payload["damaged_pouches"]), "Pouches"),
            ("PK-CARTON", Decimal(payload["cartons_used"]), "Cartons"),
        ]
        shortages = [f"{name}: short {amount - balance(db, code)}" for code, amount, name in required if balance(db, code) < amount]
        if shortages:
            raise HTTPException(status_code=409, detail="Insufficient production inputs. " + "; ".join(shortages))
        run_number = f"RUN-{datetime.now():%y%m%d}-{run_id[:6].upper()}"
        db.execute(
            "INSERT INTO production_runs VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (run_id, "murukku-200", run_number, payload["expected_packets"], payload["actual_good_packets"], payload["damaged_pouches"], payload["cartons_used"], str(payload["flour_kg"]), str(payload["oil_litres"]), str(payload["spice_kg"]), now(), user["id"]),
        )
        for (code, amount, name), unit, category in zip(
            required, ("kg", "litre", "kg", "piece", "piece"),
            ("Raw material", "Raw material", "Raw material", "Packaging", "Packaging"),
        ):
            if amount:
                add_movement(db, code, name, category, -amount, unit, "production", "production_run", run_id, f"Production issue {run_number}", user)
        add_movement(db, "FG-MUR-200", "Murukku 200 g", "Finished goods", Decimal(payload["actual_good_packets"]), "packet", "production_output", "production_run", run_id, f"Good output {run_number}", user)
        audit(db, user, "recorded_production", "production_run", run_id, json.dumps(payload, default=str))
        return {"id": run_id, "run_number": run_number, "status": "posted"}


def dispatch_order(order_id: str, quantity: int, user: dict[str, str]) -> dict[str, Any]:
    invoice_id = str(uuid.uuid4())
    with connect() as db:
        db.execute("BEGIN IMMEDIATE")
        order = db.execute(
            """SELECT o.*, c.state_code FROM orders o JOIN customers c ON c.id=o.customer_id WHERE o.id=?""",
            (order_id,),
        ).fetchone()
        if order is None:
            raise HTTPException(status_code=404, detail="Order not found.")
        if order["status"] != "approved":
            raise HTTPException(status_code=409, detail="Approve the order before dispatching.")
        if quantity != order["quantity"]:
            raise HTTPException(status_code=422, detail="Dispatch the full approved quantity; split dispatch is not enabled in this demo.")
        available = balance(db, "FG-MUR-200")
        if available < quantity:
            raise HTTPException(status_code=409, detail=f"Insufficient finished stock: {quantity - int(available)} packet shortage.")
        taxable = Decimal(order["unit_price"]) * quantity
        tax = taxable * Decimal(order["gst_rate"]) / Decimal(100)
        intra_state = order["state_code"] == "33"
        cgst = (tax / 2).quantize(CENT, rounding=ROUND_HALF_UP) if intra_state else Decimal("0")
        sgst = tax - cgst if intra_state else Decimal("0")
        igst = Decimal("0") if intra_state else tax
        total = taxable + cgst + sgst + igst
        invoice_number = f"INV-{datetime.now():%y%m%d}-{invoice_id[:6].upper()}"
        db.execute(
            "INSERT INTO invoices VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (invoice_id, invoice_number, order_id, money(taxable), money(cgst), money(sgst), money(igst), money(total), "0.00", "posted", None, None, now()),
        )
        add_movement(db, "FG-MUR-200", "Murukku 200 g", "Finished goods", Decimal(-quantity), "packet", "dispatch", "order", order_id, f"Dispatch for {order['order_number']}", user)
        db.execute("UPDATE orders SET status='dispatched' WHERE id=?", (order_id,))
        audit(db, user, "dispatched_order", "order", order_id, f"{quantity} packets; invoice {invoice_number} issued.")
        return {
            "id": invoice_id, "invoice_number": invoice_number, "taxable_amount": money(taxable),
            "cgst": money(cgst), "sgst": money(sgst), "igst": money(igst),
            "total": money(total), "status": "posted",
        }


def record_payment(invoice_id: str, payload: dict[str, Any], user: dict[str, str]) -> dict[str, Any]:
    amount = Decimal(payload["amount"])
    with connect() as db:
        db.execute("BEGIN IMMEDIATE")
        invoice = db.execute("SELECT * FROM invoices WHERE id=?", (invoice_id,)).fetchone()
        if invoice is None:
            raise HTTPException(status_code=404, detail="Invoice not found.")
        if invoice["status"] != "posted":
            raise HTTPException(status_code=409, detail="Payments can only be recorded against a posted invoice.")
        outstanding = Decimal(invoice["total"]) - Decimal(invoice["paid"])
        if amount > outstanding:
            raise HTTPException(status_code=422, detail=f"Payment exceeds outstanding balance of Rs. {money(outstanding)}.")
        payment_id = str(uuid.uuid4())
        db.execute(
            "INSERT INTO payments VALUES (?,?,?,?,?,?,?)",
            (payment_id, invoice_id, money(amount), payload["method"], payload.get("reference") or "", user["id"], now()),
        )
        new_paid = Decimal(invoice["paid"]) + amount
        db.execute("UPDATE invoices SET paid=? WHERE id=?", (money(new_paid), invoice_id))
        audit(db, user, "recorded_payment", "invoice", invoice_id, f"Rs. {money(amount)} received by {payload['method']}.")
        return {"id": payment_id, "invoice_id": invoice_id, "amount": money(amount), "paid": money(new_paid), "outstanding": money(Decimal(invoice["total"]) - new_paid)}


def cancel_invoice(invoice_id: str, reason: str, user: dict[str, str]) -> dict[str, Any]:
    with connect() as db:
        db.execute("BEGIN IMMEDIATE")
        invoice = db.execute("SELECT * FROM invoices WHERE id=?", (invoice_id,)).fetchone()
        if invoice is None:
            raise HTTPException(status_code=404, detail="Invoice not found.")
        if invoice["status"] != "posted":
            raise HTTPException(status_code=409, detail="This invoice has already been cancelled.")
        if Decimal(invoice["paid"]) > 0:
            raise HTTPException(status_code=409, detail="Refund recorded payments before cancelling this invoice.")
        credit_note = f"CN-{datetime.now():%y%m%d}-{invoice_id[:6].upper()}"
        db.execute(
            "UPDATE invoices SET status='cancelled', credit_note_number=?, cancellation_reason=? WHERE id=?",
            (credit_note, reason, invoice_id),
        )
        audit(db, user, "cancelled_invoice_with_credit_note", "invoice", invoice_id, f"{credit_note}: {reason}")
        return {"id": invoice_id, "status": "cancelled", "credit_note_number": credit_note}


PURCHASABLE_ITEMS = {
    "RM-FLOUR": ("Flour", "Raw material", "kg"),
    "RM-OIL": ("Oil", "Raw material", "litre"),
    "RM-SPICE": ("Spice mix", "Raw material", "kg"),
    "PK-POUCH": ("Pouches", "Packaging", "piece"),
    "PK-CARTON": ("Cartons", "Packaging", "piece"),
}


def record_purchase(payload: dict[str, Any], user: dict[str, str]) -> dict[str, Any]:
    item = PURCHASABLE_ITEMS.get(payload["item_code"])
    if item is None:
        raise HTTPException(status_code=422, detail="Choose a raw material or packaging item from the catalogue.")
    item_name, category, unit = item
    quantity = Decimal(payload["quantity"])
    unit_price = Decimal(payload["unit_price"])
    total = quantity * unit_price
    purchase_id = str(uuid.uuid4())
    with connect() as db:
        db.execute("BEGIN IMMEDIATE")
        db.execute(
            "INSERT INTO purchases VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (purchase_id, payload["item_code"], item_name, str(quantity), unit, money(unit_price), money(total), payload["supplier"], payload.get("reference") or "", payload["purchase_date"], now(), user["id"]),
        )
        add_movement(db, payload["item_code"], item_name, category, quantity, unit, "purchase_in", "purchase", purchase_id, f"Purchase from {payload['supplier']}", user)
        audit(db, user, "recorded_purchase", "purchase", purchase_id, f"{quantity} {unit} of {item_name} at Rs. {money(unit_price)} per {unit}.")
        return {"id": purchase_id, "item_code": payload["item_code"], "quantity": str(quantity), "unit_price": money(unit_price), "total": money(total)}

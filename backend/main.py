from __future__ import annotations

import csv
import io
import os
import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal

from fastapi import Depends, FastAPI, HTTPException, Query, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from backend.auth import ROLES, create_token, current_user, verify_password
from backend.database import DATABASE_URL, connect, initialize
from backend.workflows import (
    approve_order,
    cancel_invoice,
    create_order,
    dispatch_order,
    reject_order,
    record_purchase,
    record_payment,
    run_production,
)

initialize()

if os.getenv("DATABASE_URL") and (
    len(os.getenv("APP_SECRET", "")) < 32
    or os.getenv("APP_SECRET", "").startswith("replace-")
    or os.getenv("APP_SECRET") == "local-only-demo-secret-change-before-deployment"
):
    raise RuntimeError("Set APP_SECRET to a private random value of at least 32 characters when DATABASE_URL is configured.")

cors_origins = [
    origin.strip()
    for origin in os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",")
    if origin.strip()
]
app = FastAPI(
    title="Order-to-Audit | NIT Trichy",
    description="Benchmark-first order, production, stock-ledger and GST workflows.",
    version="1.0.0",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

User = dict[str, str]


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=128)


class OrderRequest(BaseModel):
    customer_id: str
    quantity: int = Field(gt=0, le=1_000_000)
    unit_price: Decimal = Field(gt=0, max_digits=12, decimal_places=2)


class ProductionRequest(BaseModel):
    expected_packets: int = Field(gt=0, le=1_000_000)
    actual_good_packets: int = Field(gt=0, le=1_000_000)
    flour_kg: Decimal = Field(gt=0, max_digits=14, decimal_places=3)
    oil_litres: Decimal = Field(gt=0, max_digits=14, decimal_places=3)
    spice_kg: Decimal = Field(gt=0, max_digits=14, decimal_places=3)
    damaged_pouches: int = Field(default=0, ge=0, le=1_000_000)
    cartons_used: int = Field(default=0, ge=0, le=1_000_000)


class DispatchRequest(BaseModel):
    quantity: int = Field(gt=0, le=1_000_000)


class PaymentRequest(BaseModel):
    amount: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    method: str = Field(default="Bank transfer", min_length=2, max_length=40)
    reference: str | None = Field(default=None, max_length=100)


class CancelRequest(BaseModel):
    reason: str = Field(min_length=5, max_length=500)


class PurchaseRequest(BaseModel):
    item_code: str
    quantity: Decimal = Field(gt=0, max_digits=14, decimal_places=3)
    unit_price: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    supplier: str = Field(min_length=2, max_length=120)
    reference: str = Field(default="", max_length=80)
    purchase_date: date


class CustomerRequest(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    customer_type: str = Field(min_length=2, max_length=40)
    address: str = Field(min_length=4, max_length=300)
    state: str = Field(min_length=2, max_length=60)
    state_code: str = Field(pattern=r"^\d{2}$")
    gstin: str = Field(default="", max_length=20)
    phone: str = Field(default="", max_length=20)


class OrderRejectRequest(BaseModel):
    reason: str = Field(min_length=5, max_length=500)


class ProductUpdate(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    sku: str = Field(min_length=2, max_length=40)
    unit: Literal["packet"] = "packet"
    hsn: str = Field(min_length=4, max_length=12)
    gst_rate: Decimal = Field(ge=0, le=100, max_digits=5, decimal_places=2)


class BomLineUpdate(BaseModel):
    ingredient: str = Field(min_length=2, max_length=80)
    item_code: str = Field(min_length=2, max_length=30)
    quantity_per_packet: Decimal = Field(gt=0, max_digits=14, decimal_places=3)
    unit: str = Field(min_length=1, max_length=20)


class BomUpdate(BaseModel):
    lines: list[BomLineUpdate] = Field(min_length=5, max_length=5)


def require_role(*allowed: str):
    def check(user: User = Depends(current_user)) -> dict[str, str]:
        if user["role"] not in allowed:
            raise HTTPException(status_code=403, detail="This action is not available for your role.")
        return user

    return check


def row_dicts(rows: Any) -> list[dict[str, Any]]:
    return [dict(row) for row in rows]


@app.get("/")
def home() -> dict[str, str]:
    return {"message": "Order-to-Audit System is running", "status": "success"}


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "healthy", "mode": "postgresql" if os.getenv("DATABASE_URL") else "local-demo"}


@app.post("/api/auth/login")
def login(payload: LoginRequest) -> dict[str, Any]:
    with connect() as db:
        user = db.execute(
            "SELECT id, username, display_name, role, password_hash FROM users WHERE username = ?",
            (payload.username,),
        ).fetchone()
    if user is None or not verify_password(payload.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Username or password is incorrect.")
    profile = {key: user[key] for key in ("id", "username", "display_name", "role")}
    return {"token": create_token(profile), "user": profile, "demo": True}


@app.get("/api/overview")
def overview(user: User = Depends(current_user)) -> dict[str, Any]:
    with connect() as db:
        balances = db.execute(
            """SELECT item_code, item_name, category, unit, SUM(CAST(quantity AS REAL)) AS balance
               FROM stock_movements GROUP BY item_code, item_name, category, unit ORDER BY category, item_name"""
        ).fetchall()
        production = db.execute("SELECT * FROM production_runs ORDER BY created_at DESC LIMIT 5").fetchall()
        orders = db.execute(
            """SELECT o.id, o.order_number, o.quantity, o.status, c.name AS customer_name,
                      c.state AS customer_state, i.total AS invoice_total, i.paid AS paid
               FROM orders o JOIN customers c ON c.id=o.customer_id
               LEFT JOIN invoices i ON i.order_id=o.id
               ORDER BY o.created_at DESC"""
        ).fetchall()
        invoices = db.execute("SELECT * FROM invoices ORDER BY created_at").fetchall()
        materials = db.execute(
            """SELECT item_code, SUM(CAST(quantity AS REAL)) AS balance FROM stock_movements
               WHERE category IN ('Raw material','Packaging') GROUP BY item_code"""
        ).fetchall()
        bom_rows = db.execute(
            "SELECT item_code, quantity_per_packet FROM bom_lines WHERE product_id='murukku-200'"
        ).fetchall()
    stock = {row["item_code"]: Decimal(str(row["balance"] or 0)) for row in materials}
    bom = {row["item_code"]: Decimal(row["quantity_per_packet"]) for row in bom_rows}
    invoice_rows = row_dicts(invoices)
    outstanding = sum((Decimal(row["total"]) - Decimal(row["paid"]) for row in invoice_rows if row["status"] == "posted"), Decimal(0))
    production_rows = row_dicts(production)
    current_run = production_rows[0] if production_rows else None
    return {
        "demo": True,
        "mode": "LOCAL DEMO DATA",
        "user": user,
        "summary": {
            "finished_stock": str(_balance(db_path_item="FG-MUR-200")),
            "open_orders": sum(1 for row in orders if row["status"] in ("pending_review", "approved")),
            "outstanding": str(outstanding),
            "production_yield": (
                round((int(current_run["actual_good_packets"]) / int(current_run["expected_packets"]) - 1) * 100, 1)
                if current_run
                else 0
            ),
        },
        "raw_materials": [
            {"item_code": code, "balance": str(stock.get(code, Decimal(0)))}
            for code in ("RM-FLOUR", "RM-OIL", "RM-SPICE")
        ],
        "inventory": row_dicts(balances),
        "orders": row_dicts(orders),
        "production": production_rows,
        "recent_movements": _recent_movements(),
        "benchmark": {
            "expected_packets": int(current_run["expected_packets"]) if current_run else 200,
            "actual_good_packets": int(current_run["actual_good_packets"]) if current_run else 188,
            "finished_stock_after_production": "238",
            "finished_stock_after_dispatch": "88",
            "retailer_a_taxable": "7500.00",
            "retailer_a_cgst": "187.50",
            "retailer_a_sgst": "187.50",
            "retailer_a_invoice_total": "7875.00",
            "retailer_a_outstanding": "3875.00",
            "yield_variance_percent": (
                round((int(current_run["actual_good_packets"]) / int(current_run["expected_packets"]) - 1) * 100, 1)
                if current_run
                else -6
            ),
            "oil_consumption_variance_percent": (
                round(float(
                    (Decimal(current_run["oil_litres"]) /
                     (Decimal(current_run["expected_packets"]) * bom.get("RM-OIL", Decimal(0))) - 1) * 100
                ), 1)
                if current_run and bom.get("RM-OIL")
                else None
            ),
            "distributor_shortage": max(0, 120 - int(_balance(db_path_item="FG-MUR-200"))),
        },
    }


def _balance(db_path_item: str) -> Decimal:
    with connect() as db:
        row = db.execute(
            "SELECT COALESCE(SUM(CAST(quantity AS REAL)), 0) AS balance FROM stock_movements WHERE item_code = ?",
            (db_path_item,),
        ).fetchone()
    return Decimal(str(row["balance"])).quantize(Decimal("0.001")).normalize()


def _recent_movements(limit: int = 8) -> list[dict[str, Any]]:
    with connect() as db:
        rows = db.execute(
            "SELECT * FROM stock_movements ORDER BY created_at DESC, id DESC LIMIT ?", (limit,)
        ).fetchall()
    return row_dicts(rows)


@app.get("/api/orders")
def list_orders(user: User = Depends(current_user)) -> dict[str, Any]:
    with connect() as db:
        rows = db.execute(
            """SELECT o.*, c.name AS customer_name, c.state AS customer_state, c.state_code,
                      i.id AS invoice_id, i.invoice_number, i.taxable_amount, i.cgst, i.sgst, i.igst, i.total, i.paid
               FROM orders o JOIN customers c ON c.id=o.customer_id
               LEFT JOIN invoices i ON i.order_id=o.id
               ORDER BY o.created_at DESC"""
        ).fetchall()
    results = row_dicts(rows)
    for row in results:
        row["available_stock"] = str(_balance("FG-MUR-200"))
        row["shortage"] = (
            max(0, int(row["quantity"]) - int(Decimal(row["available_stock"])))
            if row["status"] in ("pending_review", "approved")
            else 0
        )
        row["tax_treatment"] = "CGST + SGST" if row["state_code"] == "33" else "IGST"
    return {"orders": results}


@app.post("/api/orders", status_code=201)
def post_order(payload: OrderRequest, user: User = Depends(require_role("Salesman", "Admin", "Owner"))) -> dict[str, Any]:
    return {"order": create_order(payload.model_dump(), user)}


@app.post("/api/orders/{order_id}/approve")
def post_approval(order_id: str, user: User = Depends(require_role("Admin", "Owner"))) -> dict[str, Any]:
    return {"order": approve_order(order_id, user)}


@app.post("/api/orders/{order_id}/reject")
def post_rejection(
    order_id: str,
    payload: OrderRejectRequest,
    user: User = Depends(require_role("Admin", "Owner")),
) -> dict[str, Any]:
    return {"order": reject_order(order_id, payload.reason, user)}


@app.post("/api/orders/{order_id}/dispatch")
def post_dispatch(
    order_id: str,
    payload: DispatchRequest,
    user: User = Depends(require_role("Admin", "Owner")),
) -> dict[str, Any]:
    return {"invoice": dispatch_order(order_id, payload.quantity, user)}


@app.get("/api/production")
def list_production(user: User = Depends(current_user)) -> dict[str, Any]:
    with connect() as db:
        rows = db.execute("SELECT * FROM production_runs ORDER BY created_at DESC").fetchall()
        bom_rows = db.execute(
            "SELECT item_code, quantity_per_packet FROM bom_lines WHERE product_id='murukku-200'"
        ).fetchall()
    bom = {row["item_code"]: Decimal(row["quantity_per_packet"]) for row in bom_rows}
    runs = row_dicts(rows)
    for run in runs:
        expected = Decimal(run["expected_packets"])
        plans = {
            "flour_kg": bom.get("RM-FLOUR", Decimal(0)) * expected,
            "oil_litres": bom.get("RM-OIL", Decimal(0)) * expected,
            "spice_kg": bom.get("RM-SPICE", Decimal(0)) * expected,
            "pouches": bom.get("PK-POUCH", Decimal(0)) * expected,
            "cartons": bom.get("PK-CARTON", Decimal(0)) * expected,
        }
        run["planned"] = {key: format(value.normalize(), "f") for key, value in plans.items()}
        run["yield_variance_percent"] = round(
            (int(run["actual_good_packets"]) / int(run["expected_packets"]) - 1) * 100, 1
        )
        run["oil_variance_percent"] = (
            round((float(run["oil_litres"]) / float(plans["oil_litres"]) - 1) * 100, 1)
            if plans["oil_litres"]
            else None
        )
    return {"runs": runs}


@app.post("/api/production", status_code=201)
def post_production(
    payload: ProductionRequest,
    user: User = Depends(require_role("Production Supervisor", "Admin", "Owner")),
) -> dict[str, Any]:
    return {"production_run": run_production(payload.model_dump(), user)}


@app.get("/api/inventory")
def inventory(user: User = Depends(current_user)) -> dict[str, Any]:
    with connect() as db:
        rows = db.execute(
            """SELECT item_code, item_name, category, unit,
                      SUM(CAST(quantity AS REAL)) AS balance
               FROM stock_movements
               GROUP BY item_code, item_name, category, unit ORDER BY category, item_name"""
        ).fetchall()
        movements = db.execute(
            "SELECT * FROM stock_movements ORDER BY created_at DESC, id DESC LIMIT 100"
        ).fetchall()
    return {"items": row_dicts(rows), "movements": row_dicts(movements)}


@app.get("/api/purchases")
def purchases(user: User = Depends(current_user)) -> dict[str, Any]:
    with connect() as db:
        rows = db.execute("SELECT * FROM purchases ORDER BY purchase_date DESC, created_at DESC").fetchall()
    return {"purchases": row_dicts(rows)}


@app.post("/api/purchases", status_code=201)
def post_purchase(
    payload: PurchaseRequest,
    user: User = Depends(require_role("Admin", "Owner")),
) -> dict[str, Any]:
    return {"purchase": record_purchase(payload.model_dump(mode="json"), user)}


@app.get("/api/costing")
def costing(user: User = Depends(current_user)) -> dict[str, Any]:
    with connect() as db:
        run = db.execute("SELECT * FROM production_runs ORDER BY created_at DESC LIMIT 1").fetchone()
        purchases_rows = db.execute(
            """SELECT item_code, unit_price FROM (
                   SELECT item_code, unit_price,
                          ROW_NUMBER() OVER (PARTITION BY item_code ORDER BY purchase_date DESC, created_at DESC, id DESC) AS rank
                   FROM purchases
               ) WHERE rank=1"""
        ).fetchall()
    if run is None:
        return {
            "run_number": None,
            "complete": False,
            "known_cost": "0.00",
            "known_cost_per_good_packet": "0.00",
            "missing_costs": [],
            "valuation_basis": "Latest recorded purchase unit rates; opening stock is unvalued; excludes labor, energy and overheads.",
        }
    unit_prices = {row["item_code"]: Decimal(row["unit_price"]) for row in purchases_rows}
    quantities = {
        "RM-FLOUR": Decimal(run["flour_kg"]),
        "RM-OIL": Decimal(run["oil_litres"]),
        "RM-SPICE": Decimal(run["spice_kg"]),
        "PK-POUCH": Decimal(run["actual_good_packets"] + run["damaged_pouches"]),
        "PK-CARTON": Decimal(run["cartons_used"]),
    }
    components = []
    missing_costs = []
    known_cost = Decimal(0)
    for code, quantity in quantities.items():
        name, _, unit = {
            "RM-FLOUR": ("Flour", "Raw material", "kg"),
            "RM-OIL": ("Oil", "Raw material", "litre"),
            "RM-SPICE": ("Spice mix", "Raw material", "kg"),
            "PK-POUCH": ("Pouches", "Packaging", "piece"),
            "PK-CARTON": ("Cartons", "Packaging", "piece"),
        }[code]
        price = unit_prices.get(code)
        if price is None:
            missing_costs.append(name)
            components.append({"item": name, "quantity": str(quantity), "unit": unit, "unit_cost": None, "cost": None})
            continue
        cost = quantity * price
        known_cost += cost
        components.append({"item": name, "quantity": str(quantity), "unit": unit, "unit_cost": str(price), "cost": str(cost.quantize(Decimal("0.01")))})
    return {
        "run_number": run["run_number"],
        "complete": not missing_costs,
        "known_cost": str(known_cost.quantize(Decimal("0.01"))),
        "known_cost_per_good_packet": str((known_cost / Decimal(run["actual_good_packets"])).quantize(Decimal("0.01"))),
        "missing_costs": missing_costs,
        "components": components,
        "valuation_basis": "Latest recorded purchase unit rates; opening stock is unvalued; excludes labor, energy and overheads.",
    }


@app.get("/api/customers")
def customers(user: User = Depends(current_user)) -> dict[str, Any]:
    with connect() as db:
        rows = db.execute("SELECT * FROM customers ORDER BY name").fetchall()
    return {"customers": row_dicts(rows)}


@app.post("/api/customers", status_code=201)
def post_customer(
    payload: CustomerRequest,
    user: User = Depends(require_role("Admin", "Owner")),
) -> dict[str, Any]:
    if (payload.state.casefold() == "tamil nadu") != (payload.state_code == "33"):
        raise HTTPException(status_code=422, detail="Tamil Nadu must use state code 33, and state code 33 is reserved for Tamil Nadu.")
    customer_id = str(uuid.uuid4())
    with connect() as db:
        db.execute("BEGIN IMMEDIATE")
        db.execute(
            "INSERT INTO customers VALUES (?,?,?,?,?,?,?,?)",
            (customer_id, payload.name, payload.customer_type, payload.address, payload.state, payload.state_code, payload.gstin, payload.phone),
        )
        db.execute(
            "INSERT INTO audit_logs VALUES (?,?,?,?,?,?,?,?)",
            (str(uuid.uuid4()), user["display_name"], user["role"], "created_customer", "customer", customer_id, payload.name, datetime.now().astimezone().isoformat(timespec="seconds")),
        )
    return {"customer": {"id": customer_id, **payload.model_dump()}}


@app.get("/api/products")
def products(user: User = Depends(current_user)) -> dict[str, Any]:
    with connect() as db:
        products_rows = db.execute("SELECT * FROM products ORDER BY name").fetchall()
        bom = db.execute("SELECT * FROM bom_lines ORDER BY ingredient").fetchall()
    return {"products": row_dicts(products_rows), "bom": row_dicts(bom)}


@app.put("/api/products/{product_id}")
def update_product(
    product_id: str,
    payload: ProductUpdate,
    user: User = Depends(require_role("Admin", "Owner")),
) -> dict[str, Any]:
    with connect() as db:
        db.execute("BEGIN IMMEDIATE")
        product = db.execute("SELECT id FROM products WHERE id=?", (product_id,)).fetchone()
        if product is None:
            raise HTTPException(status_code=404, detail="Product not found.")
        sku_owner = db.execute("SELECT id FROM products WHERE sku=? AND id<>?", (payload.sku, product_id)).fetchone()
        if sku_owner:
            raise HTTPException(status_code=409, detail="That SKU is already assigned to another product.")
        db.execute(
            "UPDATE products SET name=?, sku=?, unit=?, hsn=?, gst_rate=? WHERE id=?",
            (payload.name, payload.sku, payload.unit, payload.hsn, str(payload.gst_rate), product_id),
        )
        db.execute(
            "INSERT INTO audit_logs VALUES (?,?,?,?,?,?,?,?)",
            (str(uuid.uuid4()), user["display_name"], user["role"], "updated_product", "product", product_id, payload.model_dump_json(), datetime.now().astimezone().isoformat(timespec="seconds")),
        )
        updated = db.execute("SELECT * FROM products WHERE id=?", (product_id,)).fetchone()
    return {"product": dict(updated)}


@app.put("/api/products/{product_id}/bom")
def update_bom(
    product_id: str,
    payload: BomUpdate,
    user: User = Depends(require_role("Admin", "Owner")),
) -> dict[str, Any]:
    allowed_items = {
        "RM-FLOUR": ("Flour", "kg"),
        "RM-OIL": ("Oil", "litre"),
        "RM-SPICE": ("Spice mix", "kg"),
        "PK-POUCH": ("Pouch", "piece"),
        "PK-CARTON": ("Carton", "piece"),
    }
    codes = [line.item_code for line in payload.lines]
    if len(set(codes)) != len(allowed_items) or set(codes) != set(allowed_items):
        raise HTTPException(status_code=422, detail="The benchmark BOM must contain exactly one line for each of the five tracked inputs.")
    if any(line.unit != allowed_items[line.item_code][1] for line in payload.lines):
        raise HTTPException(status_code=422, detail="Each BOM item must retain its inventory unit.")

    with connect() as db:
        db.execute("BEGIN IMMEDIATE")
        if db.execute("SELECT id FROM products WHERE id=?", (product_id,)).fetchone() is None:
            raise HTTPException(status_code=404, detail="Product not found.")
        db.execute("DELETE FROM bom_lines WHERE product_id=?", (product_id,))
        bom_rows = []
        for line in payload.lines:
            ingredient, unit = allowed_items[line.item_code]
            bom_rows.append(
                (str(uuid.uuid4()), product_id, line.ingredient or ingredient, line.item_code, str(line.quantity_per_packet), unit)
            )
        db.executemany(
            """INSERT INTO bom_lines (id,product_id,ingredient,item_code,quantity_per_packet,unit)
               VALUES (?,?,?,?,?,?)""",
            bom_rows,
        )
        db.execute(
            "INSERT INTO audit_logs VALUES (?,?,?,?,?,?,?,?)",
            (str(uuid.uuid4()), user["display_name"], user["role"], "updated_bom", "product", product_id, payload.model_dump_json(), datetime.now().astimezone().isoformat(timespec="seconds")),
        )
        updated = db.execute("SELECT * FROM bom_lines WHERE product_id=? ORDER BY ingredient", (product_id,)).fetchall()
    return {"bom": row_dicts(updated)}


@app.get("/api/invoices")
def invoices(user: User = Depends(current_user)) -> dict[str, Any]:
    with connect() as db:
        rows = db.execute(
            """SELECT i.*, o.order_number, c.name AS customer_name, c.state AS customer_state
               FROM invoices i JOIN orders o ON o.id=i.order_id JOIN customers c ON c.id=o.customer_id
               ORDER BY i.created_at DESC"""
        ).fetchall()
        payments = db.execute("SELECT * FROM payments ORDER BY created_at DESC").fetchall()
    return {"invoices": row_dicts(rows), "payments": row_dicts(payments)}


@app.get("/api/invoices/{invoice_id}/pdf")
def invoice_pdf(invoice_id: str, user: User = Depends(current_user)) -> Response:
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfgen import canvas
    except ImportError as exc:
        raise HTTPException(status_code=503, detail="Install the backend PDF dependencies to generate invoices.") from exc

    with connect() as db:
        row = db.execute(
            """SELECT i.*, o.order_number, o.quantity, o.unit_price, c.name AS customer_name,
                      c.address, c.state, c.state_code
               FROM invoices i JOIN orders o ON o.id=i.order_id
               JOIN customers c ON c.id=o.customer_id WHERE i.id=?""",
            (invoice_id,),
        ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Invoice not found.")
    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    pdf.setTitle(f"Tax invoice {row['invoice_number']}")
    pdf.setFont("Helvetica-Bold", 20)
    pdf.drawString(48, 790, "TIRUCHIRAPPALLI FOODS")
    pdf.setFont("Helvetica", 10)
    pdf.drawString(48, 770, "Tax invoice | GSTIN: 33AABCU9603R1ZM | Demo manufacturer")
    pdf.line(48, 752, 547, 752)
    pdf.setFont("Helvetica-Bold", 13)
    pdf.drawString(48, 725, f"Invoice {row['invoice_number']}")
    pdf.setFont("Helvetica", 10)
    invoice_date = row["created_at"]
    if isinstance(invoice_date, datetime):
        invoice_date = invoice_date.strftime("%Y-%m-%d")
    else:
        invoice_date = str(invoice_date)[:10]
    pdf.drawString(48, 705, f"Date: {invoice_date}")
    details_y = 680
    if row["status"] == "cancelled":
        pdf.setFont("Helvetica-Bold", 12)
        pdf.drawString(48, 685, f"CANCELLED · Credit note {row['credit_note_number']}")
        details_y = 658
    pdf.drawString(48, details_y, f"Bill to: {row['customer_name']}")
    pdf.drawString(48, details_y - 16, f"Address: {row['address']}")
    pdf.drawString(48, details_y - 32, f"Place of supply: {row['state']} ({row['state_code']})")
    pdf.line(48, details_y - 60, 547, details_y - 60)
    pdf.setFont("Helvetica-Bold", 10)
    pdf.drawString(48, details_y - 80, "Description")
    pdf.drawString(340, details_y - 80, "Qty")
    pdf.drawString(405, details_y - 80, "Rate")
    pdf.drawString(490, details_y - 80, "Taxable")
    pdf.setFont("Helvetica", 10)
    pdf.drawString(48, details_y - 102, "Murukku 200 g")
    pdf.drawString(340, details_y - 102, str(row["quantity"]))
    pdf.drawString(405, details_y - 102, f"Rs. {row['unit_price']}")
    pdf.drawString(490, details_y - 102, f"Rs. {row['taxable_amount']}")
    labels = [
        ("Taxable amount", row["taxable_amount"]),
        ("CGST", row["cgst"]),
        ("SGST", row["sgst"]),
        ("IGST", row["igst"]),
        ("Invoice total", row["total"]),
        ("Payment received", row["paid"]),
        ("Balance due", str(Decimal(row["total"]) - Decimal(row["paid"]))),
    ]
    y = 530
    for label, amount in labels:
        pdf.drawRightString(450, y, label)
        pdf.drawRightString(545, y, f"Rs. {amount}")
        y -= 22
    pdf.setFont("Helvetica-Oblique", 9)
    pdf.drawString(48, 90, "Generated from the local benchmark demo. Not a real tax document.")
    pdf.save()
    buffer.seek(0)
    return Response(
        buffer.getvalue(),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{row["invoice_number"]}.pdf"'},
    )


@app.post("/api/invoices/{invoice_id}/payments", status_code=201)
def post_payment(
    invoice_id: str,
    payload: PaymentRequest,
    user: User = Depends(require_role("Admin", "Owner")),
) -> dict[str, Any]:
    return {"payment": record_payment(invoice_id, payload.model_dump(), user)}


@app.post("/api/invoices/{invoice_id}/cancel")
def post_cancellation(
    invoice_id: str,
    payload: CancelRequest,
    user: User = Depends(require_role("Admin", "Owner")),
) -> dict[str, Any]:
    return {"invoice": cancel_invoice(invoice_id, payload.reason, user)}


def _report_month_bounds(month: str | None) -> tuple[date, date] | None:
    if month is None:
        return None
    try:
        start = date.fromisoformat(f"{month}-01")
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="Month must be a valid YYYY-MM value.") from exc
    next_month = date(start.year + start.month // 12, start.month % 12 + 1, 1)
    return start, next_month


@app.get("/api/reports")
def reports(
    month: str | None = Query(default=None, pattern=r"^\d{4}-(0[1-9]|1[0-2])$"),
    user: User = Depends(current_user),
) -> dict[str, Any]:
    bounds = _report_month_bounds(month)
    timestamp_cast = "::timestamptz" if DATABASE_URL else ""
    date_cast = "::date" if DATABASE_URL else ""
    if bounds:
        start, next_month = bounds
        start_timestamp = f"{start.isoformat()}T00:00:00+00:00"
        next_timestamp = f"{next_month.isoformat()}T00:00:00+00:00"
        invoice_filter = f" WHERE i.created_at >= ?{timestamp_cast} AND i.created_at < ?{timestamp_cast}"
        production_filter = f" WHERE created_at >= ?{timestamp_cast} AND created_at < ?{timestamp_cast}"
        movement_filter = f" WHERE created_at >= ?{timestamp_cast} AND created_at < ?{timestamp_cast}"
        purchase_filter = f" WHERE purchase_date >= ?{date_cast} AND purchase_date < ?{date_cast}"
        timestamp_parameters = (start_timestamp, next_timestamp)
        purchase_parameters = (start.isoformat(), next_month.isoformat())
    else:
        invoice_filter = production_filter = movement_filter = purchase_filter = ""
        timestamp_parameters = purchase_parameters = ()

    with connect() as db:
        invoices_rows = db.execute(
            f"""SELECT i.invoice_number, c.name AS customer, c.state, i.taxable_amount,
                      i.cgst, i.sgst, i.igst, i.total, i.paid, i.status, i.created_at
               FROM invoices i JOIN orders o ON o.id=i.order_id JOIN customers c ON c.id=o.customer_id
               {invoice_filter}
               ORDER BY i.created_at""",
            timestamp_parameters,
        ).fetchall()
        runs = db.execute(
            f"SELECT * FROM production_runs{production_filter} ORDER BY created_at",
            timestamp_parameters,
        ).fetchall()
        movements = db.execute(
            f"SELECT * FROM stock_movements{movement_filter} ORDER BY created_at",
            timestamp_parameters,
        ).fetchall()
        purchases_rows = db.execute(
            f"SELECT * FROM purchases{purchase_filter} ORDER BY purchase_date",
            purchase_parameters,
        ).fetchall()
    return {
        "period": month or "all",
        "sales_and_gst": row_dicts(invoices_rows),
        "production": row_dicts(runs),
        "purchases_and_stock": row_dicts(purchases_rows),
        "ledger": row_dicts(movements),
    }


@app.get("/api/reports/export/{report_name}")
def export_report(
    report_name: str,
    format: str = "csv",
    month: str | None = Query(default=None, pattern=r"^\d{4}-(0[1-9]|1[0-2])$"),
    user: User = Depends(current_user),
) -> Response:
    all_reports = reports(month=month, user=user)
    report_map = {
        "sales": all_reports["sales_and_gst"],
        "gst": all_reports["sales_and_gst"],
        "production": all_reports["production"],
        "purchases": all_reports["purchases_and_stock"],
        "ledger": all_reports["ledger"],
    }
    records = report_map.get(report_name)
    if records is None:
        raise HTTPException(status_code=404, detail="Unknown report.")
    if not records:
        raise HTTPException(status_code=404, detail="There is no data in this report yet.")
    filename = f"{report_name}-{month or date.today().isoformat()}"
    if format.lower() == "xlsx":
        try:
            from openpyxl import Workbook
        except ImportError as exc:
            raise HTTPException(status_code=503, detail="Install openpyxl to export Excel workbooks.") from exc
        workbook = Workbook()
        sheet = workbook.active
        sheet.title = report_name.title()[:31]
        sheet.append(list(records[0].keys()))
        for record in records:
            sheet.append([record[key] for key in records[0].keys()])
        output = io.BytesIO()
        workbook.save(output)
        output.seek(0)
        return StreamingResponse(
            output,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f'attachment; filename="{filename}.xlsx"'},
        )
    if format.lower() != "csv":
        raise HTTPException(status_code=400, detail="Export format must be csv or xlsx.")
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=list(records[0].keys()))
    writer.writeheader()
    writer.writerows(records)
    return Response(
        output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}.csv"'},
    )


@app.get("/api/audit")
def audit_log(user: User = Depends(require_role("Accountant/Auditor", "Admin", "Owner"))) -> dict[str, Any]:
    with connect() as db:
        rows = db.execute("SELECT * FROM audit_logs ORDER BY created_at DESC LIMIT 100").fetchall()
    return {"events": row_dicts(rows)}


@app.get("/api/roles")
def roles() -> dict[str, Any]:
    return {"roles": list(ROLES)}

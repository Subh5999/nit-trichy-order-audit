import atexit
import sqlite3
import os
import tempfile
from decimal import Decimal

import pytest

_test_database_directory = tempfile.TemporaryDirectory(prefix="order-audit-tests-")
atexit.register(_test_database_directory.cleanup)
os.environ["DEMO_DATABASE_PATH"] = os.path.join(_test_database_directory.name, "demo.sqlite3")

from fastapi.testclient import TestClient

from backend.main import app

client = TestClient(app)


def token_for(username: str, password: str = "demo123") -> str:
    response = client.post("/api/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200
    return response.json()["token"]


def headers(username: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token_for(username)}"}


def test_seeded_benchmark_stock_and_tax_totals():
    response = client.get("/api/overview", headers=headers("owner"))
    assert response.status_code == 200
    data = response.json()
    balances = {item["item_code"]: float(item["balance"]) for item in data["inventory"]}
    assert balances["RM-FLOUR"] == 120
    assert balances["RM-OIL"] == 19.5
    assert balances["RM-SPICE"] == 3.8
    assert balances["PK-POUCH"] == 306
    assert balances["PK-CARTON"] == 21
    assert balances["FG-MUR-200"] == 88
    assert data["summary"]["finished_stock"] == "88"
    assert data["benchmark"]["distributor_shortage"] == 32
    assert data["benchmark"]["yield_variance_percent"] == -6
    assert data["benchmark"]["oil_consumption_variance_percent"] == 5
    assert data["benchmark"]["finished_stock_after_production"] == "238"
    assert data["benchmark"]["finished_stock_after_dispatch"] == "88"
    seeded_purchase = client.get("/api/purchases", headers=headers("owner")).json()["purchases"][0]
    assert seeded_purchase["item_code"] == "RM-FLOUR"
    assert seeded_purchase["quantity"] == "60"
    assert seeded_purchase["unit_price"] == "45.00"
    assert seeded_purchase["total"] == "2700.00"
    benchmark_run = client.get("/api/production", headers=headers("owner")).json()["runs"][0]
    assert benchmark_run["expected_packets"] == 200
    assert benchmark_run["actual_good_packets"] == 188
    assert benchmark_run["flour_kg"] == "40"
    assert benchmark_run["oil_litres"] == "10.5"
    assert benchmark_run["spice_kg"] == "1.2"
    assert benchmark_run["damaged_pouches"] == 6
    assert benchmark_run["cartons_used"] == 9
    costing = client.get("/api/costing", headers=headers("owner")).json()
    assert costing["known_cost"] == "1800.00"
    assert costing["known_cost_per_good_packet"] == "9.57"
    assert "Oil" in costing["missing_costs"]

    orders = client.get("/api/orders", headers=headers("owner")).json()["orders"]
    retailer = next(row for row in orders if row["customer_name"] == "Retailer A")
    assert retailer["taxable_amount"] == "7500.00"
    assert retailer["cgst"] == "187.50"
    assert retailer["sgst"] == "187.50"
    assert retailer["igst"] == "0.00"
    assert retailer["total"] == "7875.00"
    assert retailer["paid"] == "4000.00"
    assert Decimal(retailer["total"]) - Decimal(retailer["paid"]) == Decimal("3875.00")


def test_insufficient_dispatch_is_blocked_without_ledger_change():
    owner_headers = headers("owner")
    before = client.get("/api/inventory", headers=owner_headers).json()
    distributor = next(
        row for row in client.get("/api/orders", headers=owner_headers).json()["orders"]
        if row["customer_name"] == "Distributor B"
    )
    assert distributor["shortage"] == 32
    assert distributor["tax_treatment"] == "IGST"
    rejected = client.post(
        f"/api/orders/{distributor['id']}/approve",
        headers=owner_headers,
    )
    assert rejected.status_code == 409
    assert "32 packet shortage" in rejected.json()["detail"]
    blocked_dispatch = client.post(
        f"/api/orders/{distributor['id']}/dispatch",
        headers=owner_headers,
        json={"quantity": 120},
    )
    assert blocked_dispatch.status_code == 409
    after = client.get("/api/inventory", headers=owner_headers).json()
    assert len(before["movements"]) == len(after["movements"])


def test_roles_restrict_production_mutations():
    response = client.post(
        "/api/production",
        headers=headers("auditor"),
        json={
            "expected_packets": 200, "actual_good_packets": 188,
            "flour_kg": 40, "oil_litres": 10.5, "spice_kg": 1.2,
            "damaged_pouches": 6, "cartons_used": 9,
        },
    )
    assert response.status_code == 403


def test_purchase_posts_cost_and_stock_movement_together():
    response = client.post(
        "/api/purchases",
        headers=headers("owner"),
        json={
            "item_code": "RM-OIL", "quantity": "1.25", "unit_price": "100",
            "supplier": "Demo oil supplier", "reference": "DEMO-BILL-002",
            "purchase_date": "2026-11-18",
        },
    )
    assert response.status_code == 201
    purchase = response.json()["purchase"]
    assert purchase["total"] == "125.00"
    inventory = client.get("/api/inventory", headers=headers("owner")).json()["items"]
    oil = next(row for row in inventory if row["item_code"] == "RM-OIL")
    assert float(oil["balance"]) == 20.75
    assert client.post(
        "/api/purchases",
        headers=headers("auditor"),
        json={
            "item_code": "RM-OIL", "quantity": 1, "unit_price": 100,
            "supplier": "Demo supplier", "purchase_date": "2026-11-18",
        },
    ).status_code == 403


def test_failed_production_rolls_back_without_partial_movements():
    owner_headers = headers("owner")
    movements_before = client.get("/api/inventory", headers=owner_headers).json()["movements"]
    response = client.post(
        "/api/production",
        headers=headers("production"),
        json={
            "expected_packets": 200, "actual_good_packets": 180,
            "flour_kg": 1000, "oil_litres": 10, "spice_kg": 1,
            "damaged_pouches": 0, "cartons_used": 0,
        },
    )
    assert response.status_code == 409
    movements_after = client.get("/api/inventory", headers=owner_headers).json()["movements"]
    assert movements_after == movements_before


def test_successful_production_posts_actual_consumption_and_output_together():
    auth = headers("production")
    response = client.post(
        "/api/production",
        headers=auth,
        json={
            "expected_packets": 10, "actual_good_packets": 9,
            "flour_kg": "2", "oil_litres": "0.5", "spice_kg": "0.05",
            "damaged_pouches": 1, "cartons_used": 1,
        },
    )
    assert response.status_code == 201
    run_id = response.json()["production_run"]["id"]
    inventory = client.get("/api/inventory", headers=auth).json()
    balances = {row["item_code"]: float(row["balance"]) for row in inventory["items"]}
    assert balances["RM-FLOUR"] == 118
    assert balances["RM-OIL"] == 20.25
    assert balances["PK-POUCH"] == 296
    assert balances["PK-CARTON"] == 20
    assert balances["FG-MUR-200"] == 97
    run = next(
        row for row in client.get("/api/production", headers=auth).json()["runs"]
        if row["id"] == run_id
    )
    assert run["planned"] == {
        "flour_kg": "2", "oil_litres": "0.5", "spice_kg": "0.05",
        "pouches": "10", "cartons": "0.45",
    }
    assert run["damaged_pouches"] == 1
    assert run["yield_variance_percent"] == -10
    assert run["oil_variance_percent"] == 0
    movements = [row for row in inventory["movements"] if row["source_id"] == run_id]
    assert len(movements) == 6
    issued = {row["item_code"]: row["quantity"] for row in movements}
    assert issued == {
        "RM-FLOUR": "-2", "RM-OIL": "-0.5", "RM-SPICE": "-0.05",
        "PK-POUCH": "-10", "PK-CARTON": "-1", "FG-MUR-200": "9",
    }


def test_invoice_pdf_and_final_payment():
    owner_headers = headers("owner")
    invoice = client.get("/api/invoices", headers=owner_headers).json()["invoices"][0]
    pdf = client.get(f"/api/invoices/{invoice['id']}/pdf", headers=owner_headers)
    assert pdf.status_code == 200
    assert pdf.headers["content-type"] == "application/pdf"
    assert pdf.content.startswith(b"%PDF")

    payment = client.post(
        f"/api/invoices/{invoice['id']}/payments",
        headers=owner_headers,
        json={"amount": "3875.00", "method": "Bank transfer", "reference": "DEMO-RECEIPT-002"},
    )
    assert payment.status_code == 201
    assert payment.json()["payment"]["outstanding"] == "0.00"
    cancelled_paid_invoice = client.post(
        f"/api/invoices/{invoice['id']}/cancel",
        headers=owner_headers,
        json={"reason": "Customer requested cancellation"},
    )
    assert cancelled_paid_invoice.status_code == 409


def test_interstate_dispatch_invoices_igst_without_local_tax():
    order = client.post(
        "/api/orders",
        headers=headers("sales"),
        json={"customer_id": "distributor-b", "quantity": 1, "unit_price": "50"},
    ).json()["order"]
    admin_headers = headers("admin")
    assert client.post(f"/api/orders/{order['id']}/approve", headers=admin_headers).status_code == 200
    dispatch = client.post(
        f"/api/orders/{order['id']}/dispatch",
        headers=admin_headers,
        json={"quantity": 1},
    )
    assert dispatch.status_code == 200
    assert dispatch.json()["invoice"]["igst"] == "2.50"
    assert dispatch.json()["invoice"]["cgst"] == "0.00"
    assert dispatch.json()["invoice"]["sgst"] == "0.00"


def test_unpaid_posted_invoice_is_cancelled_with_credit_note():
    before = client.get("/api/inventory", headers=headers("owner")).json()["items"]
    stock_before = next(row["balance"] for row in before if row["item_code"] == "FG-MUR-200")
    order = client.post(
        "/api/orders",
        headers=headers("sales"),
        json={"customer_id": "retailer-a", "quantity": 1, "unit_price": "50"},
    ).json()["order"]
    owner_headers = headers("owner")
    assert client.post(f"/api/orders/{order['id']}/approve", headers=owner_headers).status_code == 200
    dispatch = client.post(
        f"/api/orders/{order['id']}/dispatch",
        headers=owner_headers,
        json={"quantity": 1},
    )
    assert dispatch.status_code == 200
    invoice = dispatch.json()["invoice"]
    invoice_id = invoice["id"]
    assert invoice["taxable_amount"] == "50.00"
    assert invoice["cgst"] == "1.25"
    assert invoice["sgst"] == "1.25"
    assert invoice["igst"] == "0.00"
    assert invoice["total"] == "52.50"
    assert client.get("/api/orders", headers=owner_headers).json()["orders"][0]["status"] == "dispatched"
    after = client.get("/api/inventory", headers=owner_headers).json()["items"]
    stock_after = next(row["balance"] for row in after if row["item_code"] == "FG-MUR-200")
    assert float(stock_before) - float(stock_after) == 1
    movements = client.get("/api/inventory", headers=owner_headers).json()["movements"]
    assert any(row["source_id"] == order["id"] and row["movement_type"] == "dispatch" for row in movements)
    cancellation = client.post(
        f"/api/invoices/{invoice_id}/cancel",
        headers=owner_headers,
        json={"reason": "Customer cancelled the order"},
    )
    assert cancellation.status_code == 200
    assert cancellation.json()["invoice"]["credit_note_number"].startswith("CN-")


def test_all_roles_have_expected_read_and_mutation_permissions():
    usernames = {
        "Salesman": "sales",
        "Admin": "admin",
        "Production Supervisor": "production",
        "Accountant/Auditor": "auditor",
        "Owner": "owner",
    }
    role_headers = {}
    for role, username in usernames.items():
        response = client.post(
            "/api/auth/login",
            json={"username": username, "password": "demo123"},
        )
        assert response.status_code == 200
        assert response.json()["user"]["role"] == role
        role_headers[role] = {"Authorization": f"Bearer {response.json()['token']}"}

    read_routes = (
        "/api/overview", "/api/orders", "/api/production", "/api/inventory",
        "/api/customers", "/api/products", "/api/invoices", "/api/reports", "/api/costing",
    )
    for auth in role_headers.values():
        for path in read_routes:
            assert client.get(path, headers=auth).status_code == 200

    admin_or_owner = {"Admin", "Owner"}
    for role, auth in role_headers.items():
        expected = 404 if role in {"Salesman", "Admin", "Owner"} else 403
        assert client.post(
            "/api/orders",
            headers=auth,
            json={"customer_id": "missing", "quantity": 1, "unit_price": "1"},
        ).status_code == expected

        expected = 409 if role in {"Production Supervisor", "Admin", "Owner"} else 403
        assert client.post(
            "/api/production",
            headers=auth,
            json={
                "expected_packets": 1, "actual_good_packets": 1,
                "flour_kg": 1000000, "oil_litres": 1, "spice_kg": 1,
            },
        ).status_code == expected

        expected = 422 if role in admin_or_owner else 403
        assert client.post(
            "/api/purchases",
            headers=auth,
            json={
                "item_code": "INVALID", "quantity": 1, "unit_price": 1,
                "supplier": "Demo supplier", "purchase_date": "2026-11-18",
            },
        ).status_code == expected

        expected = 422 if role in admin_or_owner else 403
        assert client.post(
            "/api/customers",
            headers=auth,
            json={
                "name": "Demo Customer", "customer_type": "Retailer", "address": "Demo market",
                "state": "Tamil Nadu", "state_code": "29",
            },
        ).status_code == expected

        expected = 404 if role in admin_or_owner else 403
        assert client.post(
            "/api/invoices/missing/payments",
            headers=auth,
            json={"amount": "1", "method": "Cash"},
        ).status_code == expected
        assert client.post(
            "/api/invoices/missing/cancel",
            headers=auth,
            json={"reason": "Not a real invoice"},
        ).status_code == expected
        assert client.post("/api/orders/missing/approve", headers=auth).status_code == expected
        assert client.post(
            "/api/orders/missing/reject",
            headers=auth,
            json={"reason": "Not a real order"},
        ).status_code == expected
        assert client.post(
            "/api/orders/missing/dispatch",
            headers=auth,
            json={"quantity": 1},
        ).status_code == expected
        assert client.put(
            "/api/products/missing",
            headers=auth,
            json={"name": "Product", "sku": "SKU", "unit": "packet", "hsn": "123456", "gst_rate": 5},
        ).status_code == expected
        expected_bom = 404 if role in admin_or_owner else 403
        assert client.put(
            "/api/products/missing/bom",
            headers=auth,
            json={
                "lines": [
                    {"ingredient": name, "item_code": code, "quantity_per_packet": "0.1", "unit": unit}
                    for code, name, unit in [
                        ("RM-FLOUR", "Flour", "kg"),
                        ("RM-OIL", "Oil", "litre"),
                        ("RM-SPICE", "Spice mix", "kg"),
                        ("PK-POUCH", "Pouch", "piece"),
                        ("PK-CARTON", "Carton", "piece"),
                    ]
                ]
            },
        ).status_code == expected_bom

        expected_audit = 200 if role in {"Accountant/Auditor", "Admin", "Owner"} else 403
        assert client.get("/api/audit", headers=auth).status_code == expected_audit


def test_stock_ledger_reconciles_and_is_immutable():
    from backend.database import connect

    auth = headers("owner")
    inventory = client.get("/api/inventory", headers=auth).json()
    movements = inventory["movements"]
    assert all(row["source_type"] and row["source_id"] for row in movements)
    for item in inventory["items"]:
        balance = sum(
            (Decimal(row["quantity"]) for row in movements if row["item_code"] == item["item_code"]),
            Decimal(0),
        )
        assert balance == Decimal(str(item["balance"])).quantize(Decimal("0.001"))

    with connect() as db:
        movement_id = movements[0]["id"]
        with pytest.raises(sqlite3.IntegrityError):
            db.execute("UPDATE stock_movements SET quantity='0' WHERE id=?", (movement_id,))
        with pytest.raises(sqlite3.IntegrityError):
            db.execute("DELETE FROM stock_movements WHERE id=?", (movement_id,))


def test_order_rejection_is_role_restricted_and_audited():
    order = client.post(
        "/api/orders",
        headers=headers("sales"),
        json={"customer_id": "retailer-a", "quantity": 2, "unit_price": "50"},
    ).json()["order"]
    path = f"/api/orders/{order['id']}/reject"
    assert client.post(path, headers=headers("auditor"), json={"reason": "Not approved"}).status_code == 403
    assert client.post(path, headers=headers("admin"), json={"reason": "No"}).status_code == 422

    rejected = client.post(
        path,
        headers=headers("admin"),
        json={"reason": "Customer order requires correction"},
    )
    assert rejected.status_code == 200
    assert rejected.json()["order"]["status"] == "rejected"
    stored = next(
        row for row in client.get("/api/orders", headers=headers("owner")).json()["orders"]
        if row["id"] == order["id"]
    )
    assert stored["note"] == "Customer order requires correction"
    audit = client.get("/api/audit", headers=headers("auditor")).json()["events"]
    assert any(row["action"] == "rejected_order" and row["entity_id"] == order["id"] for row in audit)
    assert client.get("/api/auth/demo-users").status_code == 404


def test_admin_customer_creation_persists_and_is_audited():
    auth = headers("admin")
    response = client.post(
        "/api/customers",
        headers=auth,
        json={
            "name": "Demo Evaluation Retailer",
            "customer_type": "Retailer",
            "address": "Fictional demo market",
            "state": "Karnataka",
            "state_code": "29",
            "gstin": "",
            "phone": "",
        },
    )
    assert response.status_code == 201
    customer_id = response.json()["customer"]["id"]
    customers = client.get("/api/customers", headers=auth).json()["customers"]
    assert any(row["id"] == customer_id and row["state_code"] == "29" for row in customers)
    audit = client.get("/api/audit", headers=auth).json()["events"]
    assert any(row["action"] == "created_customer" and row["entity_id"] == customer_id for row in audit)


def test_product_and_bom_updates_are_restricted_and_drive_planned_consumption():
    owner_headers = headers("owner")
    product = client.get("/api/products", headers=owner_headers).json()["products"][0]
    product_payload = {key: product[key] for key in ("name", "sku", "unit", "hsn", "gst_rate")}
    assert client.put(
        f"/api/products/{product['id']}",
        headers=headers("auditor"),
        json=product_payload,
    ).status_code == 403
    updated_product = client.put(
        f"/api/products/{product['id']}",
        headers=owner_headers,
        json=product_payload,
    )
    assert updated_product.status_code == 200
    invalid_unit = {**product_payload, "unit": "box"}
    assert client.put(
        f"/api/products/{product['id']}",
        headers=owner_headers,
        json=invalid_unit,
    ).status_code == 422
    invalid_customer = client.post(
        "/api/customers",
        headers=owner_headers,
        json={
            "name": "Demo Customer", "customer_type": "Retailer", "address": "Demo market",
            "state": "Tamil Nadu", "state_code": "29",
        },
    )
    assert invalid_customer.status_code == 422

    bom = client.get("/api/products", headers=owner_headers).json()["bom"]
    lines = [
        {
            "ingredient": line["ingredient"],
            "item_code": line["item_code"],
            "quantity_per_packet": "0.06" if line["item_code"] == "RM-OIL" else line["quantity_per_packet"],
            "unit": line["unit"],
        }
        for line in bom
    ]
    assert client.put(
        f"/api/products/{product['id']}/bom",
        headers=headers("auditor"),
        json={"lines": lines},
    ).status_code == 403
    updated_bom = client.put(
        f"/api/products/{product['id']}/bom",
        headers=owner_headers,
        json={"lines": lines},
    )
    assert updated_bom.status_code == 200
    runs = client.get("/api/production", headers=owner_headers).json()["runs"]
    benchmark_run = next(row for row in runs if row["run_number"] == "RUN-2026-001")
    assert benchmark_run["planned"]["oil_litres"] == "12"
    assert benchmark_run["oil_variance_percent"] == -12.5


def test_report_exports_return_csv_and_excel_files():
    auth = headers("auditor")
    invoice = client.get("/api/invoices", headers=auth).json()["invoices"][0]
    month = invoice["created_at"][:7]
    monthly_report = client.get(f"/api/reports?month={month}", headers=auth)
    assert monthly_report.status_code == 200
    monthly_data = monthly_report.json()
    assert monthly_data["period"] == month
    assert any(row["invoice_number"] == invoice["invoice_number"] for row in monthly_data["sales_and_gst"])
    no_data = client.get("/api/reports?month=1900-01", headers=auth).json()
    assert no_data["sales_and_gst"] == []
    assert no_data["production"] == []
    assert client.get("/api/reports?month=2026-13", headers=auth).status_code == 422

    csv_report = client.get("/api/reports/export/sales?format=csv", headers=auth)
    assert csv_report.status_code == 200
    assert csv_report.headers["content-type"].startswith("text/csv")
    assert "invoice_number" in csv_report.text

    xlsx_report = client.get("/api/reports/export/gst?format=xlsx", headers=auth)
    assert xlsx_report.status_code == 200
    assert xlsx_report.headers["content-type"].startswith(
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    assert xlsx_report.content.startswith(b"PK")
    monthly_csv = client.get(f"/api/reports/export/sales?format=csv&month={month}", headers=auth)
    assert monthly_csv.status_code == 200
    assert f"sales-{month}.csv" in monthly_csv.headers["content-disposition"]
    assert client.get("/api/reports/export/sales?format=csv&month=1900-01", headers=auth).status_code == 404
    assert client.get("/api/reports/export/sales?format=pdf", headers=auth).status_code == 400

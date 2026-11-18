# Benchmark Results

## Assignment scenario

| Step | Input | Expected result |
| --- | --- | --- |
| Opening stock | Flour 100 kg; oil 30 L; spice 5 kg; pouches 500; cartons 30; finished goods 50 packets | Stored as source-referenced opening movements |
| Purchase | 60 kg flour at ₹45/kg | Flour balance increases to 160 kg; purchase value ₹2,700 |
| Production | Expected 200; good 188; flour 40 kg; oil 10.5 L; spice 1.2 kg; 6 damaged pouches; 9 cartons | Planned BOM: 40 kg flour, 10 L oil, 1 kg spice, 200 pouches, 9 cartons. Yield −6%; oil consumption variance +5%; movements post atomically |
| After production | Add 188 good packets to opening finished stock | 238 finished packets |
| Retailer A | Tamil Nadu, 150 packets at ₹50, GST 5%, payment ₹4,000 | Taxable ₹7,500; CGST ₹187.50; SGST ₹187.50; total ₹7,875; due ₹3,875 |
| Distributor B | Karnataka, 120 packets after Retailer A dispatch | 88 available; 32-packet shortage; IGST if later invoiced |

## Expected closing balances

| Item | Expected balance |
| --- | ---: |
| Flour | 120 kg |
| Oil | 19.5 L |
| Spice mix | 3.8 kg |
| Pouches | 306 |
| Cartons | 21 |
| Finished goods after production | 238 packets |
| Finished goods after Retailer A dispatch | 88 packets |

## Local verification

The backend test suite checks opening/purchase/production/closing figures, exact Retailer A tax and outstanding, Distributor B's 32-packet shortage and blocked dispatch, an interstate IGST invoice, a successful order-to-invoice/dispatch flow with stock decrement, production consumption/yield/wastage, all five roles' read and mutation permissions, ledger reconciliation and immutability, audit/rejection, customer creation, PDF invoices, monthly filtering, CSV/XLSX exports, and production rollback.

**Latest recorded test result:** 15 backend tests passed; the frontend production build completed successfully. Pytest emitted a Starlette deprecation warning about its `httpx` test-client integration. The test run verified that the seeded `backend/data/demo.sqlite3` checksum did not change and that the isolated temporary test database directory was cleaned up. This does not establish that Supabase/PostgreSQL works.

## Not validated

- Applying the SQL migration to a live Supabase/PostgreSQL instance or running transaction workflows against it.
- Automated browser tests, device-specific mobile checks, and end-to-end browser download UX.
- Production identity management, real tax/legal compliance, or full manufacturing cost accounting.

Re-run backend and frontend checks using the commands in [README.md](README.md) before relying on these results after later code changes.

# Design Note

## Application shape

The frontend is a React single-page application served by Vite. It calls a FastAPI JSON API with a signed bearer token stored for the local demo session. FastAPI applies role checks at mutation endpoints. SQLite is the no-credentials development database; a psycopg adapter can connect to PostgreSQL after the Supabase migration is applied.

## Stock and transaction model

`stock_movements` is the source of truth for balances. Each movement records item, signed quantity, unit, movement type, source type/id, actor and timestamp. SQLite triggers and a PostgreSQL trigger reject movement updates/deletes. Purchase, production, dispatch and payment mutations run in database transactions. SQLite serializes writers with `BEGIN IMMEDIATE`; the PostgreSQL adapter maps that transaction-start request to an advisory transaction lock.

Finished stock availability is rechecked in the approval and dispatch workflow. The UI's shortage display is informational and is not the final stock validation. Distributor B's unfulfillable quantity is therefore visible without allowing a negative finished-goods balance.

## Production and BOM

The BOM stores per-packet quantities for the five benchmark-tracked inputs. For a run with expected output `N`, planned quantity is `BOM per packet × N`. The API returns planned quantities and calculates yield variance as `(good output / expected output − 1) × 100`; consumption variance uses `(actual / planned − 1) × 100`. Actual issues and good output are recorded as ledger entries in the same transaction as the production run.

The BOM editor keeps item codes and inventory units fixed to avoid mixing unlike stock units. Editing BOM values changes future planned quantities; it does not rewrite posted runs or stock movements.

Monthly report filters use UTC month boundaries for timestamped records and calendar-date boundaries for purchases. Exported CSV/XLSX files use the same selected period; omitting the month parameter returns the full available history.

## Orders, tax and audit

Orders move through review, approved, dispatched, rejected or cancelled states. Dispatch is allowed only for an approved order, rechecks available stock, computes tax with `Decimal`, creates the invoice and posts the stock issue atomically. Tamil Nadu uses CGST/SGST; interstate supply uses IGST. Posted invoices are retained and cancellation records a credit-note reference rather than deleting the invoice.

Audit rows capture order decisions and operational/master-data mutations. Read-only Accountant/Auditor permissions are enforced server-side, not only hidden in the UI.

## Costing and scope

Known material cost is estimated from the latest recorded purchase rates and quantities of the latest production run. It is not a full manufacturing cost: the assignment provides no opening-stock valuation, labor, energy or overhead rates. The demo schema intentionally focuses on the single Murukku 200 g product and named benchmark movements, rather than pretending to be a complete generic ERP.

## Deployment boundary

The default SQLite seed and demo credentials are for local evaluation. PostgreSQL requires applying the migration and configuring `DATABASE_URL`, a private 32-character-or-longer `APP_SECRET`, and `CORS_ORIGINS`. The current app does not include production identity management or a hardened deployment lifecycle; PostgreSQL and production hosting require separate validation.

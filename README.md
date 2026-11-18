# Batchline · Order-to-Audit

A benchmark-first order, production and audit application for the NIT Tiruchirappalli individual internship project. It follows the Murukku 200 g scenario from purchasing and production through stock movements, dispatch, GST invoicing, payments and reports. All seeded names and contact details are fictional.

## Technology

- Frontend: React 18, Vite, Tailwind CSS, Recharts and Lucide.
- Backend: FastAPI, Pydantic, ReportLab and openpyxl.
- Local development database: SQLite.
- Optional hosted database: Supabase PostgreSQL via psycopg and the SQL migration.
- Authentication: signed bearer sessions and role-checked API routes for the five demo roles.

## Run locally

Requirements: Node.js 20+ and Python 3.10+.

From the repository root, install backend dependencies and start the API:

```bash
python -m venv backend/venv
backend/venv/bin/pip install -r backend/requirements.txt
backend/venv/bin/uvicorn backend.main:app --reload --port 8000
```

In another terminal, install frontend dependencies and start Vite:

```bash
cd frontend
npm install
npm run dev
```

Open the Vite URL (normally `http://localhost:5173`). API docs are at `http://localhost:8000/docs`. By default, the backend creates `backend/data/demo.sqlite3` and seeds the benchmark if the database is empty. No Supabase credentials are needed in local demo mode.

If port 8000 is already in use, start the API with `backend/venv/bin/uvicorn backend.main:app --reload --port 8002`, then start Vite with `VITE_API_URL=http://localhost:8002 npm run dev` from `frontend/`.

### Demo accounts

All five fictional demo accounts use `demo123`:

| Username | Role |
| --- | --- |
| `sales` | Salesman |
| `admin` | Admin |
| `production` | Production Supervisor |
| `auditor` | Accountant/Auditor (read-only) |
| `owner` | Owner |

These credentials and the local token-signing fallback are for local evaluation only. Do not expose the demo service to the public internet or use demo credentials in production.

## Implemented workflows

- Mobile-responsive order intake, review, approval/rejection and dispatch with stock checks.
- Customer creation and product/BOM editing, with fixed inventory item codes and units for the benchmark recipe.
- Transactional production and purchases; actual consumption and output post together with source-linked append-only stock movements.
- Place-of-supply GST calculation, downloadable PDF invoices, payments, outstanding balances, and invoice cancellation with a credit-note reference.
- Inventory ledger, planned-versus-actual consumption, yield and oil variance, material-cost estimate, and monthly CSV/XLSX reports.
- Audit entries for operational and master-data changes.

Stock balances come from movements rather than writable balance fields. Money uses Python `Decimal`. Direct-material costing uses latest purchase rates and is explicitly partial when rates are unavailable; opening inventory value, labor, energy and overheads are not supplied by the brief.

## Supabase PostgreSQL

Apply [`supabase/migrations/20261118000100_initial_schema.sql`](supabase/migrations/20261118000100_initial_schema.sql) in the Supabase SQL editor. It creates the schema, fictional seed data and an append-only ledger trigger. Set `DATABASE_URL` to the Supabase PostgreSQL connection string and `APP_SECRET` to a private random secret of at least 32 characters before starting the API. `CORS_ORIGINS` is a comma-separated allowlist; by default it permits the local Vite origin.

The root [`.env.example`](.env.example) lists supported backend environment variables. The API does not automatically load a `.env` file; export values in the shell or use a local environment manager. PostgreSQL execution requires applying the migration and configuring an actual database; it has not been exercised as part of the local test suite.

## Useful API routes

- `POST /api/auth/login` — create a demo session.
- `GET /api/overview`, `/api/orders`, `/api/production`, `/api/inventory`, `/api/customers`, `/api/products`, `/api/invoices`, `/api/reports`.
- `POST /api/orders/{id}/approve`, `/reject`, `/dispatch` — Admin/Owner order decisions and stock-checked dispatch.
- `POST /api/production` and `/api/purchases` — Production Supervisor/Admin/Owner and Admin/Owner respectively.
- `PUT /api/products/{id}` and `PUT /api/products/{id}/bom` — Admin/Owner master updates.
- `POST /api/invoices/{id}/payments` and `/cancel` — payment or credit-note cancellation.
- `GET /api/invoices/{id}/pdf` — PDF invoice; `/api/reports?month=YYYY-MM` and `/api/reports/export/{name}?format=csv|xlsx&month=YYYY-MM` — monthly report data and exports. Omit `month` for all available periods.

Every API data route requires a bearer token except login and health. See FastAPI's `/docs` for request fields and response schemas.

## Verify

Run from the repository root:

```bash
backend/venv/bin/python -m pytest backend/tests -q
cd frontend && npm run build
```

The backend tests cover benchmark calculations, every seeded role's read/mutation permissions, stock-ledger reconciliation and immutability, test database cleanup, audit/rejection, BOM-driven production, the order-to-invoice workflow, PDF invoices, monthly reports, and CSV/XLSX exports.

## Known limitations

- The project is a benchmark demo, not production accounting or tax software. GSTIN/company details and demo credentials are fictional placeholders; obtain professional tax review before any real invoice use.
- There is no user provisioning, password reset, refresh-token flow or production identity provider. The demo accounts are migration/seed accounts.
- Customer records can be added but not edited/deleted; the single benchmark product can be edited but additional products are not supported. The BOM editor is intentionally limited to the five tracked benchmark inventory items.
- Production postings are immutable; a dedicated reversal workflow is not yet provided. Do not treat this as a complete manufacturing execution system.
- PostgreSQL/Supabase has migration and adapter support but was not tested against a live Supabase project. Browser-level, device-specific responsiveness testing was not run.

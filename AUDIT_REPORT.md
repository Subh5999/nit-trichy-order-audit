# Technical Audit Report

## Scope

Reviewed the existing React/Vite frontend, FastAPI routes and workflows, authentication and role checks, SQLite schema/seed, Supabase PostgreSQL migration/adapter, benchmark tests, and setup documentation. The supplied Murukku 200 g scenario is used as the acceptance baseline.

## Corrections made in this audit pass

- Removed the unauthenticated demo-user endpoint that returned demo passwords.
- Added Admin/Owner order rejection with a required reason, status validation and an audit record; exposed the action in the Orders view.
- Added Admin/Owner product and BOM editing with tracked item-code/unit validation and audit records.
- Derived production planned quantities and oil/yield variance from the current BOM instead of fixed display constants.
- Added UTC month filtering to report data and CSV/XLSX downloads, with a month selector and period-specific invoice totals in the Reports view.
- Made SQLite benchmark seeding a transaction and added PostgreSQL adapter support for the bulk BOM update operation.
- Added server-side request size/value constraints and a production-database secret guard; made allowed CORS origins configurable.
- Added targeted tests for rejection, role restrictions, BOM-driven plans and CSV/XLSX downloads.

## Current status

| Area | Assessment |
| --- | --- |
| Demo authentication and role-restricted API mutations | Working for the five seeded roles; not production identity management |
| Customer and benchmark product/BOM management | Customer creation and product/BOM editing work; customer edit and additional product creation are not implemented |
| Orders, approval/rejection and shortage checks | Working for the single benchmark product |
| Production, BOM plans and stock ledger | Transactional ledger postings and calculated benchmark variance work; no production reversal workflow |
| GST, invoice PDF, payments and cancellation | Implemented and exercised locally; demo company/tax details are not real |
| Inventory/purchase, costing and reports | Implemented; monthly report filters/exports verified; cost estimate is partial when purchase rates are missing |
| Supabase/PostgreSQL | Migration and adapter are present, but live database migration/connection behavior is unverified |
| Responsive UI | Responsive layout is implemented; no automated browser/device testing was run |

## Validation performed

The current result is summarized in [BENCHMARK_RESULTS.md](BENCHMARK_RESULTS.md). The backend pytest suite, including a complete order-to-invoice dispatch, role matrix, ledger reconciliation and monthly export checks, and the frontend production build were run locally. A running API and Vite frontend were available; PostgreSQL and browser-level interaction were not validated.

## Remaining risks and limitations

- Demo passwords, a local signing-secret fallback, and seeded users are unsuitable for public deployment. The production database path enforces a private `APP_SECRET`, but there is no user-management or identity-provider integration.
- GSTIN, company details and contact data are fictional placeholders. Obtain tax/legal review before real use.
- Master data is deliberately narrow: one sellable benchmark product, five tracked input items, no customer editing, and no new-product creation.
- Production runs are immutable but there is no supported correction/reversal transaction yet.
- PostgreSQL support must be verified by applying the migration to a disposable Supabase/PostgreSQL database and exercising each transaction path before deployment.
- CSV/Excel monthly filtering and invoice PDF generation are API-tested; cross-browser download UX and small-screen device layouts are not end-to-end tested.

## Submission assessment

The local benchmark demo is suitable for a project demonstration after the recorded automated checks pass. It is not production-ready or suitable for real customer, accounting, or tax use. Treat live PostgreSQL testing and browser testing as outstanding evaluation checks.

# Ali Raza Enterprises ERP — Python application foundation

This is the first runnable UI foundation for the local-first ERP. It uses Python, FastAPI, Jinja templates, CSS and PostgreSQL via psycopg. The application foundation is intentionally read-only: it checks database connectivity, reads inventory balances and shows a fixed-rule dashboard assistant. It does not create, alter, insert, update or delete ERP data.

## Prerequisites

- Windows 11
- Python 3.11 or newer (`py -3 --version` in Command Prompt)
- PostgreSQL 18 running locally with database `ali_raza_erp`

## Start on Windows

1. Extract this folder to a normal local folder, e.g. `C:\AliRazaERP\python_app`.
2. Double-click `run_windows.bat`.
3. On the first run, the script creates `.venv`, installs dependencies and creates `.env` from `.env.example`, then opens `.env` in Notepad.
4. Set `DATABASE_PASSWORD` to your local PostgreSQL password and save the file. Do not send the password to anyone or commit/share `.env`.
5. Double-click `run_windows.bat` again.
6. Open `http://127.0.0.1:8000` in your browser.
7. Health check: `http://127.0.0.1:8000/health`.

Internet is needed once to install Python packages. The application itself runs locally. These dependencies are free/open-source.

## Security and current limits

- The server binds to `127.0.0.1` only. Do not change it to `0.0.0.0` or expose it to the factory LAN yet.
- This foundation does not yet implement ERP user login/roles. Do not treat it as production-ready or allow other people to use it.
- Do not use the PostgreSQL `postgres` superuser as the long-term application login. Before enabling transactional screens, we must create and test a least-privilege application role and define approved database access paths.
- Module links are placeholders, not working transaction screens yet.
- No SQL migration is run automatically. Existing ERP schema and test data are not modified.
- Database errors shown on the dashboard are limited to the first line; never put a password into logs or screenshots.

## Read-only dashboard assistant (new in this working copy)

- The dashboard includes a local, rule-based Inventory Assistant for total stock value, stock value by location, and searches against the existing item/variant/shade/party lookup.
- It does not call a cloud AI service, generate SQL, or accept SQL from the user. It delegates to existing parameterized read-only inventory helpers and limits displayed matches.
- It is not yet a generative AI assistant and does not answer accounting, bills, party-ledger, production-costing, HR or payroll questions.
- Application login/roles are not implemented yet. Keep the app bound to `127.0.0.1`; do not expose this endpoint to a factory network until authentication, authorization and request controls are implemented and tested.
- Database writes and financial posting are out of scope.

## Current module placeholders

Inventory, Production, Packing, Sales & Dispatch, Purchasing, Accounting, Reports and Configuration. The Configuration page is a read-only design scaffold; see `docs_CONFIG_MODULE_BLUEPRINT.md` for the future-flexible data model and the Baby Cone/Nalki rules. These are connected to routes, but actual CRUD/transaction features will be implemented only after the existing schema/functions and business rules are mapped and tested.

## Next milestones

1. Verify this application connects to the existing `ali_raza_erp` database.
2. Map verified tables/functions and add safe, read-only inventory and packing views.
3. Design login, roles and permissions; use a dedicated non-superuser DB role before any production usage.
4. Add approved transactional workflows, validations, audit history and automated tests module-by-module.
5. Design the flexible Configuration data model and approval/audit workflow; see `docs_CONFIG_MODULE_BLUEPRINT.md`.
6. Add backup/restore verification before factory deployment.


### Official logo asset (12 October 2026)
The supplied HD Ali Raza Enterprises logo is installed at `app/static/ali-raza-logo-hd.png` and is used in the sidebar, top bar and overview welcome panel. The overview logo has a subtle 3D rotation with reduced-motion accessibility support.

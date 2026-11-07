# Ali Raza Enterprises ERP

Local-first ERP application for Ali Raza Enterprises, Faisalabad, Pakistan.

## Project overview

This repository contains the Python/FastAPI application, PostgreSQL migration scripts, automated tests, UI templates, and implementation notes for a small manufacturing operation. The system is developed and verified incrementally against the business's stock, production, purchasing, packing, and accounting workflows.

## Technology

- Python 3.11+
- FastAPI and Uvicorn
- PostgreSQL 18+
- psycopg 3
- Jinja2 templates and CSS
- Automated service and integration tests

## Functional areas

- Authentication, sessions, CSRF protection, permissions and audit helpers
- Inventory and single-godown stock controls
- Purchasing and goods-receipt workflow
- Production workflows including Dyeing, Large Cone and Baby Cone
- OWN and PARTY stock ownership controls
- Packing and source-allocation workflows
- General ledger, journal validation and accounting reports
- Flexible configuration, measurement and unit-conversion services

Some workflows remain under development or are intentionally draft/read-only. A screen or route does not imply that every business process is production-ready. Consult the latest checkpoint and implementation notes before relying on a feature.

## Local setup (Windows)

1. Install Python 3.11+ and PostgreSQL.
2. Configure a local `.env` file using `.env.example` as a placeholder template.
3. Never commit or share `.env` or database credentials.
4. Run `run_windows.bat` from the project folder.
5. Open `http://127.0.0.1:8000` on the same computer.

Dependencies are listed in `requirements.txt`. Keep the application bound to localhost during development. Do not expose it to a factory network or the public internet until deployment security, least-privilege database access, backup/restore procedures and production acceptance tests are complete.

## Database safety

- Review SQL files under `database/migrations/` before applying them.
- Never reset, recreate, or migrate a live database without an explicit backup and approved change plan.
- Use a least-privilege database account for application runtime.
- Test posting, rollback, audit trails and ledger reconciliation before enabling production transactions.

## Repository hygiene

Environment files, virtual environments, logs, local database dumps, PDFs, generated backups and runtime artifacts are excluded from source synchronization. `.env.example` contains placeholders only.

## Project status

This is an active development project, not a packaged commercial release. Project notes record checkpoints, pending decisions, constraints and test evidence. Business rules must remain configurable where specified; posted transactions must retain the rule snapshots used at posting time.


import hmac
import json
from urllib.parse import parse_qs, urlencode
from decimal import Decimal, InvalidOperation
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field, ValidationError
from psycopg.errors import UniqueViolation, ForeignKeyViolation

from .authz import (
    get_current_user,
    require_permission,
    require_permission_for_user,
)
from .permission_catalog import PERMISSIONS
from .config import get_settings
from .auth_routes import router as auth_router
from .assistant import answer_inventory_question
from .db import (
    get_connection,
    get_database_status,
    get_inventory_stock,
    get_inventory_stock_page,
    get_dashboard_inventory_summary,
    get_configuration_master_data,
    get_party_ledger_data,
)
from .purchasing_service import (
    get_purchasing_page,
    supplier_code_exists,
    get_purchase_receipt_form_data,
    create_purchase_receipt_draft,
    approve_purchase_receipt,
    post_purchase_receipt,
    get_purchase_return_form_data,
    create_purchase_return_draft,
    approve_purchase_return,
    post_purchase_return,
)
from .supplier_service import create_supplier_with_audit
from .packing_service import (
    get_packing_page_data,
    get_packing_form_data,
    create_packing_order_draft,
)
from .packing_assortment_service import (
    get_packing_assortment_form_data,
    create_packing_assortment_draft,
)
from .packing_random_source_service import get_random_packing_source_candidates
from .packing_random_draft_service import create_random_packing_draft
from .production_service import get_production_dashboard_data
from .production_master_service import get_production_masters, save_production_master
from .big_cone_draft_service import get_big_cone_draft_form_data, create_big_cone_draft
from .baby_cone_measurement_service import get_baby_cone_measurement_draft_options
from .configuration_runtime_service import save_baby_cone_measurement_draft
from .dyeing_draft_service import (
    get_dyeing_draft_form_data, create_dyeing_draft,
    get_dyeing_draft_detail, get_dyeing_approval_readiness,
)
from .ownership_use_service import create_ownership_use_request, decide_ownership_use_request, list_ownership_use_requests, list_party_draft_lines
from .configuration_examples import get_configuration_examples
from .configuration_master_service import save_configuration_master_record
from .configuration_service import (
    create_configuration_draft,
    list_configuration_history,
    get_configuration_version_detail,
    get_effective_configuration,
    submit_configuration_for_approval,
    approve_configuration,
    reject_configuration,
)
from .accounting.journal_service import (
    create_journal_draft,
    approve_journal,
    post_journal,
)
from .accounting.fiscal_year_service import create_fiscal_year
from .accounting.report_service import (
    get_trial_balance,
    get_account_ledger,
    get_posting_accounts,
    get_party_ledger_activity,
    get_accounting_setup_readiness,
    get_fiscal_year_period_preview,
    get_party_opening_review,
    get_inventory_gl_reconciliation,
    get_inventory_gl_mapping_readiness,
    get_inventory_journal_review,
)
from datetime import date


BASE_DIR = Path(__file__).resolve().parent
settings = get_settings()
docs_enabled = settings.app_environment.strip().lower() != "production"


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="Local-first ERP interface foundation with controlled purchasing and inventory workflows.",
    docs_url="/docs" if docs_enabled else None,
    redoc_url="/redoc" if docs_enabled else None,
    openapi_url="/openapi.json" if docs_enabled else None,
)


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault(
        "Referrer-Policy",
        "strict-origin-when-cross-origin",
    )
    response.headers.setdefault(
        "Permissions-Policy",
        "camera=(), microphone=(), geolocation=()",
    )
    return response


app.mount(
    "/static",
    StaticFiles(directory=BASE_DIR / "static"),
    name="static",
)

app.include_router(auth_router)

templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


MODULES = [
    {
        "name": "Inventory",
        "icon": "Ã¢â€“Â¦",
        "description": "Stock balances, stock documents, ledger and transfers",
        "status": "Database audit in progress",
        "url": "/modules/inventory",
    },
    {
        "name": "Production",
        "icon": "Ã¢Å¡â„¢",
        "description": "Dyeing DRAFT capture and Baby Cone measurement DRAFT workbench",
        "status": "Dyeing + measurement DRAFT only",
        "url": "/modules/production",
    },
    {
        "name": "Packing",
        "icon": "Ã¢â€“Â£",
        "description": "Packing orders, material use, labour, wastage and FG transfer",
        "status": "Draft-only workflow enabled",
        "url": "/modules/packing",
    },
    {
        "name": "Sales & Dispatch",
        "icon": "Ã¢â€¡Â¢",
        "description": "Order-linked dispatch and inventory movement",
        "status": "Planned",
        "url": "/modules/sales-dispatch",
    },
    {
        "name": "Purchasing",
        "icon": "Ã¯Â¼â€¹",
        "description": "Purchases and supplier-side records",
        "status": "Read-only listings available",
        "url": "/modules/purchasing",
    },
    {
        "name": "Accounting",
        "icon": "Ã¢â€“Â¤",
        "description": "Ledgers, expenses, bank and PDC cheques",
        "status": "Planned",
        "url": "/modules/accounting",
    },
    {
        "name": "Reports",
        "icon": "Ã¢â€“Â¤",
        "description": "Stock, costing, profit and owner dashboard",
        "status": "Planned",
        "url": "/modules/reports",
    },
    {
        "name": "HR & Payroll",
        "icon": "Ã°Å¸â€˜Â¥",
        "description": "Employees, attendance, shifts, leave, overtime, payroll, advances and labour costing",
        "status": "Planned Ã¢â‚¬â€ implementation pending",
        "url": "/modules/hr-payroll",
    },
    {
        "name": "Configuration",
        "icon": "Ã¢Å¡â„¢",
        "description": "Flexible product, measurement, packaging and approval rules",
        "status": "Master data + draft approvals; integrations in progress",
        "url": "/configuration",
    },
]


def require_assistant_csrf(request: Request) -> None:
    """Require the dashboard CSRF token for assistant API requests."""
    csrf_cookie = request.cookies.get("are_erp_csrf", "")
    csrf_header = request.headers.get("x-csrf-token", "")

    if (
        not csrf_cookie
        or not csrf_header
        or not hmac.compare_digest(csrf_cookie, csrf_header)
    ):
        raise HTTPException(
            status_code=403,
            detail="CSRF validation failed",
        )


class AssistantQuestion(BaseModel):
    question: str = Field(default="", max_length=120)


@app.post(
    "/assistant/query",
    dependencies=[
        Depends(require_assistant_csrf),
        Depends(require_permission("assistant.query")),
    ],
)
def assistant_query(payload: AssistantQuestion) -> dict:
    """Read-only, allowlisted dashboard assistant; never accepts SQL or writes data."""
    try:
        return answer_inventory_question(payload.question)
    except Exception:
        return {
            "kind": "error",
            "message": (
                "I could not read the inventory data right now. "
                "Check the database connection and application logs locally."
            ),
            "rows": [],
            "locations": [],
        }


@app.get(
    "/inventory",
    response_class=HTMLResponse,
    dependencies=[Depends(require_permission("inventory.view"))],
)
def inventory_page(
    request: Request,
    q: str = "",
    page: int = 1,
):
    q = q.strip()[:100]

    inventory_data = get_inventory_stock_page(
        q,
        page,
        page_size=50,
    )

    rows = inventory_data["rows"]
    total = inventory_data["total"]
    page = inventory_data["page"]
    pages = inventory_data["pages"]

    return templates.TemplateResponse(
        request=request,
        name="inventory.html",
        context={
            "app_name": settings.app_name,
            "rows": rows,
            "total": total,
            "page": page,
            "pages": pages,
            "q": q,
        },
    )


@app.get(
    "/configuration",
    response_class=HTMLResponse,
)
def configuration_page(
    request: Request,
    user: dict = Depends(require_permission("configuration.view")),
    brands_page: int = 1,
    units_page: int = 1,
    shades_page: int = 1,
    variants_page: int = 1,
):
    """Show the planned flexible configuration model without writing to PostgreSQL."""

    configuration_groups = [
        {
            "title": "Product & variant builder",
            "tag": "Future-ready master data",
            "description": (
                "Add product types and products without adding new code "
                "for each product."
            ),
            "examples": [
                "Product type and process route",
                "Brand, shade, colour and variant attributes",
                "Units, alternate units and conversion rules",
                "Effective dates and active/inactive status",
            ],
        },
        {
            "title": "Baby Cone measurement rules",
            "tag": "Production Head approval",
            "description": (
                "Store measured yarn conversion per item/variant, "
                "supported by actual weighing and length measurement."
            ),
            "examples": [
                "Gross cone weight and empty-core tare",
                "Net yarn grams and measured yards",
                "Grams per yard = net grams ÃƒÂ· measured yards",
                "Required kg = yards Ãƒâ€” grams per yard ÃƒÂ· 1,000",
            ],
        },
        {
            "title": "Nalki product & packaging rules",
            "tag": "Brand-specific defaults",
            "description": (
                "Keep Nalki settings separate from Baby Cone and allow "
                "new brands and packaging types later."
            ),
            "examples": [
                "10 pieces per standard box (initial rule)",
                "Tailor: 38 g; Channel: 52 g; Golden Chain: 60 g",
                "Brand-wise 100-piece finished boxes",
                "Shade/category attributes maintained as master data",
            ],
        },
        {
            "title": "Ownership & stock policy",
            "tag": "Controlled rules",
            "description": (
                "Configure ownership policy by product type while keeping "
                "OWN and each PARTY ledger distinct."
            ),
            "examples": [
                "OWN stock and party-specific stock ledgers",
                "Allowed ownership types by product/process",
                "Party-stock use requires approval and locked rate where allowed",
                "Nalki party-stock policy needs explicit rule resolution before activation",
            ],
        },
        {
            "title": "Process loss & costing",
            "tag": "No double deduction",
            "description": (
                "Configure waste allowances and costing methods by process "
                "and product type."
            ),
            "examples": [
                "Apply agreed Dyeing waste once at material issue",
                "Excess actual loss recorded as company process variance",
                "Salary-based labour vs. theka by process",
                "Effective dates and audit history for rule changes",
            ],
        },
        {
            "title": "Approvals, permissions & audit",
            "tag": "Governed changes",
            "description": (
                "Keep configuration changes reviewable, attributable and "
                "reversible through versioned records."
            ),
            "examples": [
                "Production Head approval for Baby Cone conversion settings",
                "Record who requested, approved and changed each rule",
                "Effective-from dates and old-value/new-value history",
                "No silent edits to rules already used by posted transactions",
            ],
        },
    ]

    def _has_permission(code):
        try:
            require_permission_for_user(user, code)
            return True
        except HTTPException as exc:
            if exc.status_code == 403:
                return False
            raise

    return templates.TemplateResponse(
        request=request,
        name="configuration.html",
        context={
            "app_name": settings.app_name,
            "configuration_groups": configuration_groups,
            "configuration_examples": get_configuration_examples(),
            "can_edit_master_data": _has_permission("configuration.create"),
            "master_data": get_configuration_master_data(
                {
                    "brands": brands_page,
                    "units": units_page,
                    "shades": shades_page,
                    "variants": variants_page,
                },
                company_id=user["company_id"],
            ),
            "csrf_token": request.cookies.get("are_erp_csrf", ""),
        },
    )


@app.get("/configuration/api/effective")
def configuration_effective_api(
    config_type: str,
    config_key: str,
    on_date: date | None = None,
    user: dict = Depends(require_permission("configuration.history.view")),
):
    try:
        result = get_effective_configuration(
            company_id=user["company_id"],
            config_type=config_type,
            config_key=config_key,
            effective_on=on_date or date.today(),
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return {
        "effective_on": (on_date or date.today()).isoformat(),
        "configuration": result,
    }


@app.get(
    "/configuration/api/history",
)
def configuration_history_api(
    request: Request,
    user: dict = Depends(require_permission("configuration.history.view")),
):
    rows = list_configuration_history(company_id=user["company_id"], limit=100)
    response = {"items": rows}
    return response


@app.post("/configuration/api/master/{record_type}")
async def configuration_master_create_api(
    record_type: str, request: Request,
    user: dict = Depends(require_permission("configuration.create")),
):
    data = await _configuration_action_data(request)
    try:
        result = save_configuration_master_record(
            record_type=record_type, payload=data, user=user, request=request
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except UniqueViolation:
        raise HTTPException(status_code=409, detail="A record with this code or name already exists.")
    except ForeignKeyViolation:
        raise HTTPException(status_code=409, detail="A selected master record is no longer available.")
    return {"saved": True, "master_record": result}


@app.put("/configuration/api/master/{record_type}/{record_id}")
async def configuration_master_update_api(
    record_type: str, record_id: int, request: Request,
    user: dict = Depends(require_permission("configuration.create")),
):
    data = await _configuration_action_data(request)
    try:
        result = save_configuration_master_record(
            record_type=record_type, payload=data, user=user,
            request=request, record_id=record_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except UniqueViolation:
        raise HTTPException(status_code=409, detail="A record with this code or name already exists.")
    except ForeignKeyViolation:
        raise HTTPException(status_code=409, detail="A selected master record is no longer available.")
    return {"saved": True, "master_record": result}


@app.get("/configuration/api/versions/{version_id}")
def configuration_version_detail_api(
    version_id: int,
    user: dict = Depends(require_permission("configuration.history.view")),
):
    result = get_configuration_version_detail(
        company_id=user["company_id"], version_id=version_id
    )
    if result is None:
        raise HTTPException(status_code=404, detail="Configuration version not found.")
    return result


async def _configuration_action_data(request: Request) -> dict:
    content_type = request.headers.get("content-type", "").split(";", 1)[0].strip().lower()
    if content_type != "application/json":
        raise HTTPException(status_code=415, detail="Content-Type must be application/json.")
    body = await request.body()
    if len(body) > 8192:
        raise HTTPException(status_code=413, detail="Configuration action payload is too large.")
    csrf_cookie = request.cookies.get("are_erp_csrf", "")
    csrf_header = request.headers.get("x-csrf-token", "")
    if not csrf_cookie or not csrf_header or not hmac.compare_digest(csrf_cookie, csrf_header):
        raise HTTPException(status_code=403, detail="CSRF validation failed.")
    try:
        data = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON request.")
    if not isinstance(data, dict):
        raise HTTPException(status_code=422, detail="Request must be a JSON object.")
    return data


@app.get("/modules/production/masters", response_class=HTMLResponse,
         dependencies=[Depends(require_permission("production.view"))])
def production_masters_page(request: Request):
    user = get_current_user(request)
    data = get_production_masters(user["company_id"])
    can_edit = True
    try:
        require_permission_for_user(user, "configuration.create")
    except HTTPException as exc:
        if exc.status_code == 403:
            can_edit = False
        else:
            raise
    response = templates.TemplateResponse(
        request=request, name="production_masters.html",
        context={"app_name": settings.app_name, "data": data,
                 "can_edit": can_edit,
                 "csrf_token": request.cookies.get("are_erp_csrf", "")})
    response.headers["Cache-Control"] = "no-store"
    return response


@app.post("/modules/production/api/masters/{kind}")
async def production_master_create_api(
    kind: str, request: Request,
    user: dict = Depends(require_permission("configuration.create")),
):
    payload = await _configuration_action_data(request)
    try:
        result = save_production_master(
            kind=kind, payload=payload, company_id=user["company_id"],
            user=user, request=request)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except UniqueViolation:
        raise HTTPException(status_code=409, detail="This code already exists in the company.")
    except ForeignKeyViolation:
        raise HTTPException(status_code=409, detail="A selected department or unit is no longer available.")
    return {"saved": True, "master_record": result}


@app.put("/modules/production/api/masters/{kind}/{record_id}")
async def production_master_update_api(
    kind: str, record_id: int, request: Request,
    user: dict = Depends(require_permission("configuration.create")),
):
    payload = await _configuration_action_data(request)
    try:
        result = save_production_master(
            kind=kind, payload=payload, company_id=user["company_id"],
            user=user, request=request, record_id=record_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except UniqueViolation:
        raise HTTPException(status_code=409, detail="This code already exists in the company.")
    except ForeignKeyViolation:
        raise HTTPException(status_code=409, detail="A selected department or unit is no longer available.")
    return {"saved": True, "master_record": result}


@app.post("/configuration/api/versions/{version_id}/submit")
async def configuration_submit_api(
    request: Request,
    version_id: int,
    user: dict = Depends(require_permission("configuration.create")),
):
    data = await _configuration_action_data(request)
    try:
        result = submit_configuration_for_approval(
            company_id=user["company_id"], version_id=version_id,
            user=user, comments=data.get("comments", ""),
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    return {"submitted": True, "configuration": result}


@app.post("/configuration/api/versions/{version_id}/approve")
async def configuration_approve_api(
    request: Request,
    version_id: int,
    user: dict = Depends(require_permission("configuration.approve")),
):
    data = await _configuration_action_data(request)
    try:
        result = approve_configuration(
            company_id=user["company_id"], version_id=version_id,
            user=user, comments=data.get("comments", ""),
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    return {"approved": result["status"] == "APPROVED", "configuration": result}


@app.post("/configuration/api/versions/{version_id}/reject")
async def configuration_reject_api(
    request: Request,
    version_id: int,
    user: dict = Depends(require_permission("configuration.approve")),
):
    data = await _configuration_action_data(request)
    try:
        result = reject_configuration(
            company_id=user["company_id"], version_id=version_id,
            user=user, comments=data.get("comments", ""),
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    return {"rejected": True, "configuration": result}


@app.post(
    "/configuration/api/drafts",
)
async def configuration_create_draft_api(
    request: Request,
    user: dict = Depends(require_permission("configuration.create")),
):
    content_type = request.headers.get("content-type", "").split(";", 1)[0].strip().lower()
    if content_type != "application/json":
        raise HTTPException(status_code=415, detail="Content-Type must be application/json.")

    body = await request.body()
    if len(body) > 65536:
        raise HTTPException(status_code=413, detail="Configuration payload is too large.")

    csrf_cookie = request.cookies.get("are_erp_csrf", "")
    csrf_header = request.headers.get("x-csrf-token", "")
    if not csrf_cookie or not csrf_header or not hmac.compare_digest(csrf_cookie, csrf_header):
        raise HTTPException(status_code=403, detail="CSRF validation failed.")

    try:
        data = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON request.")

    if not isinstance(data, dict):
        raise HTTPException(status_code=422, detail="Request must be a JSON object.")

    try:
        result = create_configuration_draft(
            user=user,
            config_type=data.get("config_type", ""),
            config_key=data.get("config_key", ""),
            display_name=data.get("display_name", ""),
            payload=data.get("payload", {}),
            change_reason=data.get("change_reason", ""),
            supersedes_version_id=data.get("supersedes_version_id") or None,
        )
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    return {"created": True, "configuration": result}


@app.get("/health")
def health() -> dict:
    return {
        "app": "ok",
        "database": get_database_status()["connected"],
    }


@app.get(
    "/",
    response_class=HTMLResponse,
    dependencies=[Depends(get_current_user)],
)
def dashboard(request: Request):
    db = get_database_status()
    inventory_summary = None
    inventory_error = None

    if db.get("connected"):
        try:
            inventory_summary = get_dashboard_inventory_summary()
        except Exception:
            inventory_error = "Inventory summary is temporarily unavailable."

    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={
            "app_name": settings.app_name,
            "db": db,
            "modules": MODULES,
            "inventory_summary": inventory_summary,
            "inventory_error": inventory_error,
            "logout_csrf_token": request.cookies.get("are_erp_csrf", ""),
        },
    )


@app.get(
    "/accounting",
    response_class=HTMLResponse,
    dependencies=[Depends(require_permission("accounting.view"))],
)
def accounting_page(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="accounting.html",
        context={"app_name": settings.app_name},
    )


def _journal_page_response(request, user, *, form=None, errors=None, action_message="", ref=""):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, journal_no, entry_date, status, debit_total, credit_total
                FROM accounting.journal_entries
                WHERE company_id = %s
                ORDER BY id DESC
                LIMIT 50
                """,
                (int(user["company_id"]),),
            )
            journals = [dict(row) for row in cur.fetchall()]
            cur.execute(
                """
                SELECT id, account_code, account_name, is_control
                FROM accounting.accounts
                WHERE company_id = %s
                  AND is_active = TRUE
                  AND is_group = FALSE
                  AND (
                    is_control = FALSE
                    OR account_code IN ('1221', '1231', '2211', '2241')
                  )
                ORDER BY account_code
                """,
                (int(user["company_id"]),),
            )
            accounts = [dict(row) for row in cur.fetchall()]
            cur.execute(
                """
                SELECT id, party_code, party_name, party_type
                FROM master.parties
                WHERE company_id = %s
                  AND is_active = TRUE
                ORDER BY party_type, party_name
                """,
                (int(user["company_id"]),),
            )
            parties = [dict(row) for row in cur.fetchall()]
            cur.execute(
                """
                SELECT
                    (SELECT COUNT(*) FROM core.fiscal_years WHERE company_id = %s) AS fiscal_year_count,
                    (SELECT COUNT(*) FROM core.fiscal_years WHERE company_id = %s AND is_closed = FALSE) AS open_fiscal_year_count,
                    (
                        SELECT COUNT(*)
                        FROM core.accounting_periods p
                        JOIN core.fiscal_years fy ON fy.id = p.fiscal_year_id
                        WHERE fy.company_id = %s
                    ) AS period_count,
                    (
                        SELECT COUNT(*)
                        FROM core.accounting_periods p
                        JOIN core.fiscal_years fy ON fy.id = p.fiscal_year_id
                        WHERE fy.company_id = %s AND p.is_closed = FALSE
                    ) AS open_period_count
                """,
                (
                    int(user["company_id"]),
                    int(user["company_id"]),
                    int(user["company_id"]),
                    int(user["company_id"]),
                ),
            )
            period_setup = dict(cur.fetchone())

    def _has_permission(code):
        try:
            require_permission_for_user(user, code)
            return True
        except HTTPException as exc:
            if exc.status_code == 403:
                return False
            raise

    response = templates.TemplateResponse(
        request=request,
        name="journal_entry.html",
        context={
            "app_name": settings.app_name,
            "csrf_token": request.cookies.get("are_erp_csrf", ""),
            "journals": journals,
            "accounts": accounts,
            "parties": parties,
            "period_setup": period_setup,
            "can_approve": _has_permission("accounting.approve"),
            "can_post": _has_permission("accounting.post"),
            "form": form or {},
            "errors": errors or [],
            "action_message": action_message,
            "saved_ref": ref,
        },
    )
    response.headers["Cache-Control"] = "no-store"
    return response


@app.get(
    "/accounting/journal",
    response_class=HTMLResponse,
)
def accounting_journal_page(
    request: Request,
    saved: str = "",
    approved: str = "",
    posted: str = "",
    ref: str = "",
    user: dict = Depends(require_permission("accounting.create")),
):
    """Show company-scoped journals and the protected DRAFT entry form."""
    action_message = (
        "Journal DRAFT saved." if saved == "1" else
        "Journal approved." if approved == "1" else
        "Journal posted." if posted == "1" else ""
    )
    return _journal_page_response(request, user, action_message=action_message, ref=ref)


@app.post(
    "/accounting/journal",
    response_class=HTMLResponse,
    dependencies=[Depends(require_permission("accounting.create"))],
)
async def accounting_journal_save_draft(request: Request):
    content_type = request.headers.get("content-type", "").split(";", 1)[0].strip().lower()
    if content_type != "application/x-www-form-urlencoded":
        raise HTTPException(status_code=415, detail="Unsupported form content type.")
    body = await request.body()
    if len(body) > 32768:
        raise HTTPException(status_code=413, detail="Journal form is too large.")
    try:
        parsed = parse_qs(
            body.decode("utf-8"),
            keep_blank_values=True,
            max_num_fields=128,
        )
    except (UnicodeDecodeError, ValueError):
        raise HTTPException(status_code=400, detail="Invalid journal form.")

    cookie_token = request.cookies.get("are_erp_csrf", "")
    form_token = (parsed.get("csrf_token") or [""])[0]
    if not cookie_token or not form_token or not hmac.compare_digest(cookie_token, form_token):
        raise HTTPException(status_code=403, detail="CSRF validation failed.")

    user = get_current_user(request)
    form = {
        "entry_date": (parsed.get("entry_date") or [""])[0].strip(),
        "description": (parsed.get("description") or [""])[0].strip(),
    }
    account_ids = parsed.get("account_id", [])
    party_ids = parsed.get("party_id", [])
    debits = parsed.get("debit", [])
    credits = parsed.get("credit", [])
    descriptions = parsed.get("line_description", [])
    count = max(map(len, (account_ids, party_ids, debits, credits, descriptions)), default=0)
    lines = []
    for index in range(count):
        lines.append({
            "account_id": account_ids[index] if index < len(account_ids) else "",
            "party_id": party_ids[index] if index < len(party_ids) else "",
            "debit": debits[index] if index < len(debits) else "0",
            "credit": credits[index] if index < len(credits) else "0",
            "description": descriptions[index] if index < len(descriptions) else "",
        })
    form["lines"] = lines

    if count < 2 or count > 20 or any(not line["account_id"].strip() for line in lines):
        return _journal_page_response(
            request, user, form=form,
            errors=["Journal mein 2 se 20 lines honi chahiye aur har line ka Account ID zaroori hai."],
        )

    try:
        normalized_lines = []
        for line in lines:
            try:
                account_id = int(line["account_id"])
                party_id = int(line["party_id"]) if line["party_id"].strip() else None
            except ValueError:
                raise ValueError("Account ID aur Party ID numeric hone chahiye.")
            normalized_lines.append({
                "account_id": account_id,
                "party_id": party_id,
                "debit": line["debit"] or "0",
                "credit": line["credit"] or "0",
                "description": line["description"].strip()[:500],
            })

        with get_connection() as conn:
            try:
                result = create_journal_draft(
                    conn,
                    company_id=user["company_id"],
                    user=user,
                    request=request,
                    entry_date=form["entry_date"],
                    description=form["description"],
                    lines=normalized_lines,
                )
                conn.commit()
            except Exception:
                conn.rollback()
                raise
    except ValueError as exc:
        return _journal_page_response(request, user, form=form, errors=[str(exc)])
    except Exception:
        return _journal_page_response(
            request, user, form=form,
            errors=["Journal DRAFT save fail hua; transaction rollback kar di gayi. Application log check karein."],
        )

    return RedirectResponse(
        url="/accounting/journal?" + urlencode({"saved": "1", "ref": result["journal_no"]}),
        status_code=303,
    )


@app.post(
    "/accounting/journal/{journal_id}/approve",
    dependencies=[Depends(require_permission("accounting.approve"))],
)
async def accounting_journal_approve(request: Request, journal_id: int):
    await _validate_purchase_action_csrf(request)
    user = get_current_user(request)
    with get_connection() as conn:
        try:
            result = approve_journal(
                conn, company_id=user["company_id"], journal_id=journal_id,
                user=user, request=request,
            )
            conn.commit()
        except ValueError as exc:
            conn.rollback()
            raise HTTPException(status_code=409, detail=str(exc))
        except Exception:
            conn.rollback()
            raise HTTPException(status_code=409, detail="Journal approval failed; transaction rolled back.")
    return RedirectResponse(
        url="/accounting/journal?" + urlencode({"approved": "1", "ref": result["journal_no"]}),
        status_code=303,
    )


@app.post(
    "/accounting/journal/{journal_id}/post",
    dependencies=[Depends(require_permission("accounting.post"))],
)
async def accounting_journal_post(request: Request, journal_id: int):
    await _validate_purchase_action_csrf(request)
    user = get_current_user(request)
    with get_connection() as conn:
        try:
            result = post_journal(
                conn, company_id=user["company_id"], journal_id=journal_id,
                user=user, request=request,
            )
            conn.commit()
        except ValueError as exc:
            conn.rollback()
            raise HTTPException(status_code=409, detail=str(exc))
        except Exception:
            conn.rollback()
            raise HTTPException(status_code=409, detail="Journal posting failed; transaction rolled back.")
    return RedirectResponse(
        url="/accounting/journal?" + urlencode({"posted": "1", "ref": result["journal_no"]}),
        status_code=303,
    )


@app.get(
    "/accounting/bills",
    response_class=HTMLResponse,
    dependencies=[Depends(require_permission("accounting.bills.view"))],
)
def accounting_bills_page(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="bills.html",
        context={"app_name": settings.app_name},
    )


@app.get(
    "/accounting/party-ledger",
    response_class=HTMLResponse,
)
def accounting_party_ledger_page(
    request: Request,
    user: dict = Depends(require_permission("accounting.party_ledger.view")),
    party_id: int | None = None,
):
    ledger = get_party_ledger_data(user["company_id"], party_id)
    if ledger["selected_party"]:
        selected = ledger["selected_party"]
        activity = get_party_ledger_activity(
            user["company_id"],
            selected["id"],
            selected["opening_signed_balance"] if selected["opening_configured"] else None,
        )
        ledger.update(activity)
        ledger["journal_activity_available"] = True
    else:
        ledger["rows"] = []
        ledger["activity_message"] = "Select an available party to view posted journal activity."
        ledger["debit_total"] = Decimal("0")
        ledger["credit_total"] = Decimal("0")

    response = templates.TemplateResponse(
        request=request,
        name="party_ledger.html",
        context={
            "app_name": settings.app_name,
            "ledger": ledger,
            "selected_party_id": (
                ledger["selected_party"]["id"]
                if ledger["selected_party"] else None
            ),
        },
    )
    response.headers["Cache-Control"] = "no-store"
    return response


@app.get(
    "/accounting/reports",
    response_class=HTMLResponse,
)
def accounting_reports_page(
    request: Request,
    start_date: str | None = None,
    end_date: str | None = None,
    account_id: int | None = None,
    user: dict = Depends(require_permission("reports.view")),
):
    today = date.today()
    start = start_date or today.replace(month=1, day=1).isoformat()
    end = end_date or today.isoformat()
    try:
        report = get_trial_balance(user["company_id"], start, end)
        selected_ledger = (
            get_account_ledger(user["company_id"], account_id, start, end)
            if account_id is not None else None
        )
        accounts = get_posting_accounts(user["company_id"])
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    response = templates.TemplateResponse(
        request=request,
        name="accounting_reports.html",
        context={
            "app_name": settings.app_name,
            "report": report,
            "accounts": accounts,
            "selected_ledger": selected_ledger,
            "selected_account_id": account_id,
        },
    )
    response.headers["Cache-Control"] = "no-store"
    return response


@app.get(
    "/accounting/setup-readiness",
    response_class=HTMLResponse,
)
def accounting_setup_readiness_page(
    request: Request,
    user: dict = Depends(require_permission("reports.view")),
):
    readiness = get_accounting_setup_readiness(user["company_id"])
    party_opening_review = get_party_opening_review(user["company_id"])
    inventory_gl_reconciliation = get_inventory_gl_reconciliation(user["company_id"])
    inventory_gl_mapping_readiness = get_inventory_gl_mapping_readiness(user["company_id"])
    response = templates.TemplateResponse(
        request=request,
        name="accounting_setup_readiness.html",
        context={
            "app_name": settings.app_name,
            "readiness": readiness,
            "party_opening_review": party_opening_review,
            "inventory_gl_reconciliation": inventory_gl_reconciliation,
            "inventory_gl_mapping_readiness": inventory_gl_mapping_readiness,
        },
    )
    response.headers["Cache-Control"] = "no-store"
    return response


@app.get(
    "/accounting/inventory-journal-review",
    response_class=HTMLResponse,
)
def inventory_journal_review_page(
    request: Request,
    user: dict = Depends(require_permission("reports.view")),
):
    review = get_inventory_journal_review(user["company_id"], limit=30)
    response = templates.TemplateResponse(
        request=request,
        name="inventory_journal_review.html",
        context={"app_name": settings.app_name, "review": review},
    )
    response.headers["Cache-Control"] = "no-store"
    return response


@app.get(
    "/accounting/fiscal-period-preview",
    response_class=HTMLResponse,
)
def fiscal_period_preview_page(
    request: Request,
    start_date: str | None = None,
    end_date: str | None = None,
    created: str = "",
    user: dict = Depends(require_permission("reports.view")),
):
    preview = None
    errors = []
    today = date.today()
    default_start_year = today.year if today.month >= 7 else today.year - 1
    start_date = start_date or f"{default_start_year}-07-01"
    end_date = end_date or f"{default_start_year + 1}-06-30"
    try:
        preview = get_fiscal_year_period_preview(
            user["company_id"], start_date, end_date
        )
    except ValueError as exc:
        errors.append(str(exc))
    can_create_fiscal_year = False
    try:
        require_permission_for_user(user, "accounting.approve")
        can_create_fiscal_year = True
    except HTTPException as exc:
        if exc.status_code != 403:
            raise
    response = templates.TemplateResponse(
        request=request,
        name="fiscal_period_preview.html",
        context={
            "app_name": settings.app_name,
            "preview": preview,
            "errors": errors,
            "start_date": start_date or "",
            "end_date": end_date or "",
            "created": created == "1",
            "can_create_fiscal_year": can_create_fiscal_year,
            "csrf_token": request.cookies.get("are_erp_csrf", ""),
        },
    )
    response.headers["Cache-Control"] = "no-store"
    return response


@app.post(
    "/accounting/fiscal-year/create",
    response_class=HTMLResponse,
    dependencies=[Depends(require_permission("accounting.approve"))],
)
async def fiscal_year_create_action(request: Request):
    """Create an open July-to-June fiscal year and its twelve periods atomically."""
    await _validate_purchase_action_csrf(request)
    try:
        body = await request.body()
        parsed = parse_qs(body.decode("utf-8"), keep_blank_values=True)
        start_year_text = (parsed.get("start_year") or [""])[0].strip()
        if not start_year_text.isdigit() or len(start_year_text) != 4:
            raise ValueError("Select a valid four-digit fiscal year start year.")
        user = get_current_user(request)
        create_fiscal_year(
            user["company_id"],
            int(start_year_text),
            user=user,
            request=request,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    return RedirectResponse(
        url="/accounting/fiscal-period-preview?created=1",
        status_code=303,
    )


MODULE_PERMISSIONS = {
    "inventory": ("inventory.view",),
    "production": ("production.view",),
    "packing": ("packing.view",),
    "sales-dispatch": ("sales.view", "dispatch.view"),
    "purchasing": ("purchasing.view",),
    "accounting": ("accounting.view",),
    "reports": ("reports.view",),
    "hr-payroll": ("hr.view",),
}


unknown_permissions = {
    permission_code
    for permission_codes in MODULE_PERMISSIONS.values()
    for permission_code in permission_codes
    if permission_code not in PERMISSIONS
}

if unknown_permissions:
    raise RuntimeError(
        f"Module permissions missing from catalog: {sorted(unknown_permissions)}"
    )


@app.get(
    "/modules/{module_slug}",
    response_class=HTMLResponse,
)
def module_page(
    request: Request,
    module_slug: str,
    section: str = "suppliers",
    q: str = "",
    page: int = 1,
    saved: str = "",
    ref: str = "",
    supplier_saved: str = "",
    receipt_approved: str = "",
    receipt_posted: str = "",
    receipt_error: str = "",
    return_saved: str = "",
    return_approved: str = "",
    return_posted: str = "",
    return_error: str = "",
):
    module = next(
        (m for m in MODULES if m["url"].split("/")[-1] == module_slug),
        None,
    )

    if module is None:
        raise HTTPException(
            status_code=404,
            detail="Module not found",
        )

    required_permissions = MODULE_PERMISSIONS.get(module_slug)

    if not required_permissions:
        raise HTTPException(
            status_code=403,
            detail="Access denied: module permission is not configured.",
        )

    user = get_current_user(request)

    for permission_code in required_permissions:
        require_permission_for_user(user, permission_code)

    if module_slug == "packing":
        data = get_packing_page_data(user["company_id"], q)
        can_create_packing = False
        try:
            require_permission_for_user(user, "packing.create")
            can_create_packing = True
        except HTTPException as exc:
            if exc.status_code != 403:
                raise
        response = templates.TemplateResponse(
            request=request,
            name="packing.html",
            context={
                "app_name": settings.app_name,
                "data": data,
                "can_create_packing": can_create_packing,
                "packing_saved": saved == "1",
                "packing_ref": ref,
            },
        )
        response.headers["Cache-Control"] = "no-store"
        return response

    if module_slug == "production":
        data = get_production_dashboard_data(user["company_id"])
        can_create_dyeing = False
        try:
            require_permission_for_user(user, "production.create")
            can_create_dyeing = True
        except HTTPException as exc:
            if exc.status_code != 403:
                raise
        response = templates.TemplateResponse(
            request=request,
            name="production.html",
            context={
                "app_name": settings.app_name,
                "data": data,
                "can_create_dyeing": can_create_dyeing,
            },
        )
        response.headers["Cache-Control"] = "no-store"
        return response
    if module_slug == "purchasing":
        can_create_supplier = True
        can_approve_receipt = False
        can_post_receipt = False
        can_approve_return = False
        can_post_return = False

        try:
            require_permission_for_user(user, "purchasing.create")
        except HTTPException as exc:
            if exc.status_code == 403:
                can_create_supplier = False
            else:
                raise

        for permission_codes, context_key in (
            (("purchasing.approve", "inventory.approve"), "approve"),
            (("purchasing.post", "inventory.post"), "post"),
        ):
            try:
                for permission_code in permission_codes:
                    require_permission_for_user(user, permission_code)
                if context_key == "approve":
                    can_approve_receipt = True
                    can_approve_return = True
                else:
                    can_post_receipt = True
                    can_post_return = True
            except HTTPException as exc:
                if exc.status_code != 403:
                    raise

        data = get_purchasing_page(
            company_id=user["company_id"],
            section=section,
            search=q,
            page=page,
        )

        return templates.TemplateResponse(
            request=request,
            name="purchasing.html",
            context={
                "app_name": settings.app_name,
                "data": data,
                "can_create_supplier": can_create_supplier,
                "can_approve_receipt": can_approve_receipt,
                "can_post_receipt": can_post_receipt,
                "can_create_purchase_return": can_create_supplier,
                "can_approve_return": can_approve_return,
                "can_post_return": can_post_return,
                "return_saved": return_saved == "1",
                "return_approved": return_approved == "1",
                "return_posted": return_posted == "1",
                "return_error": return_error,
                "csrf_token": request.cookies.get("are_erp_csrf", ""),
                "receipt_saved": saved == "1",
                "receipt_approved": receipt_approved == "1",
                "receipt_posted": receipt_posted == "1",
                "receipt_error": receipt_error,
                "receipt_ref": ref,
                "supplier_saved": supplier_saved == "1",
                "supplier_ref": ref if supplier_saved == "1" else "",
            },
        )

    template_name = (
        "hr_payroll.html"
        if module_slug == "hr-payroll"
        else "module.html"
    )

    return templates.TemplateResponse(
        request=request,
        name=template_name,
        context={
            "app_name": settings.app_name,
            "module": module,
        },
    )


@app.get(
    "/modules/production/baby-cone/measurements",
    response_class=HTMLResponse,
    dependencies=[Depends(require_permission("production.create"))],
)
def baby_cone_measurement_page(request: Request, saved: str = ""):
    user = get_current_user(request)
    data = get_baby_cone_measurement_draft_options(user["company_id"])
    return templates.TemplateResponse(
        request=request,
        name="baby_cone_measurement.html",
        context={
            "app_name": settings.app_name,
            "data": data,
            "csrf_token": request.cookies.get("are_erp_csrf", ""),
            "saved": saved == "1",
            "error": "",
            "form": {},
        },
    )


@app.post(
    "/modules/production/baby-cone/measurements",
    response_class=HTMLResponse,
    dependencies=[Depends(require_permission("production.create"))],
)
async def baby_cone_measurement_save(request: Request):
    content_type = request.headers.get("content-type", "").split(";", 1)[0].strip().lower()
    if content_type != "application/x-www-form-urlencoded":
        raise HTTPException(status_code=415, detail="Unsupported Baby Cone measurement form content type.")
    body = await request.body()
    if len(body) > 16384:
        raise HTTPException(status_code=413, detail="Baby Cone measurement form is too large.")
    try:
        parsed = parse_qs(body.decode("utf-8"), keep_blank_values=True, max_num_fields=12)
    except (UnicodeDecodeError, ValueError):
        raise HTTPException(status_code=400, detail="Invalid Baby Cone measurement form.")
    cookie_token = request.cookies.get("are_erp_csrf", "")
    form_token = (parsed.get("csrf_token") or [""])[0]
    if not cookie_token or not form_token or not hmac.compare_digest(cookie_token, form_token):
        raise HTTPException(status_code=403, detail="CSRF validation failed.")

    user = get_current_user(request)
    form = {
        "baby_cone_output_line_id": (parsed.get("baby_cone_output_line_id") or [""])[0].strip(),
        "gross_weight_grams": (parsed.get("gross_weight_grams") or [""])[0].strip(),
        "empty_core_tare_grams": (parsed.get("empty_core_tare_grams") or [""])[0].strip(),
        "measured_yards": (parsed.get("measured_yards") or [""])[0].strip(),
        "required_yards": (parsed.get("required_yards") or [""])[0].strip(),
        "operator_code": (parsed.get("operator_code") or [""])[0].strip(),
    }
    try:
        output_line_id = int(form["baby_cone_output_line_id"])
        snapshot_id = int((parsed.get("configuration_snapshot_id") or [""])[0])
        required_yards_text = form["required_yards"]
        with get_connection() as conn:
            with conn.transaction():
                with conn.cursor() as cur:
                    result = save_baby_cone_measurement_draft(
                        cur,
                        company_id=user["company_id"],
                        baby_cone_output_line_id=output_line_id,
                        configuration_snapshot_id=snapshot_id,
                        user_id=user["id"],
                        gross_weight_grams=form["gross_weight_grams"],
                        empty_core_tare_grams=form["empty_core_tare_grams"],
                        measured_yards=form["measured_yards"],
                        operator_code=form["operator_code"],
                        required_yards=required_yards_text or None,
                    )
    except (ValueError, TypeError) as exc:
        data = get_baby_cone_measurement_draft_options(user["company_id"])
        return templates.TemplateResponse(
            request=request,
            name="baby_cone_measurement.html",
            context={
                "app_name": settings.app_name,
                "data": data,
                "csrf_token": cookie_token,
                "saved": False,
                "error": str(exc),
                "form": form,
            },
            status_code=422,
        )
    return RedirectResponse(
        url="/modules/production/baby-cone/measurements?saved=1",
        status_code=303,
    )


@app.get(
    "/modules/production/big-cone/new",
    response_class=HTMLResponse,
    dependencies=[Depends(require_permission("production.create"))],
)
def big_cone_draft_new_page(request: Request, saved: str = "", ref: str = ""):
    user = get_current_user(request)
    data = get_big_cone_draft_form_data(user["company_id"])
    response = templates.TemplateResponse(
        request=request,
        name="big_cone_draft.html",
        context={
            "app_name": settings.app_name, "data": data,
            "csrf_token": request.cookies.get("are_erp_csrf", ""),
            "today": date.today().isoformat(), "saved": saved == "1",
            "ref": ref, "errors": [], "form": {},
        },
    )
    response.headers["Cache-Control"] = "no-store"
    return response


@app.post(
    "/modules/production/big-cone/new",
    response_class=HTMLResponse,
    dependencies=[Depends(require_permission("production.create"))],
)
async def big_cone_draft_save(request: Request):
    content_type = request.headers.get("content-type", "").split(";", 1)[0].strip().lower()
    if content_type != "application/x-www-form-urlencoded":
        raise HTTPException(status_code=415, detail="Unsupported Big Cone form content type.")
    body = await request.body()
    if len(body) > 65536:
        raise HTTPException(status_code=413, detail="Big Cone draft form is too large.")
    try:
        parsed = parse_qs(body.decode("utf-8"), keep_blank_values=True, max_num_fields=512)
    except (UnicodeDecodeError, ValueError):
        raise HTTPException(status_code=400, detail="Invalid Big Cone draft form.")
    cookie_token = request.cookies.get("are_erp_csrf", "")
    form_token = (parsed.get("csrf_token") or [""])[0]
    if not cookie_token or not form_token or not hmac.compare_digest(cookie_token, form_token):
        raise HTTPException(status_code=403, detail="CSRF validation failed.")

    user = get_current_user(request)
    form = {
        "big_cone_date": (parsed.get("big_cone_date") or [""])[0].strip(),
        "source_dyeing_order_id": (parsed.get("source_dyeing_order_id") or [""])[0].strip(),
        "department_id": (parsed.get("department_id") or [""])[0].strip(),
        "machine_id": (parsed.get("machine_id") or [""])[0].strip(),
        "remarks": (parsed.get("remarks") or [""])[0].strip(),
        "labour_cost": (parsed.get("labour_cost") or ["0"])[0].strip(),
        "electricity_cost": (parsed.get("electricity_cost") or ["0"])[0].strip(),
        "machine_cost": (parsed.get("machine_cost") or ["0"])[0].strip(),
    }
    source_ids = parsed.get("source_dyeing_output_line_id", [])
    input_qty = parsed.get("input_quantity_kg", [])
    input_cones = parsed.get("input_cones", [])
    output_qty = parsed.get("output_quantity_kg", [])
    output_cones = parsed.get("output_cones", [])
    destinations = parsed.get("destination_type", [])
    lengths = {len(x) for x in (source_ids, input_qty, input_cones, output_qty, output_cones, destinations)}
    errors = ["Big Cone input rows are incomplete; refresh the form and try again."] if len(lengths) > 1 else []
    lines = []
    for index, source_id in enumerate(source_ids):
        if not (input_qty[index] or "").strip():
            continue
        lines.append({
            "source_dyeing_output_line_id": source_id,
            "input_quantity_kg": input_qty[index],
            "input_cones": input_cones[index],
            "output_quantity_kg": output_qty[index],
            "output_cones": output_cones[index],
            "destination_type": destinations[index],
        })
    form["lines"] = lines

    result = None
    if not errors:
        try:
            big_cone_date = date.fromisoformat(form["big_cone_date"])
            result = create_big_cone_draft(
                company_id=user["company_id"], user=user, request=request,
                big_cone_date=big_cone_date,
                source_dyeing_order_id=form["source_dyeing_order_id"],
                department_id=form["department_id"], machine_id=form["machine_id"],
                remarks=form["remarks"], lines=lines,
                labour_cost=form["labour_cost"],
                electricity_cost=form["electricity_cost"],
                machine_cost=form["machine_cost"],
            )
        except ValueError as exc:
            errors = [str(exc)]
        except Exception:
            errors = ["Big Cone DRAFT save failed; transaction rolled back. Check the application log."]

    if result:
        return RedirectResponse(
            url="/modules/production/big-cone/new?" + urlencode({"saved": "1", "ref": result["big_cone_no"]}),
            status_code=303,
        )

    data = get_big_cone_draft_form_data(user["company_id"])
    response = templates.TemplateResponse(
        request=request,
        name="big_cone_draft.html",
        context={
            "app_name": settings.app_name, "data": data,
            "csrf_token": cookie_token, "today": date.today().isoformat(),
            "saved": False, "ref": "", "errors": errors, "form": form,
        },
        status_code=422,
    )
    response.headers["Cache-Control"] = "no-store"
    return response


@app.get(
    "/modules/production/dyeing/new",
    response_class=HTMLResponse,
    dependencies=[Depends(require_permission("production.create"))],
)
def dyeing_draft_new_page(request: Request, saved: str = "", ref: str = "",
                          pending: int = 0, blocked: int = 0, saved_order_id: int = 0):
    user = get_current_user(request)
    data = get_dyeing_draft_form_data(user["company_id"])
    return templates.TemplateResponse(
        request=request,
        name="dyeing_draft.html",
        context={
            "app_name": settings.app_name,
            "data": data,
            "csrf_token": request.cookies.get("are_erp_csrf", ""),
            "today": date.today().isoformat(),
            "saved": saved == "1",
            "ref": ref,
            "saved_order_id": max(0, int(saved_order_id)),
            "pending_conversion_count": max(0, min(int(pending), 100)),
            "blocked_conversion_count": max(0, min(int(blocked), 100)),
            "error": "",
        },
    )


@app.get(
    "/modules/production/dyeing/{dyeing_order_id}",
    response_class=HTMLResponse,
    dependencies=[Depends(require_permission("production.view"))],
)
def dyeing_draft_detail_page(request: Request, dyeing_order_id: int):
    user = get_current_user(request)
    detail = get_dyeing_draft_detail(user["company_id"], dyeing_order_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="Dyeing order not found.")
    detail["approval_readiness"] = get_dyeing_approval_readiness(
        user["company_id"], dyeing_order_id
    )
    response = templates.TemplateResponse(
        request=request, name="dyeing_detail.html",
        context={"app_name": settings.app_name, "detail": detail},
    )
    response.headers["Cache-Control"] = "no-store"
    return response


@app.post(
    "/modules/production/dyeing/new",
    response_class=HTMLResponse,
    dependencies=[Depends(require_permission("production.create"))],
)
async def dyeing_draft_save(request: Request):
    content_type = request.headers.get("content-type", "").split(";", 1)[0].strip().lower()
    if content_type != "application/x-www-form-urlencoded":
        raise HTTPException(status_code=415, detail="Unsupported dyeing form content type.")
    body = await request.body()
    if len(body) > 65536:
        raise HTTPException(status_code=413, detail="Dyeing draft form is too large.")
    try:
        parsed = parse_qs(body.decode("utf-8"), keep_blank_values=True, max_num_fields=2000)
    except (UnicodeDecodeError, ValueError):
        raise HTTPException(status_code=400, detail="Invalid dyeing draft form.")
    cookie_token = request.cookies.get("are_erp_csrf", "")
    form_token = (parsed.get("csrf_token") or [""])[0]
    if not cookie_token or not form_token or not hmac.compare_digest(cookie_token, form_token):
        raise HTTPException(status_code=403, detail="CSRF validation failed.")

    user = get_current_user(request)
    try:
        date_text = (parsed.get("dyeing_date") or [""])[0].strip()
        dyeing_date = date.fromisoformat(date_text)
        remarks = (parsed.get("remarks") or [""])[0]
        keys = ("item_variant_id", "batch_id", "source_line_no", "quantity",
                "unit_id", "ownership_type_id", "owner_party_id", "notes")
        columns = [parsed.get(key, []) for key in keys]
        row_count = max((len(values) for values in columns), default=0)
        lines = []
        for index in range(row_count):
            values = [(column[index] if index < len(column) else "").strip() for column in columns]
            if not any(values):
                continue
            lines.append(dict(zip(keys, values)))

        material_keys = ("item_variant_id", "batch_id", "quantity_kg", "notes")
        material_columns = [parsed.get("material_" + key, []) for key in material_keys]
        material_count = max((len(values) for values in material_columns), default=0)
        material_lines = []
        for index in range(material_count):
            values = [(column[index] if index < len(column) else "").strip()
                      for column in material_columns]
            if not any(values):
                continue
            material_lines.append(dict(zip(material_keys, values)))

        output_keys = ("source_line_no", "source_quantity_kg", "quantity_kg", "actual_shade_id", "notes")
        output_columns = [parsed.get("output_" + key, []) for key in output_keys]
        output_count = max((len(values) for values in output_columns), default=0)
        output_lines = []
        for index in range(output_count):
            values = [(column[index] if index < len(column) else "").strip()
                      for column in output_columns]
            if not any(values):
                continue
            output_lines.append(dict(zip(output_keys, values)))

        result = create_dyeing_draft(
            company_id=user["company_id"], user=user, request=request,
            dyeing_date=dyeing_date, remarks=remarks, lines=lines,
            material_lines=material_lines, output_lines=output_lines,
            process_costs={
                field: (parsed.get(field) or ["0"])[0].strip()
                for field in (
                    "labour_cost","machine_cost","electricity_cost",
                    "water_cost","boiler_fuel_cost","drying_cost",
                )
            },
        )
    except ValueError as exc:
        data = get_dyeing_draft_form_data(user["company_id"])
        return templates.TemplateResponse(
            request=request, name="dyeing_draft.html",
            context={"app_name": settings.app_name, "data": data,
                     "csrf_token": cookie_token, "today": date.today().isoformat(),
                     "saved": False, "ref": "", "saved_order_id": 0, "error": str(exc)},
            status_code=422,
        )
    return RedirectResponse(
        url="/modules/production/dyeing/new?" + urlencode({
            "saved": "1", "ref": result["dyeing_no"], "saved_order_id": result["id"],
            "pending": result["conversion_summary"]["PENDING_CONFIGURATION"],
            "blocked": result["conversion_summary"]["BLOCKED_PRECISION"],
        }),
        status_code=303,
    )


# Purchasing state-changing form actions use the same double-submit CSRF token.
async def _validate_purchase_action_csrf(request: Request) -> None:
    content_type = (
        request.headers.get("content-type", "")
        .split(";", 1)[0]
        .strip()
        .lower()
    )
    if content_type != "application/x-www-form-urlencoded":
        raise HTTPException(status_code=415, detail="Unsupported form content type.")
    body = await request.body()
    if len(body) > 8192:
        raise HTTPException(status_code=413, detail="Action form is too large.")
    try:
        parsed = parse_qs(body.decode("utf-8"), keep_blank_values=True, max_num_fields=5)
    except (UnicodeDecodeError, ValueError):
        raise HTTPException(status_code=400, detail="Invalid action form.")
    cookie_token = request.cookies.get("are_erp_csrf", "")
    form_token = (parsed.get("csrf_token") or [""])[0]
    if not cookie_token or not form_token or not hmac.compare_digest(cookie_token, form_token):
        raise HTTPException(status_code=403, detail="CSRF validation failed.")


@app.post(
    "/modules/purchasing/receipts/{receipt_id}/approve",
    dependencies=[
        Depends(require_permission("purchasing.approve")),
        Depends(require_permission("inventory.approve")),
    ],
)
async def purchase_receipt_approve(request: Request, receipt_id: int):
    await _validate_purchase_action_csrf(request)
    user = get_current_user(request)
    try:
        result = approve_purchase_receipt(
            company_id=user["company_id"],
            receipt_id=receipt_id,
            approved_by=user["id"],
            user=user,
            request=request,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    return RedirectResponse(
        url="/modules/purchasing?" + urlencode({
            "section": "receipts", "receipt_approved": "1",
            "ref": result["receipt_no"],
        }),
        status_code=303,
    )


@app.post(
    "/modules/purchasing/receipts/{receipt_id}/post",
    dependencies=[
        Depends(require_permission("purchasing.post")),
        Depends(require_permission("inventory.post")),
    ],
)
async def purchase_receipt_post(request: Request, receipt_id: int):
    await _validate_purchase_action_csrf(request)
    user = get_current_user(request)
    try:
        result = post_purchase_receipt(
            company_id=user["company_id"],
            receipt_id=receipt_id,
            posted_by=user["id"],
            user=user,
            request=request,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    return RedirectResponse(
        url="/modules/purchasing?" + urlencode({
            "section": "receipts", "receipt_posted": "1",
            "ref": result["receipt_no"],
        }),
        status_code=303,
    )


def _purchase_return_form_response(request,master_data,form=None,lines=None,errors=None):
    response=templates.TemplateResponse(request=request,name="purchasing.html",context={
        "app_name":settings.app_name,"data":get_purchasing_page(company_id=get_current_user(request)["company_id"],section="returns",page=1),
        "can_create_supplier":False,"purchase_return_form_mode":True,"return_master_data":master_data,
        "return_form":form or {},"return_lines":lines or [{}],"return_errors":errors or [],
        "csrf_token":request.cookies.get("are_erp_csrf","")})
    response.headers["Cache-Control"]="no-store"
    return response

@app.get("/modules/purchasing/returns/new",response_class=HTMLResponse,dependencies=[Depends(require_permission("purchasing.create"))])
def purchase_return_new_page(request:Request):
    return _purchase_return_form_response(request,get_purchase_return_form_data(get_current_user(request)["company_id"]))

@app.post("/modules/purchasing/returns/new",response_class=HTMLResponse,dependencies=[Depends(require_permission("purchasing.create"))])
async def purchase_return_save_draft(request:Request):
    ctype=request.headers.get("content-type","").split(";",1)[0].strip().lower()
    if ctype!="application/x-www-form-urlencoded": raise HTTPException(status_code=415,detail="Unsupported form content type.")
    body=await request.body()
    if len(body)>65536: raise HTTPException(status_code=413,detail="Purchase Return form is too large.")
    try: data=parse_qs(body.decode("utf-8"),keep_blank_values=True,max_num_fields=120)
    except (UnicodeDecodeError,ValueError): raise HTTPException(status_code=400,detail="Invalid form submission.")
    cookie=request.cookies.get("are_erp_csrf",""); token=(data.get("csrf_token") or [""])[0]
    if not cookie or not token or not hmac.compare_digest(cookie,token): raise HTTPException(status_code=403,detail="CSRF validation failed.")
    user=get_current_user(request)
    form={k:(data.get(k) or [""])[0].strip() for k in ("purchase_receipt_id","return_date","supplier_credit_note_no","supplier_credit_note_date","reason","remarks")}
    ids=data.get("receipt_line_id",[]); qtys=data.get("returned_quantity",[]); count=max(len(ids),len(qtys))
    lines=[{"receipt_line_id":ids[i] if i<len(ids) else "","returned_quantity":qtys[i] if i<len(qtys) else ""} for i in range(count)]
    master=get_purchase_return_form_data(user["company_id"])
    if count>10 or len(ids)!=count or len(qtys)!=count:
        return _purchase_return_form_response(request,master,form,lines,["Return requires 1â€“10 complete, aligned item rows."])
    try: result=create_purchase_return_draft(user["company_id"],user["id"],user,request,form,lines)
    except ValueError as exc: return _purchase_return_form_response(request,master,form,lines,[str(exc)])
    except Exception: return _purchase_return_form_response(request,master,form,lines,["Purchase Return could not be saved. Check application log."])
    return RedirectResponse(url="/modules/purchasing?"+urlencode({"section":"returns","return_saved":"1","ref":result["return_no"]}),status_code=303)

@app.post("/modules/purchasing/returns/{return_id}/approve",dependencies=[Depends(require_permission("purchasing.approve")),Depends(require_permission("inventory.approve"))])
async def purchase_return_approve(request:Request,return_id:int):
    await _validate_purchase_action_csrf(request); user=get_current_user(request)
    try:
        result=approve_purchase_return(user["company_id"],return_id,user["id"],user,request)
    except ValueError as exc:
        raise HTTPException(status_code=409,detail=str(exc))
    except Exception:
        raise HTTPException(status_code=409,detail="Purchase Return approval failed; the transaction was rolled back.")
    return RedirectResponse(url="/modules/purchasing?"+urlencode({"section":"returns","return_approved":"1","ref":result["return_no"]}),status_code=303)

@app.post("/modules/purchasing/returns/{return_id}/post",dependencies=[Depends(require_permission("purchasing.post")),Depends(require_permission("inventory.post"))])
async def purchase_return_post(request:Request,return_id:int):
    await _validate_purchase_action_csrf(request); user=get_current_user(request)
    try:
        result=post_purchase_return(user["company_id"],return_id,user["id"],user,request)
    except ValueError as exc:
        raise HTTPException(status_code=409,detail=str(exc))
    except Exception:
        raise HTTPException(status_code=409,detail="Purchase Return posting failed; the transaction was rolled back.")
    return RedirectResponse(url="/modules/purchasing?"+urlencode({"section":"returns","return_posted":"1","ref":result["return_no"]}),status_code=303)



# Goods Receipt save creates DRAFT only; approval creates a linked approved
# stock document, and posting applies inventory plus PO quantities atomically.


def _purchase_receipt_form_response(
    request,
    master_data,
    form=None,
    lines=None,
    errors=None,
):
    response = templates.TemplateResponse(
        request=request,
        name="purchasing.html",
        context={
            "app_name": settings.app_name,
            "data": get_purchasing_page(
                company_id=get_current_user(request)["company_id"],
                section="receipts",
                page=1,
            ),
            "can_create_supplier": False,
            "receipt_form_mode": True,
            "receipt_master_data": master_data,
            "receipt_form": form or {},
            "receipt_lines": lines or [{}],
            "receipt_errors": errors or [],
            "csrf_token": request.cookies.get("are_erp_csrf", ""),
        },
    )

    response.headers["Cache-Control"] = "no-store"
    return response


@app.get(
    "/modules/purchasing/receipts/new",
    response_class=HTMLResponse,
    dependencies=[Depends(require_permission("purchasing.create"))],
)
def purchase_receipt_new_page(request: Request):
    user = get_current_user(request)
    master_data = get_purchase_receipt_form_data(user["company_id"])

    return _purchase_receipt_form_response(
        request,
        master_data,
    )


@app.post(
    "/modules/purchasing/receipts/new",
    response_class=HTMLResponse,
    dependencies=[Depends(require_permission("purchasing.create"))],
)
async def purchase_receipt_save_draft(request: Request):
    content_type = (
        request.headers.get("content-type", "")
        .split(";", 1)[0]
        .strip()
        .lower()
    )

    if content_type != "application/x-www-form-urlencoded":
        raise HTTPException(
            status_code=415,
            detail="Unsupported form content type.",
        )

    body = await request.body()

    if len(body) > 65536:
        raise HTTPException(
            status_code=413,
            detail="Goods Receipt form is too large.",
        )

    try:
        parsed = parse_qs(
            body.decode("utf-8"),
            keep_blank_values=True,
            max_num_fields=120,
        )
    except (UnicodeDecodeError, ValueError):
        raise HTTPException(
            status_code=400,
            detail="Invalid form submission.",
        )

    csrf_cookie = request.cookies.get("are_erp_csrf", "")
    csrf_form = (parsed.get("csrf_token") or [""])[0]

    if (
        not csrf_cookie
        or not csrf_form
        or not hmac.compare_digest(csrf_cookie, csrf_form)
    ):
        raise HTTPException(
            status_code=403,
            detail="CSRF validation failed.",
        )

    user = get_current_user(request)

    scalar_fields = {
        key: (parsed.get(key) or [""])[0].strip()
        for key in (
            "supplier_id",
            "purchase_order_id",
            "receipt_date",
            "supplier_invoice_no",
            "supplier_invoice_date",
            "gst_choice",
            "discount_amount",
            "freight_amount",
            "other_charges",
            "remarks",
        )
    }

    array_fields = (
        "item_variant_id",
        "purchase_order_line_id",
        "unit_id",
        "received_quantity",
        "unit_price",
        "discount_amount_line",
        "tax_amount",
        "ownership_type_id",
        "owner_party_id",
        "line_remarks",
    )

    arrays = {
        key: parsed.get(key, [])
        for key in array_fields
    }

    row_count = max(
        (len(values) for values in arrays.values()),
        default=0,
    )

    lines = []

    for index in range(row_count):
        lines.append(
            {
                "item_variant_id": (
                    arrays["item_variant_id"][index]
                    if index < len(arrays["item_variant_id"])
                    else ""
                ),
                "purchase_order_line_id": (
                    arrays["purchase_order_line_id"][index]
                    if index < len(arrays["purchase_order_line_id"])
                    else ""
                ),
                "unit_id": (
                    arrays["unit_id"][index]
                    if index < len(arrays["unit_id"])
                    else ""
                ),
                "received_quantity": (
                    arrays["received_quantity"][index]
                    if index < len(arrays["received_quantity"])
                    else ""
                ),
                "unit_price": (
                    arrays["unit_price"][index]
                    if index < len(arrays["unit_price"])
                    else ""
                ),
                "discount_amount": (
                    arrays["discount_amount_line"][index]
                    if index < len(arrays["discount_amount_line"])
                    else "0"
                ),
                "tax_amount": (
                    arrays["tax_amount"][index]
                    if index < len(arrays["tax_amount"])
                    else "0"
                ),
                "ownership_type_id": (
                    arrays["ownership_type_id"][index]
                    if index < len(arrays["ownership_type_id"])
                    else "1"
                ),
                "owner_party_id": (
                    arrays["owner_party_id"][index]
                    if index < len(arrays["owner_party_id"])
                    else ""
                ),
                "remarks": (
                    arrays["line_remarks"][index]
                    if index < len(arrays["line_remarks"])
                    else ""
                ),
            }
        )

    master_data = get_purchase_receipt_form_data(user["company_id"])

    required_line_arrays = (
        "item_variant_id",
        "purchase_order_line_id",
        "unit_id",
        "received_quantity",
        "unit_price",
        "discount_amount_line",
        "ownership_type_id",
        "owner_party_id",
        "line_remarks",
    )
    arrays_mismatch = any(
        len(arrays[key]) != row_count
        for key in required_line_arrays
    )
    gst_arrays_mismatch = (
        scalar_fields["gst_choice"].upper() == "WITH"
        and len(arrays["tax_amount"]) != row_count
    )
    if row_count > 10:
        return _purchase_receipt_form_response(
            request, master_data, scalar_fields, lines,
            ["A Goods Receipt can contain no more than 10 item lines."],
        )
    if arrays_mismatch or gst_arrays_mismatch:
        return _purchase_receipt_form_response(
            request, master_data, scalar_fields, lines,
            ["The item rows are incomplete or misaligned. Please review each line and submit again."],
        )

    try:
        result = create_purchase_receipt_draft(
            company_id=user["company_id"],
            created_by=user["id"],
            user=user,
            request=request,
            header=scalar_fields,
            lines=lines,
        )
    except ValueError as exc:
        return _purchase_receipt_form_response(
            request,
            master_data,
            scalar_fields,
            lines,
            [str(exc)],
        )
    except Exception:
        return _purchase_receipt_form_response(
            request,
            master_data,
            scalar_fields,
            lines,
            [
                "Goods Receipt could not be saved. "
                "Check the selected master data and application log."
            ],
        )

    return RedirectResponse(
        url=(
            "/modules/purchasing?"
            + urlencode(
                {
                    "section": "receipts",
                    "saved": "1",
                    "ref": result["receipt_no"],
                }
            )
        ),
        status_code=303,
    )


# Supplier Master Phase 1:
# Protected supplier creation with financial profile and audit entries.


def _supplier_form_response(
    request,
    form=None,
    errors=None,
    validated=False,
):
    response = templates.TemplateResponse(
        request=request,
        name="supplier_form.html",
        context={
            "app_name": settings.app_name,
            "csrf_token": request.cookies.get("are_erp_csrf", ""),
            "form": form or {},
            "errors": errors or [],
            "validated": validated,
        },
    )

    response.headers["Cache-Control"] = "no-store"
    return response


@app.get(
    "/modules/purchasing/suppliers/new",
    response_class=HTMLResponse,
    dependencies=[Depends(require_permission("purchasing.create"))],
)
def supplier_new_page(request: Request):
    return _supplier_form_response(request)


@app.post(
    "/modules/purchasing/suppliers/new",
    response_class=HTMLResponse,
    dependencies=[Depends(require_permission("purchasing.create"))],
)
async def supplier_create(request: Request):
    errors = []
    form = {}

    content_type = (
        request.headers.get("content-type", "")
        .split(";", 1)[0]
        .strip()
        .lower()
    )

    if content_type != "application/x-www-form-urlencoded":
        raise HTTPException(
            status_code=415,
            detail="Unsupported form content type.",
        )

    body = await request.body()

    if len(body) > 16384:
        raise HTTPException(
            status_code=413,
            detail="Form submission is too large.",
        )

    try:
        parsed = parse_qs(
            body.decode("utf-8"),
            keep_blank_values=True,
            max_num_fields=20,
        )

        form = {
            key: values[0]
            for key, values in parsed.items()
            if values
        }

    except (UnicodeDecodeError, ValueError):
        raise HTTPException(
            status_code=400,
            detail="Invalid form submission.",
        )

    csrf_cookie = request.cookies.get("are_erp_csrf", "")
    csrf_form = form.get("csrf_token", "")

    if (
        not csrf_cookie
        or not csrf_form
        or not hmac.compare_digest(csrf_cookie, csrf_form)
    ):
        raise HTTPException(
            status_code=403,
            detail="CSRF validation failed.",
        )

    user = get_current_user(request)

    allowed_fields = {
        "supplier_code",
        "supplier_name",
        "phone",
        "email",
        "address",
        "tax_number",
        "credit_limit",
        "payment_terms_days",
        "default_currency_code",
        "opening_balance",
        "opening_balance_type",
    }

    form = {
        key: value.strip()
        for key, value in form.items()
        if key in allowed_fields
    }

    code = form.get("supplier_code", "")
    name = form.get("supplier_name", "")
    email = form.get("email", "")
    currency = form.get("default_currency_code", "PKR").upper()
    opening_type = form.get("opening_balance_type", "").upper()

    if not code:
        errors.append("Supplier code is required.")
    elif len(code) > 50:
        errors.append("Supplier code cannot exceed 50 characters.")

    if not name:
        errors.append("Supplier name is required.")
    elif len(name) > 200:
        errors.append("Supplier name cannot exceed 200 characters.")

    if len(form.get("phone", "")) > 50:
        errors.append("Phone cannot exceed 50 characters.")

    if email and (
        len(email) > 254
        or "@" not in email
        or email.startswith("@")
        or email.endswith("@")
        or "." not in email.rsplit("@", 1)[-1]
    ):
        errors.append("Enter a valid email address.")

    if len(form.get("tax_number", "")) > 100:
        errors.append("Tax number cannot exceed 100 characters.")

    if len(form.get("address", "")) > 2000:
        errors.append("Address cannot exceed 2,000 characters.")

    if len(currency) != 3 or not currency.isalpha():
        errors.append(
            "Currency must be a 3-letter code, for example PKR."
        )

    opening_amount = None

    for field, label in (
        ("credit_limit", "Credit limit"),
        ("opening_balance", "Opening balance"),
    ):
        try:
            amount = Decimal(
                form.get(field, "0") or "0"
            )

            if not amount.is_finite() or amount < 0:
                raise InvalidOperation

            normalized = amount.normalize()

            fractional_places = max(
                0,
                -normalized.as_tuple().exponent,
            )

            integer_places = (
                max(0, normalized.adjusted() + 1)
                if amount
                else 0
            )

            if fractional_places > 6:
                errors.append(
                    f"{label} cannot have more than 6 decimal places."
                )

            if integer_places > 14:
                errors.append(
                    f"{label} exceeds the NUMERIC(20,6) limit."
                )

            if field == "opening_balance":
                opening_amount = amount

        except (InvalidOperation, ValueError):
            errors.append(
                f"{label} must be a valid non-negative amount."
            )

    try:
        terms = int(
            form.get("payment_terms_days", "0") or "0"
        )

        if terms < 0 or terms > 3650:
            errors.append(
                "Payment terms must be between 0 and 3,650 days."
            )

    except ValueError:
        errors.append(
            "Payment terms must be a whole number of days."
        )

    if opening_type not in ("", "DEBIT", "CREDIT"):
        errors.append(
            "Opening balance type must be DEBIT or CREDIT."
        )

    if (
        opening_amount is not None
        and opening_amount != 0
        and not opening_type
    ):
        errors.append(
            "Select DEBIT or CREDIT for a non-zero opening balance."
        )

    # Read-only duplicate check across all parties in this company.
    if code and len(code) <= 50 and not errors:
        if supplier_code_exists(user["company_id"], code):
            errors.append(
                "This supplier code is already in use."
            )

    if errors:
        return _supplier_form_response(
            request,
            form=form,
            errors=errors,
            validated=False,
        )

    try:
        with get_connection() as conn:
            try:
                result = create_supplier_with_audit(
                    conn,
                    user=user,
                    request=request,
                    supplier_code=code,
                    supplier_name=name,
                    phone=form.get("phone") or None,
                    email=email or None,
                    address=form.get("address") or None,
                    tax_number=form.get("tax_number") or None,
                    credit_limit=Decimal(
                        form.get("credit_limit", "0") or "0"
                    ),
                    payment_terms_days=terms,
                    default_currency_code=currency,
                    opening_balance=(
                        opening_amount or Decimal("0")
                    ),
                    opening_balance_type=opening_type or None,
                )

                conn.commit()

            except Exception:
                conn.rollback()
                raise

    except ValueError as exc:
        return _supplier_form_response(
            request,
            form=form,
            errors=[str(exc)],
            validated=False,
        )

    query_string = urlencode(
        {
            "section": "suppliers",
            "supplier_saved": "1",
            "ref": result["supplier_code"],
        }
    )

    return RedirectResponse(
        url=f"/modules/purchasing?{query_string}",
        status_code=303,
    )

def _packing_form_response(request, user, form_data, *, packing_form=None, lines=None, errors=None):
    response = templates.TemplateResponse(
        request=request,
        name="packing.html",
        context={
            "app_name": settings.app_name,
            "packing_form_mode": True,
            "form_data": form_data,
            "packing_form": packing_form or {},
            "packing_lines": lines or [{}],
            "packing_errors": errors or [],
            "csrf_token": request.cookies.get("are_erp_csrf", ""),
            "today": date.today().isoformat(),
        },
    )
    response.headers["Cache-Control"] = "no-store"
    return response


@app.get(
    "/modules/packing/new",
    response_class=HTMLResponse,
    dependencies=[Depends(require_permission("packing.create"))],
)
def packing_new_page(request: Request):
    user = get_current_user(request)
    form_data = get_packing_assortment_form_data(user["company_id"])
    return _packing_form_response(request, user, form_data)


@app.post(
    "/modules/packing/new",
    response_class=HTMLResponse,
    dependencies=[Depends(require_permission("packing.create"))],
)
async def packing_save_draft(request: Request):
    content_type = request.headers.get("content-type", "").split(";", 1)[0].strip().lower()
    if content_type != "application/x-www-form-urlencoded":
        raise HTTPException(status_code=415, detail="Unsupported form content type.")
    body = await request.body()
    if len(body) > 32768:
        raise HTTPException(status_code=413, detail="Packing form is too large.")
    try:
        parsed = parse_qs(
            body.decode("utf-8"),
            keep_blank_values=True,
            max_num_fields=20,
        )
    except (UnicodeDecodeError, ValueError):
        raise HTTPException(status_code=400, detail="Invalid packing form.")
    cookie_token = request.cookies.get("are_erp_csrf", "")
    form_token = (parsed.get("csrf_token") or [""])[0]
    if not cookie_token or not form_token or not hmac.compare_digest(cookie_token, form_token):
        raise HTTPException(status_code=403, detail="CSRF validation failed.")

    user = get_current_user(request)
    form = {
        "packing_date": (parsed.get("packing_date") or [""])[0].strip(),
        "remarks": (parsed.get("remarks") or [""])[0].strip(),
        "brand_id": (parsed.get("brand_id") or [""])[0].strip(),
        "finished_boxes_qty": (parsed.get("finished_boxes_qty") or [""])[0].strip(),
        "shade_codes": (parsed.get("shade_codes") or [""])[0].strip(),
    }
    form_data = get_packing_assortment_form_data(user["company_id"])
    try:
        result = create_packing_assortment_draft(
            company_id=user["company_id"],
            user_id=user["id"],
            user=user,
            request=request,
            packing_date=form["packing_date"],
            brand_id=form["brand_id"],
            finished_boxes_qty=form["finished_boxes_qty"],
            shade_codes=form["shade_codes"],
            remarks=form["remarks"],
        )
    except ValueError as exc:
        return _packing_form_response(
            request, user, form_data, packing_form=form, lines=lines,
            errors=[str(exc)],
        )
    except Exception:
        return _packing_form_response(
            request, user, form_data, packing_form=form, lines=lines,
            errors=["Packing draft could not be saved. No inventory posting was attempted."],
        )
    return RedirectResponse(
        url="/modules/packing?" + urlencode({"saved": "1", "ref": result["packing_no"]}),
        status_code=303,
    )

def _packing_random_form_response(request, candidates, *, form=None, errors=None):
    response = templates.TemplateResponse(
        request=request,
        name="packing_random.html",
        context={
            "app_name": settings.app_name,
            "candidates": candidates,
            "packing_form": form or {},
            "packing_errors": errors or [],
            "csrf_token": request.cookies.get("are_erp_csrf", ""),
            "today": date.today().isoformat(),
        },
    )
    response.headers["Cache-Control"] = "no-store"
    return response


@app.get(
    "/modules/packing/random/new",
    response_class=HTMLResponse,
    dependencies=[Depends(require_permission("packing.create"))],
)
def packing_random_new_page(request: Request):
    user = get_current_user(request)
    candidates = get_random_packing_source_candidates(user["company_id"])
    return _packing_random_form_response(request, candidates)


@app.post(
    "/modules/packing/random/new",
    response_class=HTMLResponse,
    dependencies=[Depends(require_permission("packing.create"))],
)
async def packing_random_save_draft(request: Request):
    content_type = request.headers.get("content-type", "").split(";", 1)[0].strip().lower()
    if content_type != "application/x-www-form-urlencoded":
        raise HTTPException(status_code=415, detail="Unsupported form content type.")
    body = await request.body()
    if len(body) > 65536:
        raise HTTPException(status_code=413, detail="Random packing form is too large.")
    try:
        parsed = parse_qs(
            body.decode("utf-8"),
            keep_blank_values=True,
            max_num_fields=10,
        )
    except (UnicodeDecodeError, ValueError):
        raise HTTPException(status_code=400, detail="Invalid random packing form.")

    cookie_token = request.cookies.get("are_erp_csrf", "")
    form_token = (parsed.get("csrf_token") or [""])[0]
    if not cookie_token or not form_token or not hmac.compare_digest(cookie_token, form_token):
        raise HTTPException(status_code=403, detail="CSRF validation failed.")

    user = get_current_user(request)
    form = {
        "packing_date": (parsed.get("packing_date") or [""])[0].strip(),
        "finished_boxes_qty": (parsed.get("finished_boxes_qty") or [""])[0].strip(),
        "remarks": (parsed.get("remarks") or [""])[0].strip(),
        "allocations_json": (parsed.get("allocations_json") or [""])[0],
    }
    try:
        allocations = json.loads(form["allocations_json"])
        if not isinstance(allocations, list):
            raise ValueError("Source allocations must be a list.")
        result = create_random_packing_draft(
            company_id=user["company_id"],
            user_id=user["id"],
            user=user,
            request=request,
            packing_date=form["packing_date"],
            finished_boxes_qty=form["finished_boxes_qty"],
            allocations=allocations,
            remarks=form["remarks"],
        )
    except ValueError as exc:
        candidates = get_random_packing_source_candidates(user["company_id"])
        return _packing_random_form_response(
            request, candidates, form=form, errors=[str(exc)]
        )
    except Exception:
        candidates = get_random_packing_source_candidates(user["company_id"])
        return _packing_random_form_response(
            request, candidates, form=form,
            errors=["Random packing draft could not be saved. No inventory posting was attempted."],
        )

    return RedirectResponse(
        url="/modules/packing?" + urlencode({"saved": "1", "ref": result["packing_no"]}),
        status_code=303,
    )

@app.post("/api/production/ownership-use-requests")
async def ownership_use_request_create_api(request: Request):
    data = await _configuration_action_data(request)
    user = get_current_user(request)
    module = str(data.get("module", "")).strip().upper()
    permission = "production.create" if module == "DYEING" else "packing.create" if module == "PACKING" else None
    if permission is None:
        raise HTTPException(status_code=422, detail="Module must be DYEING or PACKING.")
    require_permission_for_user(user, permission)
    try:
        effective_on = date.fromisoformat(str(data.get("effective_on", "")))
        with get_connection() as conn:
            with conn.transaction():
                with conn.cursor() as cur:
                    result = create_ownership_use_request(
                        cur, company_id=user["company_id"], module=module,
                        target_line_id=int(data.get("target_line_id")),
                        owner_party_id=int(data.get("owner_party_id")),
                        requested_quantity=data.get("requested_quantity"),
                        unit_id=int(data["unit_id"]) if data.get("unit_id") not in (None, "") else None,
                        requested_unit_rate=data.get("requested_unit_rate"),
                        reason=data.get("reason", ""), requester_id=user["id"],
                        effective_on=effective_on, user=user, request=request,
                    )
    except (ValueError, TypeError) as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return {"created": True, "ownership_use_request": result}


@app.post("/api/production/ownership-use-requests/{request_id}/decision")
async def ownership_use_request_decision_api(request_id: int, request: Request):
    data = await _configuration_action_data(request)
    user = get_current_user(request)
    try:
        with get_connection() as conn:
            with conn.transaction():
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT use_module FROM production.ownership_use_requests WHERE id=%s AND company_id=%s FOR UPDATE",
                        (int(request_id), int(user["company_id"])),
                    )
                    request_row = cur.fetchone()
                    if not request_row:
                        raise HTTPException(status_code=404, detail="PARTY-use request not found.")
                    permission = "production.approve" if request_row["use_module"] == "DYEING" else "packing.approve"
                    require_permission_for_user(user, permission)
                    decision = str(data.get("decision", "")).strip().upper()
                    if decision not in ("APPROVE", "REJECT"):
                        raise ValueError("Decision must be APPROVE or REJECT.")
                    result = decide_ownership_use_request(
                        cur, company_id=user["company_id"], request_id=request_id,
                        approver_id=user["id"], approve=(decision == "APPROVE"),
                        decision_note=data.get("decision_note", ""), user=user, request=request,
                    )
    except (ValueError, TypeError) as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    return {"decided": True, "ownership_use_request": result}



@app.get("/modules/ownership-requests", response_class=HTMLResponse)
def ownership_use_requests_page(request: Request):
    user = get_current_user(request)
    permissions = {
        "DYEING": ("production.view", "production.create", "production.approve"),
        "PACKING": ("packing.view", "packing.create", "packing.approve"),
    }
    modules = []
    can_approve_dyeing = False
    can_approve_packing = False
    for module, codes in permissions.items():
        granted = set()
        for code in codes:
            try:
                require_permission_for_user(user, code)
                granted.add(code)
            except HTTPException as exc:
                if exc.status_code != 403:
                    raise
        if granted:
            modules.append(module)
        if module == "DYEING":
            can_approve_dyeing = "production.approve" in granted
        else:
            can_approve_packing = "packing.approve" in granted
    if not modules:
        raise HTTPException(status_code=403, detail="Access denied: production or packing permission required.")
    with get_connection() as conn:
        with conn.cursor() as cur:
            requests = list_ownership_use_requests(cur, company_id=user["company_id"], modules=modules, limit=200)
            draft_lines = list_party_draft_lines(cur, company_id=user["company_id"], modules=modules)
    return templates.TemplateResponse(
        request=request, name="ownership_use_requests.html",
        context={
            "app_name": settings.app_name, "requests": requests, "draft_lines": draft_lines,
            "pending_count": sum(1 for x in requests if x["status"] == "PENDING"),
            "approved_count": sum(1 for x in requests if x["status"] == "APPROVED"),
            "rejected_count": sum(1 for x in requests if x["status"] == "REJECTED"),
            "can_approve_dyeing": can_approve_dyeing,
            "can_approve_packing": can_approve_packing,
            "csrf_token": request.cookies.get("are_erp_csrf", ""),
        },
    )

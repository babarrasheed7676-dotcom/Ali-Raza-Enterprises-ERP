
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
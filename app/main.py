
import hmac
from urllib.parse import parse_qs, urlencode
from decimal import Decimal, InvalidOperation
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field

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
)
from .purchasing_service import (
    get_purchasing_page,
    supplier_code_exists,
    get_purchase_receipt_form_data,
    create_purchase_receipt_draft,
    approve_purchase_receipt,
    post_purchase_receipt,
)
from .supplier_service import create_supplier_with_audit


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
        "icon": "â–¦",
        "description": "Stock balances, stock documents, ledger and transfers",
        "status": "Database audit in progress",
        "url": "/modules/inventory",
    },
    {
        "name": "Production",
        "icon": "âš™",
        "description": "Dyeing, Large Cone, Baby Cone and Nalki",
        "status": "Planned",
        "url": "/modules/production",
    },
    {
        "name": "Packing",
        "icon": "â–£",
        "description": "Packing orders, material use, labour, wastage and FG transfer",
        "status": "Workflow verification in progress",
        "url": "/modules/packing",
    },
    {
        "name": "Sales & Dispatch",
        "icon": "â‡¢",
        "description": "Order-linked dispatch and inventory movement",
        "status": "Planned",
        "url": "/modules/sales-dispatch",
    },
    {
        "name": "Purchasing",
        "icon": "ï¼‹",
        "description": "Purchases and supplier-side records",
        "status": "Read-only listings available",
        "url": "/modules/purchasing",
    },
    {
        "name": "Accounting",
        "icon": "â–¤",
        "description": "Ledgers, expenses, bank and PDC cheques",
        "status": "Planned",
        "url": "/modules/accounting",
    },
    {
        "name": "Reports",
        "icon": "â–¤",
        "description": "Stock, costing, profit and owner dashboard",
        "status": "Planned",
        "url": "/modules/reports",
    },
    {
        "name": "HR & Payroll",
        "icon": "ðŸ‘¥",
        "description": "Employees, attendance, shifts, leave, overtime, payroll, advances and labour costing",
        "status": "Planned â€” implementation pending",
        "url": "/modules/hr-payroll",
    },
    {
        "name": "Configuration",
        "icon": "âš™",
        "description": "Flexible product, measurement, packaging and approval rules",
        "status": "Design scaffold â€” read-only",
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
    dependencies=[Depends(require_permission("configuration.view"))],
)
def configuration_page(
    request: Request,
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
                "Grams per yard = net grams Ã· measured yards",
                "Required kg = yards Ã— grams per yard Ã· 1,000",
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

    return templates.TemplateResponse(
        request=request,
        name="configuration.html",
        context={
            "app_name": settings.app_name,
            "configuration_groups": configuration_groups,
            "master_data": get_configuration_master_data(
                {
                    "brands": brands_page,
                    "units": units_page,
                    "shades": shades_page,
                    "variants": variants_page,
                }
            ),
        },
    )


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
    dependencies=[Depends(require_permission("accounting.party_ledger.view"))],
)
def accounting_party_ledger_page(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="party_ledger.html",
        context={"app_name": settings.app_name},
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

    if module_slug == "purchasing":
        can_create_supplier = True
        can_approve_receipt = False
        can_post_receipt = False

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
                else:
                    can_post_receipt = True
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

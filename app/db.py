"""Read-only database helpers for the first application milestone."""
from contextlib import contextmanager
from decimal import Decimal
from typing import Iterator

import psycopg
from psycopg.rows import dict_row

from .config import get_settings


@contextmanager
def get_connection() -> Iterator[psycopg.Connection]:
    settings = get_settings()
    conn = psycopg.connect(settings.database_dsn, row_factory=dict_row)
    try:
        yield conn
    finally:
        conn.close()


def get_database_status() -> dict:
    """Return only minimal database connectivity status."""
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
        return {"connected": True}
    except Exception:
        return {"connected": False}


def get_inventory_stock(search: str = "") -> list[dict]:
    """Read inventory balances without modifying database records."""
    sql = """
        SELECT
            i.item_code,
            i.item_name,
            v.variant_code,
            v.variant_name,
            b.name AS brand_name,
            sh.shade_code,
            sh.shade_name,
            cl.name AS location_name,
            ot.name AS ownership_name,
            p.party_name,
            sb.quantity,
            COALESCE(u.code, bu.code, '—') AS unit_code,
            sb.average_unit_cost,
            sb.total_value
        FROM inventory.stock_balances sb
        JOIN master.item_variants v
            ON v.id = sb.item_variant_id
        JOIN master.items i
            ON i.id = v.item_id
        LEFT JOIN master.brands b
            ON b.id = v.brand_id
        LEFT JOIN master.shades sh
            ON sh.id = v.shade_id
        JOIN inventory.locations il
            ON il.id = sb.location_id
        JOIN core.locations cl
            ON cl.id = il.core_location_id
        JOIN master.ownership_types ot
            ON ot.id = sb.ownership_type_id
        LEFT JOIN master.parties p
            ON p.id = sb.owner_party_id
        LEFT JOIN master.units u
    ON u.id = v.default_unit_id
LEFT JOIN master.units bu
    ON bu.id = i.base_unit_id
        WHERE (
            %(search)s = ''
            OR i.item_code ILIKE %(pattern)s
            OR i.item_name ILIKE %(pattern)s
            OR v.variant_code ILIKE %(pattern)s
            OR v.variant_name ILIKE %(pattern)s
            OR sh.shade_code ILIKE %(pattern)s
            OR sh.shade_name ILIKE %(pattern)s
            OR p.party_name ILIKE %(pattern)s
        )
        ORDER BY i.item_name, v.variant_code, cl.name
        LIMIT 1000
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                sql,
                {
                    "search": search.strip(),
                    "pattern": f"%{search.strip()}%",
                },
            )
            return [dict(row) for row in cur.fetchall()]

def get_inventory_stock_page(
    search: str = "",
    page: int = 1,
    page_size: int = 50,
) -> dict:
    """Read-only inventory search with accurate count and SQL pagination."""
    search = search.strip()[:100]
    page = max(1, int(page))
    page_size = max(1, min(int(page_size), 200))

    params = {
        "search": search,
        "pattern": f"%{search}%",
    }

    joins = """
        FROM inventory.stock_balances sb
        JOIN master.item_variants v
            ON v.id = sb.item_variant_id
        JOIN master.items i
            ON i.id = v.item_id
        LEFT JOIN master.brands b
            ON b.id = v.brand_id
        LEFT JOIN master.shades sh
            ON sh.id = v.shade_id
        JOIN inventory.locations il
            ON il.id = sb.location_id
        JOIN core.locations cl
            ON cl.id = il.core_location_id
        JOIN master.ownership_types ot
            ON ot.id = sb.ownership_type_id
        LEFT JOIN master.parties p
            ON p.id = sb.owner_party_id
        LEFT JOIN master.units u
            ON u.id = v.default_unit_id
        LEFT JOIN master.units bu
            ON bu.id = i.base_unit_id
        WHERE (
            %(search)s = ''
            OR i.item_code ILIKE %(pattern)s
            OR i.item_name ILIKE %(pattern)s
            OR v.variant_code ILIKE %(pattern)s
            OR v.variant_name ILIKE %(pattern)s
            OR b.name ILIKE %(pattern)s
            OR sh.shade_code ILIKE %(pattern)s
            OR sh.shade_name ILIKE %(pattern)s
            OR p.party_name ILIKE %(pattern)s
            OR cl.name ILIKE %(pattern)s
        )
    """

    count_sql = "SELECT COUNT(*) AS total " + joins

    rows_sql = """
        SELECT
            i.item_code,
            i.item_name,
            v.variant_code,
            v.variant_name,
            b.name AS brand_name,
            sh.shade_code,
            sh.shade_name,
            cl.name AS location_name,
            ot.name AS ownership_name,
            p.party_name AS owner_party,
            sb.quantity,
            COALESCE(u.code, bu.code, '?') AS unit_code,
            sb.average_unit_cost,
            sb.total_value
    """ + joins + """
        ORDER BY i.item_name, v.variant_code, cl.name
        LIMIT %(limit)s OFFSET %(offset)s
    """

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(count_sql, params)
            total = int(cur.fetchone()["total"])

            pages = max(1, (total + page_size - 1) // page_size)
            page = min(page, pages)

            row_params = {
                **params,
                "limit": page_size,
                "offset": (page - 1) * page_size,
            }
            cur.execute(rows_sql, row_params)
            rows = [dict(row) for row in cur.fetchall()]

    return {
        "rows": rows,
        "total": total,
        "page": page,
        "pages": pages,
    }


def get_dashboard_inventory_summary() -> dict:
    """Read-only inventory KPIs and location-wise stock value."""
    summary_sql = """
        SELECT
            COALESCE(SUM(sb.total_value), 0) AS total_stock_value,
            COUNT(DISTINCT sb.item_variant_id) AS active_variants,
            COUNT(DISTINCT sb.location_id) AS stock_locations
        FROM inventory.stock_balances sb
        WHERE COALESCE(sb.quantity, 0) <> 0
    """

    location_sql = """
        SELECT
            cl.name AS location_name,
            COALESCE(SUM(sb.total_value), 0) AS stock_value,
            COUNT(DISTINCT sb.item_variant_id) AS variant_count
        FROM inventory.stock_balances sb
        JOIN inventory.locations il
            ON il.id = sb.location_id
        JOIN core.locations cl
            ON cl.id = il.core_location_id
        WHERE COALESCE(sb.quantity, 0) <> 0
        GROUP BY cl.id, cl.name
        ORDER BY SUM(sb.total_value) DESC NULLS LAST
    """

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(summary_sql)
            summary = dict(cur.fetchone())

            cur.execute(location_sql)
            locations = [dict(row) for row in cur.fetchall()]

    total_value = float(summary["total_stock_value"] or 0)
    max_value = max(
        (float(row["stock_value"] or 0) for row in locations),
        default=0,
    )

    for row in locations:
        value = float(row["stock_value"] or 0)
        row["stock_value"] = value
        row["bar_width"] = (
            min(100, round(value / max_value * 100, 1))
            if max_value > 0 else 0
        )

    return {
        "total_stock_value": total_value,
        "active_variants": int(summary["active_variants"] or 0),
        "stock_locations": int(summary["stock_locations"] or 0),
        "locations": locations,
    }


def get_configuration_master_data(pages: dict | None = None, page_size: int = 50, company_id: int | None = None) -> dict:
    """Read paginated configuration master data; never writes to PostgreSQL."""
    page_size = max(1, min(int(page_size), 100))
    pages = pages or {}
    result = {
        "brands": [], "units": [], "shades": [], "variants": [],
        "items": [], "item_categories": [], "yarn_counts": [], "fiber_types": [], "shade_categories": [], "shade_options": [],
        "error": None, "pagination": {},
    }

    queries = {
        "brands": """
            SELECT id, code, name, description, is_active
            FROM master.brands
            ORDER BY name
        """,
        "units": """
            SELECT id, code, name, unit_type, decimal_places, is_active
            FROM master.units
            ORDER BY name
        """,
        "shades": """
            SELECT s.id, s.brand_id, s.shade_category_id,
                   s.shade_code, s.shade_name, s.is_common,
                   b.name AS brand_name,
                   sc.name AS category_name,
                   s.is_active
            FROM master.shades s
            LEFT JOIN master.brands b ON b.id = s.brand_id
            LEFT JOIN master.shade_categories sc
                ON sc.id = s.shade_category_id
            ORDER BY b.name,
                     CASE WHEN s.shade_code ~ '^[0-9]+$' THEN 0 ELSE 1 END,
                     CASE WHEN s.shade_code ~ '^[0-9]+$' THEN s.shade_code::integer END,
                     s.shade_code
        """,
        "variants": """
            SELECT v.id, v.item_id, v.brand_id, v.shade_id, v.default_unit_id,
                   i.item_code, i.item_name,
                   v.variant_code, v.variant_name,
                   b.name AS brand_name,
                   sh.shade_code, sh.shade_name,
                   u.code AS unit_code,
                   v.is_active
            FROM master.item_variants v
            JOIN master.items i ON i.id = v.item_id
            LEFT JOIN master.brands b ON b.id = v.brand_id
            LEFT JOIN master.shades sh ON sh.id = v.shade_id
            LEFT JOIN master.units u ON u.id = v.default_unit_id
            ORDER BY i.item_name,
                     CASE WHEN sh.shade_code ~ '^[0-9]+$' THEN 0 ELSE 1 END,
                     CASE WHEN sh.shade_code ~ '^[0-9]+$' THEN sh.shade_code::integer END,
                     v.variant_code
        """,
    }

    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                for key, sql in queries.items():
                    count_sql = f"SELECT COUNT(*) AS total FROM ({sql}) AS config_count"
                    cur.execute(count_sql)
                    total = int(cur.fetchone()["total"])
                    pages_total = max(1, (total + page_size - 1) // page_size)
                    try:
                        page = int(pages.get(key, 1))
                    except (TypeError, ValueError):
                        page = 1
                    page = max(1, min(page, pages_total))
                    offset = (page - 1) * page_size

                    cur.execute(
                        f"SELECT * FROM ({sql}) AS config_page LIMIT %s OFFSET %s",
                        (page_size, offset),
                    )
                    result[key] = [dict(row) for row in cur.fetchall()]
                    result["pagination"][key] = {
                        "page": page,
                        "pages": pages_total,
                        "total": total,
                        "page_size": page_size,
                    }
                cur.execute("SELECT id,code,name,description,is_active FROM master.yarn_counts ORDER BY code")
                result["yarn_counts"] = [dict(row) for row in cur.fetchall()]
                cur.execute("SELECT id,code,name,description,is_active FROM master.fiber_types ORDER BY code")
                result["fiber_types"] = [dict(row) for row in cur.fetchall()]
                cur.execute("SELECT id,code,name,description,is_active FROM master.shade_categories ORDER BY name")
                result["shade_categories"] = [dict(row) for row in cur.fetchall()]
                cur.execute("""SELECT s.id,s.brand_id,s.shade_code,s.shade_name,
                                      s.shade_category_id,b.name AS brand_name,
                                      b.code AS brand_code,sc.name AS category_name
                               FROM master.shades s
                               JOIN master.brands b ON b.id=s.brand_id
                               LEFT JOIN master.shade_categories sc ON sc.id=s.shade_category_id
                               WHERE s.is_active AND b.is_active
                               ORDER BY b.name, CASE WHEN s.shade_code ~ '^[0-9]+$' THEN 0 ELSE 1 END,
                                        CASE WHEN s.shade_code ~ '^[0-9]+$' THEN s.shade_code::integer END,
                                        s.shade_code""")
                result["shade_options"] = [dict(row) for row in cur.fetchall()]
                cur.execute("""SELECT id,company_id,code,name,description,parent_category_id,is_active
                               FROM master.item_categories
                               WHERE (%s IS NULL OR company_id=%s)
                               ORDER BY name,id""", (company_id,company_id))
                result["item_categories"] = [dict(row) for row in cur.fetchall()]
                cur.execute("""SELECT i.id,i.company_id,i.item_category_id,i.item_code,i.item_name,
                                      i.description,i.base_unit_id,u.code AS base_unit_code,
                                      c.code AS category_code,c.name AS category_name,
                                      i.track_batch,i.track_shade,i.track_ownership,
                                      i.is_stock_item,i.is_active
                               FROM master.items i
                               JOIN master.units u ON u.id=i.base_unit_id
                               JOIN master.item_categories c ON c.id=i.item_category_id
                               WHERE (%s IS NULL OR i.company_id=%s)
                               ORDER BY i.item_name,i.id""", (company_id,company_id))
                result["items"] = [dict(row) for row in cur.fetchall()]
    except Exception as exc:
        result["error"] = (
            f"Master data could not be loaded ({type(exc).__name__})."
        )
    return result

def get_user_for_auth(username: str) -> dict | None:
    """Read one unambiguous user record for authentication; never writes."""
    if not isinstance(username, str):
        return None

    username = username.strip()
    if not username or len(username) > 200:
        return None

    sql = """
        SELECT id, company_id, username, full_name,
               password_hash, is_active
        FROM core.users
        WHERE username = %(username)s
        LIMIT 2
    """

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, {"username": username})
            rows = cur.fetchall()

    # If usernames exist in multiple companies, reject ambiguity.
    if len(rows) != 1:
        return None

    return dict(rows[0])


def get_party_ledger_data(company_id: int, party_id: int | None = None) -> dict:
    """Load company-scoped party masters and opening balances only.

    Journal activity is deliberately not fabricated: the current schema has
    no implemented general-ledger journal source yet.
    """
    sql = """
        SELECT
            p.id,
            p.party_code,
            p.party_name,
            p.party_type,
            p.is_active,
            pf.opening_balance,
            pf.opening_balance_type,
            pf.default_currency_code
        FROM master.parties p
        LEFT JOIN master.party_financial_profiles pf
            ON pf.party_id = p.id
        WHERE p.company_id = %s
        ORDER BY p.party_type, p.party_name, p.id
        LIMIT 1000
    """

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (int(company_id),))
            parties = [dict(row) for row in cur.fetchall()]

    for party in parties:
        amount = party.get("opening_balance")
        direction = str(party.get("opening_balance_type") or "").strip().upper()
        party["opening_configured"] = False
        party["opening_display"] = "Not configured"
        party["opening_signed_balance"] = None
        party["opening_balance_label"] = "Not configured"

        if amount is None:
            continue

        try:
            amount = Decimal(str(amount))
        except (TypeError, ValueError, ArithmeticError):
            party["opening_balance_label"] = "Needs review"
            continue

        if not amount.is_finite() or amount < 0:
            party["opening_balance_label"] = "Needs review"
            continue

        if direction not in ("DEBIT", "CREDIT"):
            if amount != 0:
                party["opening_balance_label"] = "Needs review"
            continue

        signed = amount if direction == "DEBIT" else -amount
        party["opening_configured"] = True
        party["opening_signed_balance"] = signed
        party["opening_balance_label"] = direction.title()
        party["opening_display"] = (
            f"{amount:,.2f} {direction.title()}"
        )

    selected_party = None
    if party_id is None and parties:
        selected_party = parties[0]
    elif party_id is not None:
        selected_party = next(
            (party for party in parties if party["id"] == int(party_id)),
            None,
        )

    return {
        "parties": parties,
        "selected_party": selected_party,
        "journal_activity_available": False,
        "activity_message": (
            "Opening balance only. Posted journal activity is not connected yet."
        ),
    }
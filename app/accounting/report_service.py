"""Read-only General Ledger reports backed only by posted journal records."""
from datetime import date, timedelta
from calendar import monthrange
from decimal import Decimal

from ..db import get_connection


def _parse_report_dates(start_date, end_date):
    try:
        start = date.fromisoformat(start_date) if isinstance(start_date, str) else start_date
        end = date.fromisoformat(end_date) if isinstance(end_date, str) else end_date
    except (TypeError, ValueError):
        raise ValueError("Report dates must use YYYY-MM-DD format.")
    if not isinstance(start, date) or not isinstance(end, date):
        raise ValueError("Both report dates are required.")
    if end < start:
        raise ValueError("Report end date cannot be earlier than start date.")
    if (end - start).days > 3660:
        raise ValueError("Report date range cannot exceed ten years.")
    return start, end


def _signed_balance(debit, credit):
    net = Decimal(str(debit or 0)) - Decimal(str(credit or 0))
    return {
        "net": net,
        "balance": abs(net),
        "balance_type": "Dr" if net > 0 else "Cr" if net < 0 else "—",
    }


def _trial_balance_is_balanced(journal_count, debit_balance_total, credit_balance_total):
    """An empty journal set is not evidence of a balanced trial balance."""
    if int(journal_count or 0) <= 0:
        return False
    debit_total = Decimal(str(debit_balance_total or 0))
    credit_total = Decimal(str(credit_balance_total or 0))
    return debit_total == credit_total


def get_trial_balance(company_id, start_date, end_date):
    """Return movement-based trial balance; never imply missing opening balances are zero."""
    start, end = _parse_report_dates(start_date, end_date)
    sql = """
        WITH movements AS (
            SELECT jl.account_id,
                   SUM(jl.debit) AS debit,
                   SUM(jl.credit) AS credit
            FROM accounting.journal_lines jl
            JOIN accounting.journal_entries je
              ON je.id = jl.journal_id AND je.company_id = jl.company_id
            WHERE jl.company_id = %s
              AND je.status IN ('POSTED', 'REVERSED')
              AND je.entry_date BETWEEN %s AND %s
            GROUP BY jl.account_id
        )
        SELECT a.id AS account_id, a.account_code, a.account_name,
               a.account_type, a.normal_balance,
               COALESCE(m.debit, 0) AS debit,
               COALESCE(m.credit, 0) AS credit
        FROM accounting.accounts a
        LEFT JOIN movements m ON m.account_id = a.id
        WHERE a.company_id = %s
          AND a.is_group = FALSE
          AND (a.is_active = TRUE OR m.account_id IS NOT NULL)
        ORDER BY a.account_code, a.id
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (int(company_id), start, end, int(company_id)))
            source_rows = [dict(row) for row in cur.fetchall()]
            cur.execute(
                """
                SELECT COUNT(*) AS journal_count
                FROM accounting.journal_entries
                WHERE company_id = %s
                  AND status IN ('POSTED', 'REVERSED')
                  AND entry_date BETWEEN %s AND %s
                """,
                (int(company_id), start, end),
            )
            journal_count = int(cur.fetchone()["journal_count"])

    rows = []
    debit_total = Decimal("0")
    credit_total = Decimal("0")
    movement_debit_total = Decimal("0")
    movement_credit_total = Decimal("0")
    for source in source_rows:
        debit = Decimal(str(source["debit"] or 0))
        credit = Decimal(str(source["credit"] or 0))
        movement = _signed_balance(debit, credit)
        debit_total += movement["balance"] if movement["net"] > 0 else Decimal("0")
        credit_total += movement["balance"] if movement["net"] < 0 else Decimal("0")
        movement_debit_total += debit
        movement_credit_total += credit
        rows.append({
            **source,
            "debit": debit,
            "credit": credit,
            "closing_balance": movement["balance"],
            "balance_type": movement["balance_type"],
        })

    return {
        "start_date": start,
        "end_date": end,
        "rows": rows,
        "debit_balance_total": debit_total,
        "credit_balance_total": credit_total,
        "movement_debit_total": movement_debit_total,
        "movement_credit_total": movement_credit_total,
        "journal_count": journal_count,
        "opening_balance_configured": False,
        "balance_basis": "Posted journal movement only — opening balances are not configured in the GL account master.",
        "balance_check_applicable": journal_count > 0,
        "is_balanced": _trial_balance_is_balanced(
            journal_count, debit_total, credit_total
        ),
    }


def get_account_ledger(company_id, account_id, start_date, end_date):
    """Return dated posted journal movements and a window-only running net movement."""
    start, end = _parse_report_dates(start_date, end_date)
    account_id = int(account_id)
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, account_code, account_name, account_type
                FROM accounting.accounts
                WHERE company_id = %s AND id = %s AND is_group = FALSE
                """,
                (int(company_id), account_id),
            )
            account = cur.fetchone()
            if not account:
                raise ValueError("Account was not found in this company or is not a posting account.")
            cur.execute(
                """
                SELECT je.id AS journal_id, je.journal_no, je.entry_date,
                       je.status, je.description AS journal_description,
                       jl.line_no, jl.party_id, jl.debit, jl.credit,
                       jl.description AS line_description,
                       p.party_code, p.party_name
                FROM accounting.journal_lines jl
                JOIN accounting.journal_entries je
                  ON je.id = jl.journal_id AND je.company_id = jl.company_id
                LEFT JOIN master.parties p
                  ON p.id = jl.party_id AND p.company_id = jl.company_id
                WHERE jl.company_id = %s AND jl.account_id = %s
                  AND je.status IN ('POSTED', 'REVERSED')
                  AND je.entry_date BETWEEN %s AND %s
                ORDER BY je.entry_date, je.id, jl.line_no
                """,
                (int(company_id), account_id, start, end),
            )
            transactions = [dict(row) for row in cur.fetchall()]

    running = Decimal("0")
    rows = []
    for tx in transactions:
        debit = Decimal(str(tx["debit"] or 0))
        credit = Decimal(str(tx["credit"] or 0))
        running += debit - credit
        rows.append({
            **tx,
            "debit": debit,
            "credit": credit,
            "running_movement": abs(running),
            "running_type": "Dr" if running > 0 else "Cr" if running < 0 else "—",
        })
    return {
        "account": dict(account),
        "start_date": start,
        "end_date": end,
        "rows": rows,
        "opening_balance_configured": False,
        "running_basis": "Running movement within selected dates only; opening balance is not configured.",
        "period_debit": sum((Decimal(str(row["debit"])) for row in rows), Decimal("0")),
        "period_credit": sum((Decimal(str(row["credit"])) for row in rows), Decimal("0")),
    }


def get_posting_accounts(company_id):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, account_code, account_name, account_type
                FROM accounting.accounts
                WHERE company_id = %s AND is_group = FALSE
                ORDER BY account_code, id
                """,
                (int(company_id),),
            )
            return [dict(row) for row in cur.fetchall()]

def get_party_ledger_activity(company_id, party_id, opening_signed_balance=None):
    """Read posted party-tagged journal lines; preserve unknown opening balances."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT je.id AS journal_id, je.journal_no, je.entry_date,
                       je.status, je.description AS journal_description,
                       jl.line_no, jl.debit, jl.credit, jl.description AS line_description,
                       a.account_code, a.account_name
                FROM accounting.journal_lines jl
                JOIN accounting.journal_entries je
                  ON je.id = jl.journal_id AND je.company_id = jl.company_id
                JOIN accounting.accounts a
                  ON a.id = jl.account_id AND a.company_id = jl.company_id
                WHERE jl.company_id = %s AND jl.party_id = %s
                  AND je.status IN ('POSTED', 'REVERSED')
                ORDER BY je.entry_date, je.id, jl.line_no
                """,
                (int(company_id), int(party_id)),
            )
            source_rows = [dict(row) for row in cur.fetchall()]

    opening_known = opening_signed_balance is not None
    running = Decimal(str(opening_signed_balance)) if opening_known else None
    movement_running = Decimal("0")
    rows = []
    for tx in source_rows:
        debit = Decimal(str(tx["debit"] or 0))
        credit = Decimal(str(tx["credit"] or 0))
        movement_running += debit - credit
        if opening_known:
            running += debit - credit
            running_balance = abs(running)
            running_type = "Dr" if running > 0 else "Cr" if running < 0 else "—"
        else:
            running_balance = None
            running_type = "Not configured"
        rows.append({
            **tx,
            "debit": debit,
            "credit": credit,
            "running_balance": running_balance,
            "running_type": running_type,
            "movement_running": abs(movement_running),
            "movement_running_type": (
                "Dr" if movement_running > 0
                else "Cr" if movement_running < 0 else "—"
            ),
        })
    return {
        "rows": rows,
        "opening_balance_configured": opening_known,
        "activity_message": (
            "Posted journal activity is connected. Running balances include the configured opening balance."
            if opening_known else
            "Posted journal activity is connected. Opening balance is not configured, so only cumulative movement is shown; no actual running balance is claimed."
        ),
        "debit_total": sum((row["debit"] for row in rows), Decimal("0")),
        "credit_total": sum((row["credit"] for row in rows), Decimal("0")),
    }


def get_accounting_setup_readiness(company_id):
    """Read-only setup audit for fiscal periods and party opening-balance readiness."""
    company_id = int(company_id)
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SET TRANSACTION READ ONLY")
            cur.execute(
                """
                SELECT
                    (SELECT COUNT(*) FROM core.fiscal_years WHERE company_id = %s) AS fiscal_year_count,
                    (SELECT COUNT(*) FROM core.fiscal_years WHERE company_id = %s AND is_closed = FALSE) AS open_fiscal_year_count,
                    (SELECT COUNT(*) FROM core.accounting_periods p
                     JOIN core.fiscal_years fy ON fy.id = p.fiscal_year_id
                     WHERE fy.company_id = %s) AS period_count,
                    (SELECT COUNT(*) FROM core.accounting_periods p
                     JOIN core.fiscal_years fy ON fy.id = p.fiscal_year_id
                     WHERE fy.company_id = %s AND p.is_closed = FALSE) AS open_period_count
                """,
                (company_id, company_id, company_id, company_id),
            )
            periods = dict(cur.fetchone())

            cur.execute(
                """
                SELECT p.party_type,
                       COUNT(*) AS party_count,
                       COUNT(pf.id) AS financial_profile_count,
                       COUNT(*) FILTER (
                           WHERE pf.id IS NOT NULL AND pf.opening_balance <> 0
                       ) AS nonzero_opening_count,
                       COUNT(*) FILTER (
                           WHERE pf.id IS NOT NULL
                             AND pf.opening_balance <> 0
                             AND pf.opening_balance_type IS NULL
                       ) AS missing_direction_count,
                       COALESCE(SUM(pf.opening_balance), 0) AS entered_opening_amount
                FROM master.parties p
                LEFT JOIN master.party_financial_profiles pf ON pf.party_id = p.id
                WHERE p.company_id = %s
                GROUP BY p.party_type
                ORDER BY p.party_type
                """,
                (company_id,),
            )
            party_rows = [dict(row) for row in cur.fetchall()]

            cur.execute(
                """
                SELECT account_code, account_name, is_active
                FROM accounting.accounts
                WHERE company_id = %s
                  AND is_control = TRUE
                  AND account_code IN ('1221', '1231', '2211', '2241')
                ORDER BY account_code
                """,
                (company_id,),
            )
            mapped_party_controls = [dict(row) for row in cur.fetchall()]

            cur.execute(
                """
                SELECT status, COUNT(*) AS entry_count
                FROM accounting.journal_entries
                WHERE company_id = %s
                GROUP BY status
                ORDER BY status
                """,
                (company_id,),
            )
            journal_statuses = [dict(row) for row in cur.fetchall()]

    party_summary = {
        str(row["party_type"]): {
            **row,
            "party_count": int(row["party_count"]),
            "financial_profile_count": int(row["financial_profile_count"]),
            "missing_profile_count": int(row["party_count"]) - int(row["financial_profile_count"]),
            "nonzero_opening_count": int(row["nonzero_opening_count"]),
            "missing_direction_count": int(row["missing_direction_count"]),
            "entered_opening_amount": Decimal(str(row["entered_opening_amount"] or 0)),
        }
        for row in party_rows
    }
    journal_counts = {str(row["status"]): int(row["entry_count"]) for row in journal_statuses}
    return {
        "periods": {key: int(value) for key, value in periods.items()},
        "parties": party_summary,
        "mapped_party_controls": mapped_party_controls,
        "journal_statuses": journal_counts,
        "journal_entry_total": sum(journal_counts.values()),
        "ready_for_journal_posting": (
            int(periods["open_fiscal_year_count"]) > 0
            and int(periods["open_period_count"]) > 0
        ),
        "opening_balances_posted_to_gl": False,
        "notice": (
            "Party master opening amounts are not General Ledger opening journals. "
            "They must be reconciled and posted through a separately approved opening-balance workflow."
        ),
    }


def get_fiscal_year_period_preview(company_id, start_date, end_date):
    """Build a read-only monthly period preview and detect company date overlaps."""
    try:
        start = date.fromisoformat(start_date) if isinstance(start_date, str) else start_date
        end = date.fromisoformat(end_date) if isinstance(end_date, str) else end_date
    except (TypeError, ValueError):
        raise ValueError("Fiscal year dates must use YYYY-MM-DD format.")
    if not isinstance(start, date) or not isinstance(end, date):
        raise ValueError("Both fiscal year dates are required.")
    if end < start:
        raise ValueError("Fiscal year end date cannot be earlier than start date.")
    if (end - start).days > 3660:
        raise ValueError("Fiscal year preview cannot exceed ten years.")
    company_id = int(company_id)

    periods = []
    cursor = start
    while cursor <= end:
        month_end = date(cursor.year, cursor.month, monthrange(cursor.year, cursor.month)[1])
        period_end = min(month_end, end)
        periods.append({
            "number": len(periods) + 1,
            "name": f"P{len(periods) + 1:02d} - {cursor.strftime('%b %Y')}",
            "start_date": cursor,
            "end_date": period_end,
            "day_count": (period_end - cursor).days + 1,
        })
        if len(periods) > 120:
            raise ValueError("Fiscal year preview exceeds 120 monthly periods.")
        cursor = period_end + timedelta(days=1)

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SET TRANSACTION READ ONLY")
            cur.execute(
                """
                SELECT id, name, start_date, end_date, is_closed
                FROM core.fiscal_years
                WHERE company_id = %s
                  AND start_date <= %s
                  AND end_date >= %s
                ORDER BY start_date
                """,
                (company_id, end, start),
            )
            conflicts = [dict(row) for row in cur.fetchall()]

    return {
        "start_date": start,
        "end_date": end,
        "periods": periods,
        "conflicts": conflicts,
        "is_valid": len(conflicts) == 0,
        "period_count": len(periods),
        "total_days": (end - start).days + 1,
        "read_only": True,
        "message": (
            "No existing fiscal-year date overlap found. This is a preview only; "
            "it does not create a fiscal year or accounting periods."
            if not conflicts else
            "The proposed date range overlaps an existing fiscal year. Do not create it until the conflict is resolved."
        ),
    }


def _inventory_gl_reconciliation_summary(
    own_stock_value,
    gl_inventory_net,
    *,
    stock_balance_rows,
    unvalued_balance_rows=0,
    negative_quantity_rows=0,
    missing_inventory_accounts=(),
    inactive_inventory_accounts=(),
):
    """Summarize stock-subledger vs GL inventory movement without posting."""
    own_value = Decimal(str(own_stock_value or 0))
    gl_value = Decimal(str(gl_inventory_net or 0))
    difference = own_value - gl_value
    missing_accounts = list(missing_inventory_accounts)
    inactive_accounts = list(inactive_inventory_accounts)

    if int(stock_balance_rows) == 0:
        status = "NO STOCK BALANCES TO RECONCILE"
    elif int(unvalued_balance_rows) or int(negative_quantity_rows):
        status = "STOCK VALUATION NEEDS REVIEW"
    elif missing_accounts or inactive_accounts:
        status = "INVENTORY CONTROL ACCOUNTS NEED REVIEW"
    elif difference != 0:
        status = "STOCK / GL VALUE MISMATCH"
    else:
        status = "STOCK / GL VALUE MATCHED"

    return {
        "own_stock_value": own_value,
        "gl_inventory_net": gl_value,
        "difference": difference,
        "stock_balance_rows": int(stock_balance_rows),
        "unvalued_balance_rows": int(unvalued_balance_rows),
        "negative_quantity_rows": int(negative_quantity_rows),
        "missing_inventory_accounts": missing_accounts,
        "inactive_inventory_accounts": inactive_accounts,
        "status": status,
        "read_only": True,
    }


def get_inventory_gl_reconciliation(company_id):
    """Compare current OWN stock valuation with posted GL inventory movements."""
    company_id = int(company_id)
    expected_codes = ("1241", "1242", "1243", "1244", "1245", "1246", "1247", "1248", "1249")
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SET TRANSACTION READ ONLY")
            cur.execute(
                "SELECT currency_code FROM core.company WHERE id = %s",
                (company_id,),
            )
            company = cur.fetchone()
            if not company:
                raise ValueError("Company was not found for inventory reconciliation.")
            company_currency = str(company["currency_code"] or "").strip().upper()

            cur.execute(
                """
                SELECT ot.code AS ownership_code, ot.name AS ownership_name,
                       ot.is_company_owned,
                       COUNT(sb.id) AS balance_rows,
                       COALESCE(SUM(sb.quantity), 0) AS quantity,
                       COALESCE(SUM(COALESCE(sb.total_value, 0)), 0) AS total_value,
                       COUNT(sb.id) FILTER (WHERE sb.total_value IS NULL) AS unvalued_rows,
                       COUNT(sb.id) FILTER (WHERE sb.quantity < 0) AS negative_quantity_rows
                FROM inventory.stock_balances sb
                JOIN master.ownership_types ot ON ot.id = sb.ownership_type_id
                WHERE sb.company_id = %s
                GROUP BY ot.code, ot.name, ot.is_company_owned
                ORDER BY ot.code
                """,
                (company_id,),
            )
            ownership_rows = [dict(row) for row in cur.fetchall()]
            cur.execute(
                """
                SELECT COUNT(*) AS posted_stock_document_count
                FROM inventory.stock_documents
                WHERE company_id = %s AND status = 'POSTED'
                """,
                (company_id,),
            )
            posted_stock_document_count = int(cur.fetchone()["posted_stock_document_count"])

            cur.execute(
                """
                SELECT a.account_code, a.account_name, a.is_active,
                       COALESCE(SUM(CASE WHEN je.id IS NOT NULL THEN jl.debit ELSE 0 END), 0) AS debit,
                       COALESCE(SUM(CASE WHEN je.id IS NOT NULL THEN jl.credit ELSE 0 END), 0) AS credit,
                       COALESCE(SUM(CASE WHEN je.id IS NOT NULL THEN jl.debit - jl.credit ELSE 0 END), 0) AS net,
                       COUNT(DISTINCT je.id) AS journal_count
                FROM accounting.accounts a
                LEFT JOIN accounting.journal_lines jl
                  ON jl.account_id = a.id AND jl.company_id = a.company_id
                LEFT JOIN accounting.journal_entries je
                  ON je.id = jl.journal_id
                 AND je.company_id = jl.company_id
                 AND je.status IN ('POSTED', 'REVERSED')
                WHERE a.company_id = %s
                  AND a.account_code = ANY(%s)
                GROUP BY a.id, a.account_code, a.account_name, a.is_active
                ORDER BY a.account_code
                """,
                (company_id, list(expected_codes)),
            )
            gl_accounts = [dict(row) for row in cur.fetchall()]

    own_rows = [row for row in ownership_rows if row["is_company_owned"]]
    party_rows = [row for row in ownership_rows if not row["is_company_owned"]]
    own_value = sum(
        (Decimal(str(row["total_value"] or 0)) for row in own_rows),
        Decimal("0"),
    )
    party_value = sum(
        (Decimal(str(row["total_value"] or 0)) for row in party_rows),
        Decimal("0"),
    )
    own_row_count = sum(int(row["balance_rows"]) for row in own_rows)
    unvalued_rows = sum(int(row["unvalued_rows"]) for row in own_rows)
    negative_rows = sum(int(row["negative_quantity_rows"]) for row in own_rows)
    account_codes = {str(row["account_code"]) for row in gl_accounts}
    missing_accounts = sorted(set(expected_codes) - account_codes)
    inactive_accounts = sorted(
        str(row["account_code"]) for row in gl_accounts if not row["is_active"]
    )
    gl_net = sum(
        (Decimal(str(row["net"] or 0)) for row in gl_accounts),
        Decimal("0"),
    )
    summary = _inventory_gl_reconciliation_summary(
        own_value,
        gl_net,
        stock_balance_rows=own_row_count,
        unvalued_balance_rows=unvalued_rows,
        negative_quantity_rows=negative_rows,
        missing_inventory_accounts=missing_accounts,
        inactive_inventory_accounts=inactive_accounts,
    )
    return {
        **summary,
        "company_currency": company_currency,
        "ownership_rows": ownership_rows,
        "party_owned_stock_value": party_value,
        "party_owned_balance_rows": sum(int(row["balance_rows"]) for row in party_rows),
        "gl_accounts": gl_accounts,
        "gl_journal_count": sum(int(row["journal_count"]) for row in gl_accounts),
        "posted_stock_document_count": posted_stock_document_count,
        "inventory_posting_gl_integration": False,
        "posting_integration_status": (
            "The inspected inventory.post_stock_document() updates stock balances and "
            "stock_ledger, then marks the stock document POSTED; it does not create "
            "accounting journal entries. No stock-table GL posting triggers were found."
        ),
        "note": (
            "This compares the current stock-balance snapshot for company-owned (OWN) "
            "stock against posted/reversed GL movement in inventory control accounts. "
            "PARTY-owned stock is shown separately and excluded from company asset value. "
            "It is not a historical opening-balance valuation."
        ),
    }


def _review_party_opening_row(party, account_rows, company_currency):
    """Validate one party opening balance without inferring missing financial data."""
    amount = (
        Decimal(str(party["opening_balance"]))
        if party.get("opening_balance") is not None else None
    )
    party_type = str(party.get("party_type") or "").strip().upper()
    direction = str(party.get("opening_balance_type") or "").strip().upper()
    currency = str(party.get("default_currency_code") or "").strip().upper()
    company_currency = str(company_currency or "").strip().upper()

    mapping = {
        ("CUSTOMER", "DEBIT"): ("1221", "ASSET", "DEBIT"),
        ("CUSTOMER", "CREDIT"): ("2241", "LIABILITY", "CREDIT"),
        ("SUPPLIER", "DEBIT"): ("1231", "ASSET", "DEBIT"),
        ("SUPPLIER", "CREDIT"): ("2211", "LIABILITY", "CREDIT"),
    }
    mapping_rule = mapping.get((party_type, direction))
    code = mapping_rule[0] if mapping_rule else ""
    account = account_rows.get(code) if code else None

    if not party.get("is_active"):
        status = "INACTIVE PARTY"
    elif party_type not in ("CUSTOMER", "SUPPLIER"):
        status = "UNSUPPORTED PARTY TYPE"
    elif not party.get("profile_id"):
        status = "PROFILE MISSING"
    elif amount is None:
        status = "OPENING AMOUNT MISSING"
    elif amount < 0:
        status = "INVALID NEGATIVE AMOUNT"
    elif amount == 0:
        status = "NO OPENING AMOUNT"
    elif direction not in ("DEBIT", "CREDIT"):
        status = "DIRECTION REQUIRED"
    elif not currency:
        status = "CURRENCY NOT SET"
    elif not company_currency:
        status = "COMPANY CURRENCY NOT CONFIGURED"
    elif currency != company_currency:
        status = "CURRENCY MISMATCH — CONVERSION REQUIRED"
    elif not account:
        status = "CONTROL ACCOUNT MISSING"
    elif (
        not account["is_active"]
        or account["is_group"]
        or not account["is_control"]
        or str(account.get("account_type") or "").upper() != mapping_rule[1]
        or str(account.get("normal_balance") or "").upper() != mapping_rule[2]
    ):
        status = "CONTROL ACCOUNT NEEDS REVIEW"
    else:
        status = "MAPPING READY — NOT POSTED"

    return {
        "party_id": int(party["id"]),
        "party_code": party["party_code"],
        "party_name": party["party_name"],
        "party_type": party_type,
        "is_active": bool(party["is_active"]),
        "profile_exists": bool(party.get("profile_id")),
        "opening_balance": amount,
        "direction": direction or "NOT SET",
        "currency": currency or "NOT CONFIGURED",
        "company_currency": company_currency or "NOT CONFIGURED",
        "account_code": code,
        "account_name": account["account_name"] if account else "",
        "status": status,
        "ready_for_review": status == "MAPPING READY — NOT POSTED",
    }


def _candidate_movement_is_balanced(candidate_lines, debit_total, credit_total):
    """Only report balance when at least one eligible candidate line exists."""
    return bool(candidate_lines) and debit_total == credit_total


def get_party_opening_review(company_id):
    """Read-only party-by-party opening balance and control-account mapping audit."""
    company_id = int(company_id)
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SET TRANSACTION READ ONLY")
            cur.execute(
                "SELECT currency_code FROM core.company WHERE id = %s",
                (company_id,),
            )
            company = cur.fetchone()
            if not company:
                raise ValueError("Company was not found for opening-balance review.")
            company_currency = str(company["currency_code"] or "").strip().upper()

            cur.execute(
                """
                SELECT p.id, p.party_code, p.party_name, p.party_type, p.is_active,
                       pf.id AS profile_id, pf.opening_balance,
                       pf.opening_balance_type, pf.default_currency_code
                FROM master.parties p
                LEFT JOIN master.party_financial_profiles pf ON pf.party_id = p.id
                WHERE p.company_id = %s
                ORDER BY p.party_type, p.party_name, p.id
                """,
                (company_id,),
            )
            parties = [dict(row) for row in cur.fetchall()]
            cur.execute(
                """
                SELECT account_code, account_name, account_type, normal_balance,
                       is_active, is_group, is_control
                FROM accounting.accounts
                WHERE company_id = %s
                  AND account_code IN ('1221', '1231', '2211', '2241')
                """,
                (company_id,),
            )
            account_rows = {str(row["account_code"]): dict(row) for row in cur.fetchall()}
            cur.execute(
                """
                SELECT account_code, account_name, account_type, account_subtype,
                       is_active, is_group, is_control
                FROM accounting.accounts
                WHERE company_id = %s
                  AND (
                    account_code ILIKE '%%OPENING%%'
                    OR account_name ILIKE '%%OPENING%%'
                    OR account_name ILIKE '%%CLEARING%%'
                    OR account_name ILIKE '%%SUSPENSE%%'
                    OR COALESCE(account_subtype, '') ILIKE '%%OPENING%%'
                    OR COALESCE(account_subtype, '') ILIKE '%%CLEARING%%'
                  )
                ORDER BY account_code
                """,
                (company_id,),
            )
            offset_candidates = [dict(row) for row in cur.fetchall()]

    reviewed = [
        _review_party_opening_row(party, account_rows, company_currency)
        for party in parties
    ]
    candidate_lines = []
    debit_total = Decimal("0")
    credit_total = Decimal("0")
    totals_by_currency = {}
    for row in reviewed:
        if not row["ready_for_review"]:
            continue
        amount = row["opening_balance"]
        if row["direction"] == "DEBIT":
            debit_total += amount
        else:
            credit_total += amount
        currency_totals = totals_by_currency.setdefault(
            row["currency"], {"debit": Decimal("0"), "credit": Decimal("0")}
        )
        currency_totals["debit" if row["direction"] == "DEBIT" else "credit"] += amount
        candidate_lines.append({
            "party_id": row["party_id"],
            "party_code": row["party_code"],
            "party_name": row["party_name"],
            "account_code": row["account_code"],
            "account_name": row["account_name"],
            "currency": row["currency"],
            "direction": row["direction"],
            "amount": amount,
        })

    return {
        "rows": reviewed,
        "party_count": len(reviewed),
        "mapping_ready_count": len(candidate_lines),
        "blocked_count": sum(1 for row in reviewed if not row["ready_for_review"]),
        "inactive_count": sum(1 for row in reviewed if row["status"] == "INACTIVE PARTY"),
        "unsupported_party_type_count": sum(
            1 for row in reviewed if row["status"] == "UNSUPPORTED PARTY TYPE"
        ),
        "currency_mismatch_count": sum(
            1 for row in reviewed
            if row["status"] == "CURRENCY MISMATCH — CONVERSION REQUIRED"
        ),
        "company_currency": company_currency,
        "candidate_lines": candidate_lines,
        "candidate_debit_total": debit_total,
        "candidate_credit_total": credit_total,
        "totals_by_currency": totals_by_currency,
        # An empty candidate set is not a successful reconciliation.
        "candidate_movement_balanced": _candidate_movement_is_balanced(
            candidate_lines, debit_total, credit_total
        ),
        "opening_balances_posted": False,
        "offset_account_configured": False,
        "offset_account_candidates": offset_candidates,
        "reconciliation_ready_for_posting": False,
        "reconciliation_notice": (
            "Party lines are a preview only. A dedicated, approved opening-balance "
            "offset account and approved opening date are still required. No journal "
            "has been created, balanced, approved or posted."
        ),
    }


INVENTORY_CATEGORY_ACCOUNT_CANDIDATES = {
    "YARN": "1241",
    "DYE_CHEM": "1242",
    "CONE": "1243",
    "TUBE": "1243",
    "NALKI": "1245",
    "PACK_MAT": "1246",
    "FG": "1247",
    "FUEL": "1248",
    "GENERAL": "1249",
}


def _inventory_gl_mapping_readiness(transaction_types, categories, account_rows, all_accounts=None, purchase_counts=None):
    """Validate candidate inventory account links; never treat candidates as approved policy."""
    category_rows = []
    for category in categories:
        code = str(category.get("code") or "").strip().upper()
        candidate_code = INVENTORY_CATEGORY_ACCOUNT_CANDIDATES.get(code)
        account = account_rows.get(candidate_code) if candidate_code else None
        if not category.get("is_active", True):
            status = "INACTIVE ITEM CATEGORY"
        elif not candidate_code:
            status = "ACCOUNT MAPPING UNRESOLVED"
        elif not account:
            status = "CANDIDATE ACCOUNT MISSING"
        elif (
            not account.get("is_active")
            or account.get("is_group")
            or not account.get("is_control")
            or str(account.get("account_type") or "").upper() != "ASSET"
            or str(account.get("normal_balance") or "").upper() != "DEBIT"
        ):
            status = "CANDIDATE ACCOUNT NEEDS REVIEW"
        else:
            status = "CANDIDATE ACCOUNT VALID ? POLICY NOT APPROVED"
        category_rows.append({
            "code": code,
            "name": category.get("name") or code,
            "item_count": int(category.get("item_count") or 0),
            "is_active": bool(category.get("is_active", True)),
            "candidate_account_code": candidate_code or "",
            "candidate_account_name": account.get("account_name", "") if account else "",
            "status": status,
        })

    transaction_rows = []
    policy_blockers = {
        "PURCHASE_RECEIPT": "GRNI, supplier payable timing, input tax and landed-cost policy unresolved",
        "PURCHASE_RETURN": "Supplier credit-note and payable reversal policy unresolved",
        "PRODUCTION_CONSUMPTION": "WIP/process-stage absorption and PARTY material treatment unresolved",
        "PRODUCTION_OUTPUT": "Output cost roll-up and WIP release policy unresolved",
        "STOCK_TRANSFER": "Transfer valuation and stage/location accounting semantics need confirmation",
        "STOCK_ADJUSTMENT": "Adjustment gain/loss counterpart and approval thresholds unresolved",
        "STOCK_OPENING": "Dedicated opening-stock clearing account and approved opening date absent",
        "STOCK_RECLASSIFICATION": "Ownership-change and category/stage reclassification policy unresolved",
        "SALES_DISPATCH": "Dispatch is not an invoice; OWN COGS and PARTY settlement rules need approval",
    }
    for tx in transaction_types:
        code = str(tx.get("code") or "").strip().upper()
        active = bool(tx.get("is_active"))
        transaction_rows.append({
            "code": code,
            "name": tx.get("name") or code,
            "is_active": active,
            "status": "POLICY REVIEW REQUIRED" if active else "INACTIVE TRANSACTION TYPE",
            "blocker": policy_blockers.get(code, "No approved transaction-specific accounting policy recorded"),
        })

    valid_candidates = sum(
        1 for row in category_rows
        if row["status"] == "CANDIDATE ACCOUNT VALID ? POLICY NOT APPROVED"
    )
    unresolved_categories = sum(
        1 for row in category_rows
        if row["status"] != "CANDIDATE ACCOUNT VALID ? POLICY NOT APPROVED"
    )
    all_accounts = list(all_accounts or account_rows.values())
    purchase_counts = purchase_counts or {}
    by_code = {str(row.get("account_code") or ""): row for row in all_accounts}

    def valid_account(code, expected_type, expected_balance):
        account = by_code.get(code)
        if not account:
            return False, "ACCOUNT MISSING"
        if (
            not account.get("is_active")
            or account.get("is_group")
            or not account.get("is_control")
            or str(account.get("account_type") or "").upper() != expected_type
            or str(account.get("normal_balance") or "").upper() != expected_balance
        ):
            return False, "ACCOUNT NEEDS REVIEW"
        return True, "ACCOUNT STRUCTURE VALID"

    supplier_ok, supplier_status = valid_account("2211", "LIABILITY", "CREDIT")
    sales_tax = by_code.get("2221")
    input_tax_candidates = [
        row for row in all_accounts
        if any(term in str(row.get("account_name") or "").lower()
               for term in ("input tax", "input gst", "gst receivable", "sales tax receivable"))
    ]
    input_tax_valid = any(
        row.get("is_active") and not row.get("is_group")
        and str(row.get("account_type") or "").upper() == "ASSET"
        and str(row.get("normal_balance") or "").upper() == "DEBIT"
        for row in input_tax_candidates
    )
    grni_candidates = [
        row for row in all_accounts
        if "goods received not invoiced" in str(row.get("account_name") or "").lower()
        or str(row.get("account_code") or "").upper() == "GRNI"
        or "grni" in str(row.get("account_name") or "").lower()
    ]
    grni_valid = any(
        row.get("is_active") and not row.get("is_group") and row.get("is_control")
        and str(row.get("account_type") or "").upper() == "LIABILITY"
        and str(row.get("normal_balance") or "").upper() == "CREDIT"
        for row in grni_candidates
    )
    purchase_account_checks = [
        {"label": "Supplier Payables", "account_code": "2211",
         "account_name": (by_code.get("2211") or {}).get("account_name", ""),
         "status": supplier_status if supplier_ok else "BLOCKED ? " + supplier_status,
         "detail": "Valid supplier control liability candidate; posting timing still needs approval."},
        {"label": "Input GST / Sales Tax Receivable",
         "account_code": ", ".join(str(row.get("account_code")) for row in input_tax_candidates),
         "account_name": ", ".join(str(row.get("account_name")) for row in input_tax_candidates),
         "status": "ASSET ACCOUNT FOUND ? POLICY REVIEW" if input_tax_valid else "BLOCKED ? INPUT TAX ASSET ACCOUNT MISSING",
         "detail": "GRN currently excludes tax from inventory cost as recoverable input GST. Recoverability and tax coding must be confirmed."},
        {"label": "Goods Received Not Invoiced (GRNI)",
         "account_code": ", ".join(str(row.get("account_code")) for row in grni_candidates),
         "account_name": ", ".join(str(row.get("account_name")) for row in grni_candidates),
         "status": "LIABILITY ACCOUNT FOUND ? POLICY REVIEW" if grni_valid else "BLOCKED ? GRNI ACCOUNT MISSING",
         "detail": "Required only if receipt and supplier invoice recognition are separated; owner/accountant must approve the chosen accrual workflow."},
        {"label": "Sales Tax Payable", "account_code": "2221",
         "account_name": (sales_tax or {}).get("account_name", ""),
         "status": "LIABILITY ? NOT INPUT TAX" if sales_tax else "ACCOUNT NOT FOUND",
         "detail": "Do not substitute this output-tax liability account for recoverable input GST."},
    ]
    receipt_status_counts = purchase_counts.get("receipt_status_counts", [])
    return_status_counts = purchase_counts.get("return_status_counts", [])
    po_currency_counts = purchase_counts.get("po_currency_counts", [])
    purchase_blockers = []
    if not supplier_ok:
        purchase_blockers.append("Supplier Payables control account 2211 is not structurally valid.")
    if not input_tax_valid:
        purchase_blockers.append("No valid Input GST / Sales Tax Receivable asset account was found.")
    if not grni_valid:
        purchase_blockers.append("No dedicated GRNI liability account was found.")
    purchase_blockers.append("GRN approval excludes GST from inventory cost as recoverable input GST; tax recoverability, invoice evidence and tax coding are not yet established.")
    purchase_blockers.append("Supplier invoice is not a separate register: only optional invoice number/date fields exist on the GRN header; there is no independent invoice approval or GRN-to-invoice matching lifecycle.")
    purchase_blockers.append("GST choice is stored in a free-text remarks marker, not a structured tax-evidence field; selecting With GST does not require supplier invoice number/date.")
    purchase_blockers.append("Purchase Receipt header has no currency-code or exchange-rate field; verify foreign-currency PO handling before journal integration.")
    purchase_blockers.append("Purchase Return supplier credit is calculated from original receipt price/tax, while stock-out valuation uses current moving average cost; any variance-account policy is not defined.")
    purchase_blockers.append("No posted GRN or Purchase Return exists in the current company dataset, so posting behavior has no live completed document to reconcile.")
    return {
        "categories": category_rows,
        "transactions": transaction_rows,
        "purchase_account_checks": purchase_account_checks,
        "purchase_blockers": purchase_blockers,
        "receipt_status_counts": receipt_status_counts,
        "return_status_counts": return_status_counts,
        "po_currency_counts": po_currency_counts,
        "posted_grn_count": int(purchase_counts.get("posted_grn_count", 0)),
        "posted_return_count": int(purchase_counts.get("posted_return_count", 0)),
        "purchase_journal_ready": False,
        "category_count": len(category_rows),
        "valid_candidate_count": valid_candidates,
        "unresolved_category_count": unresolved_categories,
        "transaction_type_count": len(transaction_rows),
        "transaction_policy_review_count": sum(1 for row in transaction_rows if row["is_active"]),
        "automatic_posting_approved": False,
        "status": "READ-ONLY CANDIDATE REVIEW ? AUTO-POSTING BLOCKED",
        "notice": (
            "Candidate account links are checked against the current chart of accounts only. "
            "They are not approved accounting policy. Transaction journals remain disabled "
            "until the debit/credit rules and controls are separately approved."
        ),
    }


def get_inventory_gl_mapping_readiness(company_id):
    """Read-only validation of inventory category candidates and transaction policy blockers."""
    company_id = int(company_id)
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SET TRANSACTION READ ONLY")
            cur.execute(
                """
                SELECT code, name, is_active
                FROM inventory.transaction_types
                ORDER BY id
                """
            )
            transaction_types = [dict(row) for row in cur.fetchall()]
            cur.execute(
                """
                SELECT c.code, c.name, c.is_active, COUNT(i.id) AS item_count
                FROM master.item_categories c
                LEFT JOIN master.items i
                  ON i.item_category_id = c.id
                 AND i.company_id = c.company_id
                WHERE c.company_id = %s
                GROUP BY c.id, c.code, c.name, c.is_active
                ORDER BY c.code
                """,
                (company_id,),
            )
            categories = [dict(row) for row in cur.fetchall()]
            cur.execute(
                """
                SELECT account_code, account_name, account_type, normal_balance,
                       is_active, is_group, is_control
                FROM accounting.accounts
                WHERE company_id = %s
                ORDER BY account_code
                """,
                (company_id,),
            )
            all_accounts = [dict(row) for row in cur.fetchall()]
            account_rows = {
                str(row["account_code"]): row for row in all_accounts
                if str(row["account_code"]) in set(INVENTORY_CATEGORY_ACCOUNT_CANDIDATES.values())
            }
            purchase_counts = {}
            for key, table in (("receipt_status_counts", "purchase_receipts"),
                               ("return_status_counts", "purchase_returns")):
                cur.execute(
                    f"SELECT status, COUNT(*) AS count FROM purchasing.{table} "
                    "WHERE company_id = %s GROUP BY status ORDER BY status",
                    (company_id,),
                )
                purchase_counts[key] = [dict(row) for row in cur.fetchall()]
            cur.execute(
                """
                SELECT COUNT(*) AS count
                FROM purchasing.purchase_receipts
                WHERE company_id = %s AND status = 'POSTED'
                """,
                (company_id,),
            )
            purchase_counts["posted_grn_count"] = int(cur.fetchone()["count"])
            cur.execute(
                """
                SELECT COUNT(*) AS count
                FROM purchasing.purchase_returns
                WHERE company_id = %s AND status = 'POSTED'
                """,
                (company_id,),
            )
            purchase_counts["posted_return_count"] = int(cur.fetchone()["count"])
            cur.execute(
                """
                SELECT currency_code, COUNT(*) AS count
                FROM purchasing.purchase_orders
                WHERE company_id = %s
                GROUP BY currency_code
                ORDER BY currency_code
                """,
                (company_id,),
            )
            purchase_counts["po_currency_counts"] = [dict(row) for row in cur.fetchall()]
    return _inventory_gl_mapping_readiness(
        transaction_types, categories, account_rows, all_accounts, purchase_counts
    )


def get_inventory_journal_review(company_id, limit=30):
    """Read-only review of recent posted stock-document valuation bases."""
    from .inventory_journal import get_stock_document_journal_basis

    company_id = int(company_id)
    limit = max(1, min(int(limit), 100))
    reviews = []
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SET TRANSACTION READ ONLY")
            cur.execute(
                """
                SELECT id, document_no, document_type, document_date, status
                FROM inventory.stock_documents
                WHERE company_id = %s AND status = 'POSTED'
                ORDER BY document_date DESC, id DESC
                LIMIT %s
                """,
                (company_id, limit),
            )
            documents = [dict(row) for row in cur.fetchall()]

        for document in documents:
            try:
                basis = get_stock_document_journal_basis(
                    conn,
                    company_id=company_id,
                    stock_document_id=int(document["id"]),
                )
                reviews.append(basis)
            except (ValueError, TypeError) as exc:
                reviews.append({
                    "document_id": int(document["id"]),
                    "document_no": document["document_no"],
                    "document_type": document["document_type"],
                    "document_date": document["document_date"],
                    "status": document["status"],
                    "categories": [],
                    "total_inward_value": Decimal("0"),
                    "total_outward_value": Decimal("0"),
                    "net_stock_value_change": Decimal("0"),
                    "gross_movement_value": Decimal("0"),
                    "line_count": 0,
                    "ready_for_mapping_review": False,
                    "automatic_journal_approved": False,
                    "blockers": [str(exc)],
                })

    return {
        "documents": reviews,
        "document_count": len(reviews),
        "ready_count": sum(1 for item in reviews if item["ready_for_mapping_review"]),
        "blocked_count": sum(1 for item in reviews if not item["ready_for_mapping_review"]),
        "automatic_journal_approved": False,
        "read_only": True,
    }

"""Transactional General Ledger journal workflow.

The journal workflow is exposed through protected routes in app.main.
Fiscal-year/period readiness, document sequencing, account references and
balanced-line validation remain fail-closed prerequisites for DRAFT creation,
approval and posting. Route callers enforce permissions and CSRF.
"""
from datetime import date
from decimal import Decimal

from .journal_rules import (
    validate_account_references,
    validate_entry_period,
    validate_journal_lines,
)
from ..audit_service import write_audit_log


def _assert_user_company(company_id, user):
    """Fail closed if the authenticated actor is outside the target company."""
    try:
        actor_company_id = int(user["company_id"])
    except (KeyError, TypeError, ValueError):
        raise ValueError("Authenticated user company context is missing.")
    if actor_company_id != int(company_id):
        raise ValueError("User is not authorized for this company's journal.")


def _entry_period(cur, company_id, entry_date):
    cur.execute(
        """
        SELECT fy.id AS fiscal_year_id, fy.start_date AS fiscal_year_start,
               fy.end_date AS fiscal_year_end, fy.is_closed AS fiscal_year_is_closed,
               p.id AS period_id, p.start_date, p.end_date, p.is_closed
        FROM core.fiscal_years fy
        JOIN core.accounting_periods p ON p.fiscal_year_id = fy.id
        WHERE fy.company_id = %s
          AND %s BETWEEN fy.start_date AND fy.end_date
          AND %s BETWEEN p.start_date AND p.end_date
        ORDER BY p.start_date
        FOR SHARE OF fy, p
        """,
        (company_id, entry_date, entry_date),
    )
    rows = cur.fetchall()
    if len(rows) != 1:
        raise ValueError("Journal date must belong to exactly one open accounting period.")
    period = rows[0]
    validate_entry_period(
        entry_date,
        {
            "start_date": period["start_date"],
            "end_date": period["end_date"],
            "is_closed": period["is_closed"],
            "fiscal_year_is_closed": period["fiscal_year_is_closed"],
        },
    )
    if entry_date < period["fiscal_year_start"] or entry_date > period["fiscal_year_end"]:
        raise ValueError("Journal date is outside its fiscal year.")
    return period


def _validate_references(cur, company_id, normalized_lines):
    account_ids = sorted({line["account_id"] for line in normalized_lines["lines"]})
    party_ids = sorted({
        line["party_id"] for line in normalized_lines["lines"]
        if line["party_id"] is not None
    })
    cur.execute(
        "SELECT * FROM accounting.accounts WHERE company_id = %s AND id = ANY(%s) FOR SHARE",
        (company_id, account_ids),
    )
    account_rows = cur.fetchall()
    accounts = {}
    for row in account_rows:
        active = row.get("is_active", row.get("active"))
        group = row.get("is_group", row.get("is_parent"))
        control = row.get("is_control", row.get("is_control_account"))
        account_code = str(row.get("account_code") or "").strip()

        # Do not guess missing account-master flags or codes. A missing
        # field could otherwise make a group/control account look postable.
        if active is None:
            raise ValueError("Account master active-status field is not recognized; journal save is blocked.")
        if group is None:
            raise ValueError("Account master group-account field is not recognized; journal save is blocked.")
        if control is None:
            raise ValueError("Account master control-account field is not recognized; journal save is blocked.")
        if not account_code:
            raise ValueError("Account master code is missing; journal save is blocked.")

        accounts[int(row["id"])] = {
            **dict(row),
            "account_code": account_code,
            "is_active": bool(active),
            "is_group": bool(group),
            "is_control": bool(control),
        }

    parties = {}
    if party_ids:
        cur.execute(
            "SELECT id, company_id, party_type, is_active FROM master.parties "
            "WHERE company_id = %s AND id = ANY(%s) FOR SHARE",
            (company_id, party_ids),
        )
        parties = {int(row["id"]): dict(row) for row in cur.fetchall()}

    # Account IDs are surrogate keys; use the stable account_code to assign
    # the supplier subledger rule instead of confusing code 2211 with row ID 2211.
    # Party subledger rules are tied to verified live COA account codes.
    # Supplier and customer control accounts must carry matching party types.
    party_control_codes = {
        "1221": {"CUSTOMER"},       # Customer Receivables
        "1231": {"SUPPLIER"},       # Supplier Advances
        "2211": {"SUPPLIER"},       # Supplier Payables
        "2241": {"CUSTOMER"},       # Customer Advances
    }
    control_party_types = {
        account_id: party_control_codes[str(account["account_code"]).strip()]
        for account_id, account in accounts.items()
        if str(account["account_code"]).strip() in party_control_codes
    }
    # A GL control account is not automatically a party subledger.
    # Only the explicitly verified customer/supplier control codes above
    # require a party_id. Bank and inventory control buckets can be posted
    # without a party until their own subledger workflows are implemented.
    validate_account_references(
        normalized_lines["lines"], accounts, parties, company_id,
        control_party_types=control_party_types,
    )


def _lock_source_journal_identity(cur, company_id, source_module, source_type, source_id):
    """Serialize source-journal creation and reject a second journal for one source."""
    if source_id is None:
        return
    module = str(source_module or "").strip().upper()
    source = str(source_type or "").strip().upper()
    if not module or not source:
        raise ValueError("Source module and source type are required for source-linked journals.")
    source_id = int(source_id)
    lock_key = f"ARE:GL-SOURCE:{int(company_id)}:{module}:{source}:{source_id}"
    cur.execute(
        "SELECT pg_advisory_xact_lock(hashtext(%s)::bigint)",
        (lock_key,),
    )
    cur.execute(
        """
        SELECT id, journal_no, status
        FROM accounting.journal_entries
        WHERE company_id = %s
          AND source_module = %s
          AND source_type = %s
          AND source_id = %s
        ORDER BY id
        FOR UPDATE
        """,
        (int(company_id), module, source, source_id),
    )
    existing = cur.fetchone()
    if existing:
        raise ValueError(
            f"This source document already has journal {existing['journal_no']} "
            f"({existing['status']}); duplicate source journals are blocked."
        )


def create_journal_draft(
    conn, *, company_id, user, request, entry_date, description, lines,
    source_module=None, source_type=None, source_id=None, reversal_of_id=None,
):
    """Create a DRAFT header and its balanced lines inside caller transaction."""
    company_id = int(company_id)
    _assert_user_company(company_id, user)
    entry_date = date.fromisoformat(entry_date) if isinstance(entry_date, str) else entry_date
    if not isinstance(entry_date, date):
        raise ValueError("Journal date is required.")
    if bool(source_id) != bool(source_module and source_type):
        raise ValueError("Source module, source type and source ID must be supplied together.")
    if source_id is not None and (isinstance(source_id, bool) or int(source_id) <= 0):
        raise ValueError("Source document ID must be a positive integer.")
    if source_id is not None:
        source_module = str(source_module).strip().upper()
        source_type = str(source_type).strip().upper()
        source_id = int(source_id)
    validated = validate_journal_lines(lines)

    with conn.cursor() as cur:
        period = _entry_period(cur, company_id, entry_date)
        _validate_references(cur, company_id, validated)
        _lock_source_journal_identity(
            cur, company_id, source_module, source_type, source_id
        )
        # Allocate the sequence in the caller's transaction. If any later
        # insert/audit fails, PostgreSQL rolls the increment back as well.
        cur.execute(
            """
            UPDATE core.document_sequences
            SET next_number = next_number + 1
            WHERE company_id = %s
              AND document_type = 'GENERAL_JOURNAL'
              AND is_active = TRUE
            RETURNING prefix, next_number - 1 AS allocated_number,
                      number_padding
            """,
            (company_id,),
        )
        sequence = cur.fetchone()
        if not sequence:
            raise ValueError(
                "General Journal sequence is not installed. "
                "Apply the approved GL migration before creating journals."
            )
        journal_no = (
            f"{sequence['prefix']}"
            f"{int(sequence['allocated_number']):0{int(sequence['number_padding'])}d}"
        )
        cur.execute(
            """
            INSERT INTO accounting.journal_entries (
                company_id, fiscal_year_id, period_id, journal_no, entry_date,
                source_module, source_type, source_id, reversal_of_id,
                status, description, debit_total, credit_total, created_by
            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,'DRAFT',%s,%s,%s,%s)
            RETURNING id
            """,
            (
                company_id, period["fiscal_year_id"], period["period_id"],
                journal_no, entry_date, source_module, source_type, source_id,
                int(reversal_of_id) if reversal_of_id is not None else None,
                str(description or "").strip()[:2000] or None,
                validated["debit_total"], validated["credit_total"], int(user["id"]),
            ),
        )
        journal_id = int(cur.fetchone()["id"])
        for line_no, line in enumerate(validated["lines"], start=1):
            cur.execute(
                """
                INSERT INTO accounting.journal_lines (
                    journal_id, company_id, line_no, account_id, party_id,
                    debit, credit, description
                ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
                """,
                (
                    journal_id, company_id, line_no, line["account_id"],
                    line["party_id"], line["debit"], line["credit"],
                    line["description"] or None,
                ),
            )

    write_audit_log(
        conn, user=user, request=request, action="CREATE",
        table_name="accounting.journal_entries", record_id=journal_id,
        document_no=journal_no,
        new_values={
            "status": "DRAFT", "entry_date": entry_date,
            "debit_total": validated["debit_total"],
            "credit_total": validated["credit_total"],
            "line_count": len(validated["lines"]),
            "source_module": source_module, "source_type": source_type,
            "source_id": source_id,
        },
        reason="General Journal DRAFT creation", module="ACCOUNTING",
    )
    return {"id": journal_id, "journal_no": journal_no, "status": "DRAFT"}


def approve_journal(conn, *, company_id, journal_id, user, request):
    """DRAFT -> APPROVED. Caller owns the transaction and permission check."""
    company_id = int(company_id)
    _assert_user_company(company_id, user)
    with conn.cursor() as cur:
        cur.execute(
            "SELECT * FROM accounting.journal_entries "
            "WHERE id=%s AND company_id=%s FOR UPDATE",
            (int(journal_id), int(company_id)),
        )
        entry = cur.fetchone()
        if not entry:
            raise ValueError("Journal was not found for this company.")
        if entry["status"] != "DRAFT":
            raise ValueError("Only a DRAFT journal can be approved.")
        period = _entry_period(cur, int(company_id), entry["entry_date"])
        cur.execute(
            """
            SELECT account_id, party_id, debit, credit, description
            FROM accounting.journal_lines
            WHERE journal_id=%s AND company_id=%s
            ORDER BY line_no FOR UPDATE
            """,
            (int(journal_id), int(company_id)),
        )
        lines = [dict(row) for row in cur.fetchall()]
        validated = validate_journal_lines(lines)
        if validated["debit_total"] != Decimal(str(entry["debit_total"])) or validated["credit_total"] != Decimal(str(entry["credit_total"])):
            raise ValueError("Journal header totals do not match its lines.")
        _validate_references(cur, int(company_id), validated)
        cur.execute(
            """
            UPDATE accounting.journal_entries
            SET status='APPROVED', approved_by=%s, approved_at=CURRENT_TIMESTAMP
            WHERE id=%s AND company_id=%s AND status='DRAFT'
            """,
            (int(user["id"]), int(journal_id), int(company_id)),
        )
    write_audit_log(
        conn, user=user, request=request, action="APPROVE",
        table_name="accounting.journal_entries", record_id=journal_id,
        document_no=entry["journal_no"],
        old_values={"status": "DRAFT"}, new_values={"status": "APPROVED"},
        reason="General Journal approval", module="ACCOUNTING",
    )
    return {"id": int(journal_id), "journal_no": entry["journal_no"], "status": "APPROVED"}


def post_journal(conn, *, company_id, journal_id, user, request):
    """APPROVED -> POSTED. Reversal journals mark the original REVERSED atomically."""
    company_id = int(company_id)
    _assert_user_company(company_id, user)
    with conn.cursor() as cur:
        cur.execute(
            "SELECT * FROM accounting.journal_entries "
            "WHERE id=%s AND company_id=%s FOR UPDATE",
            (int(journal_id), int(company_id)),
        )
        entry = cur.fetchone()
        if not entry:
            raise ValueError("Journal was not found for this company.")
        if entry["status"] != "APPROVED":
            raise ValueError("Only an APPROVED journal can be posted.")
        _entry_period(cur, int(company_id), entry["entry_date"])
        cur.execute(
            """
            SELECT account_id, party_id, debit, credit, description
            FROM accounting.journal_lines
            WHERE journal_id=%s AND company_id=%s
            ORDER BY line_no FOR UPDATE
            """,
            (int(journal_id), int(company_id)),
        )
        validated = validate_journal_lines([dict(row) for row in cur.fetchall()])
        if validated["debit_total"] != Decimal(str(entry["debit_total"])) or validated["credit_total"] != Decimal(str(entry["credit_total"])):
            raise ValueError("Journal header totals do not match its lines.")
        _validate_references(cur, int(company_id), validated)
        cur.execute(
            """
            UPDATE accounting.journal_entries
            SET status='POSTED', posted_by=%s, posted_at=CURRENT_TIMESTAMP
            WHERE id=%s AND company_id=%s AND status='APPROVED'
            """,
            (int(user["id"]), int(journal_id), int(company_id)),
        )
        reversed_original = None
        if entry["reversal_of_id"] is not None:
            cur.execute(
                """
                UPDATE accounting.journal_entries
                SET status='REVERSED'
                WHERE id=%s AND company_id=%s AND status='POSTED'
                RETURNING id, journal_no
                """,
                (entry["reversal_of_id"], int(company_id)),
            )
            reversed_original = cur.fetchone()
            if not reversed_original:
                raise ValueError("Original posted journal could not be marked REVERSED.")

    write_audit_log(
        conn, user=user, request=request, action="POST",
        table_name="accounting.journal_entries", record_id=journal_id,
        document_no=entry["journal_no"],
        old_values={"status": "APPROVED"}, new_values={"status": "POSTED"},
        reason="General Journal posting", module="ACCOUNTING",
    )
    if reversed_original:
        write_audit_log(
            conn, user=user, request=request, action="REVERSE",
            table_name="accounting.journal_entries",
            record_id=reversed_original["id"],
            document_no=reversed_original["journal_no"],
            old_values={"status": "POSTED"},
            new_values={"status": "REVERSED", "reversal_journal_no": entry["journal_no"]},
            reason="Original journal reversed by posted reversal entry",
            module="ACCOUNTING",
        )
    return {"id": int(journal_id), "journal_no": entry["journal_no"], "status": "POSTED"}


def create_journal_reversal(conn, *, company_id, journal_id, user, request, entry_date, reason):
    """Create a separate DRAFT reversal; original changes only when reversal posts."""
    company_id = int(company_id)
    _assert_user_company(company_id, user)
    journal_id = int(journal_id)
    reason = str(reason or "").strip()
    if not reason:
        raise ValueError("A reason is required to create a journal reversal.")
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, journal_no, entry_date, status
            FROM accounting.journal_entries
            WHERE id=%s AND company_id=%s
            FOR UPDATE
            """,
            (journal_id, company_id),
        )
        original = cur.fetchone()
        if not original or original["status"] != "POSTED":
            raise ValueError("Only a POSTED journal can be reversed.")
        cur.execute(
            "SELECT 1 FROM accounting.journal_entries "
            "WHERE reversal_of_id=%s AND company_id=%s",
            (journal_id, company_id),
        )
        if cur.fetchone():
            raise ValueError("A reversal already exists for this journal.")
        cur.execute(
            """
            SELECT account_id, party_id, debit, credit, description
            FROM accounting.journal_lines
            WHERE journal_id=%s AND company_id=%s
            ORDER BY line_no
            FOR SHARE
            """,
            (journal_id, company_id),
        )
        original_lines = cur.fetchall()
        if not original_lines:
            raise ValueError("The posted journal has no lines and cannot be reversed.")
        reversal_lines = [
            {
                "account_id": row["account_id"],
                "party_id": row["party_id"],
                "debit": row["credit"],
                "credit": row["debit"],
                "description": row["description"],
            }
            for row in original_lines
        ]

    return create_journal_draft(
        conn,
        company_id=company_id,
        user=user,
        request=request,
        entry_date=entry_date,
        description=f"Reversal of {original['journal_no']}: {str(reason or '').strip()}"[:2000],
        lines=reversal_lines,
        reversal_of_id=journal_id,
    )
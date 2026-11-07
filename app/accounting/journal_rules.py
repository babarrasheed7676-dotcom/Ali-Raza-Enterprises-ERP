from datetime import date
from decimal import Decimal, InvalidOperation

MONEY_SCALE = Decimal("0.000001")


def _amount(value, field):
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError(f"{field} must be a valid decimal amount")

    if not amount.is_finite():
        raise ValueError(f"{field} must be finite")
    if amount < 0:
        raise ValueError(f"{field} cannot be negative")
    try:
        normalized = amount.quantize(MONEY_SCALE)
    except InvalidOperation:
        raise ValueError(f"{field} exceeds the supported numeric range")
    if normalized != amount:
        raise ValueError(f"{field} supports a maximum of 6 decimal places")
    return amount


def validate_journal_lines(lines):
    """Validate balanced, positive, single-sided journal lines."""
    if not isinstance(lines, (list, tuple)) or len(lines) < 2:
        raise ValueError("A journal requires at least two lines")

    normalized = []
    debit_total = Decimal("0")
    credit_total = Decimal("0")

    for index, line in enumerate(lines, start=1):
        if not hasattr(line, "get"):
            raise ValueError(f"Journal line {index} must be a mapping")

        account_id = line.get("account_id")
        if isinstance(account_id, bool) or not str(account_id or "").isdigit():
            raise ValueError(f"Journal line {index} requires a valid account")

        debit = _amount(line.get("debit", 0), f"Journal line {index} debit")
        credit = _amount(line.get("credit", 0), f"Journal line {index} credit")

        if (debit > 0) == (credit > 0):
            raise ValueError(
                f"Journal line {index} must have exactly one positive side"
            )

        party_id = line.get("party_id")
        if party_id is not None:
            if isinstance(party_id, bool) or not str(party_id).isdigit():
                raise ValueError(f"Journal line {index} has an invalid party")

        debit_total += debit
        credit_total += credit
        normalized.append({
            "account_id": int(account_id),
            "party_id": int(party_id) if party_id is not None else None,
            "debit": debit,
            "credit": credit,
            "description": str(line.get("description") or "").strip()[:500],
        })

    if debit_total <= 0 or credit_total <= 0:
        raise ValueError("Journal debit and credit totals must both be positive")

    if debit_total != credit_total:
        raise ValueError("Journal is not balanced: debit must equal credit")

    return {
        "lines": normalized,
        "debit_total": debit_total,
        "credit_total": credit_total,
    }


def validate_period_ranges(periods, fiscal_year_start, fiscal_year_end):
    """Validate fiscal-year boundaries and reject overlapping periods."""
    if isinstance(fiscal_year_start, str):
        fiscal_year_start = date.fromisoformat(fiscal_year_start)
    if isinstance(fiscal_year_end, str):
        fiscal_year_end = date.fromisoformat(fiscal_year_end)

    if not isinstance(fiscal_year_start, date) or not isinstance(fiscal_year_end, date):
        raise ValueError("Fiscal year dates are invalid")
    if fiscal_year_end < fiscal_year_start:
        raise ValueError("Fiscal year end date precedes start date")

    normalized = []
    for period in periods:
        if not hasattr(period, "get"):
            raise ValueError("Each accounting period must be a mapping")
        start = period.get("start_date")
        end = period.get("end_date")
        if isinstance(start, str):
            start = date.fromisoformat(start)
        if isinstance(end, str):
            end = date.fromisoformat(end)
        if not isinstance(start, date) or not isinstance(end, date):
            raise ValueError("Accounting period dates are invalid")
        if end < start:
            raise ValueError("Accounting period end date precedes start date")
        if start < fiscal_year_start or end > fiscal_year_end:
            raise ValueError("Accounting period is outside its fiscal year")
        normalized.append((start, end))

    normalized.sort(key=lambda item: (item[0], item[1]))
    for previous, current in zip(normalized, normalized[1:]):
        if current[0] <= previous[1]:
            raise ValueError("Accounting periods must not overlap")

    return True


def validate_entry_period(entry_date, period):
    """Ensure entry date falls inside an open, valid accounting period."""
    if isinstance(entry_date, str):
        try:
            entry_date = date.fromisoformat(entry_date)
        except ValueError:
            raise ValueError("Journal entry date must be ISO YYYY-MM-DD")

    if not isinstance(entry_date, date):
        raise ValueError("Journal entry date is required")

    if not hasattr(period, "get") or not period:
        raise ValueError("No accounting period covers this journal date")

    start_date = period.get("start_date")
    end_date = period.get("end_date")
    if isinstance(start_date, str):
        start_date = date.fromisoformat(start_date)
    if isinstance(end_date, str):
        end_date = date.fromisoformat(end_date)

    if not isinstance(start_date, date) or not isinstance(end_date, date):
        raise ValueError("Accounting period dates are invalid")
    if end_date < start_date:
        raise ValueError("Accounting period end date precedes start date")
    if period.get("is_closed") or period.get("fiscal_year_is_closed"):
        raise ValueError("Accounting period is closed")
    if entry_date < start_date or entry_date > end_date:
        raise ValueError("Journal date is outside the accounting period")

    return True


def validate_account_references(
    lines,
    accounts_by_id,
    parties_by_id,
    company_id,
    control_party_types=None,
):
    """Validate company ownership and control-account party requirements.

    accounts_by_id and parties_by_id are mappings keyed by integer IDs.
    control_party_types optionally maps account IDs to required party types,
    such as {"SUPPLIER"} or {"CUSTOMER"}.
    """
    if not isinstance(accounts_by_id, dict) or not isinstance(parties_by_id, dict):
        raise ValueError("Account and party lookup data must be mappings")

    expected_types = control_party_types or {}
    validated = []

    for index, line in enumerate(lines, start=1):
        account_id = int(line["account_id"])
        account = accounts_by_id.get(account_id)
        if not account:
            raise ValueError(f"Journal line {index} account does not exist")

        if int(account.get("company_id", -1)) != int(company_id):
            raise ValueError(f"Journal line {index} account belongs to another company")
        if not account.get("is_active"):
            raise ValueError(f"Journal line {index} account is inactive")
        if account.get("is_group"):
            raise ValueError(f"Journal line {index} cannot post to a group account")

        party_id = line.get("party_id")
        party = parties_by_id.get(int(party_id)) if party_id is not None else None

        if party_id is not None and not party:
            raise ValueError(f"Journal line {index} party does not exist")
        if party:
            if int(party.get("company_id", -1)) != int(company_id):
                raise ValueError(f"Journal line {index} party belongs to another company")
            if not party.get("is_active"):
                raise ValueError(f"Journal line {index} party is inactive")

        # is_control marks a GL control bucket, not necessarily a party subledger.
        # Only explicit account-code mappings require a linked party.
        required_types = expected_types.get(account_id)
        if required_types and not party:
            raise ValueError(
                f"Journal line {index} mapped subledger account requires a party"
            )

        if party and required_types:
            allowed = {str(value).upper() for value in required_types}
            actual = str(party.get("party_type") or "").upper()
            if actual not in allowed:
                raise ValueError(f"Journal line {index} party type is invalid for account")

        validated.append({
            "account_id": account_id,
            "party_id": int(party_id) if party_id is not None else None,
        })

    return validated

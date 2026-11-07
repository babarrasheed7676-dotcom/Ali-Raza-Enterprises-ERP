from collections.abc import Mapping
from decimal import Decimal, InvalidOperation
from typing import Any

from .audit_service import write_audit_log


def _non_negative_decimal(value: Any, field: str) -> Decimal:
    try:
        result = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError(f"{field} must be a valid number.")

    if not result.is_finite() or result < 0:
        raise ValueError(f"{field} must be a non-negative finite number.")

    normalized = result.normalize()
    fractional_places = max(0, -normalized.as_tuple().exponent)
    integer_places = max(0, normalized.adjusted() + 1) if result else 0

    if fractional_places > 6:
        raise ValueError(f"{field} cannot have more than 6 decimal places.")
    if integer_places > 14:
        raise ValueError(f"{field} exceeds the database NUMERIC(20,6) limit.")

    return result


def _strict_bool(value: Any, field: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{field} must be True or False.")
    return value


def create_supplier_with_audit(
    conn: Any,
    *,
    user: Mapping[str, Any],
    request: Any,
    supplier_code: str,
    supplier_name: str,
    phone: str | None = None,
    email: str | None = None,
    address: str | None = None,
    tax_number: str | None = None,
    credit_limit: Any = 0,
    payment_terms_days: int = 0,
    default_currency_code: str = "PKR",
    opening_balance: Any = 0,
    opening_balance_type: str | None = None,
    tax_withholding_applicable: bool = False,
    is_credit_allowed: bool = True,
) -> dict:
    """
    Create a supplier and financial profile with two audit entries.

    Uses the caller's connection. Does not commit or roll back.
    The caller must commit only after this function succeeds.
    """
    supplier_code = str(supplier_code).strip()
    supplier_name = str(supplier_name).strip()
    currency = str(default_currency_code).strip().upper()
    opening_type = (
        str(opening_balance_type).strip().upper()
        if opening_balance_type else None
    )

    if not supplier_code or len(supplier_code) > 50:
        raise ValueError("Supplier code is required and must not exceed 50 characters.")
    if not supplier_name or len(supplier_name) > 200:
        raise ValueError("Supplier name is required and must not exceed 200 characters.")
    if phone is not None and len(phone) > 50:
        raise ValueError("Phone cannot exceed 50 characters.")
    if email is not None and len(email) > 254:
        raise ValueError("Email cannot exceed 254 characters.")
    if tax_number is not None and len(tax_number) > 100:
        raise ValueError("Tax number cannot exceed 100 characters.")
    if address is not None and len(address) > 2000:
        raise ValueError("Address cannot exceed 2,000 characters.")
    if len(currency) != 3 or not currency.isalpha():
        raise ValueError("Currency code must contain exactly 3 letters.")

    if isinstance(payment_terms_days, bool):
        raise ValueError("Payment terms must be a whole number.")
    try:
        payment_days = int(payment_terms_days)
    except (TypeError, ValueError):
        raise ValueError("Payment terms must be a whole number.")
    if (
        str(payment_terms_days).strip() != str(payment_days)
        or payment_days < 0
        or payment_days > 3650
    ):
        raise ValueError("Payment terms must be a whole number between 0 and 3,650 days.")

    credit_amount = _non_negative_decimal(credit_limit, "Credit limit")
    opening_amount = _non_negative_decimal(opening_balance, "Opening balance")

    if opening_type not in (None, "DEBIT", "CREDIT"):
        raise ValueError("Opening balance type must be DEBIT or CREDIT.")
    if opening_amount != 0 and opening_type is None:
        raise ValueError("A non-zero opening balance requires DEBIT or CREDIT.")

    tax_flag = _strict_bool(
        tax_withholding_applicable, "Tax withholding flag"
    )
    credit_flag = _strict_bool(is_credit_allowed, "Credit allowed flag")

    company_id = int(user["company_id"])

    supplier_values = {
        "company_id": company_id,
        "party_code": supplier_code,
        "party_name": supplier_name,
        "party_type": "SUPPLIER",
        "phone": phone or None,
        "email": email or None,
        "address": address or None,
        "tax_number": tax_number or None,
        "is_active": True,
    }

    profile_values = {
        "credit_limit": credit_amount,
        "payment_terms_days": payment_days,
        "default_currency_code": currency,
        "opening_balance": opening_amount,
        "opening_balance_type": opening_type,
        "tax_withholding_applicable": tax_flag,
        "is_credit_allowed": credit_flag,
    }

    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO master.parties (
                company_id, party_code, party_name, party_type,
                phone, email, address, tax_number, is_active
            )
            VALUES (%s, %s, %s, 'SUPPLIER', %s, %s, %s, %s, TRUE)
            RETURNING id
            """,
            (
                company_id,
                supplier_code,
                supplier_name,
                phone or None,
                email or None,
                address or None,
                tax_number or None,
            ),
        )
        party_id = cur.fetchone()["id"]

        cur.execute(
            """
            INSERT INTO master.party_financial_profiles (
                party_id, credit_limit, payment_terms_days,
                default_currency_code, opening_balance,
                opening_balance_type, tax_withholding_applicable,
                is_credit_allowed
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
            """,
            (
                party_id,
                credit_amount,
                payment_days,
                currency,
                opening_amount,
                opening_type,
                tax_flag,
                credit_flag,
            ),
        )
        profile_id = cur.fetchone()["id"]

    write_audit_log(
        conn,
        user=user,
        request=request,
        action="CREATE",
        table_name="master.parties",
        record_id=party_id,
        document_no=supplier_code,
        new_values=supplier_values,
        reason="Supplier Master creation",
    )

    write_audit_log(
        conn,
        user=user,
        request=request,
        action="CREATE",
        table_name="master.party_financial_profiles",
        record_id=profile_id,
        document_no=supplier_code,
        new_values={
            "party_id": party_id,
            **profile_values,
        },
        reason="Supplier financial profile creation",
    )

    return {
        "party_id": party_id,
        "profile_id": profile_id,
        "supplier_code": supplier_code,
    }
from decimal import Decimal


def opening_balance_status(balance):
    """None means the opening balance has not been configured."""
    if balance is None:
        return {
            "configured": False,
            "balance": None,
            "status": "Not configured",
        }

    return {
        "configured": True,
        "balance": Decimal(str(balance)),
        "status": "Configured",
    }


def calculate_running_balance(
    opening_balance,
    transactions,
    opening_balance_type,
):
    """Calculate a ledger balance using the opening balance's Dr/Cr direction."""
    if opening_balance is None:
        raise ValueError("Opening balance is not configured")

    try:
        opening_amount = Decimal(str(opening_balance))
    except (TypeError, ValueError, ArithmeticError):
        raise ValueError("Opening balance must be a valid number")

    if not opening_amount.is_finite() or opening_amount < 0:
        raise ValueError("Opening balance must be a non-negative finite number")

    direction = str(opening_balance_type or "").strip().upper()
    if direction not in ("DEBIT", "CREDIT"):
        raise ValueError("Opening balance type must be DEBIT or CREDIT")

    balance = opening_amount if direction == "DEBIT" else -opening_amount
    results = []

    for transaction in transactions:
        if not hasattr(transaction, "get"):
            raise ValueError("Each ledger transaction must be a mapping")

        try:
            debit = Decimal(str(transaction.get("debit", 0)))
            credit = Decimal(str(transaction.get("credit", 0)))
        except (TypeError, ValueError, ArithmeticError):
            raise ValueError("Transaction debit and credit must be valid numbers")

        if not debit.is_finite() or not credit.is_finite():
            raise ValueError("Debit and credit must be finite numbers")

        if debit < 0 or credit < 0:
            raise ValueError("Debit and credit must not be negative")

        if debit > 0 and credit > 0:
            raise ValueError("A transaction cannot have both debit and credit")

        balance += debit - credit
        results.append({
            "debit": debit,
            "credit": credit,
            "balance": balance,
            "balance_type": "Dr" if balance > 0 else "Cr" if balance < 0 else "",
        })

    return results
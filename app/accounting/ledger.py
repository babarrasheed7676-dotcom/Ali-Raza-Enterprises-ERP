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


def calculate_running_balance(opening_balance, transactions):
    """Calculate balances for an explicitly supplied test/read-only ledger."""
    if opening_balance is None:
        raise ValueError("Opening balance is not configured")

    balance = Decimal(str(opening_balance))
    results = []

    for transaction in transactions:
        debit = Decimal(str(transaction.get("debit", 0)))
        credit = Decimal(str(transaction.get("credit", 0)))

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

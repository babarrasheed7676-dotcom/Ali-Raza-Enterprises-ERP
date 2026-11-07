import unittest
from decimal import Decimal

from app.accounting.ledger import calculate_running_balance


class TestAccountingLedger(unittest.TestCase):
    def test_debit_opening_balance_and_credit_movement(self):
        rows = calculate_running_balance(
            Decimal("1000"),
            [{"debit": "250", "credit": "0"}, {"debit": "0", "credit": "400"}],
            "DEBIT",
        )
        self.assertEqual(rows[0]["balance"], Decimal("1250"))
        self.assertEqual(rows[0]["balance_type"], "Dr")
        self.assertEqual(rows[1]["balance"], Decimal("850"))
        self.assertEqual(rows[1]["balance_type"], "Dr")

    def test_credit_opening_balance_and_debit_movement(self):
        rows = calculate_running_balance(
            Decimal("1000"),
            [{"debit": "250", "credit": "0"}],
            "CREDIT",
        )
        self.assertEqual(rows[0]["balance"], Decimal("-750"))
        self.assertEqual(rows[0]["balance_type"], "Cr")

    def test_balance_can_cross_from_credit_to_debit(self):
        rows = calculate_running_balance(
            Decimal("100"),
            [{"debit": "150", "credit": "0"}],
            "CREDIT",
        )
        self.assertEqual(rows[0]["balance"], Decimal("50"))
        self.assertEqual(rows[0]["balance_type"], "Dr")

    def test_invalid_opening_balance_directions_are_rejected(self):
        for direction in ("", None, "DR", "CR", "UNKNOWN"):
            with self.subTest(direction=direction):
                with self.assertRaisesRegex(ValueError, "(?i)opening balance type"):
                    calculate_running_balance("100", [], direction)

    def test_invalid_opening_balance_amounts_are_rejected(self):
        for amount in ("-1", "NaN", "Infinity"):
            with self.subTest(amount=amount):
                with self.assertRaises(ValueError):
                    calculate_running_balance(amount, [], "DEBIT")

    def test_unconfigured_opening_balance_is_not_assumed_zero(self):
        with self.assertRaisesRegex(ValueError, "(?i)not configured"):
            calculate_running_balance(None, [], "DEBIT")

    def test_non_finite_transaction_amount_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "finite"):
            calculate_running_balance(
                "0", [{"debit": "NaN", "credit": "0"}], "DEBIT"
            )


if __name__ == "__main__":
    unittest.main()

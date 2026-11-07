import unittest
from datetime import date
from decimal import Decimal

from app.accounting.journal_rules import (
    validate_entry_period,
    validate_journal_lines,
    validate_period_ranges,
    validate_account_references,
)


class TestJournalRules(unittest.TestCase):
    def test_balanced_journal(self):
        result = validate_journal_lines([
            {"account_id": 1, "debit": "100.00", "credit": "0"},
            {"account_id": 2, "debit": "0", "credit": "100.00"},
        ])
        self.assertEqual(result["debit_total"], Decimal("100.00"))
        self.assertEqual(result["credit_total"], Decimal("100.00"))

    def test_unbalanced_journal_rejected(self):
        with self.assertRaisesRegex(ValueError, "not balanced"):
            validate_journal_lines([
                {"account_id": 1, "debit": "100", "credit": "0"},
                {"account_id": 2, "debit": "0", "credit": "99"},
            ])

    def test_each_line_must_have_exactly_one_positive_side(self):
        for line in (
            {"account_id": 1, "debit": "0", "credit": "0"},
            {"account_id": 1, "debit": "10", "credit": "10"},
        ):
            with self.subTest(line=line):
                with self.assertRaises(ValueError):
                    validate_journal_lines([
                        line,
                        {"account_id": 2, "debit": "10", "credit": "0"},
                    ])

    def test_negative_and_non_finite_amounts_rejected(self):
        for amount in ("-1", "NaN", "Infinity"):
            with self.subTest(amount=amount):
                with self.assertRaises(ValueError):
                    validate_journal_lines([
                        {"account_id": 1, "debit": amount, "credit": "0"},
                        {"account_id": 2, "debit": "0", "credit": "1"},
                    ])

    def test_more_than_six_decimal_places_rejected(self):
        with self.assertRaisesRegex(ValueError, "6 decimal"):
            validate_journal_lines([
                {"account_id": 1, "debit": "1.0000001", "credit": "0"},
                {"account_id": 2, "debit": "0", "credit": "1.0000001"},
            ])

    def test_invalid_account_and_party_rejected(self):
        with self.assertRaisesRegex(ValueError, "valid account"):
            validate_journal_lines([
                {"account_id": "abc", "debit": "1", "credit": "0"},
                {"account_id": 2, "debit": "0", "credit": "1"},
            ])

        with self.assertRaisesRegex(ValueError, "invalid party"):
            validate_journal_lines([
                {"account_id": 1, "party_id": "x", "debit": "1", "credit": "0"},
                {"account_id": 2, "debit": "0", "credit": "1"},
            ])

    def test_period_ranges_accept_adjacent_months(self):
        self.assertTrue(validate_period_ranges(
            [
                {"start_date": "2026-01-01", "end_date": "2026-01-31"},
                {"start_date": "2026-02-01", "end_date": "2026-02-28"},
            ],
            "2026-01-01",
            "2026-12-31",
        ))

    def test_overlapping_periods_rejected(self):
        with self.assertRaisesRegex(ValueError, "must not overlap"):
            validate_period_ranges(
                [
                    {"start_date": "2026-01-01", "end_date": "2026-01-31"},
                    {"start_date": "2026-01-31", "end_date": "2026-02-28"},
                ],
                "2026-01-01",
                "2026-12-31",
            )

    def test_period_outside_fiscal_year_rejected(self):
        with self.assertRaisesRegex(ValueError, "outside its fiscal year"):
            validate_period_ranges(
                [{"start_date": "2025-12-31", "end_date": "2026-01-31"}],
                "2026-01-01",
                "2026-12-31",
            )

    def test_mapped_control_account_requires_party(self):
        with self.assertRaisesRegex(ValueError, "mapped subledger account requires a party"):
            validate_account_references(
                [{"account_id": 10, "party_id": None}],
                {10: {"company_id": 1, "is_active": True, "is_group": False, "is_control": True}},
                {},
                1,
                {10: {"SUPPLIER"}},
            )

    def test_non_subledger_control_account_does_not_require_party(self):
        result = validate_account_references(
            [{"account_id": 10, "party_id": None}],
            {10: {"company_id": 1, "is_active": True, "is_group": False, "is_control": True}},
            {},
            1,
        )
        self.assertEqual(result[0]["party_id"], None)

    def test_account_from_another_company_rejected(self):
        with self.assertRaisesRegex(ValueError, "another company"):
            validate_account_references(
                [{"account_id": 10}],
                {10: {"company_id": 2, "is_active": True, "is_group": False, "is_control": False}},
                {},
                1,
            )

    def test_group_or_inactive_account_rejected(self):
        for account in (
            {"company_id": 1, "is_active": False, "is_group": False, "is_control": False},
            {"company_id": 1, "is_active": True, "is_group": True, "is_control": False},
        ):
            with self.subTest(account=account):
                with self.assertRaises(ValueError):
                    validate_account_references([{"account_id": 10}], {10: account}, {}, 1)

    def test_party_company_and_type_are_validated(self):
        account = {10: {"company_id": 1, "is_active": True, "is_group": False, "is_control": True}}
        with self.assertRaisesRegex(ValueError, "another company"):
            validate_account_references(
                [{"account_id": 10, "party_id": 20}],
                account,
                {20: {"company_id": 2, "party_type": "SUPPLIER", "is_active": True}},
                1,
                {10: {"SUPPLIER"}},
            )

        with self.assertRaisesRegex(ValueError, "party type is invalid"):
            validate_account_references(
                [{"account_id": 10, "party_id": 20}],
                account,
                {20: {"company_id": 1, "party_type": "CUSTOMER", "is_active": True}},
                1,
                {10: {"SUPPLIER"}},
            )

    def test_oversized_decimal_is_rejected_cleanly(self):
        with self.assertRaisesRegex(ValueError, "numeric range"):
            validate_journal_lines([
                {"account_id": 1, "debit": "1e100", "credit": "0"},
                {"account_id": 2, "debit": "0", "credit": "1e100"},
            ])

    def test_open_period_accepts_date(self):
        self.assertTrue(validate_entry_period(
            date(2026, 11, 5),
            {
                "start_date": date(2026, 11, 1),
                "end_date": date(2026, 11, 30),
                "is_closed": False,
                "fiscal_year_is_closed": False,
            },
        ))

    def test_closed_period_rejected(self):
        with self.assertRaisesRegex(ValueError, "closed"):
            validate_entry_period("2026-11-05", {
                "start_date": "2026-11-01",
                "end_date": "2026-11-30",
                "is_closed": True,
            })

    def test_date_outside_period_rejected(self):
        with self.assertRaisesRegex(ValueError, "outside"):
            validate_entry_period("2026-12-01", {
                "start_date": "2026-11-01",
                "end_date": "2026-11-30",
                "is_closed": False,
            })

    def test_missing_period_rejected(self):
        with self.assertRaisesRegex(ValueError, "No accounting period"):
            validate_entry_period("2026-11-05", None)


class TestJournalServiceReferenceMapping(unittest.TestCase):
    class FakeCursor:
        def __init__(self, accounts, parties=None):
            self.accounts = accounts
            self.parties = parties or []
            self._rows = []

        def execute(self, sql, params):
            if "FROM accounting.accounts" in sql:
                self._rows = self.accounts
            elif "FROM master.parties" in sql:
                self._rows = self.parties
            else:
                raise AssertionError("Unexpected SQL in reference validation test")

        def fetchall(self):
            return self._rows

    def test_non_party_control_accounts_do_not_require_party(self):
        from app.accounting.journal_service import _validate_references

        non_party_controls = (
            ("1212", 40), ("1232", 43),
            ("1241", 27), ("1242", 28), ("1243", 29),
            ("1244", 30), ("1245", 31), ("1246", 32),
            ("1247", 33), ("1248", 34), ("1249", 35),
            ("2221", 49), ("2222", 50), ("2223", 51),
            ("2231", 52), ("2242", 54), ("3110", 58),
        )
        for code, account_id in non_party_controls:
            with self.subTest(account_code=code):
                cursor = self.FakeCursor([{
                    "id": account_id,
                    "company_id": 1,
                    "account_code": code,
                    "is_active": True,
                    "is_group": False,
                    "is_control": True,
                }])
                self.assertIsNone(_validate_references(
                    cursor, 1,
                    {"lines": [{"account_id": account_id, "party_id": None}]},
                ))

    def test_all_party_control_accounts_still_require_party(self):
        from app.accounting.journal_service import _validate_references

        party_controls = (
            ("1221", 41), ("1231", 42),
            ("2211", 48), ("2241", 53),
        )
        for code, account_id in party_controls:
            with self.subTest(account_code=code):
                cursor = self.FakeCursor([{
                    "id": account_id,
                    "company_id": 1,
                    "account_code": code,
                    "is_active": True,
                    "is_group": False,
                    "is_control": True,
                }])
                with self.assertRaisesRegex(ValueError, "mapped subledger account requires a party"):
                    _validate_references(
                        cursor, 1,
                        {"lines": [{"account_id": account_id, "party_id": None}]},
                    )


if __name__ == "__main__":
    unittest.main()

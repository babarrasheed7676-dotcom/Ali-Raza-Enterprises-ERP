import unittest
from datetime import date
from unittest.mock import MagicMock, patch

from app.accounting.fiscal_year_service import (
    build_fiscal_year_definition,
    create_fiscal_year,
)


class TestFiscalYearDefinition(unittest.TestCase):
    def test_july_to_june_generates_twelve_contiguous_periods(self):
        result = build_fiscal_year_definition(2026)
        self.assertEqual(result["name"], "FY 2026-27")
        self.assertEqual(result["start_date"], date(2026, 7, 1))
        self.assertEqual(result["end_date"], date(2027, 6, 30))
        self.assertEqual(len(result["periods"]), 12)
        self.assertEqual(result["periods"][0]["period_name"], "P01 - Jul 2026")
        self.assertEqual(result["periods"][-1]["period_name"], "P12 - Jun 2027")
        self.assertEqual(result["periods"][7]["start_date"], date(2027, 2, 1))
        self.assertEqual(result["periods"][7]["end_date"], date(2027, 2, 28))

    def test_leap_year_february_has_29_days(self):
        result = build_fiscal_year_definition(2023)
        february = result["periods"][7]
        self.assertEqual(february["start_date"], date(2024, 2, 1))
        self.assertEqual(february["end_date"], date(2024, 2, 29))

    def test_invalid_year_is_rejected(self):
        for value in ("abc", 1899, 9999):
            with self.subTest(value=value), self.assertRaises(ValueError):
                build_fiscal_year_definition(value)

    def test_company_mismatch_is_rejected_before_database_access(self):
        with patch("app.accounting.fiscal_year_service.get_connection") as connection:
            with self.assertRaisesRegex(ValueError, "company do not match"):
                create_fiscal_year(1, 2026, user={"company_id": 2}, request=MagicMock())
            connection.assert_not_called()


if __name__ == "__main__":
    unittest.main()
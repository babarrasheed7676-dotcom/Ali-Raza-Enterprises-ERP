import unittest
from decimal import Decimal
from unittest.mock import MagicMock, patch

from app.accounting.report_service import (
    _candidate_movement_is_balanced,
    _inventory_gl_reconciliation_summary,
    _inventory_gl_mapping_readiness,
    _parse_report_dates,
    _review_party_opening_row,
    _signed_balance,
    _trial_balance_is_balanced,
    get_fiscal_year_period_preview,
)


class TestAccountingReportCalculations(unittest.TestCase):
    def test_debit_net_balance(self):
        result = _signed_balance(Decimal("150"), Decimal("40"))
        self.assertEqual(result["balance"], Decimal("110"))
        self.assertEqual(result["balance_type"], "Dr")

    def test_credit_net_balance(self):
        result = _signed_balance(Decimal("20"), Decimal("90"))
        self.assertEqual(result["balance"], Decimal("70"))
        self.assertEqual(result["balance_type"], "Cr")

    def test_zero_net_balance(self):
        result = _signed_balance(Decimal("50"), Decimal("50"))
        self.assertEqual(result["balance"], Decimal("0"))
        self.assertEqual(result["balance_type"], "—")

    def test_empty_trial_balance_is_not_marked_balanced(self):
        self.assertFalse(
            _trial_balance_is_balanced(0, Decimal("0"), Decimal("0"))
        )

    def test_nonempty_equal_trial_balance_is_balanced(self):
        self.assertTrue(
            _trial_balance_is_balanced(2, Decimal("150"), Decimal("150"))
        )

    def test_nonempty_unequal_trial_balance_is_not_balanced(self):
        self.assertFalse(
            _trial_balance_is_balanced(2, Decimal("150"), Decimal("140"))
        )

    def test_reversed_date_range_rejected(self):
        with self.assertRaisesRegex(ValueError, "earlier"):
            _parse_report_dates("2026-11-06", "2026-11-05")

    def test_invalid_date_rejected(self):
        with self.assertRaisesRegex(ValueError, "YYYY-MM-DD"):
            _parse_report_dates("05/11/2026", "2026-11-06")

    def test_range_over_ten_years_rejected(self):
        with self.assertRaisesRegex(ValueError, "ten years"):
            _parse_report_dates("2000-01-01", "2011-01-01")


class TestFiscalYearPeriodPreview(unittest.TestCase):
    def _mock_readonly_connection(self, conflicts):
        connection = MagicMock()
        connection.__enter__.return_value = connection
        cursor = MagicMock()
        cursor.fetchall.return_value = conflicts
        connection.cursor.return_value.__enter__.return_value = cursor
        return connection, cursor

    @patch("app.accounting.report_service.get_connection")
    def test_builds_contiguous_months_and_handles_leap_day(self, get_connection_mock):
        connection, cursor = self._mock_readonly_connection([])
        get_connection_mock.return_value = connection

        result = get_fiscal_year_period_preview(1, "2024-01-15", "2024-03-02")

        self.assertTrue(result["read_only"])
        self.assertTrue(result["is_valid"])
        self.assertEqual(result["period_count"], 3)
        self.assertEqual(
            [(p["start_date"].isoformat(), p["end_date"].isoformat()) for p in result["periods"]],
            [
                ("2024-01-15", "2024-01-31"),
                ("2024-02-01", "2024-02-29"),
                ("2024-03-01", "2024-03-02"),
            ],
        )
        self.assertEqual(sum(p["day_count"] for p in result["periods"]), result["total_days"])
        cursor.execute.assert_any_call("SET TRANSACTION READ ONLY")

    @patch("app.accounting.report_service.get_connection")
    def test_existing_fiscal_year_overlap_blocks_preview(self, get_connection_mock):
        conflict = {
            "id": 4, "name": "Existing FY", "start_date": None,
            "end_date": None, "is_closed": False,
        }
        connection, _ = self._mock_readonly_connection([conflict])
        get_connection_mock.return_value = connection

        result = get_fiscal_year_period_preview(1, "2026-07-01", "2027-06-30")

        self.assertFalse(result["is_valid"])
        self.assertEqual(result["conflicts"], [conflict])
        self.assertIn("overlaps", result["message"])

    @patch("app.accounting.report_service.get_connection")
    def test_invalid_or_reversed_dates_fail_before_database_access(self, get_connection_mock):
        with self.assertRaisesRegex(ValueError, "YYYY-MM-DD"):
            get_fiscal_year_period_preview(1, "01/07/2026", "2027-06-30")
        with self.assertRaisesRegex(ValueError, "earlier"):
            get_fiscal_year_period_preview(1, "2027-06-30", "2026-07-01")
        get_connection_mock.assert_not_called()


class TestInventoryGLReconciliation(unittest.TestCase):
    def test_stock_value_difference_is_flagged(self):
        result = _inventory_gl_reconciliation_summary(
            Decimal("9033.333334"),
            Decimal("0"),
            stock_balance_rows=5,
        )
        self.assertEqual(result["difference"], Decimal("9033.333334"))
        self.assertEqual(result["status"], "STOCK / GL VALUE MISMATCH")

    def test_unvalued_stock_takes_priority_over_value_match(self):
        result = _inventory_gl_reconciliation_summary(
            Decimal("100"),
            Decimal("100"),
            stock_balance_rows=2,
            unvalued_balance_rows=1,
        )
        self.assertEqual(result["status"], "STOCK VALUATION NEEDS REVIEW")

    def test_missing_inventory_control_account_is_flagged(self):
        result = _inventory_gl_reconciliation_summary(
            Decimal("100"),
            Decimal("100"),
            stock_balance_rows=1,
            missing_inventory_accounts=("1249",),
        )
        self.assertEqual(result["status"], "INVENTORY CONTROL ACCOUNTS NEED REVIEW")

    def test_no_stock_rows_is_not_reported_as_matched(self):
        result = _inventory_gl_reconciliation_summary(
            Decimal("0"),
            Decimal("0"),
            stock_balance_rows=0,
        )
        self.assertEqual(result["status"], "NO STOCK BALANCES TO RECONCILE")


class TestOpeningBalanceCandidateReconciliation(unittest.TestCase):
    def test_empty_candidate_set_is_not_balanced_even_when_totals_are_zero(self):
        self.assertFalse(
            _candidate_movement_is_balanced([], Decimal("0"), Decimal("0"))
        )

    def test_nonempty_equal_candidate_set_is_balanced(self):
        lines = [{"party_id": 7, "amount": Decimal("100")}]
        self.assertTrue(
            _candidate_movement_is_balanced(lines, Decimal("100"), Decimal("100"))
        )

    def test_nonempty_unequal_candidate_set_is_not_balanced(self):
        lines = [{"party_id": 7, "amount": Decimal("100")}]
        self.assertFalse(
            _candidate_movement_is_balanced(lines, Decimal("100"), Decimal("0"))
        )


class TestPartyOpeningBalanceReview(unittest.TestCase):
    def setUp(self):
        self.party = {
            "id": 7,
            "party_code": "C-007",
            "party_name": "Example Customer",
            "party_type": "CUSTOMER",
            "is_active": True,
            "profile_id": 3,
            "opening_balance": Decimal("1250.00"),
            "opening_balance_type": "DEBIT",
            "default_currency_code": "PKR",
        }
        self.accounts = {
            "1221": {
                "account_code": "1221",
                "account_name": "Customer Receivables",
                "account_type": "ASSET",
                "normal_balance": "DEBIT",
                "is_active": True,
                "is_group": False,
                "is_control": True,
            }
        }

    def test_valid_customer_debit_mapping_is_only_preview_ready(self):
        result = _review_party_opening_row(self.party, self.accounts, "PKR")
        self.assertEqual(result["status"], "MAPPING READY — NOT POSTED")
        self.assertEqual(result["account_code"], "1221")
        self.assertTrue(result["ready_for_review"])

    def test_inactive_party_is_blocked(self):
        party = {**self.party, "is_active": False}
        result = _review_party_opening_row(party, self.accounts, "PKR")
        self.assertEqual(result["status"], "INACTIVE PARTY")

    def test_unsupported_party_type_is_blocked(self):
        party = {**self.party, "party_type": "EMPLOYEE"}
        result = _review_party_opening_row(party, self.accounts, "PKR")
        self.assertEqual(result["status"], "UNSUPPORTED PARTY TYPE")

    def test_missing_profile_does_not_infer_currency_or_zero_balance(self):
        party = {
            **self.party,
            "profile_id": None,
            "opening_balance": None,
            "opening_balance_type": None,
            "default_currency_code": None,
        }
        result = _review_party_opening_row(party, self.accounts, "PKR")
        self.assertEqual(result["status"], "PROFILE MISSING")
        self.assertEqual(result["currency"], "NOT CONFIGURED")
        self.assertIsNone(result["opening_balance"])

    def test_foreign_currency_is_blocked_without_conversion(self):
        party = {**self.party, "default_currency_code": "USD"}
        result = _review_party_opening_row(party, self.accounts, "PKR")
        self.assertEqual(result["status"], "CURRENCY MISMATCH — CONVERSION REQUIRED")

    def test_wrong_control_account_normal_balance_is_blocked(self):
        accounts = {
            "1221": {**self.accounts["1221"], "normal_balance": "CREDIT"}
        }
        result = _review_party_opening_row(self.party, accounts, "PKR")
        self.assertEqual(result["status"], "CONTROL ACCOUNT NEEDS REVIEW")

    def test_customer_credit_maps_to_customer_advances(self):
        party = {
            **self.party,
            "opening_balance_type": "CREDIT",
        }
        accounts = {
            "2241": {
                "account_code": "2241",
                "account_name": "Customer Advances",
                "account_type": "LIABILITY",
                "normal_balance": "CREDIT",
                "is_active": True,
                "is_group": False,
                "is_control": True,
            }
        }
        result = _review_party_opening_row(party, accounts, "PKR")
        self.assertEqual(result["account_code"], "2241")
        self.assertEqual(result["status"], "MAPPING READY — NOT POSTED")

    def test_supplier_debit_maps_to_supplier_advances(self):
        party = {
            **self.party,
            "party_type": "SUPPLIER",
            "opening_balance_type": "DEBIT",
        }
        accounts = {
            "1231": {
                "account_code": "1231",
                "account_name": "Supplier Advances",
                "account_type": "ASSET",
                "normal_balance": "DEBIT",
                "is_active": True,
                "is_group": False,
                "is_control": True,
            }
        }
        result = _review_party_opening_row(party, accounts, "PKR")
        self.assertEqual(result["account_code"], "1231")
        self.assertEqual(result["status"], "MAPPING READY — NOT POSTED")

    def test_supplier_credit_maps_to_supplier_payables(self):
        party = {
            **self.party,
            "party_type": "SUPPLIER",
            "opening_balance_type": "CREDIT",
        }
        accounts = {
            "2211": {
                "account_code": "2211",
                "account_name": "Supplier Payables",
                "account_type": "LIABILITY",
                "normal_balance": "CREDIT",
                "is_active": True,
                "is_group": False,
                "is_control": True,
            }
        }
        result = _review_party_opening_row(party, accounts, "PKR")
        self.assertEqual(result["account_code"], "2211")
        self.assertEqual(result["status"], "MAPPING READY — NOT POSTED")

    def test_company_currency_must_be_configured(self):
        result = _review_party_opening_row(self.party, self.accounts, "")
        self.assertEqual(result["status"], "COMPANY CURRENCY NOT CONFIGURED")

    def test_negative_opening_amount_is_blocked(self):
        party = {**self.party, "opening_balance": Decimal("-1")}
        result = _review_party_opening_row(party, self.accounts, "PKR")
        self.assertEqual(result["status"], "INVALID NEGATIVE AMOUNT")


class TestInventoryGLMappingReadiness(unittest.TestCase):
    def setUp(self):
        self.transactions = [
            {"code": "PURCHASE_RECEIPT", "name": "Purchase Receipt", "is_active": True},
            {"code": "SALES_DISPATCH", "name": "Sales Dispatch", "is_active": True},
        ]
        self.categories = [
            {"code": "YARN", "name": "Yarn / Thread", "item_count": 1},
            {"code": "LABEL", "name": "Labels", "item_count": 1},
        ]
        self.accounts = {
            "1241": {
                "account_code": "1241", "account_name": "Raw Yarn / Thread Inventory",
                "account_type": "ASSET", "normal_balance": "DEBIT",
                "is_active": True, "is_group": False, "is_control": True,
            }
        }

    def test_valid_candidate_is_not_marked_approved(self):
        result = _inventory_gl_mapping_readiness(self.transactions, self.categories, self.accounts)
        yarn = next(row for row in result["categories"] if row["code"] == "YARN")
        self.assertEqual(yarn["status"], "CANDIDATE ACCOUNT VALID ? POLICY NOT APPROVED")
        self.assertFalse(result["automatic_posting_approved"])

    def test_unmapped_label_category_is_flagged(self):
        result = _inventory_gl_mapping_readiness(self.transactions, self.categories, self.accounts)
        label = next(row for row in result["categories"] if row["code"] == "LABEL")
        self.assertEqual(label["status"], "ACCOUNT MAPPING UNRESOLVED")

    def test_missing_candidate_account_is_flagged(self):
        result = _inventory_gl_mapping_readiness(
            self.transactions, [{"code": "NALKI", "item_count": 1}], {}
        )
        self.assertEqual(result["categories"][0]["status"], "CANDIDATE ACCOUNT MISSING")

    def test_wrong_account_type_or_flags_are_flagged(self):
        accounts = {"1241": {**self.accounts["1241"], "is_group": True}}
        result = _inventory_gl_mapping_readiness(
            self.transactions, [{"code": "YARN", "item_count": 1}], accounts
        )
        self.assertEqual(result["categories"][0]["status"], "CANDIDATE ACCOUNT NEEDS REVIEW")

    def test_inactive_category_is_flagged(self):
        result = _inventory_gl_mapping_readiness(
            self.transactions,
            [{"code": "YARN", "item_count": 1, "is_active": False}],
            self.accounts,
        )
        self.assertEqual(result["categories"][0]["status"], "INACTIVE ITEM CATEGORY")

    def test_purchase_controls_flag_missing_input_tax_and_grni(self):
        all_accounts = [self.accounts["1241"], {
            "account_code": "2211", "account_name": "Supplier Payables",
            "account_type": "LIABILITY", "normal_balance": "CREDIT",
            "is_active": True, "is_group": False, "is_control": True,
        }, {
            "account_code": "2221", "account_name": "Sales Tax Payable",
            "account_type": "LIABILITY", "normal_balance": "CREDIT",
            "is_active": True, "is_group": False, "is_control": True,
        }]
        result = _inventory_gl_mapping_readiness(
            self.transactions, self.categories, self.accounts, all_accounts, {}
        )
        controls = {row["label"]: row for row in result["purchase_account_checks"]}
        self.assertIn("INPUT TAX ASSET ACCOUNT MISSING", controls["Input GST / Sales Tax Receivable"]["status"])
        self.assertIn("GRNI ACCOUNT MISSING", controls["Goods Received Not Invoiced (GRNI)"]["status"])
        self.assertEqual(controls["Sales Tax Payable"]["status"], "LIABILITY ? NOT INPUT TAX")
        self.assertTrue(any("GST from inventory cost" in item for item in result["purchase_blockers"]))
        self.assertTrue(any("not a separate register" in item for item in result["purchase_blockers"]))
        self.assertTrue(any("free-text remarks marker" in item for item in result["purchase_blockers"]))
        self.assertFalse(result["purchase_journal_ready"])

    def test_valid_supplier_payable_account_is_recognized(self):
        supplier = {
            "account_code": "2211", "account_name": "Supplier Payables",
            "account_type": "LIABILITY", "normal_balance": "CREDIT",
            "is_active": True, "is_group": False, "is_control": True,
        }
        result = _inventory_gl_mapping_readiness(
            self.transactions, self.categories, self.accounts, [supplier], {}
        )
        controls = {row["label"]: row for row in result["purchase_account_checks"]}
        self.assertEqual(controls["Supplier Payables"]["status"], "ACCOUNT STRUCTURE VALID")

    def test_transaction_policy_remains_blocked(self):
        result = _inventory_gl_mapping_readiness(self.transactions, self.categories, self.accounts)
        self.assertTrue(all(row["status"] == "POLICY REVIEW REQUIRED" for row in result["transactions"]))
        self.assertFalse(result["automatic_posting_approved"])


if __name__ == "__main__":
    unittest.main()
import unittest
from datetime import date
from unittest.mock import patch

from app.accounting.inventory_journal import create_stock_document_journal_draft


class FakeCursor:
    def __init__(self, document=None, lines=None):
        self.document = document
        self.lines = lines or []
        self.calls = []
        self.fetchall_calls = 0

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def execute(self, sql, params=None):
        self.calls.append((sql, params))

    def fetchone(self):
        return self.document

    def fetchall(self):
        self.fetchall_calls += 1
        return self.lines


class FakeConnection:
    def __init__(self, cursor):
        self.fake_cursor = cursor

    def cursor(self):
        return self.fake_cursor


class TestInventoryJournalBridge(unittest.TestCase):
    def setUp(self):
        self.document = {
            "id": 77,
            "company_id": 1,
            "document_no": "ST-000077",
            "document_type": "STOCK_ADJUSTMENT",
            "document_date": date(2026, 11, 5),
            "status": "POSTED",
        }
        self.lines = [{
            "line_id": 1,
            "quantity_in": 1,
            "quantity_out": 0,
            "unit_cost": 10,
            "total_cost": 10,
            "ownership_type_id": 1,
            "owner_party_id": None,
            "category_code": "YARN",
            "category_name": "Yarn",
        }]
        self.user = {"id": 1, "company_id": 1}
        self.lines_for_journal = [
            {"account_id": 101, "debit": "10.00", "credit": "0"},
            {"account_id": 102, "debit": "0", "credit": "10.00"},
        ]

    @patch("app.accounting.inventory_journal.create_journal_draft")
    def test_posted_own_stock_document_creates_source_linked_draft(self, create):
        create.return_value = {"id": 5, "journal_no": "GJ-000005", "status": "DRAFT"}
        cur = FakeCursor(self.document, self.lines)
        result = create_stock_document_journal_draft(
            FakeConnection(cur), company_id=1, stock_document_id=77,
            user=self.user, request=object(), journal_lines=self.lines_for_journal,
        )
        self.assertEqual(result["status"], "DRAFT")
        kwargs = create.call_args.kwargs
        self.assertEqual(kwargs["source_module"], "INVENTORY")
        self.assertEqual(kwargs["source_type"], "STOCK_DOCUMENT")
        self.assertEqual(kwargs["source_id"], 77)
        self.assertEqual(kwargs["entry_date"], date(2026, 11, 5))
        self.assertEqual(kwargs["lines"], self.lines_for_journal)

    @patch("app.accounting.inventory_journal.create_journal_draft")
    def test_stock_opening_is_blocked_without_approved_clearing_policy(self, create):
        doc = {**self.document, "document_type": "STOCK_OPENING"}
        with self.assertRaisesRegex(ValueError, "opening-stock clearing account"):
            create_stock_document_journal_draft(
                FakeConnection(FakeCursor(doc, self.lines)), company_id=1,
                stock_document_id=77, user=self.user, request=object(),
                journal_lines=self.lines_for_journal,
            )
        create.assert_not_called()

    @patch("app.accounting.inventory_journal.create_journal_draft")
    def test_unposted_stock_document_is_blocked(self, create):
        doc = {**self.document, "status": "APPROVED"}
        with self.assertRaisesRegex(ValueError, "POSTED"):
            create_stock_document_journal_draft(
                FakeConnection(FakeCursor(doc, self.lines)), company_id=1,
                stock_document_id=77, user=self.user, request=object(),
                journal_lines=self.lines_for_journal,
            )
        create.assert_not_called()

    @patch("app.accounting.inventory_journal.create_journal_draft")
    def test_party_owned_stock_is_blocked(self, create):
        party_lines = [
            {**self.lines[0], "ownership_type_id": 2, "owner_party_id": 9}
        ]
        with self.assertRaisesRegex(ValueError, "PARTY-owned"):
            create_stock_document_journal_draft(
                FakeConnection(FakeCursor(self.document, party_lines)),
                company_id=1, stock_document_id=77, user=self.user,
                request=object(), journal_lines=self.lines_for_journal,
            )
        create.assert_not_called()

    @patch("app.accounting.inventory_journal.create_journal_draft")
    def test_journal_amount_must_match_stock_valuation(self, create):
        wrong_amount = [
            {"account_id": 101, "debit": "9.00", "credit": "0"},
            {"account_id": 102, "debit": "0", "credit": "9.00"},
        ]
        with self.assertRaisesRegex(ValueError, "does not match"):
            create_stock_document_journal_draft(
                FakeConnection(FakeCursor(self.document, self.lines)),
                company_id=1, stock_document_id=77, user=self.user,
                request=object(), journal_lines=wrong_amount,
            )
        create.assert_not_called()

    @patch("app.accounting.inventory_journal.create_journal_draft")
    def test_empty_stock_document_is_blocked(self, create):
        with self.assertRaisesRegex(ValueError, "no lines"):
            create_stock_document_journal_draft(
                FakeConnection(FakeCursor(self.document, [])),
                company_id=1, stock_document_id=77, user=self.user,
                request=object(), journal_lines=self.lines_for_journal,
            )
        create.assert_not_called()

    @patch("app.accounting.inventory_journal.create_journal_draft")
    def test_cross_company_or_missing_document_is_blocked(self, create):
        with self.assertRaisesRegex(ValueError, "not found"):
            create_stock_document_journal_draft(
                FakeConnection(FakeCursor(None, [])), company_id=1,
                stock_document_id=77, user=self.user, request=object(),
                journal_lines=self.lines_for_journal,
            )
        create.assert_not_called()


if __name__ == "__main__":
    unittest.main()
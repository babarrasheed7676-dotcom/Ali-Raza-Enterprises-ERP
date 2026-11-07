import unittest
from datetime import date
from decimal import Decimal

from app.accounting.inventory_journal import get_stock_document_journal_basis


class FakeCursor:
    def __init__(self, document, rows):
        self.document = document
        self.rows = rows

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def execute(self, sql, params=None):
        self.last_sql = sql
        self.last_params = params

    def fetchone(self):
        return self.document

    def fetchall(self):
        return self.rows


class FakeConnection:
    def __init__(self, document, rows):
        self.cur = FakeCursor(document, rows)

    def cursor(self):
        return self.cur


def document(doc_type="PRODUCTION_OUTPUT"):
    return {
        "id": 7, "document_no": "ST-000007",
        "document_type": doc_type, "document_date": date(2026, 11, 5),
        "status": "POSTED",
    }


def line(**overrides):
    base = {
        "line_id": 1, "quantity_in": Decimal("10"),
        "quantity_out": Decimal("0"), "unit_cost": Decimal("5"),
        "total_cost": Decimal("50"), "ownership_type_id": 1,
        "owner_party_id": None, "category_code": "NALKI",
        "category_name": "Nalki",
    }
    return {**base, **overrides}


class TestInventoryJournalBasis(unittest.TestCase):
    def test_groups_category_and_calculates_inward_outward_basis(self):
        result = get_stock_document_journal_basis(
            FakeConnection(document(), [
                line(line_id=1, total_cost=None),
                line(line_id=2, quantity_in=0, quantity_out=2,
                     unit_cost=Decimal("5"), total_cost=None),
            ]),
            company_id=1, stock_document_id=7,
        )
        self.assertEqual(result["total_inward_value"], Decimal("50"))
        self.assertEqual(result["total_outward_value"], Decimal("10"))
        self.assertEqual(result["net_stock_value_change"], Decimal("40"))
        self.assertEqual(result["categories"][0]["line_count"], 2)
        self.assertTrue(result["ready_for_mapping_review"])
        self.assertFalse(result["automatic_journal_approved"])

    def test_missing_category_is_a_blocker(self):
        result = get_stock_document_journal_basis(
            FakeConnection(document(), [line(category_code=None)]),
            company_id=1, stock_document_id=7,
        )
        self.assertFalse(result["ready_for_mapping_review"])
        self.assertIn("category/account mapping key is missing", result["blockers"][0])

    def test_missing_cost_is_a_blocker(self):
        result = get_stock_document_journal_basis(
            FakeConnection(document(), [
                line(unit_cost=None, total_cost=None)
            ]),
            company_id=1, stock_document_id=7,
        )
        self.assertFalse(result["ready_for_mapping_review"])
        self.assertIn("neither a valid total cost nor unit cost", result["blockers"][0])

    def test_party_stock_is_excluded_and_blocks_are_reported(self):
        result = get_stock_document_journal_basis(
            FakeConnection(document(), [
                line(ownership_type_id=2, owner_party_id=99)
            ]),
            company_id=1, stock_document_id=7,
        )
        self.assertEqual(result["categories"], [])
        self.assertFalse(result["ready_for_mapping_review"])
        self.assertTrue(any("PARTY-owned" in item for item in result["blockers"]))

    def test_stock_transfer_never_proposes_gl_journal(self):
        result = get_stock_document_journal_basis(
            FakeConnection(document("STOCK_TRANSFER"), [
                line(),
                line(line_id=2, quantity_in=0, quantity_out=10),
            ]),
            company_id=1, stock_document_id=7,
        )
        self.assertFalse(result["ready_for_mapping_review"])
        self.assertTrue(any("location movement" in item for item in result["blockers"]))

    def test_unregistered_document_type_is_blocked(self):
        result = get_stock_document_journal_basis(
            FakeConnection(document("TEST_INWARD"), [line()]),
            company_id=1, stock_document_id=7,
        )
        self.assertFalse(result["ready_for_mapping_review"])
        self.assertTrue(any("Unsupported stock document type" in item for item in result["blockers"]))

    def test_non_posted_document_rejected(self):
        with self.assertRaisesRegex(ValueError, "POSTED"):
            get_stock_document_journal_basis(
                FakeConnection({**document(), "status": "DRAFT"}, []),
                company_id=1, stock_document_id=7,
            )

    def test_missing_document_rejected(self):
        with self.assertRaisesRegex(ValueError, "not found"):
            get_stock_document_journal_basis(
                FakeConnection(None, []), company_id=1, stock_document_id=7,
            )


if __name__ == "__main__":
    unittest.main()
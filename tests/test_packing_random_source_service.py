import unittest
from unittest.mock import patch

from app import packing_random_source_service as service


class FakeCursor:
    def __init__(self, rows=None):
        self.rows = rows or []
        self.query = None
        self.params = None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def execute(self, query, params):
        self.query = query
        self.params = params

    def fetchall(self):
        return self.rows


class FakeConnection:
    def __init__(self, cursor):
        self.fake_cursor = cursor

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def cursor(self):
        return self.fake_cursor


class RandomPackingSourceSelectorTests(unittest.TestCase):
    def test_requires_positive_company(self):
        with self.assertRaises(ValueError):
            service.get_random_packing_source_candidates(0)

    def test_empty_source_register_returns_empty_candidates(self):
        cursor = FakeCursor([])
        with patch.object(service, "get_connection", return_value=FakeConnection(cursor)):
            self.assertEqual([], service.get_random_packing_source_candidates(1))
        self.assertEqual((1, 1, 1, 1, 1, 1), cursor.params)

    def test_query_fails_closed_on_source_and_quality_status(self):
        cursor = FakeCursor([])
        with patch.object(service, "get_connection", return_value=FakeConnection(cursor)):
            service.get_random_packing_source_candidates(1)
        sql = cursor.query
        self.assertIn("o.status='POSTED'", sql)
        self.assertIn("ol.output_type='GOOD'", sql)
        self.assertIn("ol.quality_status='ACCEPTED'", sql)
        self.assertIn("rl.return_status='ACCEPTED'", sql)
        self.assertIn("rl.quality_status='ACCEPTED'", sql)
        self.assertIn("e.source_bucket_count=1", sql)
        self.assertIn("inventory.stock_balances", sql)
        self.assertIn("i.item_code='NALKI'", sql)

    def test_party_return_without_proven_stage_is_not_assumed_as_available(self):
        cursor = FakeCursor([])
        with patch.object(service, "get_connection", return_value=FakeConnection(cursor)):
            service.get_random_packing_source_candidates(1)
        # Return rows must carry an explicit stage; selector never infers it.
        self.assertIn("rl.process_stage_id", cursor.query)
        self.assertIn("rl.process_stage_id IS NOT NULL", cursor.query)
        self.assertIn("b.process_stage_id IS NOT DISTINCT FROM e.process_stage_id", cursor.query)


if __name__ == "__main__":
    unittest.main()
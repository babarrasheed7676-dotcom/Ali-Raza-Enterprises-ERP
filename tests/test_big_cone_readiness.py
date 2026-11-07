import inspect
import unittest
from unittest.mock import patch

from app.big_cone_draft_service import (
    get_big_cone_readiness,
    _big_cone_stock_dimension_shortfalls,
)


class BigConeReadinessSafetyTests(unittest.TestCase):
    def test_invalid_ids_are_rejected_before_database_access(self):
        with patch("app.big_cone_draft_service.get_connection") as connection:
            with self.assertRaisesRegex(ValueError, "valid Big Cone document"):
                get_big_cone_readiness(1, 0)
            connection.assert_not_called()

    def test_negative_company_is_rejected_before_database_access(self):
        with patch("app.big_cone_draft_service.get_connection") as connection:
            with self.assertRaisesRegex(ValueError, "valid Big Cone document"):
                get_big_cone_readiness(-1, 10)
            connection.assert_not_called()

    def test_readiness_query_is_explicitly_read_only_and_has_no_write_sql(self):
        source = inspect.getsource(get_big_cone_readiness).upper()
        self.assertIn("SET TRANSACTION READ ONLY", source)
        for forbidden in ("INSERT INTO", "UPDATE ", "DELETE FROM", "FOR UPDATE"):
            self.assertNotIn(forbidden, source)

    @staticmethod
    def _material(line_no, input_kg, stock_kg, other_draft_kg="0", batch_id=7):
        return {
            "line_no": line_no,
            "input_quantity_kg": input_kg,
            "current_source_stock_kg": stock_kg,
            "other_active_draft_allocations_kg": other_draft_kg,
            "item_variant_id": 10,
            "batch_id": batch_id,
            "location_id": 1,
            "ownership_type_id": 1,
            "owner_party_id": None,
            "process_stage_id": 2,
        }

    def test_stock_preflight_aggregates_same_exact_stock_dimensions(self):
        rows = [
            self._material(1, "6", "10"),
            self._material(2, "6", "10"),
        ]
        blockers = _big_cone_stock_dimension_shortfalls(rows)
        self.assertEqual(len(blockers), 1)
        self.assertIn("12 KG", blockers[0])
        self.assertIn("10 KG", blockers[0])

    def test_other_active_draft_claim_is_counted_once_per_dimension(self):
        rows = [
            self._material(1, "6", "10", "3"),
            self._material(2, "2", "10", "3"),
        ]
        blockers = _big_cone_stock_dimension_shortfalls(rows)
        self.assertEqual(len(blockers), 1)
        self.assertIn("11 KG", blockers[0])

    def test_different_batches_are_checked_as_separate_stock_dimensions(self):
        rows = [
            self._material(1, "6", "10", batch_id=7),
            self._material(2, "6", "10", batch_id=8),
        ]
        self.assertEqual(_big_cone_stock_dimension_shortfalls(rows), [])

    def test_preflight_never_claims_measured_wastage_or_approval(self):
        source = inspect.getsource(get_big_cone_readiness)
        self.assertIn('"measured_wastage_kg": None', source)
        self.assertIn('"ready_for_approval": False', source)
        self.assertIn('"read_only": True', source)


if __name__ == "__main__":
    unittest.main()

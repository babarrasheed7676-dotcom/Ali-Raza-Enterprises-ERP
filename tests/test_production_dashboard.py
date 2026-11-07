import unittest

from app.production_service import (
    PROCESS_ORDER_SOURCES, _status_summary,
    _big_cone_register_rows, _baby_cone_register_rows,
)


class ProductionDashboardTests(unittest.TestCase):
    def test_process_allowlist_is_fixed_and_complete(self):
        keys = [key for key, _label, _table in PROCESS_ORDER_SOURCES]
        tables = [table for _key, _label, table in PROCESS_ORDER_SOURCES]
        self.assertEqual(
            keys,
            [
                "production_orders",
                "dyeing",
                "large_cone",
                "baby_cone",
                "rewinding",
                "nalki",
                "outside_dyeing",
                "outside_labeling",
                "packing",
            ],
        )
        self.assertEqual(len(tables), len(set(tables)))

    def test_status_summary_returns_integer_counts(self):
        self.assertEqual(
            _status_summary(
                [
                    {"status": "DRAFT", "total": 2},
                    {"status": "POSTED", "total": 1},
                ]
            ),
            [
                {"status": "DRAFT", "count": 2},
                {"status": "POSTED", "count": 1},
            ],
        )

    def test_status_summary_handles_empty_process(self):
        self.assertEqual(_status_summary([]), [])

    def test_big_cone_register_calculates_unreconciled_difference_without_calling_it_wastage(self):
        rows = _big_cone_register_rows([{
            "id": 4, "big_cone_no": "BC-0004", "big_cone_date": "2026-11-07",
            "status": "DRAFT", "input_quantity_kg": "18.750",
            "output_quantity_kg": "18.000", "total_process_cost": "125.50",
            "material_line_count": 2, "output_line_count": 3,
        }])
        self.assertEqual(rows[0]["unreconciled_difference_kg"], 0.750)
        self.assertEqual(rows[0]["material_line_count"], 2)
        self.assertEqual(rows[0]["output_line_count"], 3)
        self.assertNotIn("wastage_quantity_kg", rows[0])

    def test_big_cone_register_handles_empty_and_null_totals(self):
        self.assertEqual(_big_cone_register_rows([]), [])
        rows = _big_cone_register_rows([{
            "id": 1, "big_cone_no": "BC-0001", "big_cone_date": "2026-11-07",
            "status": "DRAFT", "input_quantity_kg": None,
            "output_quantity_kg": None, "total_process_cost": None,
        }])
        self.assertEqual(rows[0]["unreconciled_difference_kg"], 0)
        self.assertEqual(rows[0]["process_cost"], 0)


    def test_baby_cone_register_counts_evidence_without_inventing_wastage(self):
        rows = _baby_cone_register_rows([{
            "id": 9, "baby_cone_no": "BABY-0009", "baby_cone_date": "2026-11-07",
            "status": "DRAFT", "input_quantity_kg": "10.000",
            "output_quantity_kg": "9.750", "total_process_cost": "42.50",
            "material_line_count": 2, "output_line_count": 3,
            "measurement_count": 3, "cost_line_count": 2, "loss_line_count": 1,
        }])
        self.assertEqual(rows[0]["unreconciled_difference_kg"], 0.250)
        self.assertEqual(rows[0]["measurement_count"], 3)
        self.assertEqual(rows[0]["cost_line_count"], 2)
        self.assertEqual(rows[0]["loss_line_count"], 1)
        self.assertNotIn("wastage_quantity_kg", rows[0])

    def test_baby_cone_register_handles_empty_and_null_values(self):
        self.assertEqual(_baby_cone_register_rows([]), [])
        rows = _baby_cone_register_rows([{
            "id": 1, "baby_cone_no": "BABY-0001", "baby_cone_date": "2026-11-07",
            "status": "DRAFT", "input_quantity_kg": None,
            "output_quantity_kg": None, "total_process_cost": None,
        }])
        self.assertEqual(rows[0]["unreconciled_difference_kg"], 0)
        self.assertEqual(rows[0]["measurement_count"], 0)
        self.assertEqual(rows[0]["cost_line_count"], 0)
        self.assertEqual(rows[0]["loss_line_count"], 0)


if __name__ == "__main__":
    unittest.main()

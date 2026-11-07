import unittest

from app.production_service import PROCESS_ORDER_SOURCES, _status_summary


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


if __name__ == "__main__":
    unittest.main()
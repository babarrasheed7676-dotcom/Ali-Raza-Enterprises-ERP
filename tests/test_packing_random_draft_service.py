import unittest

from app.packing_random_draft_service import _selected_candidates, _positive_int


class RandomPackingDraftInputTests(unittest.TestCase):
    def candidate(self):
        return {
            "source_type": "FRESH_NALKI",
            "source_line_id": 101,
            "source_table": "production.nalki_output_lines",
            "item_variant_id": 55,
            "brand_id": 2,
            "shade_id": 77,
            "available_pieces": 8,
            "unit_cost": "1.250000",
            "ownership_type_id": 1,
            "owner_party_id": None,
            "batch_id": 9,
            "location_id": 3,
            "process_stage_id": 4,
            "stock_verified": True,
            "output_type": "GOOD",
            "quality_status": "ACCEPTED",
        }

    def test_client_can_only_choose_source_identity_and_quantity(self):
        selected = _selected_candidates(
            [self.candidate()],
            [{"source_type": "FRESH_NALKI", "source_line_id": 101,
              "quantity_pieces": 3, "available_pieces": 999999,
              "unit_cost": "0", "ownership_type_id": 2}],
        )
        self.assertEqual(selected[0]["quantity_pieces"], 3)
        self.assertEqual(selected[0]["available_pieces"], 8)
        self.assertEqual(selected[0]["unit_cost"], "1.250000")
        self.assertEqual(selected[0]["ownership_type_id"], 1)

    def test_unknown_source_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "not an eligible live source line"):
            _selected_candidates([self.candidate()], [
                {"source_type": "FRESH_NALKI", "source_line_id": 999,
                 "quantity_pieces": 1}
            ])

    def test_duplicate_source_is_rejected(self):
        submitted = [
            {"source_type": "FRESH_NALKI", "source_line_id": 101, "quantity_pieces": 1},
            {"source_type": "FRESH_NALKI", "source_line_id": 101, "quantity_pieces": 1},
        ]
        with self.assertRaisesRegex(ValueError, "duplicates a source line"):
            _selected_candidates([self.candidate()], submitted)

    def test_positive_integer_bounds(self):
        self.assertEqual(_positive_int("4", "qty"), 4)
        for value in ("0", "-1", "1.5", "100001", "abc"):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    _positive_int(value, "qty")


if __name__ == "__main__":
    unittest.main()

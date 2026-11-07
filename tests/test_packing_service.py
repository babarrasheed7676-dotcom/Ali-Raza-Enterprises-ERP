import unittest
from datetime import date, timedelta
from app.packing_service import (
    PIECES_PER_SMALL_BOX,
    SMALL_BOXES_PER_FINISHED_BOX,
    PIECES_PER_FINISHED_BOX,
    normalize_packing_lines,
    parse_packing_date,
    validate_packing_source_quantity,
    ELIGIBLE_PACKING_SOURCE_STAGE_CODES,
    validate_packing_material_quantities,
    validate_packing_empty_box_return,
    validate_packing_quality,
    validate_packing_wastage,
    validate_packing_labour,
    REGULAR_SMALL_BOX_VARIANT_CODE,
    calculate_finished_box_material_requirements,
    validate_finished_box_shade_composition,
)


class PackingDraftRulesTests(unittest.TestCase):
    def test_packaging_relationship_is_100_pieces_per_finished_box(self):
        self.assertEqual(PIECES_PER_SMALL_BOX, 10)
        self.assertEqual(SMALL_BOXES_PER_FINISHED_BOX, 10)
        self.assertEqual(PIECES_PER_FINISHED_BOX, 100)

    def test_normalizes_finished_boxes_to_small_boxes_and_pieces(self):
        result = normalize_packing_lines([
            {"item_variant_id": "2", "finished_boxes_qty": "3"}
        ])
        self.assertEqual(result[0]["quantity_pieces"], 300)
        self.assertEqual(result[0]["small_boxes_qty"], 30)
        self.assertEqual(result[0]["finished_boxes_qty"], 3)

    def test_rejects_duplicate_variants(self):
        with self.assertRaisesRegex(ValueError, "duplicate"):
            normalize_packing_lines([
                {"item_variant_id": "2", "finished_boxes_qty": "1"},
                {"item_variant_id": "2", "finished_boxes_qty": "2"},
            ])

    def test_rejects_fractional_finished_box_count(self):
        with self.assertRaisesRegex(ValueError, "whole finished-box"):
            normalize_packing_lines([
                {"item_variant_id": "2", "finished_boxes_qty": "1.5"}
            ])

    def test_rejects_non_positive_variant_ids(self):
        with self.assertRaisesRegex(ValueError, "positive"):
            normalize_packing_lines([
                {"item_variant_id": "0", "finished_boxes_qty": "1"}
            ])

    def test_rejects_empty_or_too_many_lines(self):
        with self.assertRaisesRegex(ValueError, "1–20"):
            normalize_packing_lines([])
        with self.assertRaisesRegex(ValueError, "1–20"):
            normalize_packing_lines([
                {"item_variant_id": str(i), "finished_boxes_qty": "1"}
                for i in range(1, 22)
            ])



    def test_regular_box_is_10_piece_and_finished_box_is_separate_100_piece_pack(self):
        self.assertEqual(REGULAR_SMALL_BOX_VARIANT_CODE, "PACK_BOX-STD")
        self.assertEqual(calculate_finished_box_material_requirements(1), {
            "finished_100_piece_boxes": 1,
            "regular_10_piece_boxes": 10,
            "nalki_pieces": 100,
        })
        self.assertEqual(calculate_finished_box_material_requirements(120), {
            "finished_100_piece_boxes": 120,
            "regular_10_piece_boxes": 1200,
            "nalki_pieces": 12000,
        })

    def test_finished_box_requires_100_unique_shades_same_brand_and_one_each(self):
        lines=[{"item_variant_id":i,"brand_id":1,"shade_id":i,"available_pieces":5} for i in range(1,101)]
        result=validate_finished_box_shade_composition(lines,5)
        self.assertEqual(len(result),100)
        self.assertTrue(all(x["quantity_pieces"]==5 and x["pieces_per_finished_box"]==1 for x in result))

    def test_finished_box_rejects_duplicate_shades_or_mixed_brands(self):
        lines=[{"item_variant_id":i,"brand_id":1,"shade_id":i,"available_pieces":1} for i in range(1,101)]
        lines[-1]["shade_id"]=lines[0]["shade_id"]
        with self.assertRaisesRegex(ValueError,"100 different shades"):
            validate_finished_box_shade_composition(lines,1)
        lines[-1]["shade_id"]=100
        lines[-1]["brand_id"]=2
        with self.assertRaisesRegex(ValueError,"same brand"):
            validate_finished_box_shade_composition(lines,1)

    def test_finished_box_rejects_missing_shade_and_insufficient_stock(self):
        lines=[{"item_variant_id":i,"brand_id":1,"shade_id":i,"available_pieces":2} for i in range(1,100)]
        with self.assertRaisesRegex(ValueError,"exactly 100 unique shades"):
            validate_finished_box_shade_composition(lines,1)
        lines=[{"item_variant_id":i,"brand_id":1,"shade_id":i,"available_pieces":1} for i in range(1,101)]
        with self.assertRaisesRegex(ValueError,"insufficient OWN stock"):
            validate_finished_box_shade_composition(lines,2)

    def test_packing_sources_are_process_stages_not_warehouse_locations(self):
        self.assertEqual(ELIGIBLE_PACKING_SOURCE_STAGE_CODES, ("NALKI", "LABELING"))

    def test_rejects_insufficient_own_source_stock(self):
        with self.assertRaisesRegex(ValueError, "Insufficient OWN Nalki stock"):
            validate_packing_source_quantity(100, 99)

    def test_accepts_exact_source_stock_quantity(self):
        self.assertIsNone(validate_packing_source_quantity(100, 100))


    def test_material_issue_arithmetic_and_over_issue(self):
        values = validate_packing_material_quantities(100, 70, 20, 10)
        self.assertEqual(values["issued"], 100)
        with self.assertRaisesRegex(ValueError, "cannot exceed issued"):
            validate_packing_material_quantities(100, 80, 15, 10)

    def test_empty_small_box_returns_cannot_exceed_issued_boxes(self):
        values = validate_packing_empty_box_return(10, 8, 2)
        self.assertEqual(values["good_returned"] + values["damaged_returned"], 10)
        with self.assertRaisesRegex(ValueError, "cannot exceed small boxes issued"):
            validate_packing_empty_box_return(10, 9, 2)

    def test_quality_status_and_quantity_limits(self):
        self.assertEqual(validate_packing_quality(100, 100, 0)["status"], "PASSED")
        self.assertEqual(validate_packing_quality(100, 90, 10)["status"], "PARTIAL")
        self.assertEqual(validate_packing_quality(100, 0, 100)["status"], "FAILED")
        with self.assertRaisesRegex(ValueError, "cannot exceed inspected"):
            validate_packing_quality(100, 95, 10)

    def test_wastage_requires_valid_type_positive_quantity_and_reason(self):
        values = validate_packing_wastage("label", "2", "Damaged label roll")
        self.assertEqual(values["wastage_type"], "LABEL")
        with self.assertRaisesRegex(ValueError, "reason is required"):
            validate_packing_wastage("LABEL", 1, " ")
        with self.assertRaisesRegex(ValueError, "valid packing wastage type"):
            validate_packing_wastage("UNKNOWN", 1, "Test")

    def test_packing_labour_is_box_based_and_non_negative(self):
        values = validate_packing_labour(10, "1.50")
        self.assertEqual(values["labour_amount"], 15)
        self.assertEqual(values["labour_type"], "PACKING")
        with self.assertRaisesRegex(ValueError, "cannot be negative"):
            validate_packing_labour(10, -1)

    def test_accepts_today_and_rejects_future_date(self):
        self.assertEqual(parse_packing_date(date.today().isoformat()), date.today())
        with self.assertRaisesRegex(ValueError, "future"):
            parse_packing_date((date.today() + timedelta(days=1)).isoformat())


if __name__ == "__main__":
    unittest.main()
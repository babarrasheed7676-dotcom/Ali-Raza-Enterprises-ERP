import unittest
from decimal import Decimal

from app.dyeing_draft_service import get_dyeing_approval_readiness


class FakeCursor:
    def __init__(self, replies):
        self.replies = list(replies)
        self.calls = []

    def execute(self, query, params=None):
        self.calls.append((query, params))

    def _pop(self, expected):
        if not self.replies:
            raise AssertionError("Unexpected cursor fetch; no fake response remains.")
        kind, value = self.replies.pop(0)
        if kind != expected:
            raise AssertionError(f"Expected {expected} response, received {kind}.")
        return value

    def fetchone(self):
        return self._pop("one")

    def fetchall(self):
        return self._pop("all")


def ready_replies(*, ownership_code="OWN", raw_batch=101, raw_available="10",
                  raw_cost="4", allocated="10", shade_exists=True,
                  output_variant_exact=True, output_batch=None,
                  chemical_batch=201, chemical_conversion="NOT_REQUIRED",
                  chemical_available="1", chemical_cost="2",
                  party_snapshot=True, party_request=501, party_rate="5",
                  party_cost="5", total_process_cost="80",
                  chemical_source_link=True):
    party = ownership_code == "PARTY"
    chemical = {
        "line_no": 1,
        "item_variant_id": 900,
        "source_material_line_id": 11 if chemical_source_link else None,
        "source_material_line_no": 1 if chemical_source_link else None,
        "batch_id": chemical_batch,
        "quantity": Decimal("1"),
        "unit_id": 1,
        "ownership_type_id": 2 if party else 1,
        "owner_party_id": 77 if party else None,
        "ownership_use_request_id": party_request if party else None,
        "ownership_locked_unit_rate": Decimal(party_rate) if party else None,
        "ownership_cost_total": Decimal(party_cost) if party else None,
        "ownership_cost_snapshot": {"rate": party_rate} if party and party_snapshot else None,
        "track_batch": True,
        "ownership_code": ownership_code,
        "conversion_status": chemical_conversion,
        "converted_quantity": Decimal("1"),
        "source_unit_code": "KG",
        "base_unit_code": "KG",
        "available_quantity": Decimal(chemical_available),
        "average_unit_cost": Decimal(chemical_cost) if chemical_cost is not None else None,
        "batch_no": "CHEM-001" if chemical_batch else None,
    }
    return [
        ("one", {"id": 10, "dyeing_no": "DY-TEST", "status": "DRAFT",
                 "total_process_cost": Decimal(total_process_cost)}),
        ("one", {"location_id": 9}),
        ("one", {"id": 1}),
        ("one", {"id": 1}),
        ("all", [{
            "id": 11, "line_no": 1, "item_variant_id": 5423,
            "batch_id": raw_batch, "quantity_kg": Decimal("10"),
            "item_code": "YARN", "variant_code": "YARN-40/2-COTTON",
            "available_quantity": Decimal(raw_available),
            "average_unit_cost": Decimal(raw_cost) if raw_cost is not None else None,
        }]),
        ("all", [{
            "id": 11, "line_no": 1, "quantity_kg": Decimal("10"),
            "allocated_quantity": Decimal(allocated),
        }]),
        ("all", [{
            "id": 21, "line_no": 1, "actual_shade_id": 2701,
            "shade_code": "3000", "shade_name": "Black",
            "yarn_count_id": 1, "fiber_type_id": 1, "brand_id": 1,
            "output_item_variant_id": 900,
            "output_batch_id": output_batch,
            "output_brand_id": 1 if output_variant_exact else None,
            "output_shade_id": 2701 if output_variant_exact else None,
            "output_yarn_count_id": 1, "output_fiber_type_id": 1,
            "output_item_code": "YARN",
            "shade_variant_exists": shade_exists,
            "output_variant_exact": output_variant_exact,
        }]),
        ("all", [chemical]),
    ]


class DyeingApprovalReadinessTests(unittest.TestCase):
    def test_missing_company_scoped_order_returns_none(self):
        cur = FakeCursor([("one", None)])
        self.assertIsNone(get_dyeing_approval_readiness(1, 999, cursor=cur))
        self.assertEqual(len(cur.calls), 1)

    def test_missing_batches_and_shade_variant_block_approval(self):
        replies = ready_replies(raw_batch=None, raw_available="0", raw_cost=None,
                                allocated="9", shade_exists=False,
                                output_variant_exact=False, chemical_batch=None,
                                chemical_available="0", chemical_cost=None)
        result = get_dyeing_approval_readiness(1, 10, cursor=FakeCursor(replies))
        self.assertFalse(result["ready"])
        self.assertEqual(result["status"], "BLOCKED")
        self.assertTrue(any("received OWN batch" in x for x in result["blockers"]))
        self.assertTrue(any("unused material or measured wastage" in x for x in result["blockers"]))
        self.assertTrue(any("configure an active YARN variant" in x for x in result["blockers"]))
        self.assertTrue(any("received batch" in x for x in result["blockers"]))
        self.assertFalse(result["stock_movement_performed"])

    def test_existing_variant_must_be_the_exact_saved_output_variant(self):
        replies = ready_replies(shade_exists=True, output_variant_exact=False)
        result = get_dyeing_approval_readiness(1, 10, cursor=FakeCursor(replies))
        self.assertFalse(result["ready"])
        self.assertTrue(any("DRAFT still points to the raw Yarn variant" in x
                            for x in result["blockers"]))

    def test_draft_output_batch_must_remain_blank_until_posting(self):
        replies = ready_replies(output_batch=888)
        result = get_dyeing_approval_readiness(1, 10, cursor=FakeCursor(replies))
        self.assertFalse(result["ready"])
        self.assertTrue(any("output batch must remain unassigned" in x
                            for x in result["blockers"]))

    def test_pending_conversion_blocks_chemical_issue(self):
        replies = ready_replies(chemical_conversion="PENDING_CONFIGURATION")
        result = get_dyeing_approval_readiness(1, 10, cursor=FakeCursor(replies))
        self.assertFalse(result["ready"])
        self.assertTrue(any("unit conversion status is PENDING_CONFIGURATION" in x
                            for x in result["blockers"]))

    def test_party_stock_uses_locked_rate_snapshot_not_own_average_cost(self):
        replies = ready_replies(
            ownership_code="PARTY", chemical_batch=201,
            chemical_available="1", chemical_cost=None,
            party_snapshot=True, party_request=501, party_rate="5.25",
            party_cost="5.25",
        )
        result = get_dyeing_approval_readiness(1, 10, cursor=FakeCursor(replies))
        self.assertTrue(result["ready"], result["blockers"])
        self.assertEqual(result["status"], "READY_FOR_APPROVAL")
        self.assertEqual(result["checks"]["chemical_lines_ready"], 1)
        self.assertFalse(result["stock_movement_performed"])

    def test_party_stock_without_locked_rate_snapshot_is_blocked(self):
        replies = ready_replies(
            ownership_code="PARTY", chemical_batch=201,
            chemical_available="1", chemical_cost=None,
            party_snapshot=False,
        )
        result = get_dyeing_approval_readiness(1, 10, cursor=FakeCursor(replies))
        self.assertFalse(result["ready"])
        self.assertTrue(any("PARTY use request, approval and locked-rate cost snapshot"
                            in x for x in result["blockers"]))

    def test_dye_chemical_line_must_link_to_exact_yarn_input(self):
        replies = ready_replies(chemical_source_link=False)
        result = get_dyeing_approval_readiness(1, 10, cursor=FakeCursor(replies))
        self.assertFalse(result["ready"])
        self.assertTrue(any("fiber-specific costing" in x for x in result["blockers"]))

    def test_zero_process_cost_is_a_warning_not_an_inferred_cost(self):
        replies = ready_replies(total_process_cost="0")
        result = get_dyeing_approval_readiness(1, 10, cursor=FakeCursor(replies))
        self.assertTrue(result["ready"], result["blockers"])
        self.assertEqual(len(result["warnings"]), 1)
        self.assertIn("Total process cost is zero", result["warnings"][0])


if __name__ == "__main__":
    unittest.main()
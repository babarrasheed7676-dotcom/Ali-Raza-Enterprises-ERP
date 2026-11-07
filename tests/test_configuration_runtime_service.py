import unittest
from decimal import Decimal
from datetime import date

from app.configuration_runtime_service import (
    SYSTEM_DEFAULT_NALKI_PACKAGING,
    validate_nalki_packaging_payload,
)


class NalkiPackagingConfigurationRuntimeTests(unittest.TestCase):
    def test_system_default_matches_two_distinct_packaging_levels(self):
        rule = validate_nalki_packaging_payload(SYSTEM_DEFAULT_NALKI_PACKAGING)
        self.assertEqual(rule["units_per_pack"], 100)
        self.assertEqual(rule["inner_packaging_code"], "PACK_BOX-STD")
        self.assertEqual(rule["inner_packs_per_pack"], 10)

    def test_approved_nalki_rule_accepts_exact_business_relationship(self):
        payload = dict(SYSTEM_DEFAULT_NALKI_PACKAGING)
        payload["effective_from"] = "2026-11-01"
        rule = validate_nalki_packaging_payload(payload)
        self.assertEqual(rule["product_code"], "NALKI")

    def test_wrong_finished_box_piece_count_fails_closed(self):
        payload = dict(SYSTEM_DEFAULT_NALKI_PACKAGING, units_per_pack=90)
        with self.assertRaisesRegex(ValueError, "exactly 100 pieces"):
            validate_nalki_packaging_payload(payload)

    def test_wrong_regular_box_code_fails_closed(self):
        payload = dict(SYSTEM_DEFAULT_NALKI_PACKAGING, inner_packaging_code="PACK_BOX-LARGE")
        with self.assertRaisesRegex(ValueError, "PACK_BOX-STD"):
            validate_nalki_packaging_payload(payload)

    def test_wrong_regular_box_count_fails_closed(self):
        payload = dict(SYSTEM_DEFAULT_NALKI_PACKAGING, inner_packs_per_pack=9)
        with self.assertRaisesRegex(ValueError, "exactly 10"):
            validate_nalki_packaging_payload(payload)

    def test_inactive_approved_rule_fails_closed(self):
        payload = dict(SYSTEM_DEFAULT_NALKI_PACKAGING, active=False)
        with self.assertRaisesRegex(ValueError, "inactive"):
            validate_nalki_packaging_payload(payload)

    def test_other_product_rule_cannot_be_used_for_nalki(self):
        payload = dict(SYSTEM_DEFAULT_NALKI_PACKAGING, product_type="Baby Cone")
        with self.assertRaisesRegex(ValueError, "product_type"):
            validate_nalki_packaging_payload(payload)


if __name__ == "__main__":
    unittest.main(verbosity=2)


class NalkiPackagingSnapshotResolutionTests(unittest.TestCase):
    class FakeCursor:
        def __init__(self, rows):
            self.rows = rows
            self.query = None
            self.params = None
        def execute(self, query, params):
            self.query = query
            self.params = params
        def fetchall(self):
            return self.rows

    def test_no_approved_version_uses_pinned_system_default(self):
        from app.configuration_runtime_service import resolve_nalki_packaging_snapshot
        target = date(2026, 11, 5)
        cur = self.FakeCursor([])
        result = resolve_nalki_packaging_snapshot(cur, company_id=1, effective_on=target)
        self.assertEqual(result["source"], "SYSTEM_DEFAULT")
        self.assertIsNone(result["configuration_version_id"])
        self.assertEqual(result["effective_on"], target)
        self.assertEqual(result["payload"]["units_per_pack"], 100)

    def test_approved_version_is_pinned_by_id_and_payload(self):
        from app.configuration_runtime_service import resolve_nalki_packaging_snapshot
        payload = dict(SYSTEM_DEFAULT_NALKI_PACKAGING)
        payload["effective_from"] = "2026-10-01"
        cur = self.FakeCursor([{
            "id": 44, "payload": payload,
            "effective_from": date(2026, 10, 1), "effective_to": None,
        }])
        result = resolve_nalki_packaging_snapshot(cur, company_id=1, effective_on=date(2026, 11, 5))
        self.assertEqual(result["source"], "APPROVED_VERSION")
        self.assertEqual(result["configuration_version_id"], 44)
        self.assertEqual(result["payload"]["inner_packaging_code"], "PACK_BOX-STD")

    def test_multiple_approved_matches_fail_closed(self):
        from app.configuration_runtime_service import resolve_nalki_packaging_snapshot
        rows = [{"id": 1, "payload": SYSTEM_DEFAULT_NALKI_PACKAGING},
                {"id": 2, "payload": SYSTEM_DEFAULT_NALKI_PACKAGING}]
        cur = self.FakeCursor(rows)
        with self.assertRaisesRegex(RuntimeError, "More than one"):
            resolve_nalki_packaging_snapshot(cur, company_id=1, effective_on=date(2026, 11, 5))

    def test_invalid_approved_payload_does_not_fall_back_to_default(self):
        from app.configuration_runtime_service import resolve_nalki_packaging_snapshot
        payload = dict(SYSTEM_DEFAULT_NALKI_PACKAGING, units_per_pack=90)
        cur = self.FakeCursor([{"id": 44, "payload": payload,
                                "effective_from": date(2026, 10, 1), "effective_to": None}])
        with self.assertRaisesRegex(ValueError, "exactly 100"):
            resolve_nalki_packaging_snapshot(cur, company_id=1, effective_on=date(2026, 11, 5))


class PurchaseConfigurationSnapshotResolutionTests(unittest.TestCase):
    class QueueCursor:
        def __init__(self, responses):
            self.responses = list(responses)
            self.calls = []
        def execute(self, query, params):
            self.calls.append((query, params))
        def fetchall(self):
            return self.responses.pop(0)

    def setUp(self):
        self.item = {"id": 4, "item_code": "NALKI", "item_name": "Nalki"}
        self.unit = {"id": 3, "code": "PCS", "name": "Piece", "decimal_places": 0}

    def test_missing_approved_rules_pin_exact_master_baselines(self):
        from app.configuration_runtime_service import resolve_purchase_line_configuration_snapshots
        cur = self.QueueCursor([[], []])
        snapshots = resolve_purchase_line_configuration_snapshots(
            cur, company_id=1, effective_on=date(2026, 11, 5),
            item_master=self.item, unit_master=self.unit,
        )
        self.assertEqual([s["config_type"] for s in snapshots],
                         ["PRODUCT_DEFINITION", "UNIT_DEFINITION"])
        self.assertTrue(all(s["source"] == "SYSTEM_DEFAULT_MASTER" for s in snapshots))
        self.assertEqual(snapshots[0]["payload"]["master_id"], 4)
        self.assertEqual(snapshots[1]["payload"]["code"], "PCS")

    def test_approved_product_and_unit_versions_are_pinned(self):
        from app.configuration_runtime_service import resolve_purchase_line_configuration_snapshots
        product = {"effective_from": "2026-11-01", "code": "NALKI",
                   "name": "Nalki Product", "product_type": "Nalki",
                   "attributes": {}, "active": True}
        unit = {"effective_from": "2026-11-01", "code": "PCS",
                "name": "Piece", "base_unit_code": "PCS", "factor_to_base": "1"}
        cur = self.QueueCursor([
            [{"id": 51, "payload": product}],
            [{"id": 52, "payload": unit}],
        ])
        snapshots = resolve_purchase_line_configuration_snapshots(
            cur, company_id=1, effective_on=date(2026, 11, 5),
            item_master=self.item, unit_master=self.unit,
        )
        self.assertEqual([s["configuration_version_id"] for s in snapshots], [51, 52])
        self.assertTrue(all(s["source"] == "APPROVED_VERSION" for s in snapshots))

    def test_approved_product_code_mismatch_fails_closed(self):
        from app.configuration_runtime_service import resolve_purchase_line_configuration_snapshots
        product = {"effective_from": "2026-11-01", "code": "OTHER",
                   "name": "Other", "product_type": "Other",
                   "attributes": {}, "active": True}
        cur = self.QueueCursor([[{"id": 51, "payload": product}]])
        with self.assertRaisesRegex(ValueError, "does not match"):
            resolve_purchase_line_configuration_snapshots(
                cur, company_id=1, effective_on=date(2026, 11, 5),
                item_master=self.item, unit_master=self.unit,
            )

    def test_unit_conversion_is_not_silently_applied_to_receipt(self):
        from app.configuration_runtime_service import resolve_purchase_line_configuration_snapshots
        unit = {"effective_from": "2026-11-01", "code": "PCS",
                "name": "Piece", "base_unit_code": "BOX", "factor_to_base": "10"}
        cur = self.QueueCursor([[], [{"id": 52, "payload": unit}]])
        with self.assertRaisesRegex(ValueError, "conversion is not enabled"):
            resolve_purchase_line_configuration_snapshots(
                cur, company_id=1, effective_on=date(2026, 11, 5),
                item_master=self.item, unit_master=self.unit,
            )

    def test_duplicate_effective_product_versions_fail_closed(self):
        from app.configuration_runtime_service import resolve_purchase_line_configuration_snapshots
        rows = [{"id": 51, "payload": {}}, {"id": 52, "payload": {}}]
        cur = self.QueueCursor([rows])
        with self.assertRaisesRegex(RuntimeError, "Multiple approved"):
            resolve_purchase_line_configuration_snapshots(
                cur, company_id=1, effective_on=date(2026, 11, 5),
                item_master=self.item, unit_master=self.unit,
            )


class BabyConeMeasurementProfileSnapshotTests(unittest.TestCase):
    class FakeCursor:
        def __init__(self, rows):
            self.rows = rows
            self.query = None
            self.params = None
        def execute(self, query, params):
            self.query, self.params = query, params
        def fetchall(self):
            return self.rows

    def profile(self, **overrides):
        payload = {
            "effective_from": "2026-11-01",
            "profile_code": "BABY-CONE-GPY",
            "variant_code": "BC-20",
            "method": "weight_per_length",
            "tolerance_percent": "2.5",
            "requires_operator": True,
            "requires_approval": True,
            "active": True,
        }
        payload.update(overrides)
        return {"id": 81, "payload": payload,
                "effective_from": date(2026, 11, 1), "effective_to": None}

    def resolve(self, rows):
        from app.configuration_runtime_service import resolve_baby_cone_measurement_profile_snapshot
        return resolve_baby_cone_measurement_profile_snapshot(
            self.FakeCursor(rows), company_id=1, effective_on=date(2026, 11, 6),
            config_key="BABY-CONE-WEIGHT-LENGTH", variant_code="BC-20",
        )

    def test_approved_profile_pins_exact_version_and_payload(self):
        result = self.resolve([self.profile()])
        self.assertEqual(result["config_type"], "MEASUREMENT_PROFILE")
        self.assertEqual(result["configuration_version_id"], 81)
        self.assertEqual(result["source"], "APPROVED_VERSION")
        self.assertEqual(result["payload"]["method"], "weight_per_length")
        self.assertTrue(result["payload"]["requires_approval"])

    def test_missing_approved_profile_fails_closed_without_default(self):
        with self.assertRaisesRegex(ValueError, "No approved"):
            self.resolve([])

    def test_duplicate_effective_profiles_fail_closed(self):
        with self.assertRaisesRegex(RuntimeError, "Multiple approved"):
            self.resolve([self.profile(), self.profile(id=82)])

    def test_variant_mismatch_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "does not match"):
            self.resolve([self.profile(variant_code="OTHER")])

    def test_wrong_method_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "weight_per_length"):
            self.resolve([self.profile(method="manual")])

    def test_inactive_profile_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "inactive"):
            self.resolve([self.profile(active=False)])


class BabyConeMeasurementDraftPersistenceTests(unittest.TestCase):
    class FakeCursor:
        def __init__(self, snapshot_row, saved_id=301):
            self.snapshot_row = snapshot_row
            self.saved_id = saved_id
            self.calls = []
            self.last = None
        def execute(self, query, params):
            self.calls.append((query, params))
            self.last = query
        def fetchone(self):
            if len(self.calls) == 1:
                return self.snapshot_row
            return {"id": self.saved_id}

    def snapshot(self, status="DRAFT", variant="BC-20"):
        return {
            "id": 81,
            "config_type": "MEASUREMENT_PROFILE",
            "configuration_version_id": 81,
            "source": "APPROVED_VERSION",
            "effective_on": date(2026, 11, 6),
            "payload_snapshot": {
                "profile_code": "BABY-CONE-GPY",
                "variant_code": variant,
                "method": "weight_per_length",
                "tolerance_percent": "2.5",
                "requires_operator": True,
                "requires_approval": True,
                "active": True,
            },
            "order_company_id": 1,
            "order_status": status,
            "variant_code": "BC-20",
        }

    def save(self, cursor, **overrides):
        from app.configuration_runtime_service import save_baby_cone_measurement_draft
        args = {
            "company_id": 1,
            "baby_cone_output_line_id": 12,
            "configuration_snapshot_id": 81,
            "user_id": 7,
            "gross_weight_grams": "120",
            "empty_core_tare_grams": "20",
            "measured_yards": "500",
            "operator_code": "OP-01",
            "required_yards": "2500",
        }
        args.update(overrides)
        return save_baby_cone_measurement_draft(cursor, **args)

    def test_draft_measurement_is_saved_with_exact_profile_and_calculation(self):
        cur = self.FakeCursor(self.snapshot())
        result = self.save(cur)
        self.assertEqual(result["measurement_id"], 301)
        self.assertEqual(result["required_yarn_kg"], Decimal("0.5"))
        self.assertEqual(cur.calls[1][1][0:3], (1, 12, 81))
        self.assertIn("ON CONFLICT (baby_cone_output_line_id)", cur.calls[1][0])

    def test_posted_order_cannot_receive_measurement(self):
        cur = self.FakeCursor(self.snapshot(status="POSTED"))
        with self.assertRaisesRegex(ValueError, "only be saved while"):
            self.save(cur)
        self.assertEqual(len(cur.calls), 1)

    def test_variant_mismatch_cannot_receive_measurement(self):
        cur = self.FakeCursor(self.snapshot(variant="OTHER"))
        with self.assertRaisesRegex(ValueError, "does not match"):
            self.save(cur)
        self.assertEqual(len(cur.calls), 1)

    def test_missing_profile_snapshot_cannot_receive_measurement(self):
        cur = self.FakeCursor(None)
        with self.assertRaisesRegex(ValueError, "snapshot/output line"):
            self.save(cur)
        self.assertEqual(len(cur.calls), 1)


class ProcessRouteSnapshotResolutionTests(unittest.TestCase):
    class FakeCursor:
        def __init__(self, rows):
            self.rows = rows
            self.calls = []
        def execute(self, query, params):
            self.calls.append((query, params))
        def fetchall(self):
            return self.rows

    def payload(self, **overrides):
        result = {
            "effective_from": "2026-11-01",
            "route_code": "NALKI-FROM-LARGE-CONE",
            "route_name": "Large Cone to Nalki",
            "product_type": "Nalki",
            "steps": [{
                "sequence_no": 1, "process_code": "NALKI_PRODUCTION",
                "input_product_type": "LARGE_CONE",
                "output_product_type": "NALKI", "optional": False,
            }],
            "active": True,
        }
        result.update(overrides)
        return result

    def test_approved_nalki_route_pins_version_and_payload(self):
        from app.configuration_runtime_service import resolve_process_route_snapshot
        payload = self.payload()
        cur = self.FakeCursor([{"id": 91, "payload": payload, "effective_from": date(2026, 11, 1), "effective_to": None}])
        result = resolve_process_route_snapshot(
            cur, company_id=1, effective_on=date(2026, 11, 6),
            config_key="NALKI-FROM-LARGE-CONE",
        )
        self.assertEqual(result["configuration_version_id"], 91)
        self.assertEqual(result["source"], "APPROVED_VERSION")
        self.assertEqual(result["payload"]["steps"][0]["input_product_type"], "LARGE_CONE")

    def test_payload_effective_date_must_match_approved_version(self):
        from app.configuration_runtime_service import resolve_process_route_snapshot
        payload = self.payload(effective_from="2026-10-01")
        cur = self.FakeCursor([{"id": 91, "payload": payload,
                                "effective_from": date(2026, 11, 1), "effective_to": None}])
        with self.assertRaisesRegex(ValueError, "effective date does not match"):
            resolve_process_route_snapshot(cur, company_id=1, effective_on=date(2026, 11, 6),
                                           config_key="NALKI-FROM-LARGE-CONE")

    def test_payload_end_date_must_match_approved_version(self):
        from app.configuration_runtime_service import resolve_process_route_snapshot
        payload = self.payload(effective_to="2026-12-31")
        cur = self.FakeCursor([{"id": 91, "payload": payload,
                                "effective_from": date(2026, 11, 1), "effective_to": None}])
        with self.assertRaisesRegex(ValueError, "end date does not match"):
            resolve_process_route_snapshot(cur, company_id=1, effective_on=date(2026, 11, 6),
                                           config_key="NALKI-FROM-LARGE-CONE")

    def test_missing_approved_route_fails_closed(self):
        from app.configuration_runtime_service import resolve_process_route_snapshot
        with self.assertRaisesRegex(ValueError, "No approved process route"):
            resolve_process_route_snapshot(
                self.FakeCursor([]), company_id=1, effective_on=date(2026, 11, 6),
                config_key="NALKI-FROM-LARGE-CONE",
            )

    def test_duplicate_effective_routes_fail_closed(self):
        from app.configuration_runtime_service import resolve_process_route_snapshot
        rows = [{"id": 91, "payload": self.payload(), "effective_from": date(2026, 11, 1), "effective_to": None}, {"id": 92, "payload": self.payload(), "effective_from": date(2026, 11, 1), "effective_to": None}]
        with self.assertRaisesRegex(RuntimeError, "Multiple approved"):
            resolve_process_route_snapshot(
                self.FakeCursor(rows), company_id=1, effective_on=date(2026, 11, 6),
                config_key="NALKI-FROM-LARGE-CONE",
            )

    def test_baby_cone_cannot_be_nalki_source(self):
        from app.configuration_runtime_service import validate_process_route_payload
        payload = self.payload(steps=[{
            "sequence_no": 1, "process_code": "NALKI_PRODUCTION",
            "input_product_type": "BABY_CONE",
            "output_product_type": "NALKI", "optional": False,
        }])
        with self.assertRaisesRegex(ValueError, "cannot use Baby Cone"):
            validate_process_route_payload(payload, config_key="NALKI-FROM-LARGE-CONE")

    def test_nalki_route_must_have_large_cone_to_nalki_step(self):
        from app.configuration_runtime_service import validate_process_route_payload
        payload = self.payload(steps=[{
            "sequence_no": 1, "process_code": "NALKI_PRODUCTION",
            "input_product_type": "RAW_THREAD",
            "output_product_type": "NALKI", "optional": False,
        }])
        with self.assertRaisesRegex(ValueError, "Large Cone to Nalki"):
            validate_process_route_payload(payload, config_key="NALKI-FROM-LARGE-CONE")

    def test_discontinuous_route_steps_are_rejected(self):
        from app.configuration_runtime_service import validate_process_route_payload
        payload = self.payload(steps=[
            {"sequence_no": 1, "process_code": "STEP1", "input_product_type": "A", "output_product_type": "B"},
            {"sequence_no": 2, "process_code": "STEP2", "input_product_type": "C", "output_product_type": "NALKI"},
        ])
        payload["product_type"] = "Other"
        with self.assertRaisesRegex(ValueError, "discontinuous"):
            validate_process_route_payload(payload, config_key="NALKI-FROM-LARGE-CONE")

    def test_inactive_route_is_rejected(self):
        from app.configuration_runtime_service import validate_process_route_payload
        with self.assertRaisesRegex(ValueError, "inactive"):
            validate_process_route_payload(self.payload(active=False), config_key="NALKI-FROM-LARGE-CONE")


class OwnershipPolicyRuntimeResolutionTests(unittest.TestCase):
    class FakeCursor:
        def __init__(self, rows): self.rows=rows; self.calls=[]
        def execute(self, query, params): self.calls.append((query,params))
        def fetchall(self): return self.rows

    def own_payload(self):
        return {"effective_from":"2026-11-01","product_type":"Nalki",
                "allowed_owners":["OWN"],"party_rate_required":False,
                "party_stock_requires_approval":False}

    def test_own_only_nalki_policy_is_valid(self):
        from app.configuration_runtime_service import validate_ownership_policy_payload
        result=validate_ownership_policy_payload(self.own_payload(),config_key="NALKI-OWNERSHIP")
        self.assertEqual(result["allowed_owners"],["OWN"])

    def test_party_requires_locked_rate_and_approval(self):
        from app.configuration_runtime_service import validate_ownership_policy_payload
        payload=self.own_payload(); payload.update(allowed_owners=["OWN","PARTY"],party_rate_required=False,party_stock_requires_approval=True)
        with self.assertRaisesRegex(Exception,"party-rate policy"):
            validate_ownership_policy_payload(payload,config_key="NALKI-OWNERSHIP")
        payload["party_rate_required"]=True; payload["party_stock_requires_approval"]=False
        with self.assertRaisesRegex(Exception,"approval policy"):
            validate_ownership_policy_payload(payload,config_key="NALKI-OWNERSHIP")

    def test_party_policy_with_both_controls_is_valid(self):
        from app.configuration_runtime_service import validate_ownership_policy_payload
        payload=self.own_payload(); payload.update(allowed_owners=["OWN","PARTY"],party_rate_required=True,party_stock_requires_approval=True)
        result=validate_ownership_policy_payload(payload,config_key="NALKI-OWNERSHIP")
        self.assertEqual(result["allowed_owners"],["OWN","PARTY"])

    def test_config_key_must_match_product_type(self):
        from app.configuration_runtime_service import validate_ownership_policy_payload
        with self.assertRaisesRegex(ValueError,"key must match"):
            validate_ownership_policy_payload(self.own_payload(),config_key="BABY-CONE-OWNERSHIP")

    def test_resolver_pins_approved_policy_version(self):
        from app.configuration_runtime_service import resolve_ownership_policy_snapshot
        cur=self.FakeCursor([{"id":55,"payload":self.own_payload()}])
        result=resolve_ownership_policy_snapshot(cur,company_id=1,effective_on=date(2026,11,6),config_key="NALKI-OWNERSHIP")
        self.assertEqual(result["configuration_version_id"],55)
        self.assertEqual(result["source"],"APPROVED_VERSION")

    def test_missing_approved_policy_fails_closed(self):
        from app.configuration_runtime_service import resolve_ownership_policy_snapshot
        with self.assertRaisesRegex(ValueError,"No approved ownership policy"):
            resolve_ownership_policy_snapshot(self.FakeCursor([]),company_id=1,effective_on=date(2026,11,6),config_key="NALKI-OWNERSHIP")

    def test_multiple_approved_policies_fail_closed(self):
        from app.configuration_runtime_service import resolve_ownership_policy_snapshot
        rows=[{"id":55,"payload":self.own_payload()},{"id":56,"payload":self.own_payload()}]
        with self.assertRaisesRegex(RuntimeError,"Multiple approved ownership policies"):
            resolve_ownership_policy_snapshot(self.FakeCursor(rows),company_id=1,effective_on=date(2026,11,6),config_key="NALKI-OWNERSHIP")

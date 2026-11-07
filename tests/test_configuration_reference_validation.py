import unittest

from app.configuration_service import _validate_configuration_references


class FakeCursor:
    def __init__(self, rows):
        self.rows = rows
        self.sql = ""
        self.params = None

    def execute(self, sql, params):
        self.sql = sql
        self.params = params

    def fetchall(self):
        return self.rows

    def fetchone(self):
        return self.rows[0] if self.rows else None


class ConfigurationReferenceValidationTests(unittest.TestCase):
    def test_measurement_profile_requires_active_baby_cone_variant(self):
        cur = FakeCursor([])
        with self.assertRaisesRegex(ValueError, "active variant under the BABY_CONE item"):
            _validate_configuration_references(
                cur, company_id=1, config_type="MEASUREMENT_PROFILE",
                payload={"variant_code": "BC-1500"},
            )
        self.assertIn("BABY_CONE", cur.sql)
        self.assertEqual(cur.params, (1, "BC-1500"))

    def test_measurement_profile_accepts_one_matching_variant(self):
        cur = FakeCursor([{"id": 42}])
        _validate_configuration_references(
            cur, company_id=1, config_type="MEASUREMENT_PROFILE",
            payload={"variant_code": "BC-1500"},
        )

    def test_measurement_profile_rejects_ambiguous_variant_code(self):
        cur = FakeCursor([{"id": 42}, {"id": 43}])
        with self.assertRaisesRegex(ValueError, "ambiguous"):
            _validate_configuration_references(
                cur, company_id=1, config_type="MEASUREMENT_PROFILE",
                payload={"variant_code": "BC-1500"},
            )

    def test_process_route_rejects_unknown_or_inactive_stage(self):
        cur = FakeCursor([{"code": "NALKI"}])
        payload = {"steps": [
            {"process_code": "NALKI"},
            {"process_code": "NALKI_PRODUCTION"},
        ]}
        with self.assertRaisesRegex(ValueError, "NALKI_PRODUCTION"):
            _validate_configuration_references(
                cur, company_id=1, config_type="PROCESS_ROUTE", payload=payload
            )
        self.assertEqual(cur.params, (1, ["NALKI", "NALKI_PRODUCTION"]))

    def test_process_route_accepts_actual_active_stage(self):
        cur = FakeCursor([{"code": "NALKI"}])
        _validate_configuration_references(
            cur, company_id=1, config_type="PROCESS_ROUTE",
            payload={"steps": [{"process_code": "NALKI"}]},
        )


    def test_process_cost_rule_rejects_unknown_or_inactive_stage(self):
        cur = FakeCursor([{"code": "DYEING"}])
        with self.assertRaisesRegex(ValueError, "UNKNOWN_STAGE"):
            _validate_configuration_references(
                cur, company_id=1, config_type="PROCESS_COST_RULE",
                payload={"process_code": "UNKNOWN_STAGE"},
            )
        self.assertEqual(cur.params, (1, ["UNKNOWN_STAGE"]))

    def test_process_cost_rule_accepts_active_stage(self):
        cur = FakeCursor([{"code": "DYEING"}])
        _validate_configuration_references(
            cur, company_id=1, config_type="PROCESS_COST_RULE",
            payload={"process_code": "DYEING"},
        )

    def test_ownership_policy_rejects_unknown_or_inactive_owner_type(self):
        cur = FakeCursor([{"code": "OWN"}])
        with self.assertRaisesRegex(ValueError, "PARTY"):
            _validate_configuration_references(
                cur, company_id=1, config_type="OWNERSHIP_POLICY",
                payload={"allowed_owners": ["OWN", "PARTY"]},
            )
        self.assertIn("master.ownership_types", cur.sql)
        self.assertEqual(cur.params, (["OWN", "PARTY"],))

    def test_ownership_policy_accepts_active_own_and_party_types(self):
        cur = FakeCursor([{"code": "OWN"}, {"code": "PARTY"}])
        _validate_configuration_references(
            cur, company_id=1, config_type="OWNERSHIP_POLICY",
            payload={"allowed_owners": ["OWN", "PARTY"]},
        )

    def test_ownership_policy_requires_at_least_one_owner_reference(self):
        cur = FakeCursor([])
        with self.assertRaisesRegex(ValueError, "at least one active ownership type"):
            _validate_configuration_references(
                cur, company_id=1, config_type="OWNERSHIP_POLICY",
                payload={"allowed_owners": []},
            )
        self.assertEqual(cur.sql, "")

    def test_packaging_rule_rejects_unknown_or_inactive_product_item(self):
        cur = FakeCursor([])
        with self.assertRaisesRegex(ValueError, "inactive product item: NOT_REAL"):
            _validate_configuration_references(
                cur, company_id=1, config_type="PACKAGING_RULE",
                payload={"product_code": "NOT_REAL"},
            )
        self.assertIn("master.items", cur.sql)
        self.assertEqual(cur.params, (1, "NOT_REAL"))

    def test_packaging_rule_accepts_active_product_item(self):
        cur = FakeCursor([{"item_code": "NALKI"}])
        _validate_configuration_references(
            cur, company_id=1, config_type="PACKAGING_RULE",
            payload={"product_code": "nalki"},
        )
        self.assertEqual(cur.params, (1, "NALKI"))

    def test_packaging_rule_rejects_unknown_or_inactive_base_unit(self):
        cur = FakeCursor([])
        with self.assertRaisesRegex(ValueError, "inactive base unit: UNKNOWN"):
            _validate_configuration_references(
                cur, company_id=1, config_type="PACKAGING_RULE",
                payload={"base_unit_code": "UNKNOWN"},
            )
        self.assertIn("master.units", cur.sql)
        self.assertEqual(cur.params, ("UNKNOWN",))

    def test_packaging_rule_accepts_active_base_unit(self):
        cur = FakeCursor([{"code": "PCS"}])
        _validate_configuration_references(
            cur, company_id=1, config_type="PACKAGING_RULE",
            payload={"base_unit_code": "pcs"},
        )
        self.assertEqual(cur.params, ("PCS",))

    def test_packaging_rule_allows_unlinked_generic_rule(self):
        cur = FakeCursor([])
        _validate_configuration_references(
            cur, company_id=1, config_type="PACKAGING_RULE",
            payload={"product_type": "Nalki"},
        )
        self.assertEqual(cur.sql, "")


if __name__ == "__main__":
    unittest.main(verbosity=2)

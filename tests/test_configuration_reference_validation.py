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

    def test_other_configuration_types_do_not_require_process_references(self):
        cur = FakeCursor([])
        _validate_configuration_references(
            cur, company_id=1, config_type="PACKAGING_RULE",
            payload={"product_type": "Nalki"},
        )
        self.assertEqual(cur.sql, "")


if __name__ == "__main__":
    unittest.main(verbosity=2)

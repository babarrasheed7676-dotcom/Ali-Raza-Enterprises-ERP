import unittest

from app.configuration_examples import get_configuration_examples
from app.configuration_service import validate_configuration_payload


class ConfigurationExampleTests(unittest.TestCase):
    def test_every_editor_example_passes_its_typed_payload_model(self):
        examples = get_configuration_examples()
        typed_examples = {key:value for key,value in examples.items() if key != "OWNERSHIP_POLICY_PRESETS"}
        self.assertEqual(len(typed_examples), 11)
        for config_type, example in typed_examples.items():
            with self.subTest(config_type=config_type):
                validated = validate_configuration_payload(config_type, example["payload"])
                self.assertEqual(validated["effective_from"], example["payload"]["effective_from"])

    def test_nalki_packaging_example_preserves_two_distinct_packaging_levels(self):
        payload = get_configuration_examples()["PACKAGING_RULE"]["payload"]
        self.assertEqual(payload["units_per_pack"], 100)
        self.assertEqual(payload["inner_packaging_code"], "PACK_BOX-STD")
        self.assertEqual(payload["inner_packs_per_pack"], 10)

    def test_nalki_ownership_example_does_not_enable_party_stock(self):
        payload = get_configuration_examples()["OWNERSHIP_POLICY"]["payload"]
        self.assertEqual(payload["allowed_owners"], ["OWN"])
        self.assertFalse(payload["party_rate_required"])
        self.assertFalse(payload["party_stock_requires_approval"])

    def test_ownership_policy_presets_are_separate_and_safe(self):
        from app.configuration_runtime_service import validate_ownership_policy_payload
        presets = get_configuration_examples()["OWNERSHIP_POLICY_PRESETS"]
        nalki = presets["NALKI"]
        dyeing = presets["DYEING"]
        self.assertEqual(nalki["key"], "NALKI-OWNERSHIP")
        self.assertEqual(nalki["payload"]["allowed_owners"], ["OWN"])
        self.assertEqual(dyeing["key"], "DYEING-OWNERSHIP")
        self.assertEqual(dyeing["payload"]["allowed_owners"], ["OWN", "PARTY"])
        self.assertTrue(dyeing["payload"]["party_rate_required"])
        self.assertTrue(dyeing["payload"]["party_stock_requires_approval"])
        validate_ownership_policy_payload(nalki["payload"], config_key=nalki["key"])
        validate_ownership_policy_payload(dyeing["payload"], config_key=dyeing["key"])

    def test_unit_conversion_example_uses_existing_master_unit_codes(self):
        from app.unit_conversion_service import unit_conversion_key
        payload = get_configuration_examples()["UNIT_CONVERSION"]["payload"]
        self.assertEqual(payload["from_unit_code"], "KG")
        self.assertEqual(payload["to_unit_code"], "G")
        self.assertEqual(unit_conversion_key(payload["from_unit_code"], payload["to_unit_code"]), "KG-TO-G")
        self.assertNotEqual(payload["to_unit_code"], "GRAM")

    def test_nalki_route_example_uses_large_cone_not_baby_cone(self):
        payload = get_configuration_examples()["PROCESS_ROUTE"]["payload"]
        self.assertEqual(payload["steps"][0]["input_product_type"], "LARGE_CONE")
        self.assertNotEqual(payload["steps"][0]["input_product_type"], "BABY_CONE")

    def test_baby_cone_approval_policy_targets_operational_measurement_profile(self):
        from app.configuration_rules import ConfigurationApprovalPolicy
        policy = get_configuration_examples()["APPROVAL_POLICY"]["payload"]
        self.assertEqual(policy["config_type"], "MEASUREMENT_PROFILE")
        self.assertEqual(policy["required_role_code"], "PRODUCTION_HEAD")
        validated = ConfigurationApprovalPolicy.model_validate(policy)
        self.assertEqual(validated.config_type, "MEASUREMENT_PROFILE")


if __name__ == "__main__":
    unittest.main(verbosity=2)
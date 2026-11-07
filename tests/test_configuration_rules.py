from datetime import date
from decimal import Decimal
import unittest

from pydantic import ValidationError
from app.configuration_rules import (
    BabyConeMeasurement,
    EffectivePeriod,
    OwnershipPolicy,
    PackagingRule,
    ProcessCostRule,
    AttributeDefinition,
    UnitConversion,
    MeasurementProfile,
    ProcessRoute,
    ProcessRouteStep,
    ConfigurationApprovalPolicy,
)


class ConfigurationRulesTests(unittest.TestCase):
    def test_effective_period_rejects_end_before_start(self):
        with self.assertRaises(ValidationError):
            EffectivePeriod(
                effective_from=date(2026, 10, 29),
                effective_to=date(2026, 10, 28),
            )

    def test_baby_cone_measurement_calculates_net_weight_and_yards(self):
        measurement = BabyConeMeasurement(
            effective_from=date(2026, 10, 29),
            variant_code="TEST-BC-01",
            gross_weight_grams=Decimal("120"),
            empty_core_tare_grams=Decimal("20"),
            measured_yards=Decimal("500"),
            measured_on=date(2026, 10, 29),
            operator_code="TEST-OP",
        )
        self.assertEqual(measurement.net_yarn_grams, Decimal("100"))
        self.assertEqual(measurement.grams_per_yard, Decimal("0.2"))

    def test_baby_cone_measurement_rejects_tare_equal_to_gross(self):
        with self.assertRaises(ValidationError):
            BabyConeMeasurement(
                effective_from=date(2026, 10, 29),
                variant_code="TEST-BC-01",
                gross_weight_grams=Decimal("20"),
                empty_core_tare_grams=Decimal("20"),
                measured_yards=Decimal("500"),
                measured_on=date(2026, 10, 29),
                operator_code="TEST-OP",
            )

    def test_party_ownership_requires_rate_and_approval(self):
        with self.assertRaises(ValidationError):
            OwnershipPolicy(
                effective_from=date(2026, 10, 29),
                product_type="Nalki",
                allowed_owners=["OWN", "PARTY"],
                party_rate_required=False,
                party_stock_requires_approval=True,
            )

    def test_packaging_rejects_zero_units_per_pack(self):
        with self.assertRaises(ValidationError):
            PackagingRule(
                effective_from=date(2026, 10, 29),
                product_type="Nalki",
                packaging_code="TEST-BOX",
                units_per_pack=0,
            )

    def test_process_cost_rejects_waste_above_100_percent(self):
        with self.assertRaises(ValidationError):
            ProcessCostRule(
                effective_from=date(2026, 10, 29),
                process_code="TEST-PROCESS",
                labour_method="theka",
                waste_allowance_percent=Decimal("101"),
            )


    def test_new_item_can_have_its_own_packaging_rule(self):
        rule = PackagingRule(
            effective_from=date(2026, 10, 30),
            product_type="NEW-PRODUCT-TYPE",
            product_code="NEW-ITEM-001",
            packaging_code="CARTON",
            base_unit_code="PIECE",
            units_per_pack=24,
        )
        self.assertEqual(rule.product_code, "NEW-ITEM-001")
        self.assertEqual(rule.units_per_pack, 24)

    def test_nested_packaging_accepts_matching_relationship_fields(self):
        rule = PackagingRule(
            effective_from=date(2026, 10, 30),
            product_type="Nalki",
            product_code="NALKI-TEST",
            packaging_code="FINISHED-BOX",
            units_per_pack=100,
            inner_packaging_code="SMALL-BOX",
            inner_packs_per_pack=10,
        )
        self.assertEqual(rule.inner_packaging_code, "SMALL-BOX")
        self.assertEqual(rule.inner_packs_per_pack, 10)

    def test_nested_packaging_rejects_missing_inner_pack_count(self):
        with self.assertRaises(ValidationError):
            PackagingRule(
                effective_from=date(2026, 10, 30),
                product_type="Nalki",
                packaging_code="FINISHED-BOX",
                units_per_pack=100,
                inner_packaging_code="SMALL-BOX",
            )

    def test_nested_packaging_rejects_missing_inner_pack_code(self):
        with self.assertRaises(ValidationError):
            PackagingRule(
                effective_from=date(2026, 10, 30),
                product_type="Nalki",
                packaging_code="FINISHED-BOX",
                units_per_pack=100,
                inner_packs_per_pack=10,
            )


    def test_choice_attribute_requires_unique_allowed_values(self):
        with self.assertRaises(ValidationError):
            AttributeDefinition(
                effective_from=date(2026, 11, 5),
                code="LIGHT",
                label="Light",
                data_type="choice",
                scope="variant",
            )

    def test_text_attribute_rejects_choice_values(self):
        with self.assertRaises(ValidationError):
            AttributeDefinition(
                effective_from=date(2026, 11, 5),
                code="NOTES",
                label="Notes",
                data_type="text",
                scope="product",
                allowed_values=["A", "B"],
            )

    def test_unit_conversion_rejects_same_source_and_target(self):
        with self.assertRaises(ValidationError):
            UnitConversion(
                effective_from=date(2026, 11, 5),
                from_unit_code="KG",
                to_unit_code="KG",
                factor=Decimal("1"),
            )

    def test_measurement_profile_accepts_weight_per_length(self):
        profile = MeasurementProfile(
            effective_from=date(2026, 11, 5),
            profile_code="BABY-CONE-GPY",
            variant_code="BC-TEST",
            method="weight_per_length",
            tolerance_percent=Decimal("2.5"),
            requires_approval=True,
        )
        self.assertTrue(profile.requires_approval)

    def test_process_route_requires_unique_ordered_steps(self):
        with self.assertRaises(ValidationError):
            ProcessRoute(
                effective_from=date(2026, 11, 5),
                route_code="ROUTE-1",
                route_name="Test route",
                product_type="Nalki",
                steps=[
                    ProcessRouteStep(
                        sequence_no=2,
                        process_code="PACK",
                        input_product_type="Nalki",
                        output_product_type="Finished Nalki",
                    ),
                    ProcessRouteStep(
                        sequence_no=1,
                        process_code="LABEL",
                        input_product_type="Nalki",
                        output_product_type="Labelled Nalki",
                    ),
                ],
            )

    def test_configuration_approval_policy_defaults_to_separation(self):
        policy = ConfigurationApprovalPolicy(
            effective_from=date(2026, 11, 5),
            config_type="BABY_CONE_MEASUREMENT",
            required_role_code="PRODUCTION_HEAD",
        )
        self.assertTrue(policy.separate_requester_approver)
        self.assertEqual(policy.minimum_approvals, 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
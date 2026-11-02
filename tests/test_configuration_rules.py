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


if __name__ == "__main__":
    unittest.main(verbosity=2)

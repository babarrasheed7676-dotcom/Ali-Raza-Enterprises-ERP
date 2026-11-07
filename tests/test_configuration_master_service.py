import unittest

from app.configuration_master_service import _bool, _positive_id, _text, save_configuration_master_record, _ALLOWED_TYPES, _shade_usage_from_category_code


class ConfigurationMasterValidationTests(unittest.TestCase):
    def test_additional_reference_master_types_are_allowlisted(self):
        self.assertTrue({"YARN_COUNT", "FIBER_TYPE", "SHADE_CATEGORY", "ITEM_CATEGORY", "ITEM"}.issubset(_ALLOWED_TYPES))

    def test_text_is_trimmed_and_enforces_required(self):
        self.assertEqual(_text("  Cotton  ", "Name", 20), "Cotton")
        with self.assertRaises(ValueError):
            _text(" ", "Name", 20)

    def test_text_enforces_schema_length(self):
        with self.assertRaises(ValueError):
            _text("x" * 51, "Brand code", 50)

    def test_boolean_parser_accepts_explicit_values_only(self):
        self.assertTrue(_bool(True))
        self.assertFalse(_bool("false"))
        with self.assertRaises(ValueError):
            _bool("maybe")

    def test_positive_id_rejects_zero_and_non_numeric(self):
        self.assertEqual(_positive_id("12", "Brand"), 12)
        for value in ("0", "-1", "abc", None):
            with self.subTest(value=value), self.assertRaises(ValueError):
                _positive_id(value, "Brand")

    def test_unsupported_type_rejected_before_database_access(self):
        with self.assertRaisesRegex(ValueError, "Unsupported master-data type"):
            save_configuration_master_record(
                record_type="PARTY", payload={}, user={"id": 1, "company_id": 1}, request=None
            )

    def test_master_payload_must_be_object(self):
        with self.assertRaisesRegex(ValueError, "JSON object"):
            save_configuration_master_record(
                record_type="BRAND", payload=[], user={"id": 1, "company_id": 1}, request=None
            )



class ShadeUsageClassificationTests(unittest.TestCase):
    def test_ladies_and_gents_are_not_common(self):
        self.assertEqual(_shade_usage_from_category_code("LADIES"), ("LADIES", False))
        self.assertEqual(_shade_usage_from_category_code("GENTS"), ("GENTS", False))

    def test_common_category_sets_legacy_common_flag(self):
        self.assertEqual(_shade_usage_from_category_code("COMMON"), ("COMMON", True))

    def test_unknown_shade_usage_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "Ladies, Gents or Common"):
            _shade_usage_from_category_code("FESTIVE")


if __name__ == "__main__":
    unittest.main(verbosity=2)


class ConfigurationVariantIdentityTests(unittest.TestCase):
    def test_nalki_variant_requires_brand_and_shade(self):
        from app.configuration_master_service import validate_variant_identity
        with self.assertRaisesRegex(ValueError, "brand and a shade"):
            validate_variant_identity(item_code="NALKI", brand_id=1, shade_id=None,
                                      shade_brand_id=None, yarn_count_id=None, fiber_type_id=None)

    def test_label_variant_rejects_mismatched_shade_brand(self):
        from app.configuration_master_service import validate_variant_identity
        with self.assertRaisesRegex(ValueError, "does not belong"):
            validate_variant_identity(item_code="LABEL", brand_id=1, shade_id=10,
                                      shade_brand_id=2, yarn_count_id=None, fiber_type_id=None)

    def test_shade_brand_is_derived_when_not_supplied(self):
        from app.configuration_master_service import validate_variant_identity
        self.assertEqual(validate_variant_identity(
            item_code="NALKI", brand_id=None, shade_id=10, shade_brand_id=2,
            yarn_count_id=None, fiber_type_id=None), 2)

    def test_yarn_requires_yarn_count_and_fiber(self):
        from app.configuration_master_service import validate_variant_identity
        with self.assertRaisesRegex(ValueError, "yarn count and fiber type"):
            validate_variant_identity(item_code="YARN", brand_id=None, shade_id=None,
                                      shade_brand_id=None, yarn_count_id=1, fiber_type_id=None)

    def test_yarn_variant_accepts_both_required_dimensions(self):
        from app.configuration_master_service import validate_variant_identity
        self.assertIsNone(validate_variant_identity(
            item_code="YARN", brand_id=None, shade_id=None, shade_brand_id=None,
            yarn_count_id=1, fiber_type_id=2))

    def test_generic_packaging_variant_needs_no_shade_or_yarn_attributes(self):
        from app.configuration_master_service import validate_variant_identity
        self.assertIsNone(validate_variant_identity(
            item_code="PACK_BOX", brand_id=None, shade_id=None, shade_brand_id=None,
            yarn_count_id=None, fiber_type_id=None))
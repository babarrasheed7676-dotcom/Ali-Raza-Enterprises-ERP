import unittest

from app.packing_assortment_service import (
    EXPECTED_ASSORTMENT_SHADES,
    normalize_assortment_shade_codes,
)


class PackingAssortmentRulesTests(unittest.TestCase):
    def test_accepts_exactly_100_unique_shades(self):
        codes = [str(n) for n in range(1, 101)]
        self.assertEqual(normalize_assortment_shade_codes(",".join(codes)), codes)
        self.assertEqual(len(normalize_assortment_shade_codes("\n".join(codes))), EXPECTED_ASSORTMENT_SHADES)

    def test_accepts_special_black_white_and_off_white_codes(self):
        codes = [str(n) for n in range(1, 98)] + ["3000", "3001", "3002"]
        self.assertEqual(len(normalize_assortment_shade_codes(" ".join(codes))), 100)

    def test_rejects_less_or_more_than_100_codes(self):
        with self.assertRaisesRegex(ValueError, "exactly 100"):
            normalize_assortment_shade_codes(",".join(str(n) for n in range(1, 100)))
        with self.assertRaisesRegex(ValueError, "exactly 100"):
            normalize_assortment_shade_codes(",".join(str(n) for n in range(1, 102)))

    def test_rejects_duplicate_shades(self):
        codes = [str(n) for n in range(1, 100)] + ["1"]
        with self.assertRaisesRegex(ValueError, "Duplicate shade"):
            normalize_assortment_shade_codes(",".join(codes))

    def test_rejects_shade_codes_outside_master_range(self):
        codes = [str(n) for n in range(1, 100)] + ["3003"]
        with self.assertRaisesRegex(ValueError, "Shade codes must"):
            normalize_assortment_shade_codes(",".join(codes))

    def test_rejects_non_numeric_shade_tokens(self):
        codes = [str(n) for n in range(1, 100)] + ["Black"]
        with self.assertRaisesRegex(ValueError, "Shade codes must"):
            normalize_assortment_shade_codes(",".join(codes))


if __name__ == "__main__":
    unittest.main()
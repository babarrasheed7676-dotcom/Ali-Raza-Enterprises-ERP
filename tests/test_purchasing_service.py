import unittest

from app.purchasing_service import (
    _normalize_supplier_invoice_no,
    _require_single_raw_store_location,
)


class TestPurchaseReceiptWarehouseResolution(unittest.TestCase):
    def test_one_raw_store_returns_its_inventory_location_id(self):
        self.assertEqual(_require_single_raw_store_location([{"id": 9}]), 9)

    def test_missing_raw_store_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "exactly one"):
            _require_single_raw_store_location([])

    def test_duplicate_raw_stores_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "exactly one"):
            _require_single_raw_store_location([{"id": 9}, {"id": 10}])


class TestSupplierInvoiceNormalization(unittest.TestCase):
    def test_trims_and_uppercases_invoice_number(self):
        self.assertEqual(_normalize_supplier_invoice_no("  inv-  0042  "), "INV- 0042")

    def test_collapses_repeated_whitespace(self):
        self.assertEqual(_normalize_supplier_invoice_no("ab\t  12\n"), "AB 12")

    def test_blank_invoice_is_optional(self):
        self.assertIsNone(_normalize_supplier_invoice_no("   "))

    def test_none_invoice_is_optional(self):
        self.assertIsNone(_normalize_supplier_invoice_no(None))


if __name__ == "__main__":
    unittest.main()
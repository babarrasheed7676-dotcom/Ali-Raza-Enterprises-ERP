import unittest
from app.permission_catalog import PERMISSIONS, ROLE_PERMISSIONS, validate_catalog


class ProductionPermissionRegressionTests(unittest.TestCase):
    def test_production_head_can_approve_and_post(self):
        grants = ROLE_PERMISSIONS["PRODUCTION_HEAD"]
        self.assertTrue({"production.view", "production.approve", "production.post"}.issubset(grants))

    def test_production_operator_cannot_approve_or_post(self):
        grants = ROLE_PERMISSIONS["PRODUCTION_OPERATOR"]
        self.assertTrue({"production.view", "production.create"}.issubset(grants))
        self.assertNotIn("production.approve", grants)
        self.assertNotIn("production.post", grants)

    def test_big_cone_uses_existing_shared_production_permissions(self):
        self.assertTrue({"production.create", "production.approve", "production.post"}.issubset(PERMISSIONS))
        self.assertFalse(any(code.startswith("big_cone.") for code in PERMISSIONS))

    def test_permission_catalog_is_consistent(self):
        self.assertEqual(validate_catalog(), [])


if __name__ == "__main__":
    unittest.main()

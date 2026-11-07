import inspect
import unittest
from unittest.mock import patch

from app.big_cone_draft_service import get_big_cone_readiness


class BigConeReadinessSafetyTests(unittest.TestCase):
    def test_invalid_ids_are_rejected_before_database_access(self):
        with patch("app.big_cone_draft_service.get_connection") as connection:
            with self.assertRaisesRegex(ValueError, "valid Big Cone document"):
                get_big_cone_readiness(1, 0)
            connection.assert_not_called()

    def test_negative_company_is_rejected_before_database_access(self):
        with patch("app.big_cone_draft_service.get_connection") as connection:
            with self.assertRaisesRegex(ValueError, "valid Big Cone document"):
                get_big_cone_readiness(-1, 10)
            connection.assert_not_called()

    def test_readiness_query_is_explicitly_read_only_and_has_no_write_sql(self):
        source = inspect.getsource(get_big_cone_readiness).upper()
        self.assertIn("SET TRANSACTION READ ONLY", source)
        for forbidden in ("INSERT INTO", "UPDATE ", "DELETE FROM", "FOR UPDATE"):
            self.assertNotIn(forbidden, source)

    def test_preflight_never_claims_measured_wastage_or_approval(self):
        source = inspect.getsource(get_big_cone_readiness)
        self.assertIn('"measured_wastage_kg": None', source)
        self.assertIn('"ready_for_approval": False', source)
        self.assertIn('"read_only": True', source)


if __name__ == "__main__":
    unittest.main()

from datetime import date
from pydantic import ValidationError
import unittest

from app.permission_catalog import ROLE_PERMISSIONS
from app.configuration_service import (
    validate_configuration_payload,
    get_configuration_version_detail,
    _date_ranges_overlap,
    _require_separate_approver,
    _supersession_end_date,
    _select_effective_configuration,
    _validate_unit_conversion_units,
)


class ConfigurationServiceValidationTests(unittest.TestCase):
    def test_valid_packaging_rule_is_normalized_for_json_storage(self):
        result = validate_configuration_payload(
            "PACKAGING_RULE",
            {
                "effective_from": "2026-11-05",
                "product_type": "Nalki",
                "packaging_code": "FINISHED-BOX",
                "units_per_pack": 100,
                "inner_packaging_code": "SMALL-BOX",
                "inner_packs_per_pack": 10,
            },
        )
        self.assertEqual(result["units_per_pack"], 100)
        self.assertEqual(result["effective_from"], "2026-11-05")

    def test_party_policy_requires_rate_and_approval(self):
        with self.assertRaises(ValidationError):
            validate_configuration_payload(
                "OWNERSHIP_POLICY",
                {
                    "effective_from": "2026-11-05",
                    "product_type": "Nalki",
                    "allowed_owners": ["OWN", "PARTY"],
                    "party_rate_required": True,
                    "party_stock_requires_approval": False,
                },
            )

    def test_unknown_configuration_type_is_rejected(self):
        with self.assertRaises(ValueError):
            validate_configuration_payload("ARBITRARY_SQL", {})

    def test_non_object_payload_is_rejected(self):
        with self.assertRaises(ValueError):
            validate_configuration_payload("UNIT_DEFINITION", ["KG", "GRAM"])


class ConfigurationApprovalGuardTests(unittest.TestCase):
    def test_configuration_permissions_are_exclusive_to_erp_admin(self):
        for role_code, permissions in ROLE_PERMISSIONS.items():
            config_permissions = {code for code in permissions if code.startswith("configuration.")}
            if role_code == "ERP_ADMIN":
                self.assertEqual(config_permissions, {
                    "configuration.view", "configuration.create",
                    "configuration.history.view", "configuration.approve",
                })
            else:
                self.assertEqual(config_permissions, set(), role_code)

    def test_creator_cannot_approve_own_draft(self):
        with self.assertRaisesRegex(ValueError, "creator cannot approve"):
            _require_separate_approver(7, 7)

    def test_different_admin_can_approve(self):
        _require_separate_approver(7, 8)

    def test_non_overlapping_adjacent_effective_ranges_are_allowed(self):
        self.assertFalse(_date_ranges_overlap(
            date(2026, 7, 1), date(2026, 12, 31),
            date(2027, 1, 1), None,
        ))

    def test_overlapping_effective_ranges_are_detected(self):
        self.assertTrue(_date_ranges_overlap(
            date(2026, 7, 1), None,
            date(2027, 1, 1), date(2027, 6, 30),
        ))

    def test_supersession_closes_prior_version_day_before_new_start(self):
        self.assertEqual(
            _supersession_end_date(date(2027, 1, 1), date(2026, 7, 1), None),
            date(2026, 12, 31),
        )

    def test_supersession_rejects_new_start_before_or_on_prior_start(self):
        with self.assertRaisesRegex(ValueError, "must start after"):
            _supersession_end_date(date(2026, 7, 1), date(2026, 7, 1), None)

    def test_supersession_rejects_already_ended_predecessor(self):
        with self.assertRaisesRegex(ValueError, "already ends before"):
            _supersession_end_date(date(2027, 1, 1), date(2026, 7, 1), date(2026, 12, 1))

    def test_effective_configuration_returns_single_approved_version(self):
        row = {"id": 12, "status": "APPROVED"}
        self.assertEqual(_select_effective_configuration([row]), row)

    def test_effective_configuration_returns_none_when_no_version_matches(self):
        self.assertIsNone(_select_effective_configuration([]))

    def test_effective_configuration_fails_closed_on_multiple_matches(self):
        with self.assertRaisesRegex(RuntimeError, "multiple APPROVED versions"):
            _select_effective_configuration([{"id": 12}, {"id": 13}])

    def test_open_ended_ranges_overlap(self):
        self.assertTrue(_date_ranges_overlap(
            date(2026, 7, 1), None,
            date(2026, 7, 1), None,
        ))


if __name__ == "__main__":
    unittest.main(verbosity=2)


class ConfigurationVersionDetailTests(unittest.TestCase):
    def test_detail_returns_payload_and_approval_audit_events_company_scoped(self):
        from unittest.mock import patch

        version = {
            "id": 7, "config_type": "PACKAGING_RULE", "config_key": "NALKI-BOX",
            "version_no": 1, "display_name": "Nalki box", "payload": {"units_per_pack": 100},
            "status": "PENDING", "effective_from": date(2026, 11, 5),
            "effective_to": None, "supersedes_version_id": None,
            "change_reason": "Initial setup", "created_by": 3, "created_at": None,
            "approved_by": None, "approved_at": None,
        }
        approvals = [{"decision": "SUBMITTED", "decided_by": 3, "comments": "Review"}]
        audits = [{"event_type": "SUBMITTED", "changed_by": 3, "reason": "Review"}]

        class FakeCursor:
            def __enter__(self):
                return self
            def __exit__(self, *args):
                return False
            def __init__(self):
                self.last_rows = []
                self.single = None
            def execute(self, query, params):
                self.params = params
                if "FROM configuration.config_versions" in query:
                    self.single = version
                elif "FROM configuration.config_approval_events" in query:
                    self.last_rows = approvals
                elif "FROM configuration.config_audit_events" in query:
                    self.last_rows = audits
            def fetchone(self):
                return self.single
            def fetchall(self):
                return self.last_rows

        class FakeConnection:
            def __init__(self):
                self.fake_cursor = FakeCursor()
            def __enter__(self):
                return self
            def __exit__(self, *args):
                return False
            def cursor(self):
                return self.fake_cursor

        connection = FakeConnection()
        with patch("app.configuration_service.get_connection", return_value=connection):
            result = get_configuration_version_detail(company_id=1, version_id=7)

        self.assertEqual(result["version"]["payload"]["units_per_pack"], 100)
        self.assertEqual(result["approval_events"], approvals)
        self.assertEqual(result["audit_events"], audits)
        self.assertEqual(connection.fake_cursor.params, (1, 7))

    def test_detail_returns_none_for_version_outside_company(self):
        from unittest.mock import patch

        class FakeCursor:
            def __enter__(self):
                return self
            def __exit__(self, *args):
                return False
            def execute(self, query, params):
                self.params = params
            def fetchone(self):
                return None
            def fetchall(self):
                return []

        class FakeConnection:
            def __init__(self):
                self.fake_cursor = FakeCursor()
            def __enter__(self):
                return self
            def __exit__(self, *args):
                return False
            def cursor(self):
                return self.fake_cursor

        connection = FakeConnection()
        with patch("app.configuration_service.get_connection", return_value=connection):
            result = get_configuration_version_detail(company_id=1, version_id=999)

        self.assertIsNone(result)
        self.assertEqual(connection.fake_cursor.params, (1, 999))


class ApprovalPolicyEnforcementUnitTests(unittest.TestCase):
    def test_required_role_is_enforced_case_insensitively(self):
        from app.configuration_service import _validate_approval_policy
        _validate_approval_policy(
            {"required_role_code": "PRODUCTION_HEAD", "minimum_approvals": 1},
            {"production_head"},
        )

    def test_wrong_role_is_rejected(self):
        from app.configuration_service import _validate_approval_policy
        with self.assertRaisesRegex(ValueError, "different approver role"):
            _validate_approval_policy(
                {"required_role_code": "PRODUCTION_HEAD", "minimum_approvals": 1},
                {"ERP_ADMIN"},
            )

    def test_multiple_approvals_are_allowed_when_role_is_satisfied(self):
        from app.configuration_service import _validate_approval_policy
        _validate_approval_policy(
            {"required_role_code": "ERP_ADMIN", "minimum_approvals": 2},
            {"ERP_ADMIN"},
        )

    def test_approval_count_requires_distinct_approvers(self):
        from app.configuration_service import _next_approval_count
        self.assertEqual(_next_approval_count([3], 4), 2)
        with self.assertRaisesRegex(ValueError, "already approved"):
            _next_approval_count([3, 4], 4)

    def test_approval_count_handles_duplicate_historical_rows_safely(self):
        from app.configuration_service import _next_approval_count
        self.assertEqual(_next_approval_count([3, 3, 4], 5), 3)

    def test_missing_required_role_fails_closed(self):
        from app.configuration_service import _validate_approval_policy
        with self.assertRaisesRegex(ValueError, "different approver role"):
            _validate_approval_policy(
                {"required_role_code": "ERP_ADMIN", "minimum_approvals": 1},
                set(),
            )


class ApprovalPolicySeparationTests(unittest.TestCase):
    def test_policy_cannot_disable_requester_approver_separation(self):
        from app.configuration_service import _validate_approval_policy
        with self.assertRaisesRegex(ValueError, "separation is mandatory"):
            _validate_approval_policy(
                {
                    "required_role_code": "ERP_ADMIN",
                    "minimum_approvals": 1,
                    "separate_requester_approver": False,
                },
                {"ERP_ADMIN"},
            )


class UnitConversionDimensionValidationTests(unittest.TestCase):
    class Cursor:
        def __init__(self, rows): self.rows=rows
        def execute(self, query, params): self.query=query; self.params=params
        def fetchall(self): return self.rows

    def test_active_units_with_same_dimension_are_accepted(self):
        cur=self.Cursor([
            {"code":"MG","unit_type":"WEIGHT","decimal_places":6,"is_active":True},
            {"code":"KG","unit_type":"WEIGHT","decimal_places":3,"is_active":True},
        ])
        _validate_unit_conversion_units(cur,{"from_unit_code":"MG","to_unit_code":"KG"})
        self.assertIn("FOR SHARE",cur.query)
        self.assertEqual(cur.params,(["MG","KG"],))

    def test_cross_dimension_conversion_is_rejected(self):
        cur=self.Cursor([
            {"code":"MG","unit_type":"WEIGHT","decimal_places":6,"is_active":True},
            {"code":"L","unit_type":"VOLUME","decimal_places":3,"is_active":True},
        ])
        with self.assertRaisesRegex(ValueError,"dimensions do not match"):
            _validate_unit_conversion_units(cur,{"from_unit_code":"MG","to_unit_code":"L"})

    def test_approval_precision_cannot_exceed_target_unit_storage(self):
        cur=self.Cursor([
            {"code":"MG","unit_type":"WEIGHT","decimal_places":6,"is_active":True},
            {"code":"KG","unit_type":"WEIGHT","decimal_places":3,"is_active":True},
        ])
        with self.assertRaisesRegex(ValueError,"exceeds target unit KG storage precision"):
            _validate_unit_conversion_units(
                cur,{"from_unit_code":"MG","to_unit_code":"KG","rounding_places":6},
                require_target_precision=True,
            )

    def test_inactive_or_missing_unit_is_rejected(self):
        cur=self.Cursor([{"code":"MG","unit_type":"WEIGHT","decimal_places":6,"is_active":True}])
        with self.assertRaisesRegex(ValueError,"both exist and be active"):
            _validate_unit_conversion_units(cur,{"from_unit_code":"MG","to_unit_code":"KG"})

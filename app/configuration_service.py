"""Company-scoped draft and approval workflow for governed configuration."""
from __future__ import annotations

from datetime import date
from typing import Any

from pydantic import ValidationError
from psycopg.types.json import Jsonb

from .configuration_rules import (
    ProductDefinition, UnitDefinition, PackagingRule, BabyConeMeasurement,
    OwnershipPolicy, ProcessCostRule, AttributeDefinition, UnitConversion,
    MeasurementProfile, ProcessRoute, ConfigurationApprovalPolicy,
)
from .db import get_connection

CONFIGURATION_MODELS = {
    "PRODUCT_DEFINITION": ProductDefinition,
    "UNIT_DEFINITION": UnitDefinition,
    "PACKAGING_RULE": PackagingRule,
    "BABY_CONE_MEASUREMENT": BabyConeMeasurement,
    "OWNERSHIP_POLICY": OwnershipPolicy,
    "PROCESS_COST_RULE": ProcessCostRule,
    "ATTRIBUTE_DEFINITION": AttributeDefinition,
    "UNIT_CONVERSION": UnitConversion,
    "MEASUREMENT_PROFILE": MeasurementProfile,
    "PROCESS_ROUTE": ProcessRoute,
    "APPROVAL_POLICY": ConfigurationApprovalPolicy,
}


def validate_configuration_payload(config_type: str, payload: dict) -> dict:
    model = CONFIGURATION_MODELS.get(config_type)
    if model is None:
        raise ValueError("Unsupported configuration type.")
    if not isinstance(payload, dict):
        raise ValueError("Configuration payload must be a JSON object.")
    validated = model.model_validate(payload)
    return validated.model_dump(mode="json")


def _date_ranges_overlap(start_a, end_a, start_b, end_b) -> bool:
    end_a = end_a or date.max
    end_b = end_b or date.max
    return start_a <= end_b and start_b <= end_a


def _supersession_end_date(new_start: date, prior_start: date, prior_end: date | None = None) -> date:
    if new_start <= prior_start:
        raise ValueError("A superseding version must start after the prior version's effective_from date.")
    if prior_end is not None and prior_end < new_start:
        raise ValueError("The selected approved version already ends before the new version starts.")
    from datetime import timedelta
    return new_start - timedelta(days=1)


def _require_separate_approver(created_by: int, approver_id: int) -> None:
    if int(created_by) == int(approver_id):
        raise ValueError("Separation of duties: the draft creator cannot approve or reject their own configuration.")


def _validate_approval_policy(policy_payload: dict, actor_role_codes: set[str]) -> None:
    """Fail closed when a configured approval policy cannot be satisfied."""
    required_role = str(policy_payload.get("required_role_code") or "").strip().upper()
    if not required_role or required_role not in {str(code).upper() for code in actor_role_codes}:
        raise ValueError("Approval blocked: the active configuration policy requires a different approver role.")
    if policy_payload.get("separate_requester_approver", True) is not True:
        raise ValueError(
            "Approval blocked: requester/approver separation is mandatory for configuration changes."
        )
    minimum_approvals = int(policy_payload.get("minimum_approvals", 1))
    if minimum_approvals < 1 or minimum_approvals > 5:
        raise ValueError("Approval blocked: minimum_approvals must be between 1 and 5.")


def _validate_unit_conversion_units(cur, payload: dict, *, require_target_precision: bool = False) -> None:
    """Require active source/target units with matching physical dimensions."""
    source = str(payload.get("from_unit_code") or "").strip().upper()
    target = str(payload.get("to_unit_code") or "").strip().upper()
    if not source or not target or source == target:
        raise ValueError("Unit conversion requires two different active units.")
    cur.execute(
        """SELECT code,unit_type,decimal_places,is_active FROM master.units
           WHERE code = ANY(%s) FOR SHARE""",
        ([source, target],),
    )
    rows = cur.fetchall()
    units = {str(row["code"]).upper(): dict(row) for row in rows}
    if set(units) != {source, target} or any(not units[code]["is_active"] for code in (source, target)):
        raise ValueError("Unit conversion source and target must both exist and be active in Units Master.")
    if str(units[source]["unit_type"]).upper() != str(units[target]["unit_type"]).upper():
        raise ValueError(
            f"Unit conversion dimensions do not match ({units[source]['unit_type']} vs {units[target]['unit_type']})."
        )
    if require_target_precision:
        rounding_places = int(payload.get("rounding_places", 3))
        target_places = int(units[target]["decimal_places"])
        if rounding_places > target_places:
            raise ValueError(
                f"Approval blocked: conversion rounding precision ({rounding_places}) exceeds target unit {target} storage precision ({target_places})."
            )



def _validate_configuration_references(cur, *, company_id: int, config_type: str, payload: dict) -> None:
    """Validate selected operational references against active company masters."""
    if config_type == "OWNERSHIP_POLICY":
        owner_codes = sorted({
            str(code or "").strip().upper()
            for code in payload.get("allowed_owners", [])
        })
        if not owner_codes or any(not code for code in owner_codes):
            raise ValueError("Ownership Policy must select at least one active ownership type.")
        cur.execute(
            """SELECT upper(code) AS code
               FROM master.ownership_types
               WHERE is_active IS TRUE AND upper(code)=ANY(%s)
               FOR SHARE""",
            (owner_codes,),
        )
        available = {str(row["code"]).upper() for row in cur.fetchall()}
        missing = sorted(set(owner_codes) - available)
        if missing:
            raise ValueError(
                "Ownership Policy references unknown or inactive ownership type(s): "
                + ", ".join(missing)
            )

    elif config_type == "PACKAGING_RULE":
        product_code = str(payload.get("product_code") or "").strip().upper()
        if product_code:
            cur.execute(
                """SELECT item_code
                   FROM master.items
                   WHERE company_id=%s AND upper(item_code)=%s
                     AND is_active IS TRUE
                   FOR SHARE""",
                (int(company_id), product_code),
            )
            if not cur.fetchone():
                raise ValueError(
                    "Packaging Rule references an unknown or inactive product item: "
                    + product_code
                )

        unit_code = str(payload.get("base_unit_code") or "").strip().upper()
        if unit_code:
            cur.execute(
                """SELECT code
                   FROM master.units
                   WHERE upper(code)=%s AND is_active IS TRUE
                   FOR SHARE""",
                (unit_code,),
            )
            if not cur.fetchone():
                raise ValueError(
                    "Packaging Rule references an unknown or inactive base unit: "
                    + unit_code
                )

    elif config_type == "MEASUREMENT_PROFILE":
        variant_code = str(payload.get("variant_code") or "").strip().upper()
        if not variant_code:
            raise ValueError("A real Baby Cone variant code is required.")
        cur.execute(
            """SELECT v.id
               FROM master.item_variants v
               JOIN master.items i ON i.id=v.item_id
               WHERE i.company_id=%s
                 AND upper(i.item_code)='BABY_CONE'
                 AND upper(v.variant_code)=%s
                 AND i.is_active IS TRUE AND v.is_active IS TRUE
               FOR SHARE OF v,i""",
            (int(company_id), variant_code),
        )
        matches = cur.fetchall()
        if len(matches) != 1:
            if not matches:
                raise ValueError(
                    "Measurement Profile must reference an existing active variant under the BABY_CONE item."
                )
            raise ValueError(
                "Measurement Profile variant code is ambiguous; use a unique active Baby Cone variant."
            )

    elif config_type in {"PROCESS_ROUTE", "PROCESS_COST_RULE"}:
        if config_type == "PROCESS_ROUTE":
            codes = sorted({
                str(step.get("process_code") or "").strip().upper()
                for step in payload.get("steps", [])
            })
            label = "Process route"
        else:
            codes = [str(payload.get("process_code") or "").strip().upper()]
            label = "Process cost rule"
        if not codes or any(not code for code in codes):
            raise ValueError(f"Every {label.lower()} must select an active process stage.")
        cur.execute(
            """SELECT upper(code) AS code
               FROM master.process_stages
               WHERE company_id=%s AND is_active IS TRUE
                 AND upper(code)=ANY(%s)
               FOR SHARE""",
            (int(company_id), codes),
        )
        available = {str(row["code"]).upper() for row in cur.fetchall()}
        missing = sorted(set(codes) - available)
        if missing:
            raise ValueError(
                f"{label} references unknown or inactive process stage(s): "
                + ", ".join(missing)
            )


def _next_approval_count(existing_approver_ids, actor_id: int) -> int:
    """Count distinct independent approvers and prevent duplicate votes."""
    approvers = {int(value) for value in existing_approver_ids}
    if int(actor_id) in approvers:
        raise ValueError("This approver has already approved this configuration version.")
    approvers.add(int(actor_id))
    return len(approvers)


def _enforce_config_approval_policy(cur, *, company_id: int, config_type: str, actor_id: int) -> dict | None:
    """Apply the effective APPROVAL_POLICY and return it for approval threshold handling."""
    cur.execute(
        """SELECT id,payload FROM configuration.config_versions
           WHERE company_id=%s AND config_type='APPROVAL_POLICY' AND status='APPROVED'
             AND effective_from<=CURRENT_DATE
             AND (effective_to IS NULL OR effective_to>=CURRENT_DATE)
             AND upper(payload->>'config_type')=upper(%s)
           ORDER BY id FOR SHARE""",
        (int(company_id), str(config_type)),
    )
    policies = cur.fetchall()
    if len(policies) > 1:
        raise ValueError("Approval blocked: multiple active approval policies match this configuration type.")
    if not policies:
        return
    policy = dict(policies[0])["payload"]
    cur.execute(
        """SELECT upper(r.code) AS code
           FROM core.user_roles ur
           JOIN core.roles r ON r.id=ur.role_id
           WHERE ur.user_id=%s AND r.company_id=%s AND r.is_active IS TRUE""",
        (int(actor_id), int(company_id)),
    )
    role_codes = {str(row["code"]).upper() for row in cur.fetchall()}
    _validate_approval_policy(dict(policy), role_codes)
    return dict(policy)


def create_configuration_draft(
    *, user: dict, config_type: str, config_key: str,
    display_name: str, payload: dict, change_reason: str,
    supersedes_version_id: int | None = None,
) -> dict:
    config_type = str(config_type).strip().upper()
    config_key = str(config_key).strip().upper()
    display_name = str(display_name).strip()
    change_reason = str(change_reason).strip()

    if not config_key or len(config_key) > 120:
        raise ValueError("Configuration key is required (maximum 120 characters).")
    if not display_name or len(display_name) > 160:
        raise ValueError("Display name is required (maximum 160 characters).")
    if not change_reason or len(change_reason) > 2000:
        raise ValueError("Change reason is required (maximum 2,000 characters).")

    validated_payload = validate_configuration_payload(config_type, payload)
    company_id, user_id = int(user["company_id"]), int(user["id"])
    if supersedes_version_id is not None:
        supersedes_version_id = int(supersedes_version_id)
        if supersedes_version_id <= 0:
            raise ValueError("Superseded version ID must be a positive integer.")

    with get_connection() as conn:
        with conn.transaction():
            with conn.cursor() as cur:
                if config_type == "UNIT_CONVERSION":
                    expected_key = f"{validated_payload['from_unit_code'].strip().upper()}-TO-{validated_payload['to_unit_code'].strip().upper()}"
                    if config_key != expected_key:
                        raise ValueError(f"Unit conversion key must be {expected_key} for the selected direction.")
                    _validate_unit_conversion_units(cur, validated_payload)
                _validate_configuration_references(
                    cur, company_id=company_id, config_type=config_type, payload=validated_payload
                )
                lock_key = f"{company_id}:{config_type}:{config_key}"
                cur.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))", (lock_key,))
                cur.execute(
                    """SELECT COALESCE(MAX(version_no), 0) + 1 AS next_version
                       FROM configuration.config_versions
                       WHERE company_id=%s AND config_type=%s AND config_key=%s""",
                    (company_id, config_type, config_key),
                )
                version_no = int(cur.fetchone()["next_version"])
                if supersedes_version_id is not None:
                    cur.execute(
                        """SELECT id,config_type,config_key,status,effective_from,effective_to
                           FROM configuration.config_versions
                           WHERE company_id=%s AND id=%s FOR SHARE""",
                        (company_id, supersedes_version_id),
                    )
                    prior = cur.fetchone()
                    if not prior or prior["status"] != "APPROVED":
                        raise ValueError("Only an APPROVED version in this company can be superseded.")
                    if prior["config_type"] != config_type or prior["config_key"] != config_key:
                        raise ValueError("The superseded version must have the same configuration type and key.")
                    _supersession_end_date(validated_payload["effective_from"], prior["effective_from"], prior["effective_to"])
                cur.execute(
                    """INSERT INTO configuration.config_versions
                       (company_id,config_type,config_key,version_no,display_name,
                        payload,status,effective_from,effective_to,change_reason,created_by,supersedes_version_id)
                       VALUES (%s,%s,%s,%s,%s,%s,'DRAFT',%s,%s,%s,%s,%s)
                       RETURNING id,version_no,status,effective_from,effective_to,created_at""",
                    (
                        company_id, config_type, config_key, version_no,
                        display_name, Jsonb(validated_payload),
                        validated_payload["effective_from"],
                        validated_payload.get("effective_to"),
                        change_reason, user_id, supersedes_version_id,
                    ),
                )
                row = dict(cur.fetchone())
                cur.execute(
                    """INSERT INTO configuration.config_audit_events
                       (company_id,config_version_id,config_type,config_key,
                        event_type,new_payload,changed_by,reason)
                       VALUES (%s,%s,%s,%s,'CREATED',%s,%s,%s)""",
                    (
                        company_id, row["id"], config_type, config_key,
                        Jsonb(validated_payload), user_id, change_reason,
                    ),
                )
    return row


def _get_locked_configuration_version(cur, company_id: int, version_id: int) -> dict:
    cur.execute(
        """SELECT id,company_id,config_type,config_key,version_no,payload,
                  status,effective_from,effective_to,change_reason,created_by,supersedes_version_id
           FROM configuration.config_versions
           WHERE company_id=%s AND id=%s
           FOR UPDATE""",
        (int(company_id), int(version_id)),
    )
    row = cur.fetchone()
    if not row:
        raise ValueError("Configuration version was not found in this company.")
    return dict(row)


def submit_configuration_for_approval(
    *, company_id: int, version_id: int, user: dict, comments: str = "",
) -> dict:
    actor_id = int(user["id"])
    comments = str(comments or "").strip()
    if len(comments) > 2000:
        raise ValueError("Submission comments cannot exceed 2,000 characters.")

    with get_connection() as conn:
        with conn.transaction():
            with conn.cursor() as cur:
                row = _get_locked_configuration_version(cur, company_id, version_id)
                if int(row["created_by"]) != actor_id:
                    raise ValueError("Only the draft creator can submit this configuration.")
                if row["status"] != "DRAFT":
                    raise ValueError("Only a DRAFT configuration can be submitted.")
                lock_key = f'{company_id}:{row["config_type"]}:{row["config_key"]}'
                cur.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))", (lock_key,))
                cur.execute(
                    """UPDATE configuration.config_versions
                       SET status='PENDING'
                       WHERE company_id=%s AND id=%s AND status='DRAFT'
                       RETURNING id,status""",
                    (int(company_id), int(version_id)),
                )
                updated = cur.fetchone()
                if not updated:
                    raise ValueError("Configuration status changed; refresh and try again.")
                reason = comments or "Submitted for configuration approval."
                cur.execute(
                    """INSERT INTO configuration.config_approval_events
                       (config_version_id,decision,decided_by,comments)
                       VALUES (%s,'SUBMITTED',%s,%s)""",
                    (int(version_id), actor_id, comments or None),
                )
                cur.execute(
                    """INSERT INTO configuration.config_audit_events
                       (company_id,config_version_id,config_type,config_key,
                        event_type,new_payload,changed_by,reason)
                       VALUES (%s,%s,%s,%s,'SUBMITTED',%s,%s,%s)""",
                    (
                        int(company_id), int(version_id), row["config_type"],
                        row["config_key"], Jsonb(row["payload"]), actor_id, reason,
                    ),
                )
    return {"id": int(version_id), "status": "PENDING"}


def approve_configuration(
    *, company_id: int, version_id: int, user: dict, comments: str = "",
) -> dict:
    actor_id = int(user["id"])
    comments = str(comments or "").strip()
    if len(comments) > 2000:
        raise ValueError("Approval comments cannot exceed 2,000 characters.")

    with get_connection() as conn:
        with conn.transaction():
            with conn.cursor() as cur:
                row = _get_locked_configuration_version(cur, company_id, version_id)
                if row["status"] != "PENDING":
                    raise ValueError("Only a PENDING configuration can be approved.")
                _require_separate_approver(row["created_by"], actor_id)
                if row["config_type"] == "UNIT_CONVERSION":
                    expected_key = f"{row['payload']['from_unit_code'].strip().upper()}-TO-{row['payload']['to_unit_code'].strip().upper()}"
                    if row["config_key"] != expected_key:
                        raise ValueError(f"Approval blocked: unit conversion key must be {expected_key}.")
                    _validate_unit_conversion_units(cur, row["payload"], require_target_precision=True)
                approval_policy = _enforce_config_approval_policy(
                    cur, company_id=int(company_id),
                    config_type=str(row["config_type"]), actor_id=actor_id,
                )
                required_approvals = int((approval_policy or {}).get("minimum_approvals", 1))
                lock_key = f'{company_id}:{row["config_type"]}:{row["config_key"]}'
                cur.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))", (lock_key,))
                cur.execute(
                    """SELECT decided_by FROM configuration.config_approval_events
                       WHERE config_version_id=%s AND decision='APPROVED'""",
                    (int(version_id),),
                )
                existing_approvers = [int(item["decided_by"]) for item in cur.fetchall()]
                approvals_received = _next_approval_count(existing_approvers, actor_id)
                predecessor = None
                if row.get("supersedes_version_id") is not None:
                    cur.execute(
                        """SELECT id,payload,effective_from,effective_to,status
                           FROM configuration.config_versions
                           WHERE company_id=%s AND id=%s AND config_type=%s AND config_key=%s
                           FOR UPDATE""",
                        (int(company_id), int(row["supersedes_version_id"]), row["config_type"], row["config_key"]),
                    )
                    predecessor = cur.fetchone()
                    if not predecessor or predecessor["status"] != "APPROVED":
                        raise ValueError("The selected predecessor is no longer APPROVED; refresh and create a new draft.")
                    _supersession_end_date(row["effective_from"], predecessor["effective_from"], predecessor["effective_to"])
                excluded_ids = [int(version_id)]
                if predecessor:
                    excluded_ids.append(int(predecessor["id"]))
                cur.execute(
                    """SELECT effective_from,effective_to
                       FROM configuration.config_versions
                       WHERE company_id=%s AND config_type=%s AND config_key=%s
                         AND status='APPROVED' AND id <> ALL(%s)
                       FOR UPDATE""",
                    (int(company_id), row["config_type"], row["config_key"], excluded_ids),
                )
                for existing in cur.fetchall():
                    if _date_ranges_overlap(
                        row["effective_from"], row["effective_to"],
                        existing["effective_from"], existing["effective_to"],
                    ):
                        raise ValueError(
                            "Approval blocked: effective dates overlap another APPROVED version. "
                            "Set non-overlapping dates before resubmitting."
                        )
                cur.execute(
                    """INSERT INTO configuration.config_approval_events
                       (config_version_id,decision,decided_by,comments)
                       VALUES (%s,'APPROVED',%s,%s)""",
                    (int(version_id), actor_id, comments or None),
                )
                if approvals_received < required_approvals:
                    return {
                        "id": int(version_id), "status": "PENDING",
                        "approvals_received": approvals_received,
                        "approvals_required": required_approvals,
                    }
                cur.execute(
                    """UPDATE configuration.config_versions
                       SET status='APPROVED',approved_by=%s,approved_at=CURRENT_TIMESTAMP
                       WHERE company_id=%s AND id=%s AND status='PENDING'
                       RETURNING id,status,approved_at""",
                    (actor_id, int(company_id), int(version_id)),
                )
                updated = cur.fetchone()
                if not updated:
                    raise ValueError("Configuration status changed; refresh and try again.")
                reason = comments or "Configuration approved after independent review."
                if predecessor:
                    prior_end = _supersession_end_date(row["effective_from"], predecessor["effective_from"], predecessor["effective_to"])
                    cur.execute(
                        """UPDATE configuration.config_versions
                           SET status='RETIRED',effective_to=%s
                           WHERE company_id=%s AND id=%s AND status='APPROVED'
                           RETURNING id""",
                        (prior_end, int(company_id), int(predecessor["id"])),
                    )
                    if not cur.fetchone():
                        raise ValueError("The predecessor changed during approval; refresh and retry.")
                    cur.execute(
                        """INSERT INTO configuration.config_audit_events
                           (company_id,config_version_id,config_type,config_key,
                            event_type,old_payload,new_payload,changed_by,reason)
                           VALUES (%s,%s,%s,%s,'SUPERSEDED',%s,%s,%s,%s)""",
                        (int(company_id), int(predecessor["id"]), row["config_type"],
                         row["config_key"], Jsonb(predecessor["payload"]),
                         Jsonb(predecessor["payload"]), actor_id,
                         f"Superseded by configuration version {int(version_id)} effective {row['effective_from']}."),
                    )
                cur.execute(
                    """INSERT INTO configuration.config_audit_events
                       (company_id,config_version_id,config_type,config_key,
                        event_type,old_payload,new_payload,changed_by,reason)
                       VALUES (%s,%s,%s,%s,'APPROVED',%s,%s,%s,%s)""",
                    (
                        int(company_id), int(version_id), row["config_type"],
                        row["config_key"], Jsonb(row["payload"]), Jsonb(row["payload"]),
                        actor_id, reason,
                    ),
                )
    return {"id": int(version_id), "status": "APPROVED", "approvals_received": approvals_received, "approvals_required": required_approvals}


def reject_configuration(
    *, company_id: int, version_id: int, user: dict, comments: str,
) -> dict:
    actor_id = int(user["id"])
    comments = str(comments or "").strip()
    if len(comments) < 5 or len(comments) > 2000:
        raise ValueError("Rejection reason is required (5–2,000 characters).")

    with get_connection() as conn:
        with conn.transaction():
            with conn.cursor() as cur:
                row = _get_locked_configuration_version(cur, company_id, version_id)
                if row["status"] != "PENDING":
                    raise ValueError("Only a PENDING configuration can be rejected.")
                _require_separate_approver(row["created_by"], actor_id)
                _enforce_config_approval_policy(
                    cur, company_id=int(company_id),
                    config_type=str(row["config_type"]), actor_id=actor_id,
                )
                lock_key = f'{company_id}:{row["config_type"]}:{row["config_key"]}'
                cur.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))", (lock_key,))
                cur.execute(
                    """UPDATE configuration.config_versions
                       SET status='REJECTED'
                       WHERE company_id=%s AND id=%s AND status='PENDING'
                       RETURNING id,status""",
                    (int(company_id), int(version_id)),
                )
                updated = cur.fetchone()
                if not updated:
                    raise ValueError("Configuration status changed; refresh and try again.")
                cur.execute(
                    """INSERT INTO configuration.config_approval_events
                       (config_version_id,decision,decided_by,comments)
                       VALUES (%s,'REJECTED',%s,%s)""",
                    (int(version_id), actor_id, comments),
                )
                cur.execute(
                    """INSERT INTO configuration.config_audit_events
                       (company_id,config_version_id,config_type,config_key,
                        event_type,old_payload,new_payload,changed_by,reason)
                       VALUES (%s,%s,%s,%s,'REJECTED',%s,%s,%s,%s)""",
                    (
                        int(company_id), int(version_id), row["config_type"],
                        row["config_key"], Jsonb(row["payload"]), Jsonb(row["payload"]),
                        actor_id, comments,
                    ),
                )
    return {"id": int(version_id), "status": "REJECTED"}


def _select_effective_configuration(rows) -> dict | None:
    rows = list(rows)
    if len(rows) > 1:
        raise RuntimeError("Configuration integrity error: multiple APPROVED versions are effective for the same key and date.")
    return dict(rows[0]) if rows else None


def get_effective_configuration(
    *, company_id: int, config_type: str, config_key: str, effective_on: date,
) -> dict | None:
    config_type = str(config_type).strip().upper()
    config_key = str(config_key).strip().upper()
    if config_type not in CONFIGURATION_MODELS:
        raise ValueError("Unsupported configuration type.")
    if not config_key or len(config_key) > 120:
        raise ValueError("Configuration key is required (maximum 120 characters).")
    if not isinstance(effective_on, date):
        raise ValueError("A valid effective date is required.")
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT id,config_type,config_key,version_no,display_name,payload,
                          effective_from,effective_to,approved_by,approved_at
                   FROM configuration.config_versions
                   WHERE company_id=%s AND config_type=%s AND config_key=%s
                     AND status='APPROVED'
                     AND effective_from <= %s
                     AND (effective_to IS NULL OR effective_to >= %s)
                   ORDER BY version_no DESC
                   LIMIT 2""",
                (int(company_id), config_type, config_key, effective_on, effective_on),
            )
            return _select_effective_configuration(cur.fetchall())


def list_configuration_history(*, company_id: int, limit: int = 100) -> list[dict]:
    limit = max(1, min(int(limit), 200))
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT id,config_type,config_key,version_no,display_name,
                          status,effective_from,effective_to,supersedes_version_id,change_reason,
                          created_by,created_at,approved_by,approved_at
                   FROM configuration.config_versions
                   WHERE company_id=%s
                   ORDER BY created_at DESC,id DESC
                   LIMIT %s""",
                (int(company_id), limit),
            )
            return [dict(row) for row in cur.fetchall()]


def get_configuration_version_detail(*, company_id: int, version_id: int) -> dict | None:
    """Return a version's immutable payload and company-scoped decision/audit trail."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT id,config_type,config_key,version_no,display_name,payload,
                          status,effective_from,effective_to,supersedes_version_id,
                          change_reason,created_by,created_at,approved_by,approved_at
                   FROM configuration.config_versions
                   WHERE company_id=%s AND id=%s""",
                (int(company_id), int(version_id)),
            )
            version = cur.fetchone()
            if not version:
                return None
            version = dict(version)
            cur.execute(
                """SELECT decision,decided_by,decided_at,comments
                   FROM configuration.config_approval_events
                   WHERE config_version_id=%s
                   ORDER BY decided_at,id""",
                (int(version_id),),
            )
            approvals = [dict(row) for row in cur.fetchall()]
            cur.execute(
                """SELECT event_type,old_payload,new_payload,changed_by,changed_at,reason
                   FROM configuration.config_audit_events
                   WHERE company_id=%s AND config_version_id=%s
                   ORDER BY changed_at,id""",
                (int(company_id), int(version_id)),
            )
            audit = [dict(row) for row in cur.fetchall()]
    return {"version": version, "approval_events": approvals, "audit_events": audit}

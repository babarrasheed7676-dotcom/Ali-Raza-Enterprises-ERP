"""Safe, typed starter payloads for the Configuration UI.

Examples are editable drafts only. Loading an example never writes to the DB
or activates an operational rule.
"""
from datetime import date


def get_configuration_examples() -> dict:
    today = date.today().isoformat()
    return {
        "PRODUCT_DEFINITION": {
            "label": "Product definition",
            "help": "Create a reusable product definition. This does not create a live item or variant.",
            "key": "NEW-PRODUCT-CODE",
            "name": "New product definition",
            "payload": {
                "effective_from": today,
                "code": "NEW-PRODUCT-CODE",
                "name": "New product",
                "product_type": "NEW-PRODUCT-TYPE",
                "attributes": {},
                "active": True,
            },
        },
        "UNIT_DEFINITION": {
            "label": "Unit definition",
            "help": "Define a unit and its factor to a base unit. Confirm unit codes before approval.",
            "key": "NEW-UNIT",
            "name": "New unit",
            "payload": {
                "effective_from": today,
                "code": "NEW-UNIT",
                "name": "New unit",
                "base_unit_code": None,
                "factor_to_base": "1",
            },
        },
        "PACKAGING_RULE": {
            "label": "Packaging rule",
            "help": "Nalki reference: 10 pieces per regular small box; 10 small boxes (100 pieces) per separate finished wall box. Draft example only.",
            "key": "NALKI-FINISHED-WALL-BOX",
            "name": "Nalki finished wall box",
            "payload": {
                "effective_from": today,
                "product_type": "Nalki",
                "product_code": "NALKI",
                "packaging_code": "FINISHED-WALL-BOX",
                "base_unit_code": "PCS",
                "units_per_pack": 100,
                "inner_packaging_code": "PACK_BOX-STD",
                "inner_packs_per_pack": 10,
                "net_weight_grams": None,
                "active": True,
            },
        },
        "BABY_CONE_MEASUREMENT": {
            "label": "Baby Cone measurement",
            "help": "Enter a real measured variant, gross weight, empty-core tare, measured yards and operator. Example numbers are placeholders.",
            "key": "BABY-CONE-MEASUREMENT-EXAMPLE",
            "name": "Baby Cone measurement example",
            "payload": {
                "effective_from": today,
                "variant_code": "REPLACE-WITH-REAL-VARIANT",
                "gross_weight_grams": "120",
                "empty_core_tare_grams": "20",
                "measured_yards": "500",
                "measured_on": today,
                "operator_code": "REPLACE-WITH-OPERATOR",
            },
        },
        "OWNERSHIP_POLICY": {
            "label": "Ownership policy",
            "help": "Nalki starter policy is OWN only. PARTY is intentionally not enabled; do not add it without the owner's explicit policy decision.",
            "key": "NALKI-OWNERSHIP",
            "name": "Nalki ownership policy",
            "payload": {
                "effective_from": today,
                "product_type": "Nalki",
                "allowed_owners": ["OWN"],
                "party_rate_required": False,
                "party_stock_requires_approval": False,
            },
        },
        "OWNERSHIP_POLICY_PRESETS": {
            "NALKI": {
                "label": "Nalki ? OWN only",
                "help": "Nalki stock remains ARE-owned by default. PARTY stock is not enabled in this preset.",
                "key": "NALKI-OWNERSHIP",
                "name": "Nalki ownership policy",
                "payload": {
                    "effective_from": today,
                    "product_type": "Nalki",
                    "allowed_owners": ["OWN"],
                    "party_rate_required": False,
                    "party_stock_requires_approval": False,
                },
            },
            "DYEING": {
                "label": "Dyeing ? OWN + controlled PARTY",
                "help": "Dyeing may use OWN or PARTY stock. PARTY requires a separately approved request and a locked PKR rate; no stock is posted by this policy.",
                "key": "DYEING-OWNERSHIP",
                "name": "Dyeing ownership policy",
                "payload": {
                    "effective_from": today,
                    "product_type": "Dyeing",
                    "allowed_owners": ["OWN", "PARTY"],
                    "party_rate_required": True,
                    "party_stock_requires_approval": True,
                },
            },
        },
        "PROCESS_COST_RULE": {
            "label": "Process cost rule",
            "help": "Salary/theka method by process. Theka is for Nalki work only; do not apply it to Baby Cone salary.",
            "key": "NALKI-PACKING-COST",
            "name": "Nalki packing labour method",
            "payload": {
                "effective_from": today,
                "process_code": "NALKI_PACKING",
                "labour_method": "theka",
                "waste_allowance_percent": "0",
                "active": True,
            },
        },
        "ATTRIBUTE_DEFINITION": {
            "label": "Attribute definition",
            "help": "Define typed attributes. Nalki light grades can use A, B, C and D as controlled choices.",
            "key": "LIGHT-GRADE",
            "name": "Light grade",
            "payload": {
                "effective_from": today,
                "code": "LIGHT",
                "label": "Light grade",
                "data_type": "choice",
                "scope": "variant",
                "required": False,
                "allowed_values": ["A", "B", "C", "D"],
                "decimal_places": 3,
                "active": True,
            },
        },
        "UNIT_CONVERSION": {
            "label": "Unit conversion",
            "help": "Directed conversion example. Verify both unit codes exist and the factor is correct before approval.",
            "key": "KG-TO-G",
            "name": "Kilogram to gram",
            "payload": {
                "effective_from": today,
                "from_unit_code": "KG",
                "to_unit_code": "G",
                "factor": "1000",
                "rounding_places": 3,
                "active": True,
            },
        },
        "MEASUREMENT_PROFILE": {
            "label": "Measurement profile",
            "help": "Baby Cone currently supports the measured weight_per_length method only. Piece-weight and manual methods are not enabled until their measurement schema and workflow are implemented. Replace the placeholder variant code and confirm the real tolerance; this starter creates only an editable DRAFT example and assumes no production weight.",
            "key": "BABY-CONE-WEIGHT-LENGTH",
            "name": "Baby Cone weight and length profile",
            "payload": {
                "effective_from": today,
                "profile_code": "BABY-CONE-GPY",
                "variant_code": "REPLACE-WITH-REAL-VARIANT",
                "method": "weight_per_length",
                "tolerance_percent": "2.5",
                "requires_operator": True,
                "requires_approval": True,
                "active": True,
            },
        },
        "PROCESS_ROUTE": {
            "label": "Process route",
            "help": "Nalki production must originate from Large Cone, never Baby Cone. Review actual process codes before approving.",
            "key": "NALKI-FROM-LARGE-CONE",
            "name": "Nalki from Large Cone route",
            "payload": {
                "effective_from": today,
                "route_code": "NALKI-FROM-LARGE-CONE",
                "route_name": "Large Cone to Nalki",
                "product_type": "Nalki",
                "steps": [
                    {
                        "sequence_no": 1,
                        "process_code": "NALKI",
                        "input_product_type": "LARGE_CONE",
                        "output_product_type": "NALKI",
                        "optional": False,
                    }
                ],
                "active": True,
            },
        },
        "APPROVAL_POLICY": {
            "label": "Approval policy",
            "help": "Baby Cone Measurement Profile changes require Production Head review. The workflow still enforces independent ERP Administrator approval.",
            "key": "BABY-CONE-MEASUREMENT-APPROVAL",
            "name": "Baby Cone measurement profile approval",
            "payload": {
                "effective_from": today,
                "config_type": "MEASUREMENT_PROFILE",
                "required_role_code": "PRODUCTION_HEAD",
                "minimum_approvals": 1,
                "separate_requester_approver": True,
                "active": True,
            },
        },
    }

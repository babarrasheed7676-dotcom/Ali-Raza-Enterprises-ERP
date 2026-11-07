"""Central permission and role catalog for Ali Raza Enterprises ERP.

Design-only catalog. Does not seed or modify database records.
"""

PERMISSIONS = {
    "assistant.query": ("Assistant", "Use the read-only ERP assistant"),

    "inventory.view": ("Inventory", "View stock and inventory records"),
    "inventory.create": ("Inventory", "Create inventory documents"),
    "inventory.approve": ("Inventory", "Approve inventory documents"),
    "inventory.post": ("Inventory", "Post inventory documents"),

    "production.view": ("Production", "View production records"),
    "production.create": ("Production", "Create production documents"),
    "production.approve": ("Production", "Approve production documents"),
    "production.post": ("Production", "Post production documents"),

    "packing.view": ("Packing", "View packing records"),
    "packing.create": ("Packing", "Create packing documents"),
    "packing.approve": ("Packing", "Approve packing documents"),
    "packing.post": ("Packing", "Post packing documents"),

    "sales.view": ("Sales", "View sales orders"),
    "sales.create": ("Sales", "Create sales orders"),

    "dispatch.view": ("Dispatch", "View dispatch records"),
    "dispatch.create": ("Dispatch", "Create dispatch documents"),
    "dispatch.approve": ("Dispatch", "Approve dispatch documents"),
    "dispatch.post": ("Dispatch", "Post dispatch documents"),

    "purchasing.view": ("Purchasing", "View purchasing records"),
    "purchasing.create": ("Purchasing", "Create purchase documents"),
    "purchasing.approve": ("Purchasing", "Approve purchase documents"),
    "purchasing.post": ("Purchasing", "Post purchase documents"),

    "accounting.view": ("Accounting", "View accounting records"),
    "accounting.create": ("Accounting", "Create accounting documents"),
    "accounting.approve": ("Accounting", "Approve accounting documents"),
    "accounting.post": ("Accounting", "Post accounting documents"),

    "accounting.bills.view": ("Bills", "View accounting bills"),
    "accounting.bills.create": ("Bills", "Create accounting bills"),
    "accounting.bills.approve": ("Bills", "Approve accounting bills"),
    "accounting.bills.post": ("Bills", "Post accounting bills"),

    "accounting.party_ledger.view": ("Party Ledger", "View party ledgers"),
    "reports.view": ("Reports", "View authorized ERP reports"),

    "configuration.view": ("Configuration", "View ERP configuration"),
    "configuration.create": ("Configuration", "Create configuration records"),
    "configuration.history.view": ("Configuration", "View configuration history"),
    "configuration.approve": ("Configuration", "Approve or reject submitted configuration versions"),

    "hr.view": ("HR & Payroll", "View HR records"),
    "hr.create": ("HR & Payroll", "Create HR records"),
    "hr.approve": ("HR & Payroll", "Approve HR records"),
    "hr.payroll.view": ("HR & Payroll", "View payroll records"),
    "hr.payroll.process": ("HR & Payroll", "Process payroll"),

    "security.users.manage": ("Security", "Manage ERP users"),
    "security.roles.manage": ("Security", "Manage roles"),
    "security.user_roles.manage": ("Security", "Assign users to company roles"),
    "security.role_permissions.manage": ("Security", "Assign permissions to company roles"),
    "security.permissions.manage": ("Security", "Manage permission definitions"),

    "audit.view": ("Audit", "View audit records"),
    "audit.export": ("Audit", "Export audit records"),
}

ROLES = {
    "OWNER": "Owner",
    "ERP_ADMIN": "ERP Administrator",
    "PRODUCTION_HEAD": "Production Head",
    "PRODUCTION_OPERATOR": "Production Operator",
    "STORE_OFFICER": "Store / Inventory Officer",
    "PACKING_SUPERVISOR": "Packing / Nalki Supervisor",
    "SALES_DISPATCH": "Sales & Dispatch Officer",
    "PURCHASING_OFFICER": "Purchasing Officer",
    "ACCOUNTS_OFFICER": "Accounts Officer",
    "HR_PAYROLL_OFFICER": "HR & Payroll Officer",
    "AUDITOR": "Auditor / Read-only",
}

# Proposed starting matrix. This is not an authorization grant until
# separately reviewed, approved and seeded into the database.
ROLE_PERMISSIONS = {
    "OWNER": frozenset(PERMISSIONS) - frozenset({
        "configuration.view", "configuration.create",
        "configuration.history.view", "configuration.approve",
    }),

    "ERP_ADMIN": frozenset({
        "inventory.view", "production.view", "packing.view",
        "sales.view", "dispatch.view", "purchasing.view",
        "accounting.view", "accounting.bills.view",
        "accounting.party_ledger.view", "reports.view",
        "configuration.view", "configuration.create", "configuration.history.view", "configuration.approve",
        "hr.view", "hr.payroll.view",
        "security.users.manage", "audit.view",
    }),

    "PRODUCTION_HEAD": frozenset({
        "production.view", "production.create",
        "production.approve", "production.post",
        "inventory.view", "reports.view",
    }),

    "PRODUCTION_OPERATOR": frozenset({
        "production.view", "production.create",
    }),

    "STORE_OFFICER": frozenset({
        "inventory.view", "inventory.create",
        "purchasing.view",
    }),

    "PACKING_SUPERVISOR": frozenset({
        "packing.view", "packing.create",
        "packing.approve", "packing.post",
        "inventory.view",
    }),

    "SALES_DISPATCH": frozenset({
        "sales.view", "sales.create",
        "dispatch.view", "dispatch.create",
    }),

    "PURCHASING_OFFICER": frozenset({
        "purchasing.view", "purchasing.create",
    }),

    "ACCOUNTS_OFFICER": frozenset({
        "accounting.view", "accounting.create",
        "accounting.bills.view", "accounting.bills.create",
        "accounting.party_ledger.view", "reports.view",
    }),

    "HR_PAYROLL_OFFICER": frozenset({
        "hr.view", "hr.create", "hr.payroll.view",
    }),

    "AUDITOR": frozenset({
        "inventory.view", "production.view", "packing.view",
        "sales.view", "dispatch.view", "purchasing.view",
        "accounting.view", "accounting.bills.view",
        "accounting.party_ledger.view", "reports.view",
        "hr.view", "hr.payroll.view", "audit.view",
    }),
}


def validate_catalog():
    """Return catalog inconsistencies without changing any data."""
    errors = []

    for role_code, permissions in ROLE_PERMISSIONS.items():
        if role_code not in ROLES:
            errors.append(f"Unknown role: {role_code}")

        for permission_code in permissions:
            if permission_code not in PERMISSIONS:
                errors.append(
                    f"{role_code} references unknown permission: {permission_code}"
                )

    for permission_code in PERMISSIONS:
        if not isinstance(permission_code, str) or not permission_code.strip():
            errors.append("Permission codes must be non-empty strings.")

    return errors

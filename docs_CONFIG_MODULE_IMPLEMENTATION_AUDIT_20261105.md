# Configuration Module — Implementation Audit & Phase 1 Proposal
Date: 05-Nov-2026
Status: audit completed; migration is a proposal only and has NOT been applied.

## Environment recovery
- Remote Commander device AhmadArshiqMeer is online.
- PostgreSQL port 5432 responds.
- pgAdmin process is running.
- Safe working copy exists at the established project path.
- ERP health endpoint returned HTTP 200 with {"app":"ok","database":true}.
- The ERP server was restarted after the power interruption.

## Verified existing master-data foundation
The database already contains these master tables:
brands, fiber_types, item_categories, item_variants, items, machines,
ownership_types, parties, party_financial_profiles, process_stages,
shade_categories, shades, units, yarn_counts.

Verified row counts:
- brands: 3
- fiber_types: 7
- item_categories: 10
- items: 10
- item_variants: 5,423
- units: 8
- shades: 2,709
- shade_categories: 3
- process_stages: 8
- ownership_types: 2
- yarn_counts: 4
- machines: 0

The current master schema already has unique keys and foreign keys for core
brand/shade/unit/item/variant relationships. Do not create duplicate copies
of these master entities. The existing /configuration page is protected by
configuration.view and is read-only. The existing get_configuration_master_data()
function only reads and paginates brands, units, shades and variants.

## Main gap
The current module is a read-only display plus a design scaffold. It has no
configuration persistence tables, no save/submit/approve routes, no effective
version history, and no configuration audit workflow. The existing
app/configuration_rules.py contains validation models only and does not
persist data.

## Phase 1 proposal
A draft SQL file named 20261105_002_configuration_foundation_PROPOSAL.sql
proposes a separate configuration schema with:
1. config_versions — company-scoped, versioned JSONB rule payloads and lifecycle.
2. config_approval_events — explicit submit/approve/reject history.
3. config_audit_events — old/new payload audit records and actor/reason.

The proposal deliberately reuses core.company and core.users and leaves
master.* tables authoritative. It does not seed or enable a Nalki PARTY-stock
policy because that business rule remains unresolved.

## Safety
- The proposal SQL has NOT been executed.
- No database schema, master data, business transactions, roles or permissions
  were changed during this audit.
- The initial schema inventory and all focused master-table metadata/count
  queries ran in READ ONLY transactions.
- Do not enable write routes until the DB role, permission catalogue,
  approval state machine, audit immutability and tests are implemented.

## Next implementation stages
1. Review and approve the proposed additive schema migration.
2. Implement typed payload validation for product attributes, measurements,
   units/conversions, packaging, process routes, ownership and costing policies.
3. Implement server-side permission checks, CSRF protection and draft-only save.
4. Implement submit/approve/reject with separation of duties and version locking.
5. Add read/write UI for the first approved configuration categories.
6. Add tests for rollback, duplicates, effective dates, tenant boundaries,
   concurrent updates, audit history and posted-transaction snapshot integrity.
7. Only then enable production configuration writes.

## Phase 1A — validation layer progress (05-Nov-2026)
- Created a pre-change backup at BACKUP_CONFIGURATION_VALIDATORS_20261105.
- Extended app/configuration_rules.py with reusable validation models for typed
  attributes, unit conversions, measurement profiles, ordered process routes
  and configuration approval policies.
- Added six focused tests to tests/test_configuration_rules.py.
- Syntax compilation passed for both changed Python files.
- Focused test suite passed: 16 tests, 0 failures.
- No DB migration was applied and no business/master records were changed.
- Existing page remains read-only. The new models are validation-only until the
  persistence, permission, approval and audit layers are completed.

## Access confirmation
- pgAdmin desktop shell and its local Python web process are running.
- pgAdmin's local Python process has active TCP sessions to PostgreSQL on 5432.
- ERP is running on 127.0.0.1:8000 and its health endpoint confirms database=true.

## Phase 1B — approved migration and draft persistence (05-Nov-2026)
- Explicit user approval received before applying the migration.
- Created a PostgreSQL custom-format backup:
  database/backups/ali_raza_erp_pre_configuration_20261105.dump
  verified size: 959,053 bytes; pg_dump exit code 0.
- Preflight confirmed database ali_raza_erp, PostgreSQL 18.6, current role
  postgres, company and user FK targets, and existing configuration permission
  assignments.
- Applied migration 20261105_002_configuration_foundation.sql successfully.
- Verified three new tables and seven indexes:
  config_versions, config_approval_events, config_audit_events.
- Company count remained 1 and user count remained 2.
- Added app/configuration_service.py with allow-listed Pydantic payload types,
  company-scoped version sequencing under an advisory transaction lock,
  DRAFT-only insert, and matching configuration audit event in the same
  transaction.
- Added authenticated GET /configuration/api/history and CSRF-protected
  POST /configuration/api/drafts. Both enforce existing server-side permissions.
- Added draft editor and version-history table to configuration.html.
- No approval endpoint or permission grant has been enabled. Approval remains
  separate until a dedicated configuration.approve permission is approved and
  assigned. DRAFT records do not affect operational rules or posted documents.
- Added four service validation tests; all four passed. The earlier 16 rule
  tests also passed.


## 05-Nov-2026 — Administrator-only access control

User approval: configuration module access is restricted to the ERP Administrator role only.

Read-only pre-change verification (company_id=1): active roles OWNER=12, ERP_ADMIN=13, AUDITOR=22; configuration permissions 82=view, 83=create, 84=history.view. Existing users remain `erp_test` (STORE_OFFICER) and `nadeem` (PURCHASING_OFFICER); neither is assigned ERP_ADMIN.

Applied in one PostgreSQL transaction to `core.role_permissions`:
- Granted `configuration.view`, `configuration.create`, and `configuration.history.view` to active company role `ERP_ADMIN` (role id 13).
- Removed those three configuration permissions from `OWNER` and `AUDITOR` so that the ERP_ADMIN role is the sole role with configuration access.
- No user-role assignments were changed. No user account was promoted. No configuration records, stock, accounting, purchasing, or master data were changed.

Post-change verification: ERP_ADMIN has exactly the three configuration permissions; all other company roles, including OWNER, AUDITOR, STORE_OFFICER, and PURCHASING_OFFICER, have no `configuration.*` permissions.

Important operational note: no active user is currently assigned the ERP_ADMIN role, so existing accounts remain denied until an authorized administrator account is explicitly assigned that role. Do not promote `erp_test` or `nadeem` without separate explicit approval. Approval/rejection workflow and `configuration.approve` permission remain unimplemented; draft save and history are the current supported actions.


## Phase 1C — controlled approval workflow (05-Nov-2026)

See `docs_CONFIGURATION_APPROVAL_WORKFLOW_20261105.md` for the detailed checkpoint. Implemented DRAFT → PENDING → APPROVED/REJECTED transitions, CSRF-protected endpoints, independent approver enforcement, effective-date overlap guard, approval/audit event writes, and administrator-only `configuration.approve` permission. Permission id 97 is assigned only to ERP_ADMIN role id 13. Babar Rasheed (user id 3) is active as ERP_ADMIN; a second ERP_ADMIN is required to approve his own submitted drafts. Approved configuration versions are not yet consumed by operational stock/costing modules. No configuration drafts or business records were created. Backup: `BACKUP_CONFIG_APPROVAL_PHASE_20261105_20261105_203027`; DB backup: `database/backups/ali_raza_erp_pre_config_approval_20261105.dump` (974,912 bytes, pg_dump exit 0). Focused config tests: 25 passed; Python compile, Jinja template, route registration and health checks passed.


## Phase 1C verification correction — 05-Nov-2026
Final focused configuration test count is 26/26 passed. The static role matrix was aligned with the live admin-only assignment: ERP_ADMIN alone has configuration.view, configuration.create, configuration.history.view and configuration.approve; OWNER, AUDITOR and operational roles have none. Full checkpoint: `docs_CONFIGURATION_APPROVAL_WORKFLOW_20261105.md`.


## Phase 1D — controlled configuration supersession (05-Nov-2026)

- Added optional predecessor selection to configuration draft creation. The selected predecessor must be APPROVED, belong to the same company, and match the same configuration type/key.
- Added effective-date boundary validation: a replacement starts after the predecessor's start; a predecessor that already ended before the new start cannot be selected.
- On independent approval, the service locks the predecessor and competing approved versions, checks overlap, then atomically changes the predecessor to RETIRED and sets its effective_to to the day before the new version's effective_from.
- Preserved the predecessor's payload and wrote a SUPERSEDED audit event. New approval and predecessor retirement are in one transaction. No new permission or migration was needed; existing schema fields/status/event types were reused.
- UI history displays record IDs and effective end dates. Draft form accepts an optional predecessor ID.
- Verification: 29/29 focused configuration tests passed; Python compilation, app import, Jinja template load, route registration, health HTTP 200/database=true passed. Read-only DB check confirmed supersedes_version_id exists and config_versions count remains 0; PostgreSQL accepted the array-exclusion predicate.
- No draft, retirement, operational rule, stock, production, costing, or accounting record was created or changed.
- Code backup: BACKUP_CONFIG_SUPERSESSION_20261105_204110. New database dump attempt was stopped because unattended PostgreSQL password authentication did not complete; no DB writes were performed. The last completed database backup remains the verified pre-approval dump.
- Master addendum updated: Ali_Raza_Enterprises_ERP_MASTER_ADDENDUM_04-05_NOV_2026_CONFIGURATION_PHASE1D_SUPERSESSION.pdf.

Operational boundary: approved configuration versions remain governed records only and are not yet consumed by live operational modules. Integration still requires rule-by-rule validation and immutable snapshots on posted documents.


## Phase 1E — effective configuration resolver and packing readiness (05-Nov-2026)

- Added a company-scoped, read-only effective configuration lookup by type/key/date and GET /configuration/api/effective, protected by configuration.history.view. The resolver returns no match when no APPROVED version is effective and fails closed on multiple matches.
- Tests now cover one match, no match and duplicate matches. Focused configuration suite: 32/32 passed.
- Python compilation, application import, configuration template load, live OpenAPI route registration and post-restart health HTTP 200/database=true passed. A read-only probe lookup returned no record. No DB writes.
- Packing readiness audit: /modules/packing is currently a generic placeholder; no dedicated packing service, UI, API routes or packing tests exist. Database packing tables exist. Read-only counts: 2 DRAFT packing orders, 4 items, 2 labour rows, 2 POSTED FG transfer rows; material consumption, returns, completions, QC and wastage are 0. No rows were changed.
- Existing item rows use 10 pieces per box, while the confirmed business model distinguishes 10-piece small boxes and 100-piece finished wall boxes. Resolve both packaging levels explicitly before operational integration. Packing order and FG transfer location FKs point to different location schemas; confirm single-godown mapping. Enforce Nalki source from Large Cone, never Baby Cone.
- Code backup before resolver changes: BACKUP_CONFIG_EFFECTIVE_LOOKUP_20261105. Full findings: docs_CONFIGURATION_PHASE1E_EFFECTIVE_LOOKUP_AND_PACKING_AUDIT_20261105.md.
- Next gate: dedicated packing service/UI, explicit nested packaging, single-godown enforcement, and immutable approved-configuration version snapshot on packing documents. Preserve existing test rows and posted transfers.


### Packing location mapping clarification (read-only)
- core.locations has nine logical stage/location records; inventory.locations has nine rows mapped to them by core_location_id, all currently allow_stock=true.
- Existing packing order TEST-COST-002 uses core location id 7 (Packing); its POSTED FG transfers use inventory location id 5, mapped to core location id 8 (Finished Goods).
- This does not establish nine physical godowns. Preserve one physical godown; process stages remain workflow dimensions. Before stock posting, validate a single physical godown mapping and use process_stage_id for stage tracking. No location rows or posted transfers were changed.


## Packing Module Phase 1 — draft-only implementation (05-Nov-2026)

- Replaced the generic Packing placeholder with a dedicated Packing Orders page and draft form. Added GET/POST /modules/packing/new; POST validates form content type, size, field count and double-submit CSRF.
- Added app/packing_service.py: company-scoped order list/search, active OWN Nalki variants with positive company stock, strict server-side variant and date validation, 1–20 lines, whole finished-box counts, unique variant lines, and transactional draft creation.
- Packaging relationship is represented explicitly using existing columns: 100 pieces per finished wall box = 10 small boxes × 10 pieces. Header planned_quantity_boxes stores finished wall boxes; item boxes_qty stores small boxes; pieces_per_box remains 10.
- Draft transaction writes packing_orders, packing_order_items, packing_order_status_history and core.audit_log together. No inventory reservation, consumption, stock ledger, FG transfer, weight/cost calculation, labour payment or accounting entry occurs.
- Weight is intentionally not calculated; non-null weight fields use zero placeholders and item unit_cost/total_cost remain NULL. PARTY stock remains excluded.
- Permissions were not changed. OWNER and PACKING_SUPERVISOR have packing.create; ERP_ADMIN (Babar account) currently has packing.view only. The draft-create link is hidden for Babar. No role or user changes.
- Read-only source stock: NALKI-CHANNEL-1 300 pcs at Finished Goods stage; NALKI-GOLDEN_CHAIN-1 123 pcs across Nalki, Labeling and Finished Goods. These are process-stage labels within one physical godown, not separate warehouses.
- Verification: 39/39 packing + configuration tests passed; Python compilation, Jinja template load/render, OpenAPI GET/POST route registration passed. App restarted; health app=ok, database=true.
- Real PostgreSQL INSERT and audit SQL were tested inside a deliberately rolled-back outer transaction. Result was a valid DRAFT; post-rollback counts remained 2 packing orders, 4 items, 2 labour rows, 2 POSTED FG transfers, 0 packing status-history rows and 0 core.audit_log rows.
- No migration/schema change or business data modification. Code backup: BACKUP_PACKING_PHASE1_20261105. Full record: docs_PACKING_MODULE_PHASE1_DRAFT_WORKFLOW_20261105.md.

Next gate: implement source traceability, empty small-box returns, material consumption, Nalki-only theka labour, QC, wastage and FG transfer before enabling approval/posting. Preserve one physical godown and all existing POSTED transfers.


## Phase 1F — Type-specific editor, version review and effective lookup (05-Nov-2026)

### Implemented
- Added `app/configuration_examples.py` with editable starter payloads and field guidance for all 11 supported configuration types:
  PRODUCT_DEFINITION, UNIT_DEFINITION, PACKAGING_RULE, BABY_CONE_MEASUREMENT,
  OWNERSHIP_POLICY, PROCESS_COST_RULE, ATTRIBUTE_DEFINITION, UNIT_CONVERSION,
  MEASUREMENT_PROFILE, PROCESS_ROUTE and APPROVAL_POLICY.
- Configuration type selection now loads the matching starter key, display name,
  help text and JSON payload. This is an editable example only; loading it does
  not save or activate a rule.
- Nalki packaging example reflects the two distinct levels:
  PACK_BOX-STD is the 10-piece regular box; a separate finished wall box has
  100 pieces and contains 10 regular boxes.
- Nalki ownership example is OWN only. PARTY stock is not enabled; any future
  PARTY path must enforce a named owner, request, approval and locked rate.
- Nalki process-route example explicitly takes input from LARGE_CONE, not
  BABY_CONE. Light grade example uses A/B/C/D.
- Corrected `BabyConeMeasurement` to inherit the effective-period fields.
  The draft persistence service requires `effective_from` for every config type;
  this previously missing field meant a Baby Cone measurement could validate
  on its own but could not be saved through the versioned draft service.
- Added company-scoped GET `/configuration/api/versions/{version_id}`:
  returns the selected version payload, approval events and audit events.
  It returns 404 for a version outside the current company.
- Configuration history now has a View action so an administrator can inspect
  the complete payload and decision/audit trail before submitting or approving.
- Added a read-only Effective Configuration Lookup panel to query the approved
  version by type, key and date using the existing effective resolver.

### Verification
- Configuration-specific tests: 38/38 passed.
- Full application unit suite: **178/178 passed**.
- Python compilation passed.
- Jinja configuration template rendered successfully with all required
  controls and examples.
- Inline JavaScript syntax passed Node `--check`.
- Application restarted successfully; health returned
  `{"app":"ok","database":true}`.
- OpenAPI confirms all configuration routes, including the new version-detail
  route.
- Read-only database verification: config_versions=0,
  config_approval_events=0, config_audit_events=0.

### Data safety and remaining boundary
- No configuration draft, approval, rejection, master-data row, stock movement,
  accounting entry, production record, role or permission was created or changed
  in this phase.
- The existing Brands, Units, Shades and Item Variants tables remain visible
  read-only on the page. This phase completes the governed rule editor/review
  workflow, not master-data CRUD.
- APPROVED configuration versions remain stored rules. They are not yet consumed
  by live Purchasing, Production, Nalki, Outside Labeling, Packing or costing
  transactions. Those integrations require rule-specific validation and
  immutable version snapshots on operational documents before activation.
- No default Nalki PARTY-stock policy was seeded or activated.
- Code backup: `BACKUP_CONFIGURATION_COMPLETION_20261105_221116`.

### Phase 1F completion statement
The standalone governed Configuration rule workflow now supports typed starter
payloads for all 11 models, draft save, submit, independent approval/rejection,
supersession, history, payload/audit inspection and effective-date lookup.
It is ready for controlled administrator use as a rule register. Master-data
CRUD and operational consumption remain separate implementation gates and are
not represented as completed.
# Configuration Phase 1G — Audited Master Data Editing

**Date:** 05-Nov-2026  
**Status:** Master-data create/edit foundation implemented in the SAFE WORKING COPY.

## Delivered
- Added `app/configuration_master_service.py` for controlled master-data operations.
- Added CSRF-protected POST and PUT endpoints:
  - `/configuration/api/master/{record_type}`
  - `/configuration/api/master/{record_type}/{record_id}`
- Endpoints require the existing `configuration.create` permission (ERP_ADMIN role only under the current permission catalog).
- Added a master-data editor to the Configuration page and Edit actions for records on the current paginated page.
- Every successful change writes a `core.audit_log` entry in the same database transaction.
- No hard delete operation exists.

## Supported scope
- **Brands:** create new brand; edit display name and description. Brand code is immutable after creation.
- **Units:** create new unit; edit display name. Unit code, unit type and decimal precision are immutable after creation to avoid silently changing historical quantity semantics.
- **Shades:** create shade for an existing active brand and optional active shade category; edit shade name, category, common flag and active flag. Brand and shade code are immutable.
- **Item variants:** edit display name and active flag only. Variant code, item, brand, shade and unit identity are immutable. New variants are intentionally blocked here until the dedicated item/variant setup workflow can validate the complete item definition.

## Dependency and safety guards
- No hard deletes.
- Brand deactivation is blocked while active shades, active variants or non-zero stock depend on it.
- Shade deactivation is blocked while active variants or non-zero stock depend on it.
- Unit deactivation is blocked while items, variants or machines reference it.
- Variant deactivation is blocked while its stock balance is non-zero.
- Master table identifiers, variant identity fields, stock ledger, inventory, posted documents and accounting records are not rewritten.
- Brands, Units and Shades are shared master tables in the current schema (not company-scoped). The endpoints therefore preserve shared identity and record all changes against the authenticated company/user in the audit log.
- View-only users do not see master-data edit controls. The API independently enforces `configuration.create`.

## Read-only live baseline
- Brands: 3
- Units: 8
- Shades: 2,709
- Item Variants: 5,423
- Page preview: 50 records per page for Shades and Item Variants.
- Master-data read queries returned successfully with no query error.
- Configuration-specific audit rows before any operator edits: 0.
- Configuration versions at verification: 0.

## Verification
- Full application suite: **184/184 tests passed**.
- Configuration-specific suite: 44/44 passed.
- Python compilation passed.
- Jinja template rendered for editor-enabled and view-only contexts.
- Inline JavaScript syntax passed Node `--check`.
- FastAPI route registry includes both POST and PUT master-data endpoints.
- Application restarted; health: `{"app":"ok","database":true}`.
- Final read-only baseline confirmed the four master record counts above and no configuration audit/version records created by this implementation.

## Not included / next gates
- No live master-data create/edit/deactivate operation was performed during implementation; no sample/dummy master record was inserted.
- No new item variant creation. This requires a dedicated item/variant workflow that validates item category, base unit, tracking flags, shade/brand relationships, ownership, and existing item code conventions.
- The current editor uses validated JSON payloads. A field-based form can replace this after the business-specific variant setup is designed.
- Approved configuration rule versions still need controlled, version-pinned adoption by Purchasing, Production, Nalki, Outside Labeling, Packing and costing.
- Global master-table governance and access separation should be reviewed before introducing a second company/tenant.

## Backup
`BACKUP_CONFIGURATION_PHASE1G_MASTER_DATA_20261105_223211`

**Completion boundary:** Existing master data can now be managed through audited, non-destructive operations within the explicitly supported scope. This phase does not claim that all master-data types or all operational rule integrations are complete.


---

# Configuration Phase 1H — Immutable Rule Snapshot Integration for Nalki Packing

**Date:** 05-Nov-2026  
**Status:** First operational configuration consumer integrated in SAFE WORKING COPY.

## Scope
The first live consumer of the governed Configuration register is Nalki Packing. All three DRAFT creation paths now resolve and attach the applicable Nalki finished-wall-box packaging rule:
1. Fixed 100-shade, same-brand assortment.
2. Random 100-piece workflow with fresh and accepted usable-return sources.
3. Legacy generic packing draft service, retained behind its existing service/API boundary.

## Rule identity and business semantics
- Configuration type: `PACKAGING_RULE`
- Configuration key: `NALKI-FINISHED-WALL-BOX`
- Finished wall box: exactly 100 Nalki pieces.
- Inner regular box: `PACK_BOX-STD`, exactly 10 pieces.
- One finished wall box contains 10 regular boxes.
- The finished 100-piece wall box remains a distinct finished-product pack; `PACK_BOX-STD` is never reinterpreted as the finished wall box.
- This phase does not infer any per-piece weight or create material/stock movements.

## Runtime resolution
- Resolve only an APPROVED version for the same company, exact type/key and packing date within effective_from/effective_to.
- Lock the selected version row `FOR SHARE` during the DRAFT transaction.
- More than one effective approved match is a hard error.
- An approved but malformed/incompatible rule is a hard error; no silent fallback.
- If no approved version exists, pin an explicit `SYSTEM_DEFAULT` baseline snapshot with the same validated 100/10 relationship. This is not represented as an approved Configuration version.
- The resolved payload and source/version identity are attached in the same transaction as the packing DRAFT.

## Database protection
Migration `20261105_006_packing_configuration_snapshots.sql` adds `production.packing_configuration_snapshots`.
Migration `20261105_007_packing_configuration_snapshot_guard.sql` hardens the trigger:
- Only the exact Nalki packaging rule identity is accepted.
- Snapshot must match the parent DRAFT order's company, creator and packing date.
- APPROVED_VERSION snapshots must reference an APPROVED, effective, same-company/type/key version and exactly match its payload.
- SYSTEM_DEFAULT snapshots must match the database-guarded baseline values (100 pieces, 10 regular boxes, PACK_BOX-STD, Nalki, PCS).
- UPDATE and DELETE are rejected; one snapshot per order/type/key.
- Snapshot row can only be inserted while the parent packing order remains DRAFT.

## Tests and live verification
- Configuration + packing focused suites passed.
- Full application suite: **195/195 passed**.
- Python compilation passed.
- Application restarted; health returned `{"app":"ok","database":true}`.
- Packing page list query returned both existing orders and displayed “Not available” where no snapshot exists; no old order was backfilled.
- Database rollback probe inserted a temporary DRAFT and matching SYSTEM_DEFAULT snapshot, verified snapshot readback, verified UPDATE rejection, and verified tampered default payload rejection. The outer transaction was deliberately rolled back.
- Post-rollback snapshot row count: **0**.
- No real packing order, configuration version, inventory, stock ledger, FG transfer, labour row, accounting entry, master data, role or permission was created/changed by this phase.

## Backups and files
- Database pre-migration backup: `database/backups/ali_raza_erp_pre_packing_config_snapshot_20261105.dump`
- Additional pre-guard backup: `database/backups/ali_raza_erp_pre_packing_snapshot_guard_20261105.dump`
- Code snapshot: `BACKUP_PACKING_CONFIG_VERSION_PINNING_20261105_224033`
- Migration 006: `database/migrations/20261105_006_packing_configuration_snapshots.sql`
- Migration 007: `database/migrations/20261105_007_packing_configuration_snapshot_guard.sql`
- Runtime resolver: `app/configuration_runtime_service.py`
- Tests: `tests/test_configuration_runtime_service.py`

## Remaining Configuration integration
This is the first consumer, not blanket completion of all operational adoption. Remaining rule families need separate adapters and snapshots:
- Product/Item and Unit definitions → master/item setup and Purchasing.
- Unit conversions and measurement profiles → inventory, production and costing.
- Baby Cone measurement and process routes → Baby Cone / Nalki production as applicable.
- Ownership policy → OWN/PARTY source and issue validation; PARTY Nalki remains disabled until owner/request/approval/locked-rate policy is approved.
- Process cost rules → production and outside-labeling cost capture without double counting.
- Approval policy → operational maker-checker gates only after role mapping and separation-of-duties review.

Do not create an APPROVED version or mutate a master record merely to demonstrate this integration. No factory deployment or posting is included.

**Completion boundary:** Nalki Packing now pins a validated immutable packaging-rule snapshot to each new DRAFT order. Existing orders remain unchanged; operational posting and other rule-family integrations remain future phases.


---

# Configuration Phase 1I — Controlled Item Variant Creation

**Date:** 05-Nov-2026  
**Status:** Implemented and verified in SAFE WORKING COPY.

## Delivery
The Configuration master editor now supports creating new `master.item_variants` through the existing CSRF-protected POST API, in addition to the prior limited edit capability.

## Required and optional fields
- Required: active `item_id`, unique-per-item `variant_code`, and active `default_unit_id` (defaults to the item's base unit).
- Default unit must exactly match the item's base unit. Any unit conversion must be separately configured; this editor cannot silently redefine quantity semantics.
- Optional: display name, brand, shade, yarn count and fiber type.
- A selected shade must be active. Its brand is authoritative; a separately supplied brand must match it.
- Nalki and Label variants require an active brand and a shade belonging to that brand.
- Yarn, Big Cone and Baby Cone variants require both an active yarn count and active fiber type.
- Other item types accept only validated optional attributes; no unverified assumptions are made about shade tracking.
- The item itself must be active. No item, unit, brand, shade, yarn-count or fiber-type identity can be supplied as free text in place of a validated active master ID.

## Audit and transaction
- Variant insert and `core.audit_log` entry are performed in the same database transaction.
- No hard delete.
- Existing variant identity fields remain immutable on edit; only display name and active status can be edited.
- Deactivation of a variant with non-zero stock remains blocked.
- The UI displays active item IDs/base units, yarn-count IDs and fiber-type IDs to support validated JSON entry.

## Verification
- Configuration master-data tests: **12/12 passed**.
- Full application suite: **201/201 passed**.
- Python compilation passed.
- Jinja template rendered in editor-enabled and view-only modes.
- Inline JavaScript syntax passed Node check.
- Application restarted; health: `{"app":"ok","database":true}`.
- OpenAPI confirms POST create and PUT update routes.
- A real service-level create was executed inside an outer rollback transaction using a temporary FUEL_WOOD variant code. Both the variant and its audit row were confirmed absent after rollback.
- A Nalki variant without shade was rejected before insert.
- Live read-only counts after verification: item variants 5,423; Configuration audit rows 0; Configuration versions 0; Packing configuration snapshots 0.
- No actual item variant, brand, shade, unit, configuration version, packing order, stock, ledger, labour, FG transfer, accounting entry, role or permission was changed.

## Backup
`BACKUP_CONFIGURATION_VARIANT_CREATE_20261105_224531`

## Remaining boundaries
- Editor continues to use validated JSON rather than a fully guided field-by-field variant wizard.
- No actual master record was created during implementation.
- Configuration rules still need separate operational adapters/snapshots for Purchasing, Production, Outside Labeling and costing. Nalki Packing is the first integrated consumer.
- No factory deployment or operational posting.

**Completion boundary:** Brand, Unit, Shade and Item Variant master-data create/edit paths are now available within the validated scope. Existing production identities remain unchanged.


---

# Configuration Phase 1J — Purchasing Product and Unit Rule Snapshots

**Date:** 05-Nov-2026  
**Status:** Implemented and verified in SAFE WORKING COPY; full Goods Receipt workflow end-to-end remains blocked by the absence of an active supplier master record.

## Scope
Goods Receipt DRAFT creation now resolves and attaches two configuration identities for every receipt line:
1. `PRODUCT_DEFINITION` keyed by the actual item code.
2. `UNIT_DEFINITION` keyed by the selected unit code.

The resolver selects only one APPROVED version for the same company, exact type/key and receipt date. The selected version row is locked `FOR SHARE` and its exact payload/version ID is pinned. Multiple effective versions, wrong keys, invalid payloads, inactive product definitions or unsupported unit conversions fail closed.

When no approved version exists, the receipt line pins a clearly identified `SYSTEM_DEFAULT_MASTER` snapshot of the active existing master item/unit identity. This is not misrepresented as an approved configuration version.

## Unit-conversion boundary
This phase does **not** apply unit conversions or change received quantity, unit price, GST, freight, costing or PO matching. The existing Purchasing rule still requires the variant's exact default unit. If an approved Unit Definition would require a conversion (factor other than 1 or a different base unit), the receipt is blocked until a separately designed conversion workflow is implemented and tested. No silent multiplication/division is allowed.

## Database protection
Migration `20261105_008_purchasing_configuration_snapshots.sql` adds `purchasing.purchase_configuration_snapshots`.
- One immutable Product Definition and Unit Definition snapshot per receipt line/key.
- Snapshot parent receipt and line must belong to the same company.
- Parent must remain DRAFT.
- Creator and effective date must match the parent receipt.
- APPROVED_VERSION must point to a same-company, exact-type/key, approved and effective version with identical JSON payload.
- SYSTEM_DEFAULT_MASTER must identify the actual active master item or unit and its current code/name/precision.
- UPDATE and DELETE are rejected by a database trigger.

## Audit
Goods Receipt creation audit payload now records each line's configuration type/key, source, version ID and payload alongside the receipt's other audit details. Snapshot inserts, receipt/lines and audit row are in the same database transaction.

## Verification
- Configuration runtime suite: **16/16 passed**.
- Purchasing service suite: **7/7 passed**.
- Full application suite: **206/206 passed**.
- Python compilation passed.
- Application restarted; health returned `{"app":"ok","database":true}`.
- OpenAPI confirms existing Goods Receipt create/approve/post routes remain registered.
- Live resolver selected `SYSTEM_DEFAULT_MASTER` for NALKI and PCS; no rows were written.
- Transactional database probe created a temporary DRAFT receipt/line and two master snapshots, verified both inserts, verified UPDATE and DELETE rejection, then rolled the entire transaction back. Post-rollback snapshot count remained **0**.
- Read-only baseline: purchase receipts=0, receipt lines=0, purchase configuration snapshots=0, configuration versions=0, active company suppliers=0.
- Because there are currently no active supplier master records for company 1, the real Goods Receipt service could not be exercised end-to-end without inventing or inserting a supplier. No supplier was created.
- No purchase receipt, PO, stock, ledger, accounting, master data, configuration version, role or permission was changed.

## Backups
- Code snapshot: `BACKUP_PURCHASING_CONFIG_PINNING_20261105_225241`
- Database backup: `database/backups/ali_raza_erp_pre_purchasing_config_snapshot_20261105.dump`
- Migration: `database/migrations/20261105_008_purchasing_configuration_snapshots.sql`

## Remaining Purchasing integration
- Unit Conversion rules require a dedicated explicit quantity-conversion design, precision/rounding policy, PO unit compatibility, and line-level original/base quantity snapshots. Not enabled in this phase.
- Ownership Policy rules require product-family mapping and maker-checker controls. Supplier GRN remains OWN-only; PARTY material is not enabled here.
- Product Definition snapshots are validation/history only; they do not create or mutate master items.
- GST/tax rules, costing and accounting posting remain separate work; this phase does not infer a tax rate or post any financial/stock document.

**Completion boundary:** New Goods Receipt DRAFT lines now pin Product and Unit configuration identity/version evidence in the same transaction. End-to-end GRN workflow verification is pending an active supplier master record; no real purchasing record was created.


---

# Configuration Phase 1K — Approved Unit Conversion Engine

**Date:** 05-Nov-2026  
**Status:** Directional conversion resolver and Decimal calculation engine implemented and tested. NOT enabled in Purchasing or stock posting.

## Delivery
New module: `app/unit_conversion_service.py`.

- Canonical directional key: `{FROM}-TO-{TO}`, e.g. `KG-TO-G` or `BOX-TO-PCS`.
- Resolves exactly one same-company `UNIT_CONVERSION` version in APPROVED status, effective on the requested transaction date.
- Locks the approved configuration version with `FOR SHARE`.
- Validates the typed `UnitConversion` payload, active flag, exact source/target direction, configuration key and matching effective-from date.
- Verifies both source and target units exist and are active in `master.units`.
- Does not infer or reverse a conversion. A reverse direction requires its own separately approved rule.
- Returns the exact configuration version ID, factor, source/target codes, effective date and explicit rounding policy as immutable snapshot data.

## Arithmetic
`convert_unit_quantity()` uses Python Decimal arithmetic only:
- target quantity = source quantity × approved factor.
- rounding is explicit `ROUND_HALF_UP`.
- conversion rule precision must fit the target stock quantity scale (maximum 3 decimal places for this service boundary).
- negative, zero, NaN, infinite, invalid-factor and zero-after-rounding results are blocked.
- returns original quantity, source unit, factor, unrounded target, rounded target, target unit and rounding difference for audit/traceability.

## Important operational boundary
This engine is deliberately NOT wired into Goods Receipt, Purchase Orders, inventory stock documents or accounting. Current GRN line schema stores one quantity and one unit; stock ledger also stores one quantity and has scale 3. Before activating conversion, a separate schema and workflow phase must preserve:
1. entered/source quantity and source unit;
2. exact approved conversion version and factor;
3. unrounded target quantity and rounded base quantity;
4. target/base unit;
5. unit-price conversion (inverse relationship) and amount invariance;
6. PO ordered/received quantities in the PO's own unit, including partial receipts;
7. inventory posting only in the agreed stock/base unit;
8. supplier returns and reversal using original source/base snapshots.

No live quantity or unit behaviour was changed.

## Verification
- New unit-conversion tests: **16/16 passed**.
- Full application unit suite: **222/222 passed**.
- Python compilation passed.
- ERP health: `{"app":"ok","database":true}`.
- Active units confirmed in live DB: BOX, CONE, G, KG, L, M, PCS, SET.
- Approved UNIT_CONVERSION versions currently: **0**.
- Live resolver correctly failed closed for BOX-TO-PCS because no approved version exists.
- Existing purchase configuration snapshots: **0**.
- No configuration versions, purchase receipts, PO quantities, stock, ledger, accounting, master data, roles or permissions were changed.
- Code backup: `BACKUP_UNIT_CONVERSION_ENGINE_20261105_225954`.

## Next safe phase
Design and implement source/base quantity traceability for Goods Receipt and PO matching, including price normalization, stock posting, returns and reversal, with a dedicated migration and transactional tests. Do not enable alternate units until all paths pass.


## Purchasing and Inventory Traceability Discovery (next implementation gate)
Read-only inspection of live schema, routes and database functions found:
- Current database contains 0 purchase orders, 0 PO lines, 0 GRNs, 0 GRN lines, 0 purchase returns and 0 purchase-return lines. Active supplier count was already verified as 0 in Phase 1J.
- The Purchasing UI exposes PO information as a read-only listing; there is no PO create/edit/approve route in `app/main.py`. A complete PO workflow must be built before alternate-unit PO quantities can be tested.
- GRN approval creates one linked inward stock document. Its line quantity is copied from `purchase_receipt_lines.received_quantity`; GRN posting later updates PO `received_quantity` from the same GRN quantity.
- The generic inventory stock document and stock ledger have no unit_id column. `inventory.post_stock_document` moves the supplied numeric quantity into `inventory.stock_balances` and `inventory.stock_ledger`; both use numeric(18,3) quantity. Therefore inventory quantity must remain in the item's canonical base unit.
- Purchase Returns use the original GRN line's quantity/unit and later create outward stock document lines. Any conversion feature must preserve the original GRN conversion snapshot and convert the returned source quantity using that same factor/version; it must not resolve a newer rule at return time.
- GRN landed-cost calculation is based on entered quantity × entered unit price, then discounts/freight/other charges are allocated by net line value. Conversion must preserve line value exactly and normalize per-base-unit cost as source unit price ÷ source-to-base factor; rounding unit cost must not alter the line's six-decimal landed total.
- PO remaining-quantity enforcement currently compares GRN quantity directly with PO ordered/received quantity. Once alternate units are enabled, both sides must be compared in base quantity while retaining the original PO/source quantity and unit for display and audit.

### Required order of implementation
1. Build a real PO DRAFT → approval workflow with source quantity/unit, base quantity/unit and immutable approved conversion snapshot.
2. Add additive GRN source/base quantity fields and pin the conversion version used on the receipt date; preserve exact line value and normalize unit price.
3. Update PO matching/posting to compare base quantities and update base received quantity atomically.
4. Update supplier returns to reuse the original GRN conversion snapshot and create outward stock quantities in base units.
5. Verify reversal/rollback, partial receipts, partial returns, rounding boundaries and total-cost invariance in transactional tests.
6. Only then enable alternate units in the GRN UI. Until that full chain passes, current exact-default-unit behaviour remains enforced.

This discovery did not change schema, routes, database records, stock or accounting.
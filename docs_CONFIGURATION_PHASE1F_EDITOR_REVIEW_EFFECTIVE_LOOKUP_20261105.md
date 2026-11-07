

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

# Smart Entry Engine — Phase 1 Purchase Receipt Pilot
Date: 2026-11-08

## Scope delivered
- Added reusable presentation primitives in `app/static/smart-entry.css`.
- Added the Smart Entry keyboard/controller layer in `app/static/smart-entry.js`.
- First piloted on Goods Receipt, then opted in across Purchase Return, New Supplier, General Journal, Big Cone, Dyeing, Baby Cone Measurement, 100-Shade Packing, Random 100-Piece Packing, Department/Machine Masters, PARTY Stock Use Requests and both guided Configuration editors.
- Added visible keyboard guidance and a live status region.
- Enter advances between fields; native selects keep their normal type-to-select behavior and then move focus forward.
- Alt+N adds a line on Goods Receipt, Purchase Return and General Journal where each form has one unambiguous add-line action.
- Ctrl+Enter invokes the browser's normal form validation and submits the existing DRAFT route.
- Repeat last item copies variant, unit, PO-line selection and unit price; quantity, discounts, GST amount and remarks are reset for deliberate re-entry.
- Repeated item variants show a non-blocking warning; the operator remains in control.
- Existing live receipt totals, PO filtering, GST choice, single-godown resolution, server validation, CSRF, audit and DRAFT-only service are unchanged.

## Safety boundaries
- No database, schema, records, permissions, roles, prices, GST rates, stock or ledger logic changed.
- No automatic autosave or cross-tab persistence was added. Explicit session-only recovery copies are enabled for Goods Receipt and Purchase Return; unfinished data is never stored without the operator clicking Save recovery copy.
- No approval/post action was added to the entry form.
- The normal server-side validation remains authoritative.
- No server restart was performed.

## Backup
- `app/templates/purchasing.html.smart_entry_backup_20261108_014802`
- `app/static/app.css.smart_entry_backup_20261108_014802`

## Verification
- `node --check app/static/smart-entry.js`: passed.
- Jinja compilation of `app/templates/purchasing.html`: passed.
- Local static route `/static/smart-entry.js`: HTTP 200.
- Existing ERP server was left running; no restart.
- No Goods Receipt was submitted and no business data was created.

## Phase 2 rollout (same implementation session)
- Moved the shared Smart Entry CSS and JavaScript into the global base layout; only forms opting in with `data-smart-entry` receive keyboard behavior.
- Enabled the shared keyboard contract on New Supplier: Enter advances ordinary input fields; Ctrl+Enter uses native browser validation and the existing supplier-save endpoint.
- Enabled the shared keyboard contract on Purchase Return: Alt+N adds a return line and focuses its item selector; Ctrl+Enter uses the existing DRAFT-only save endpoint.
- Enabled the shared keyboard contract on General Journal: Alt+N invokes its existing Add line button; Ctrl+Enter submits through the existing journal DRAFT endpoint; account and party selects retain native selection behavior.
- Enabled keyboard-first navigation on Big Cone and Dyeing DRAFT forms: Enter advances ordinary input fields; Ctrl+Enter invokes existing server validation and DRAFT save. Their current machine/source selectors and multi-group line controls are left unchanged.
- Enabled keyboard-first navigation on Baby Cone Measurement, 100-Shade Packing and Random 100-Piece Packing. Random Packing's date and box-quantity inputs are associated with the form from outside its markup; the engine now uses the form's native controls collection so those fields participate in focus order.
- Enabled keyboard-first navigation on Department/Machine Masters, PARTY Stock Use Requests and the guided Configuration master-data/configuration-draft editors. Their existing JavaScript submit handlers remain responsible for API calls; the shared engine only invokes the normal submit event.
- The engine auto-focuses only the first eligible entry form on multi-form pages and refuses Ctrl+Enter when no enabled submit control exists.
- Goods Receipt now declares its add-line button and line container through data attributes; repeat-last-item and duplicate-item notice remain receipt-specific adapters.
- No service, route, permission, schema or accounting rules changed.

## Verification after Phase 2
- `node --check app/static/smart-entry.js`: passed.
- Jinja compilation: `base.html`, `purchasing.html`, `supplier_form.html`, `journal_entry.html`, `big_cone_draft.html`, `dyeing_draft.html`, `baby_cone_measurement.html`, `packing.html`, `packing_random.html`, `production_masters.html`, `ownership_use_requests.html`, `configuration.html` all passed.
- Existing ERP health: `{"app":"ok","database":true}`.
- Static JavaScript and CSS served HTTP 200.
- No supplier, journal, receipt or other business document was submitted; no server restart.

## Phase 3 — Searchable pickers and explicit DRAFT recovery
- Added inline search inputs to opted-in native selects with 25 or more non-empty options. The original select remains the submitted control; no IDs or values are rewritten.
- Search filters option text and optgroup labels, reports match counts, selects a unique match with Enter, focuses the native select with ArrowDown, and clears with Escape or after selection.
- Selects whose options encode PO, GRN, department, batch, ownership or party dependencies remain native and untouched so the search layer cannot reveal invalid relationships.
- A MutationObserver initializes pickers for newly added/cloned production and purchasing rows. Cloned search controls are rebuilt with fresh listeners rather than retaining inert copied UI.
- Explicit Save recovery copy / Restore copy / Delete copy controls are enabled only on Goods Receipt and Purchase Return in this pilot.
- Recovery uses the current browser tab's `sessionStorage` only, expires after 2 hours, is capped at 128 KB, and is never uploaded. It excludes hidden fields (including CSRF), password/file/submit controls, disabled/read-only controls and token-like names. No automatic save occurs.
- Restore rebuilds dynamic line counts using the form's existing add/remove controls, restores named field values, and never submits. The operator must review the restored data and normal server validation still applies.
- A successful DRAFT response clears the previous recovery copy; a validation error leaves it available for manual recovery.
- Chrome headless tests passed for 50-option search, unique-match selection, cloned-row picker initialization, multi-line Goods Receipt and Purchase Return recovery, CSRF exclusion, and successful-save cleanup.

## Verification after Phase 3
- `node --check app/static/smart-entry.js`: passed.
- Jinja compilation of all 12 opted-in templates: passed.
- Chrome browser tests: `BROWSER_SMART_SELECT_TEST_OK`, `BROWSER_SMART_RECOVERY_TEST_OK`, `BROWSER_GOODS_RECEIPT_RECOVERY_TEST_OK`.
- Existing ERP health: `{"app":"ok","database":true}`.
- Static JavaScript and CSS served HTTP 200.
- No business document was submitted; no database, schema, stock, ledger, permission or accounting logic changed; no server restart.
- Backups: `app/static/smart-entry.js.large_select_backup_20261108_020635`, `app/static/smart-entry.css.large_select_backup_20261108_020635`, `app/templates/purchasing.html.recovery_backup_20261108_021058`.

## Next rollout
Continue searchable picker coverage across the remaining opted-in forms and extend recovery only after each multi-section form's row-recreation and validation behavior is reviewed. Accounting forms require extra care: the engine must not calculate or alter debit/credit values, and the existing server-side balance/period guards remain authoritative.

## Phase 4 — Baby Cone Measurement local recovery
- Enabled the existing explicit session-only recovery controls on Baby Cone Measurement.
- The measurement output-line selector is restored first and its existing change handler re-derives the hidden configuration snapshot ID from the selected output line. The hidden snapshot field remains excluded from recovery storage.
- Gross weight, tare, measured yards, optional required yards and operator code are restored as ordinary named fields. The measurement preview recalculates from restored values; server-side profile and measurement validation remains authoritative.
- The successful-save redirect returns to the same measurement page with `saved=1`; the template passes that state to the recovery engine so the previous local copy is cleared after a successful DRAFT save. Validation errors keep the copy available.
- Big Cone and both Packing forms were reviewed but intentionally not enabled in this phase: Big Cone submits only the currently enabled source-order row group and returns to a separate readiness page after save; Packing forms also redirect away after save and Random Packing serializes selected source allocations into a hidden JSON field. They need form-specific recovery/cleanup adapters so stale allocations or disabled dependent rows cannot be restored ambiguously.
- Backup: `app/templates/baby_cone_measurement.html.recovery_backup_20261108_025108`.
- Verification: Baby Cone template Jinja compilation passed; `node --check app/static/smart-entry.js` passed; Chrome headless test `BABY_CONE_RECOVERY_BROWSER_TEST_OK` passed (selected output line restored, snapshot ID re-derived, measurement values restored, successful-save cleanup cleared session storage).
- No business document was submitted; no database, schema, stock, ledger, permissions, accounting or production calculation logic changed; no server restart.

## Phase 5 — Big Cone and Packing recovery rollout
- Big Cone DRAFT form now offers explicit local recovery. Only enabled source-order row values are captured; the selected source order is restored first, then its existing filter re-enables the matching source rows. Department is restored before the machine filter is reapplied, preserving the valid department/machine pairing. Source-line hidden IDs and CSRF remain excluded and stay sourced from the current server-rendered form.
- Big Cone successful DRAFT creation redirects to the separate readiness page. That page clears only the Big Cone recovery key on load; validation failures remain on the entry page and retain the recovery copy. Approval and posting controls are not modified.
- Standard 100-Shade Packing now offers explicit local recovery for date, brand, finished-box quantity, shade-code text and remarks. The packing list's successful-save confirmation clears its recovery key.
- Random 100-Piece Packing has a form-specific recovery adapter for selected source-line allocations because its checkboxes/quantity controls are intentionally unnamed and its submitted allocation JSON is generated at submit time. Recovery stores selected source type + source line ID + quantity, matches only currently rendered eligible source lines, re-enables their quantity fields and updates the selected-line count. If a previously saved source line is no longer available on the reopened form, it is skipped and the user is explicitly warned; the current submit handler rebuilds allocation JSON from the restored visible selections. The successful-save confirmation clears the random-packing recovery key.
- Backups: `app/templates/big_cone_draft.html.recovery_backup_20261108_025528`; `app/templates/big_cone_readiness.html.recovery_clear_backup_20261108_025528`; `app/templates/packing.html.recovery_backup_20261108_025651`; `app/templates/packing_random.html.recovery_backup_20261108_025949`; `app/static/smart-entry.js.random_packing_recovery_backup_20261108_025919`.
- Browser verification: `BIG_CONE_RECOVERY_BROWSER_TEST_OK` (source order, department/machine dependency, only active source row, costs/remarks restored, successful redirect cleanup); `PACKING_RECOVERY_BROWSER_TEST_OK` (brand, box quantity, shade codes, remarks, cleanup); `RANDOM_PACKING_RECOVERY_BROWSER_TEST_OK` (selected allocations restored, missing candidate skipped with warning, submit JSON rebuilt from current candidates, cleanup).
- Jinja compilation passed for Big Cone entry/readiness, Baby Cone measurement, standard Packing and Random Packing templates. `node --check app/static/smart-entry.js` passed. ERP health remained `app=ok, database=true`; static JS HTTP 200.
- Recovery remains explicit, tab-local session storage with 2-hour expiry and 128 KB limit. It is not encrypted and is never uploaded. No business document was submitted; no database/schema, stock, ledger, posting, costing, production calculation, permission or accounting logic changed; no server restart.

## Phase 6 — Dyeing recovery safety review
- Reviewed the complete Dyeing DRAFT form and its client-side row/dependency logic. Recovery remains intentionally disabled; keyboard-first Smart Entry remains enabled.
- Yarn input rows are dynamic and define the line-number namespace consumed by both output rows and dye/chemical rows. Removing an input renumbers those references.
- Output rows contain a source-input line number; multiple output shades may point to one yarn input. Restoring output rows before yarn inputs or restoring stale source numbers could silently change allocation intent.
- Dye/chemical rows are dynamically filtered by the selected item variant, ownership type and party owner. Batch options encode all three dimensions; invalid options are hidden/disabled and a stale selected batch is cleared by the existing handler.
- Chemical source-line selectors also depend on the current yarn-input row count. A generic field restore could restore a line number that now points to a different input.
- The server redirects successful DRAFT saves back to the Dyeing form with `saved=1`; validation failures re-render the form with HTTP 422. A future adapter must clear recovery only on the successful redirect and retain it on validation failure.
- Safe implementation requires a form-specific adapter that restores yarn input rows first, rebuilds source-line choices, restores output/chemical rows, reapplies variant/ownership/party batch filtering, validates each saved source-line identity against a stable fingerprint, and warns/skips unavailable batch candidates. Current line-number-only references do not provide stable identity, so no recovery code was added.
- Also reviewed remaining non-recovery forms: Configuration includes edit/create modes and AJAX-driven master/configuration editors; Production Masters uses hidden record identity and dynamic editor state; PARTY Stock Use Requests uses custom selection state; Journal Entry has accounting-sensitive dynamic rows; Supplier form contains financial/bank/credit details. These remain excluded from generic recovery pending dedicated adapters and security/data-minimization review.
- No files outside this documentation note were changed in this review. No business document was submitted; no database/schema, stock, ledger, costing, posting, roles, permissions or accounting logic changed; no server restart.

## Phase 7 — Dyeing recovery adapter design (implementation gate)
Read-only review of `app/dyeing_draft_service.py` confirms the server accepts 1–100 yarn input lines, 1–100 dyed output lines and 1–100 dye/chemical lines. It normalizes yarn input `line_no` from current row order; each output and each chemical line references that line number. Output allocations are aggregated per source input and cannot exceed its entered KG quantity. The server remains authoritative for all validations.

### Required client-side snapshot shape
- Store three independent ordered sections: `materials`, `outputs`, and `chemicals`, plus order date, remarks and six actual process-cost fields.
- Assign each material row a temporary recovery-only key at snapshot time. Do not add hidden form inputs or submit these keys to the server.
- At save time, map each output/chemical `source_line_no` to the temporary key of the currently selected material row. Store the key, not just the mutable line number.
- Retain each section's row values by explicit row position within that section. Store no CSRF, hidden IDs, server IDs, credentials or unrelated page fields.

### Safe restore order
1. Validate snapshot version, route, 2-hour expiry, size cap and section counts (1–100 each) before mutating the page.
2. Recreate material rows first; restore variant, quantity, optional batch and notes; dispatch the existing native change events only where handlers exist.
3. Rebuild output and chemical source-line selectors from the restored material row order. Convert saved material recovery keys to the new current line numbers; if a key is missing, leave that reference unselected and show a visible warning rather than guessing.
4. Restore output shade, source-consumed KG, output KG and notes.
5. Restore chemical variant, ownership, party, unit, quantity and notes in dependency order. Re-run the existing variant/ownership/party batch filter; restore a batch only if that exact option remains enabled after filtering. Otherwise leave batch blank and warn.
6. Re-run the existing source-line selector synchronization after all material rows exist. Never submit automatically; require operator review and normal server validation.

### Clear and failure behavior
- Clear only after the successful redirect with `saved=1`; never clear on the HTTP 422 validation re-render.
- If any section cannot be recreated, stop and preserve the snapshot; do not partially submit or silently discard unmatched rows.
- If a source mapping or batch candidate is stale, restore all other safe values, leave that dependent selection blank and report exactly what needs review.
- Preserve the explicit Save recovery copy / Restore copy / Delete copy controls; sessionStorage remains tab-local, expires after 2 hours, max 128 KB, not encrypted and never uploaded.

### Implementation gate
This adapter must be implemented as a dedicated `dyeing` branch in `app/static/smart-entry.js`; do not route the form through the generic single-line-container recovery path. Keep the form's existing `data-smart-entry="dyeing"`, native names, line-number contract, source filters and all server/service code unchanged. Before enabling `data-smart-recovery="session"`, test three independent row counts, multiple outputs from one input, deleted/reordered input references, changed batch availability, variant/ownership/party changes, missing options, 100-line boundary, malformed/oversized/expired snapshots, successful redirect cleanup and 422 retention in a real browser harness. No DB/schema migration or business-logic change is required or permitted for this adapter.

- No application code changed in this design phase. No business document was submitted; no database/schema, stock, ledger, costing, posting, roles, permissions or accounting logic changed; no server restart.

## Phase 8 — Dyeing adapter implementation draft (2026-11-08)

A dedicated client-side adapter draft was created at `app/static/dyeing-recovery.js`. It uses a versioned v2 snapshot and three independently ordered sections (materials, outputs, chemicals), with date/remarks and six actual process-cost fields. It recreates source material rows first, rebuilds source-line choices, then restores outputs and chemicals. Chemical variant/ownership/party changes are dispatched before attempting to restore a batch; a batch that is no longer eligible is left blank with a warning. The adapter has a 2-hour sessionStorage TTL, 128 KB cap, 100-row per-section cap, explicit Save/Restore/Delete controls, and no automatic submission. CSRF and hidden fields are excluded by design.

**Activation deliberately withheld.** No connected browser automation or browser-test runtime was available on the authorized PC (Playwright, Puppeteer, Selenium and jsdom were not installed). JavaScript syntax, Jinja parsing, app health and static serving were verified, but these do not prove correct interactive behavior across all three dependent sections. Therefore the new adapter file is currently dormant: it is not included by the Dyeing template, and the form has no `data-smart-recovery="session"` opt-in. Existing Dyeing entry behavior is unchanged. Do not activate until real-browser tests cover multiple outputs per input, input row add/delete/reorder, changed chemical variant/ownership/party and batch eligibility, missing options, 100-row limits, malformed/oversized/expired snapshots, 422 retention, and successful-save cleanup.

No Dyeing service, route, database, stock, ledger, costing, posting, role, permission or accounting code was changed. No business document was submitted and no server restart occurred. Backups created before work:
- `app/static/smart-entry.js.dyeing_adapter_backup_20261108_031758`
- `app/templates/dyeing_draft.html.dyeing_adapter_backup_20261108_031758`

## Phase 9 — Chrome headless adapter edge-case verification (2026-11-08)

The dormant Dyeing recovery adapter was tightened before any activation:
- Save now refuses a section count outside 1–100 instead of writing a snapshot that the restore validator would immediately reject.
- Snapshot size is measured in UTF-8 bytes with Blob and capped at 131,072 bytes on both save and restore.
- Restore rejects malformed JSON, expired snapshots, timestamps more than one minute in the future, oversized payloads, non-object scalar payloads, and invalid per-section row arrays; invalid snapshots are cleared safely.
- No auto-save was added. Save/Restore/Delete remain explicit controls.

A Chrome headless browser harness on the authorized PC exercised the adapter against the same form IDs, row classes, field names, add/remove controls, source-line rebuilding and chemical batch-filter event flow:
- Core dependency/recovery checks: **7/7 passed** (three independent section counts, material values, multiple output source lines, PARTY batch after variant/ownership/party filtering, scalar fields, ineligible batch blank + warning).
- Edge cases: **6/6 passed** (malformed snapshot, expired snapshot, oversized snapshot, 101-row rejection, no invalid snapshot saved, exact 100-row boundary accepted).
- Combined: **13/13 passed**.

**Activation remains gated.** These are isolated browser-harness tests, not a signed-in end-to-end run against the live authenticated Dyeing page. The live template still does not load this adapter and has no recovery opt-in; therefore current production entry behavior is unchanged. Before activation, still require route-integrated checks of successful-save cleanup and 422 retention using the actual rendered page and confirmation that the browser's tab storage is available. No business document was submitted. No DB/schema/service/route/stock/ledger/costing/posting/permission/accounting changes and no server restart.

## Phase 10 — Dyeing recovery source-reference contract clarification (2026-11-08)

The Phase 7 temporary-key design is a stronger future-proof option, but the current dormant adapter implements a deliberately narrower positional contract. The live Dyeing form has no material-row reorder control: rows are added at the end and removed explicitly; the existing server normalizer assigns `line_no` from current row order. The adapter snapshots all material rows in order, recreates the exact saved material-row count in that same order before restoring dependent rows, and then restores output/chemical `source_line_no` values against the rebuilt selector list. Under this current no-reorder UI, saved ordinal N therefore continues to identify the same restored material row.

This is **not** a stable identity across arbitrary row reordering. If a reorder feature, drag/drop, sorting, or any other row permutation is introduced, positional recovery must be disabled or upgraded to temporary recovery-only material keys and dependent references mapped through those keys before any activation. Do not add such keys as submitted hidden inputs. Current template inspection confirms `syncSourceLineChoices()` rebuilds output and chemical selectors from material DOM order, while `removeDyeingRow()` and `addDyeingRow()` update those choices. The template still does not include `dyeing-recovery.js` and has no `data-smart-recovery="session"`; recovery remains dormant.

The exact scalar field allowlist is `dyeing_date`, `remarks`, `labour_cost`, `machine_cost`, `electricity_cost`, `water_cost`, `boiler_fuel_cost`, and `drying_cost`. The current form has `#dyeing-form`, `.smart-entry-toolbar`, `#material-lines`, `#output-lines`, `#chemical-lines`, and the three matching add buttons/template IDs expected by the adapter. `saved=1` is rendered as `saved` in the Jinja template; the route-integrated cleanup flag still needs to be deliberately passed by the template before activation. HTTP 422 retention and successful redirect cleanup remain unverified against the authenticated live route.

No application template, adapter activation, service, route, database, stock, ledger, costing, posting, role, permission or accounting logic was changed in this clarification. No business document was submitted; no server restart.

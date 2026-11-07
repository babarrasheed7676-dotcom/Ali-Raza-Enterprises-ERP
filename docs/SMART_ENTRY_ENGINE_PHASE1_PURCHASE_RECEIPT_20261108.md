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

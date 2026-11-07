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
- No autosave or browser persistence was added; unfinished form data is not silently stored.
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

## Next rollout
Continue the rollout to remaining production drafts and inventory after reviewing each form's dynamic row behavior and module-specific validation. Accounting forms require extra care: the engine must not calculate or alter debit/credit values, and the existing server-side balance/period guards remain authoritative.

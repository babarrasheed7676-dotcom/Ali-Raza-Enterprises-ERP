# ERP Database Routine Route Reachability Audit — 7 November 2026

## Scope and safety

Read-only static review of app/main.py, Python services, and app templates in the Git mirror. This checks whether database routines have application route/caller evidence. No app code, database object, role, grant, DSN, production record, or server state was changed.

## Purchase receipt and return paths — route evidence found

The current application source contains these protected routes:

| Workflow | Route | Permission dependencies |
|---|---|---|
| Purchase receipt approval | POST /modules/purchasing/receipts/{receipt_id}/approve | purchasing.approve + inventory.approve |
| Purchase receipt posting | POST /modules/purchasing/receipts/{receipt_id}/post | purchasing.post + inventory.post |
| Purchase return draft | GET/POST /modules/purchasing/returns/new | purchasing.create |
| Purchase return approval | POST /modules/purchasing/returns/{return_id}/approve | purchasing.approve + inventory.approve |
| Purchase return posting | POST /modules/purchasing/returns/{return_id}/post | purchasing.post + inventory.post |

State-changing purchase receipt/return actions validate the double-submit CSRF token in their route/service paths. Receipt and return approval/posting call the purchasing service functions which directly invoke inventory approval/posting routines. This is current route evidence for candidate runtime EXECUTE on the three routines documented in the caller map, subject to restored-database testing and table-level permission analysis.

## Sales & Dispatch — no active route found

- app/main.py module registry labels Sales & Dispatch as status Planned and links to /modules/sales-dispatch.
- The route-decorator inventory in app/main.py contains no GET/POST/PUT/DELETE/PATCH route for /modules/sales-dispatch or a sales order/dispatch API.
- Search of app Python and HTML files found no direct call to sales.confirm_sales_order, sales.cancel_sales_order, sales.reserve_sales_order_line, or sales.post_dispatch.
- The database call graph shows sales.post_dispatch calls stock approval, reservation consumption, and stock posting; sales.reserve_sales_order_line calls document numbering.
- These database routines are therefore not supported by a current application route in the inspected source. Do not include their EXECUTE grants in the initial web-runtime grant candidate until the Sales & Dispatch workflow is implemented and route-protected.

## Packing FG transfer — no active caller found

- Search of app Python and HTML files found no reference to production.post_packing_fg_transfer or production.packing_fg_transfers.
- The database routine exists and calls document numbering, stock approval, and stock posting.
- The routine has no current Python route/service caller evidence in the inspected app tree. Do not grant EXECUTE to the web runtime role solely because the routine exists in PostgreSQL.

## Other database routines

- inventory.get_available_stock, production.calculate_packing_cost, production.calculate_packing_cost_test, and production.post_packing_fg_transfer have no direct Python call reference in the static scan (FG transfer has the database-level calls described above).
- inventory.consume_stock_reservation is called by sales.post_dispatch, but Sales & Dispatch is Planned and no route is present.
- These conclusions apply to the current app source only. External SQL clients, scripts, future routes, dynamic SQL, or other databases may invoke routines outside this source tree.

## Initial runtime grant design implication

1. Keep the initial candidate EXECUTE list limited to verified current route workflows: core.get_next_document_no, inventory.approve_stock_document, and inventory.post_stock_document. Even these remain candidates, not grants, until restored-database least-privilege tests pass.
2. Do not grant EXECUTE on sales or packing transfer routines to the web runtime role while their route/workflow is Planned or absent.
3. Preserve the separate purchase draft, approval, and posting controls. Never collapse normal Save into posting.
4. Ensure the runtime role has only the exact table rights required by direct SQL and SECURITY INVOKER routine/trigger reads. Routine EXECUTE does not automatically grant the underlying table rights.
5. Revisit the candidate list when Sales & Dispatch or packing FG transfer gains a protected route and a tested service lifecycle.

## Status

Current application route evidence reviewed. No grants, role changes, DSN changes, code changes, or live data changes were performed.

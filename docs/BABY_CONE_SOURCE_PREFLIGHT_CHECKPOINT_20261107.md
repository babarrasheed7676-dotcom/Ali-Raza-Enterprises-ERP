# Baby Cone Source Preflight — Live Readiness Checkpoint — 7 November 2026

## Scope and safety
Read-only verification against company 1 in the local PostgreSQL database and the Baby Cone source preflight service. No application/database records, schema, permissions, stock, running processes, or configuration were changed.

## Runtime result
- Application health had previously been verified as app OK / database connected; this checkpoint did not restart the live server.
- The exact stock dimension index exists: `inventory.uq_stock_balance_dimension` on company, item variant, batch, location, ownership type, owner party, and process stage.
- Stock balance rows inspected: 5; null quantity rows: 0; duplicate exact-dimension groups: 0.
- Baby Cone preflight is read-only; DRAFT creation remains disabled; no reservation or stock posting occurs.

## Current data blockers
- POSTED Big Cone orders for company 1: 0.
- POSTED Big Cone output lines grouped by destination: none.
- Therefore eligible POSTED Large Cone → BABY_CONE source lines: 0. No sample source was inserted.
- Active YARN variants: 2 (`YARN-40/2-COTTON`, `YARN-50/3-COTTON`).
- Approved Baby Cone `MEASUREMENT_PROFILE` versions: 0.
- Active company departments: 0.
- Active company machines: 0.
- RAW_STORE godown, BIG_CONE stage, and BABY_CONE stage are present and active.

## Interpretation
The empty source register is explained by the absence of POSTED Big Cone production/output records, not by a missing stock-balance unique key. The current company also has no approved Baby Cone measurement profiles and no active department/machine setup. These are genuine setup/data gates; do not fabricate operational records to make the preflight appear ready.

## Safe next sequence
1. Configure real departments and machines through the approved master-data process.
2. Approve effective Baby Cone measurement profiles for the actual output variants and retain the existing weight-per-length method.
3. Complete and POST real Big Cone orders whose output destination is BABY_CONE, with exact stock dimensions.
4. Re-run the read-only preflight and validate party ownership/rates and source quantities.
5. Keep Baby Cone DRAFT creation disabled until material/output linkage, salary/labour and overhead capture, and measured-loss/reconciliation rules are verified.
6. Do not implement inventory posting, reservation, approval, or reversal based only on this checkpoint.

## Explicit non-actions
No database writes, dummy masters, dummy orders, stock reservations, inventory postings, code changes, server restart, or permission changes were made in this checkpoint.

# Nalki Packing — Phase 2D: Random 100-Piece Reuse Validation
Date: 05-Nov-2026
Backup: BACKUP_PACKING_PHASE2D_RANDOM_RULES_20261105

## Business rules carried forward
1. Random finished box contains exactly 100 Nalki pieces from 100 unique shade IDs, one piece of each shade per finished box.
2. Fresh Nalki and party-rejected-but-still-usable Nalki may be mixed in the same random-box run.
3. Rejected usable stock is optional and is not automatically prioritized. It is not wastage.
4. Preserve the original source line, batch, brand/shade, ownership type, owner party and existing unit cost for every allocation.
5. Do not convert PARTY stock into OWN stock. OWN rows must not carry an owner party; PARTY rows must retain their owner party.
6. Carry the existing Nalki source cost into the random packing composition; do not re-add the original Nalki production cost as a new process charge.
7. This random workflow is separate from the fixed 100-shade assortment workflow. It does not impose the fixed-assortment single-brand selection rule; every shade still resolves to one consistent brand variant.
8. One random finished box consumes 10 separate regular 10-piece boxes. The regular box is PACK_BOX-STD; the finished 100-piece box is a separate finished-product pack.

## Implementation in this phase
- Added app/packing_random_service.py with pure validation only.
- Supports mixed fresh and verified usable party-rejected source allocations.
- Requires exactly 100 unique shade IDs and exactly one piece per shade per finished box. If a shade is supplied by more than one source allocation, the total for that shade must equal the finished-box count.
- Requires positive source-line, variant, shade and brand IDs; valid OWN/PARTY ownership and owner-party relationship; positive quantities within the supplied source availability; nonnegative finite existing unit cost.
- Party-rejected source allocation is rejected unless the caller explicitly identifies it as verified usable.
- Source-line duplicates are rejected; source unit cost is carried and line total is calculated from that existing cost.
- Random workflow permits mixed brands where the shade IDs are distinct; the fixed assortment workflow remains separately brand-restricted.
- Added 8 unit tests in tests/test_packing_random_service.py.

## Live database source-readiness audit
Read-only transaction against company 1:
- production.nalki_output_lines: 0 rows.
- production.outside_labeling_return_lines: 0 rows.
- production.packing_orders: 2 existing rows.
- production.packing_order_items: 4 existing rows.
- production.packing_order_status_history: 0 rows.
- Therefore no live fresh Nalki output or outside-labeling return source lines currently exist to exercise source-line mapping. No rejected-usable stock source table was found by name in the current production schema. Do not assume outside-labeling returns are the same thing as party-rejected Nalki.
- Existing two packing orders and four item rows remain unchanged.

## Validation
- Targeted packing suites: 33/33 passed.
- Full test suite: 161/161 passed.
- Python compileall: passed.
- Live health: app=ok, database=true.
- All source-readiness queries ran in a READ ONLY transaction.
- No database schema, stock, ledger, existing packing rows, permissions, roles, labour approvals, posted FG transfers, or accounting records changed.

## Remaining work
1. Identify the authoritative operational source for party-rejected-but-usable Nalki and its approval/quality status before building the live source selector. It must not be guessed from outside-labeling return records.
2. Add source-line allocation persistence and traceability after the source mapping is confirmed. Do not enable random packing stock issue, material consumption, labour payment, QC posting, or finished-goods transfer yet.
3. Keep fixed 100-shade assortment and random 100-piece workflows separate in the UI and records.
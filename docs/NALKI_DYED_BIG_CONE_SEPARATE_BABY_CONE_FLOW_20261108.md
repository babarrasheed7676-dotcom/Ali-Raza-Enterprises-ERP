# Nalki Direct from Dyed Big Cone — Baby Cone Separate Flow
Date: 8 November 2026
Scope: Source-code review and authoritative factory workflow correction. No production data changed.

## Factory rule (authoritative)
Nalki is a separate production process. Nalki is made directly from the dyed Big Cone / dyed dyeing cone output after Dyeing. Nalki is NOT made from Baby Cone and Baby Cone is NOT an intermediate step for Nalki.

## Correct process structure
1. PURCHASE / RAW_STORE: purchased raw yarn.
2. BIG_CONE: wind raw yarn onto perforated jaali/dye cones, exactly 1.25 KG per prepared cone, for dyeing.
3. DYEING: consume prepared Big Cone yarn and produce dyed Big Cone / dyed cone stock, preserving shade, batch, variant, ownership and cost lineage.
4. After Dyeing, keep the production routes separate:
   - NALKI: direct input is eligible POSTED dyed Big Cone output from Dyeing.
   - BABY_CONE: a separate production process with its own independently verified source, conversion, measurements, costing, loss and approval rules. It is never the source of Nalki.
5. Nalki then follows its own agreed outside-labeling and packing/finished-goods flow. Do not merge its production with Baby Cone.

## Source-code findings
- Big Cone DRAFT service reads purchased OWN YARN stock at RAW_STORE / PURCHASE and prepares 1.25 KG cones for DYEING. Its output destination allow-list is DYEING.
- Dyeing DRAFT service creates DYED_THREAD output lines at RAW_STORE / DYEING, but the inspected workflow still lacks a completed separate approval/posting stock handoff.
- Baby Cone source preflight currently searches POSTED Big Cone output lines with destination_type='BABY_CONE'. That does not match the Big Cone service allow-list and would bypass Dyeing. It must not be repurposed as a Nalki source.
- The inspected application source has no completed Nalki source-selection / DRAFT / approval / posting service-route implementation established by this audit. A production overview reference to nalki_orders alone is not an operational workflow.

## Required implementation sequence
1. Complete Dyeing DRAFT -> separate approval -> posting. Posting must consume prepared Big Cone stock and create immutable, traceable DYED_BIG_CONE / dyed cone inventory at RAW_STORE / DYEING (use the approved item identity; do not silently relabel DYED_THREAD if the factory master distinguishes it).
2. Implement Nalki source preflight against eligible POSTED Dyeing output / DYEING-stage dyed Big Cone stock. Enforce source-output-line lineage, shade, batch, variant, OWN/PARTY owner, party rate/cost, exact KG quantity, single RAW_STORE location and prevention of double allocation.
3. Implement Nalki's own DRAFT -> separate approval -> posting and its previously agreed Nalki-specific product, shade, box, labeling, labour and reconciliation rules.
4. Audit Baby Cone separately. Do not connect Baby Cone to Nalki. Its valid source and production rules must be confirmed independently before enabling its production entry.
5. Keep one physical godown. Process stages are workflow dimensions, not separate warehouses. Do not create dummy machines, departments, stock or production records.

## Safety boundary
This correction is documentation/source-review only. No schema, code, master data, roles, permissions, inventory, stock, ledger, production records or server process was changed. No existing audit/test was repeated unnecessarily.

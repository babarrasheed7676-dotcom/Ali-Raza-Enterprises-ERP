# Nalki Route Validation Mismatch — 8 Nov 2026

## Confirmed factory rule
Nalki production input is the dyed Big Cone / dyed cone output after Dyeing. Baby Cone is a separate process and is never Nalki's input. The 1.25 KG perforated jaali cones are prepared in Big Cone before Dyeing; do not confuse raw pre-dye Big Cone with dyed post-dye Big Cone.

## Exact code mismatch found (read-only)
1. app/configuration_examples.py currently seeds PROCESS_ROUTE key NALKI-FROM-LARGE-CONE, route name "Large Cone to Nalki", and a step LARGE_CONE -> NALKI. Its help text says Nalki must originate from Large Cone.
2. app/configuration_runtime_service.py validate_process_route_payload() rejects BABY_CONE input but also requires a LARGE_CONE -> NALKI step.
3. This validation/example does not encode the actual factory route: DYEING output (dyed Big Cone) -> NALKI. Simply removing the Baby Cone rejection would not fix the mismatch.
4. The Nalki packing source is a later-stage process and does not implement Nalki production input selection. Do not mistake packing availability for Nalki production source linkage.

## Required correction before enabling route setup
- Replace the stale route example with a clearly named NALKI-FROM-DYED-BIG-CONE route whose input product type explicitly represents the approved dyed Big Cone output from Dyeing (final canonical code must match the active item/product master; do not invent a product code).
- Update route validation to require Dyeing's posted dyed Big Cone output as the Nalki input and reject Baby Cone and undyed/raw Big Cone inputs.
- Ensure Dyeing posting emits the canonical dyed Big Cone stock item at RAW_STORE / DYEING, preserving batch, shade, variant, ownership and cost.
- Add strict Nalki source-line linkage and allocation protection; Nalki posting must consume only eligible posted dyed output and create Nalki output with auditable cost lineage.
- Review existing approved configuration versions before changing validator compatibility. Do not silently mutate historical approved snapshots or production records.

## Safety
This is a source-code audit note only. No source code, database schema/data, configuration versions, roles, permissions, inventory, stock, ledger or server process was changed.

# ERP Migration File Integrity Manifest — 8 November 2026

## Scope

SHA-256 and static DDL-token inventory for the 31 current `database/migrations/*.sql` files. Files with `.backup` suffixes were excluded. This is a repository integrity manifest, not proof that any migration was applied to the live database. The database has no migration ledger, and no migration was executed during this audit.

## Summary

- Current migration files: **31**
- `CREATE TABLE` statements: **12**
- `ALTER TABLE` statements: **26**
- `CREATE FUNCTION` statements: **52**
- `CREATE TRIGGER` statements: **45**
- `CREATE INDEX` statements: **26**
- Matches for `DROP TABLE`, `TRUNCATE TABLE`, or `DELETE FROM`: **0**
- All 31 file hashes below were computed from the safe working copy.

Counts are simple static token counts, not a full SQL parser. A migration may also contain other DDL such as constraints, policies, comments, grants, or trigger/function replacements not represented by these columns.

## File manifest

| Migration file | SHA-256 | CT | AT | FN | TR | IX |
|---|---|---:|---:|---:|---:|---:|
| 20261105_001_general_ledger.sql | e5a1cc80274e6f034875b27027409890308a2f3c3a2a71f5bb662d27a72cfc94 | 2 | 0 | 3 | 3 | 10 |
| 20261105_002_configuration_foundation.sql | 3c58261e90b3176473f448a98860ff3f9a3f4d1e416ef9e95e253275bad1770a | 3 | 0 | 0 | 0 | 3 |
| 20261105_003_packing_source_allocations.sql | c755d1cbadd03a71de638ec94cd7e04d1d3dd8f3b4689a60d249fe5188bb125b | 1 | 2 | 1 | 1 | 5 |
| 20261105_004_packing_source_guard_hardening.sql | 5d89e340771e00889b40a01ec75203fee8bddeab9c50c5f03bbe05410abf8e82 | 0 | 0 | 1 | 0 | 0 |
| 20261105_005_packing_source_item_guard.sql | 417de843ffd1753d18f98b13be5b28407d7838369c37ca2b2c42c38636cd105 | 0 | 0 | 1 | 0 | 0 |
| 20261105_006_packing_configuration_snapshots.sql | d8ba18a1695e6d8a0c1dc4f6db1e4245757e92f2454d03e1982b873c06979ed5 | 1 | 0 | 1 | 1 | 0 |
| 20261105_007_packing_configuration_snapshot_guard.sql | 509864d6f9895d08365bb486e753b8dfe11eeac662ad1e9fd5c58683845c8009 | 0 | 0 | 1 | 0 | 0 |
| 20261105_008_purchasing_configuration_snapshots.sql | d0df0c5592a70010a9d3b7111077773c32aa3b1de8315a501f1ea62267e19a15 | 1 | 0 | 1 | 1 | 0 |
| 20261106_009_baby_cone_configuration_snapshots.sql | 78c9f39d0fda9b9ef81f43f17226f569511c23a3bccc0cbb319a4f9002138325 | 1 | 0 | 1 | 1 | 0 |
| 20261106_010_baby_cone_measurement_drafts.sql | d80e2e586c9eb48c2267738d6164921bfb52f18df6772fd6d7f4f6d1df93e657 | 1 | 0 | 1 | 1 | 0 |
| 20261106_011_ownership_use_requests.sql | 1851adf6bb4739129abcd8c2a501f24854acbe931a6eda7c952e9ed6c373aed8 | 1 | 4 | 3 | 5 | 1 |
| 20261106_012_party_use_approval_gate.sql | 840c4f4bf86fc7ca7d6d25abdc1d82053f13caa78c1b103129ab3d6c4f44e46c | 0 | 0 | 1 | 2 | 0 |
| 20261106_013_party_use_cost_snapshots.sql | 043e8066cc03d3c5a31cc830fb1e5dbc7cb9053a0b519ff5f372a01d429c3cce | 0 | 4 | 2 | 2 | 0 |
| 20261106_014_party_cost_snapshot_rounding.sql | 8c700182e7431e82805d8fca368de2a6c1be1ebf88bf4f94c844699121982d6c | 0 | 0 | 1 | 0 | 0 |
| 20261106_015_party_dyeing_cost_immutability.sql | dabb3385701326a671ebb0f722fb871d730cd6999bd519261ef89d63f5ec3cf0 | 0 | 0 | 1 | 0 | 0 |
| 20261106_016_party_request_link_immutability.sql | 28ff526af311b22e5472d4958f6f2dfeec00aeda1e4b4c1739aa2eb10971d350 | 0 | 0 | 2 | 4 | 0 |
| 20261106_017_party_request_record_integrity.sql | f08aae6616ff8d8463c8169be8d48ca3b7698e987c10fd7f74ac30378371bc3b | 0 | 0 | 2 | 1 | 0 |
| 20261107_018_dyeing_unit_conversion_snapshots.sql | 5aabee396c37778596629728f520013ef0f770eda0b7cdd1626e71a2ac603f92 | 1 | 0 | 2 | 2 | 1 |
| 20261107_019_dyeing_conversion_snapshot_integrity.sql | 53352707270d8ad66fdb13111c844b27563a4bac5dc9f91e71e33007f1f2c67c | 0 | 2 | 1 | 0 | 0 |
| 20261107_020_dyeing_conversion_precision_guard.sql | a8a0fe297c09d92fd83190b1fbd30fa20137156255b9681d626b8b7b99627a0b | 0 | 2 | 0 | 0 | 0 |
| 20261107_021_production_source_line_traceability.sql | 79be6c0ac76ea4e32169c019ac76aa8fba51f7475ddfe16f9e24f3ac8cf856bc | 0 | 4 | 4 | 4 | 2 |
| 20261107_022_big_cone_dyeing_output_type_correction.sql | da3fec4a815330f69dbfd74ea1e489f36faf264ee8bf85e9d50f81f752907f76 | 0 | 0 | 1 | 0 | 0 |
| 20261107_023_production_source_quantity_allocation_guard.sql | 99595e8a1097e4ba70694d1fbed13986fa011fb7dce39c7cc7306f421a1d508d | 0 | 0 | 2 | 0 | 0 |
| 20261107_024_production_source_line_immutability.sql | 0048f726b626c0b57e815699b0dd267b388a4e70eb940e94959f8fe93a7ecdb6 | 0 | 0 | 2 | 6 | 0 |
| 20261107_025_release_cancelled_production_source_allocations.sql | fdc9f4b733a7224a74decc02aab2388ab6c8e6d1a34dcbeec21b0e87e48ab139 | 0 | 0 | 2 | 0 | 0 |
| 20261107_026_production_input_output_lineage.sql | a3eca0c1360416d24fb1614641bbd67be3270573e5db3e7e5d1e6def990033f9 | 0 | 4 | 4 | 6 | 2 |
| 20261107_027_single_godown_production_stage_guards.sql | 68a66da58ccaa75580eeaa6462c7190e41cd484ee8d486e2bf8356c55cc073f4 | 0 | 0 | 2 | 0 | 0 |
| 20261107_028_fail_closed_production_source_masters.sql | bffd3880f49cdc0db15f6760bfb5bbef1212852245d7cad071ed3ab35df3630b | 0 | 0 | 2 | 0 | 0 |
| 20261107_029_dyeing_yarn_input_output_traceability.sql | aad8bee3d4b32a77c18d55a46677a7abbe7d93529ed6e590531bae9329cad5b4 | 0 | 2 | 3 | 3 | 1 |
| 20261107_030_dyeing_shade_and_output_batch_identity.sql | a195194430ac2364e0d4a0e66a94ab7028edf6688569a678bb6a4be65c33899a | 0 | 0 | 2 | 0 | 0 |
| 20261107_031_dyeing_consumption_source_yarn_lineage.sql | d025fd05266a93987185b424c0bfbeb5301113dbde43d6b4ed4785b00965978d | 0 | 2 | 2 | 2 | 1 |

## Important constraints

- These hashes establish the exact current file contents only. Recompute before any staging or factory deployment.
- No migration execution status is recorded in the database; do not mark scripts as applied based solely on this manifest.
- Apply migrations only to a verified isolated staging restore after checking prerequisites and ordering.
- Keep live database privileges, ownership, schema, records, DSN and server process unchanged until separately approved.

## Status

Read-only migration file integrity inventory created. No migration was run and no database object was changed.

## Transaction and rerun-safety characteristics

A second static pass checked every migration file for transaction boundaries and object-removal statements:

- **31/31** scripts contain explicit top-level `BEGIN;` and `COMMIT;` markers.
- All **12/12** `CREATE TABLE` statements are plain `CREATE TABLE`, not `CREATE TABLE IF NOT EXISTS`. They are not safe to rerun blindly after successful application.
- Three migrations intentionally drop existing objects before recreating/replacing them:
  - `20261106_012_party_use_approval_gate.sql`: drops two named triggers and `production.assert_party_use_request_link()` using `IF EXISTS`.
  - `20261107_019_dyeing_conversion_snapshot_integrity.sql`: drops `ck_dyeing_unit_conversion_status` before replacing the constraint.
  - `20261107_024_production_source_line_immutability.sql`: drops two named source-line triggers using `IF EXISTS`.
- No `DROP TABLE`, `TRUNCATE TABLE`, or `DELETE FROM` statement was found in the 31 files.
- These properties do not establish full idempotency. Other `ALTER TABLE`, `CREATE INDEX`, constraint, function and trigger statements may also fail if replayed against an already-migrated schema.

**Deployment rule:** on a restored staging database, determine the exact migration boundary first, then execute each missing migration once in filename order with preconditions, postconditions and recorded hash/result. Never replay the full directory against the live database or assume `BEGIN/COMMIT` makes a migration safe to rerun.

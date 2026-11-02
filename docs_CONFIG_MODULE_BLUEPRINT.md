# Ali Raza Enterprises ERP — Flexible Configuration Module Blueprint

**Status:** Design scaffold added to the UI on 16 October 2026. The current page is read-only and does not persist settings. Do not treat this as a completed operational configuration module.

## Design objective

Configuration must be data-driven and extensible. Adding a future product, brand, shade, product attribute, unit, package, conversion method, production route, costing policy or approval rule should normally be possible through master data rather than a new code release.

## Proposed configuration entities

1. **Product types** — user-defined types such as Baby Cone, Nalki, Large Cone, future products; each may reference configurable attributes, process routes and policies.
2. **Products / variants** — code, name, type, unit, brand, shade, category, attributes and active status. Avoid fixed brand/shade enums in code.
3. **Attribute definitions** — attribute name, data type, unit, required/optional flag, allowed values, validation and scope (product, variant, batch or production order).
4. **Units and conversions** — configurable units and conversion relationships with precision and effective dates.
5. **Measurement profiles** — measurement method, required readings, formula, tolerance, evidence/operator and approval requirements.
6. **Packaging profiles** — pieces per box, package levels, allowed brand/category mixing, tare/empty packaging returns and component consumption.
7. **Process routes** — configurable ordered stages and permitted input/output product types; avoid embedding the complete business flow as hard-coded branching.
8. **Ownership policies** — allowed ownership types by product type/process, party-stock permission, required rate, authorization and settlement policy.
9. **Costing and loss policies** — salary/theka method by process, waste allowance, how often allowance is applied, excess-variance treatment and effective dates.
10. **Approval policies** — required role, scope and action; approval cannot be inferred from a user-interface control alone.
11. **Configuration versions and audit** — draft/review/approved/retired lifecycle, effective-from/to, changed-by, approved-by, old/new values, reason and references to transactions using the version.

## Initial Baby Cone requirements

- Keep item/variant-specific grams-per-yard profiles.
- Record gross cone weight, empty cone/core tare, net yarn grams, measured yards, date, operator and approval metadata.
- Formula: `grams_per_yard = net_yarn_grams / measured_yards`.
- Formula: `required_kg = yards * grams_per_yard / 1000`.
- Validate positive measured yards and net weight; retain the original measurement rather than overwriting it.
- Production Head approval is required for this configuration change; Owner approval is not required by the stated rule.
- Keep OWN stock and each individual PARTY stock ledger separate.
- Apply the agreed Dyeing waste allowance once at material issue; excess actual loss is company process variance. Do not deduct the same allowance again downstream.

## Initial Nalki requirements

- Initial packaging default: 10 pieces per standard box.
- Initial brand weights: Tailor 38 g, Channel 52 g, Golden Chain 60 g.
- Brands, shades, categories and packaging profiles must be addable as master data; current brands and shade ranges must not become hard-coded limits.
- Support brand-wise 100-piece finished boxes and configured allowed mixing rules.
- **Unresolved policy conflict:** an earlier configuration instruction says Nalki must not have Party Stock; later discussion describes controlled authorized PARTY-stock use. Do not activate party stock for Nalki until the user explicitly resolves the conflict. Store the policy as configurable, not a permanent code branch.

## Safety and implementation order

1. Map existing PostgreSQL tables/functions and identify which configuration tables already exist.
2. Propose migration SQL for review; never apply schema changes automatically.
3. Use a least-privilege application database role and enforce permissions server-side.
4. Add versioned configuration records and approval/audit events before enabling save buttons.
5. Validate changes against posted transactions; historic transactions retain the rule version used when they were posted.
6. Test formulas, duplicate prevention, approvals, concurrent edits, rollback, backups and migration restore.
7. Only then make configuration write-enabled. Until then, the UI is explicitly read-only.

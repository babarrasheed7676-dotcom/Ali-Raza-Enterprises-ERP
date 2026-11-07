# Configuration Phase 1D — Controlled Supersession
Date: 05-Nov-2026

## Implemented
- Draft creation accepts an optional supersedes_version_id and validates that the referenced record is APPROVED, belongs to the same company, and has the same configuration type and key.
- The new version must begin after the predecessor's effective start and cannot supersede a predecessor that already ended before the new start.
- Independent approval remains mandatory; the draft creator cannot approve their own submission.
- Approval locks the predecessor and all competing approved versions, checks for date overlap, then atomically marks the predecessor RETIRED and closes its effective period to the day before the new version begins.
- The old payload is retained; a SUPERSEDED audit event records the transition. The new version approval and predecessor retirement occur in the same database transaction.
- History now shows record IDs and effective end dates so an administrator can select the predecessor.
- No new permission or database migration was required; the existing supersedes_version_id column, RETIRED status, and SUPERSEDED audit event type were used.

## Verification
- Python compilation passed for configuration service and API.
- Focused configuration suite: 29/29 passed, including three supersession date-boundary tests.
- No configuration draft was created; no existing configuration version was retired; no operational rules or business records were changed.
- A code backup was created before edits under BACKUP_CONFIG_SUPERSESSION_20261105_204110.
- Database backup attempt was stopped because PostgreSQL password authentication did not complete in the unattended process. No DB writes were made; the previously verified pre-approval backup remains the last completed database backup.

## Operational boundary
Supersession changes only the governed configuration version history after an independent approval. Approved configurations are not yet consumed by production, stock, packaging, or costing calculations. Operational integration still requires rule-by-rule validation and immutable snapshots on posted documents.
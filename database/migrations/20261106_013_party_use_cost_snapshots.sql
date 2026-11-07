-- Ali Raza Enterprises ERP
-- 20261106_013_party_use_cost_snapshots
-- Immutable, per-line approved PARTY-use rate/total/policy snapshot.
BEGIN;
ALTER TABLE production.dyeing_consumption_lines
 ADD COLUMN ownership_policy_version_id BIGINT REFERENCES configuration.config_versions(id) ON DELETE RESTRICT,
 ADD COLUMN ownership_locked_unit_rate NUMERIC(20,6),
 ADD COLUMN ownership_cost_total NUMERIC(20,6),
 ADD COLUMN ownership_cost_snapshot JSONB,
 ADD COLUMN ownership_cost_snapshotted_at TIMESTAMPTZ;
ALTER TABLE production.packing_source_allocations
 ADD COLUMN ownership_policy_version_id BIGINT REFERENCES configuration.config_versions(id) ON DELETE RESTRICT,
 ADD COLUMN ownership_locked_unit_rate NUMERIC(20,6),
 ADD COLUMN ownership_cost_total NUMERIC(20,6),
 ADD COLUMN ownership_cost_snapshot JSONB,
 ADD COLUMN ownership_cost_snapshotted_at TIMESTAMPTZ;
ALTER TABLE production.dyeing_consumption_lines
 ADD CONSTRAINT ck_dyeing_party_cost_snapshot_complete CHECK (
  (ownership_cost_snapshot IS NULL AND ownership_policy_version_id IS NULL
   AND ownership_locked_unit_rate IS NULL AND ownership_cost_total IS NULL
   AND ownership_cost_snapshotted_at IS NULL)
  OR (ownership_cost_snapshot IS NOT NULL AND ownership_policy_version_id IS NOT NULL
   AND ownership_locked_unit_rate>0 AND ownership_cost_total>=0
   AND ownership_cost_snapshotted_at IS NOT NULL
   AND ownership_cost_snapshot->>'module'='DYEING'
   AND ownership_use_request_id IS NOT NULL
   AND (ownership_cost_snapshot->>'request_id')::bigint=ownership_use_request_id)
 );
ALTER TABLE production.packing_source_allocations
 ADD CONSTRAINT ck_packing_party_cost_snapshot_complete CHECK (
  (ownership_cost_snapshot IS NULL AND ownership_policy_version_id IS NULL
   AND ownership_locked_unit_rate IS NULL AND ownership_cost_total IS NULL
   AND ownership_cost_snapshotted_at IS NULL)
  OR (ownership_cost_snapshot IS NOT NULL AND ownership_policy_version_id IS NOT NULL
   AND ownership_locked_unit_rate>0 AND ownership_cost_total>=0
   AND ownership_cost_snapshotted_at IS NOT NULL
   AND ownership_cost_snapshot->>'module'='PACKING'
   AND ownership_use_request_id IS NOT NULL
   AND (ownership_cost_snapshot->>'request_id')::bigint=ownership_use_request_id)
 );
CREATE OR REPLACE FUNCTION production.guard_ownership_cost_snapshot()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE req production.ownership_use_requests%ROWTYPE; line_company BIGINT;
BEGIN
 IF OLD.ownership_cost_snapshot IS NOT NULL AND (
   NEW.ownership_cost_snapshot IS DISTINCT FROM OLD.ownership_cost_snapshot
   OR NEW.ownership_policy_version_id IS DISTINCT FROM OLD.ownership_policy_version_id
   OR NEW.ownership_locked_unit_rate IS DISTINCT FROM OLD.ownership_locked_unit_rate
   OR NEW.ownership_cost_total IS DISTINCT FROM OLD.ownership_cost_total
   OR NEW.ownership_cost_snapshotted_at IS DISTINCT FROM OLD.ownership_cost_snapshotted_at
 ) THEN
  RAISE EXCEPTION 'An approved PARTY-use cost snapshot is immutable';
 END IF;
 IF NEW.ownership_cost_snapshot IS NOT NULL THEN
  SELECT * INTO req FROM production.ownership_use_requests
   WHERE id=NEW.ownership_use_request_id FOR SHARE;
  IF TG_TABLE_NAME='dyeing_consumption_lines' THEN
   SELECT company_id INTO line_company FROM production.dyeing_orders WHERE id=NEW.dyeing_order_id;
  ELSE
   line_company:=NEW.company_id;
  END IF;
  IF req.id IS NULL OR req.status<>'APPROVED'
   OR req.use_module<>(CASE WHEN TG_TABLE_NAME='dyeing_consumption_lines' THEN 'DYEING' ELSE 'PACKING' END)
   OR req.target_line_id<>NEW.id OR req.company_id<>line_company
   OR req.owner_party_id<>NEW.owner_party_id
   OR req.ownership_policy_version_id<>NEW.ownership_policy_version_id
   OR req.locked_unit_rate<>NEW.ownership_locked_unit_rate
   OR req.requested_quantity<>(CASE WHEN TG_TABLE_NAME='dyeing_consumption_lines' THEN NEW.quantity ELSE NEW.quantity_pieces END)
   OR req.unit_id IS DISTINCT FROM (CASE WHEN TG_TABLE_NAME='dyeing_consumption_lines' THEN NEW.unit_id ELSE NULL::bigint END)
   OR NEW.ownership_type_id<>2 OR NEW.ownership_use_request_id IS NULL
   OR NEW.ownership_locked_unit_rate IS DISTINCT FROM
      (NEW.ownership_cost_snapshot->>'locked_unit_rate')::numeric
   OR NEW.ownership_cost_total IS DISTINCT FROM
      (NEW.ownership_cost_snapshot->>'total_cost')::numeric
   OR NEW.ownership_policy_version_id IS DISTINCT FROM
      (NEW.ownership_cost_snapshot->>'ownership_policy_version_id')::bigint
   OR (NEW.ownership_cost_snapshot->>'owner_party_id')::bigint IS DISTINCT FROM NEW.owner_party_id
   OR (NEW.ownership_cost_snapshot->>'quantity')::numeric IS DISTINCT FROM
      (CASE WHEN TG_TABLE_NAME='dyeing_consumption_lines' THEN NEW.quantity ELSE NEW.quantity_pieces END)
  THEN
   RAISE EXCEPTION 'PARTY-use cost snapshot does not match its source line';
  END IF;
 END IF;
 RETURN NEW;
END; $$;
CREATE TRIGGER trg_dyeing_party_cost_snapshot
BEFORE INSERT OR UPDATE ON production.dyeing_consumption_lines
FOR EACH ROW EXECUTE FUNCTION production.guard_ownership_cost_snapshot();
CREATE TRIGGER trg_packing_party_cost_snapshot
BEFORE INSERT OR UPDATE ON production.packing_source_allocations
FOR EACH ROW EXECUTE FUNCTION production.guard_ownership_cost_snapshot();

CREATE OR REPLACE FUNCTION production.guard_party_use_approval_before_advance()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF OLD.status='DRAFT' AND NEW.status<>'DRAFT' THEN
  IF TG_TABLE_NAME='dyeing_orders' THEN
   IF EXISTS (
    SELECT 1 FROM production.dyeing_consumption_lines l
    LEFT JOIN production.ownership_use_requests r ON r.id=l.ownership_use_request_id
    WHERE l.dyeing_order_id=NEW.id AND l.ownership_type_id=2
      AND (r.id IS NULL OR r.use_module<>'DYEING' OR r.target_line_id<>l.id
           OR r.status<>'APPROVED' OR r.locked_unit_rate IS NULL
           OR r.owner_party_id<>l.owner_party_id OR r.requested_quantity<>l.quantity
           OR l.ownership_cost_snapshot IS NULL
           OR l.ownership_locked_unit_rate IS DISTINCT FROM r.locked_unit_rate
           OR l.ownership_cost_total IS DISTINCT FROM (l.quantity*r.locked_unit_rate))
   ) THEN
    RAISE EXCEPTION 'Dyeing DRAFT cannot advance: each PARTY line requires approved request, locked rate and immutable cost snapshot';
   END IF;
  ELSE
   IF EXISTS (
    SELECT 1 FROM production.packing_source_allocations a
    LEFT JOIN production.ownership_use_requests r ON r.id=a.ownership_use_request_id
    WHERE a.packing_order_id=NEW.id AND a.ownership_type_id=2
      AND (r.id IS NULL OR r.use_module<>'PACKING' OR r.target_line_id<>a.id
           OR r.status<>'APPROVED' OR r.locked_unit_rate IS NULL
           OR r.owner_party_id<>a.owner_party_id OR r.requested_quantity<>a.quantity_pieces
           OR a.ownership_cost_snapshot IS NULL
           OR a.ownership_locked_unit_rate IS DISTINCT FROM r.locked_unit_rate
           OR a.ownership_cost_total IS DISTINCT FROM (a.quantity_pieces*r.locked_unit_rate))
   ) THEN
    RAISE EXCEPTION 'Packing DRAFT cannot advance: each PARTY allocation requires approved request, locked rate and immutable cost snapshot';
   END IF;
  END IF;
 END IF;
 RETURN NEW;
END; $$;
COMMIT;

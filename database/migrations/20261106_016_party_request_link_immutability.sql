-- Ali Raza Enterprises ERP
-- 20261106_016_party_request_link_immutability
-- Prevent approved/pending PARTY request links and cost snapshots from being detached or deleted.
BEGIN;
CREATE OR REPLACE FUNCTION production.guard_ownership_use_request_link()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE req production.ownership_use_requests%ROWTYPE;
BEGIN
 IF TG_OP='DELETE' THEN
  IF OLD.ownership_use_request_id IS NOT NULL OR EXISTS (
    SELECT 1 FROM production.ownership_use_requests r
    WHERE r.target_line_id=OLD.id
      AND r.use_module=CASE WHEN TG_TABLE_NAME='dyeing_consumption_lines' THEN 'DYEING' ELSE 'PACKING' END
  ) THEN
   RAISE EXCEPTION 'A PARTY source line linked to a use request cannot be deleted';
  END IF;
  RETURN OLD;
 END IF;
 IF TG_OP='UPDATE' AND OLD.ownership_use_request_id IS NOT NULL
    AND NEW.ownership_use_request_id IS DISTINCT FROM OLD.ownership_use_request_id THEN
  RAISE EXCEPTION 'A PARTY-use request link cannot be detached or replaced';
 END IF;
 IF TG_TABLE_NAME='dyeing_consumption_lines' THEN
  IF NEW.ownership_type_id=1 AND NEW.ownership_use_request_id IS NOT NULL THEN
   RAISE EXCEPTION 'OWN dyeing material cannot link a PARTY-use request';
  END IF;
  IF NEW.ownership_type_id=2 AND NEW.ownership_use_request_id IS NOT NULL THEN
   SELECT * INTO req FROM production.ownership_use_requests
   WHERE id=NEW.ownership_use_request_id AND use_module='DYEING'
    AND target_line_id=NEW.id AND owner_party_id=NEW.owner_party_id
    AND requested_quantity=NEW.quantity;
   IF NOT FOUND OR req.company_id<>(SELECT company_id FROM production.dyeing_orders WHERE id=NEW.dyeing_order_id) THEN
    RAISE EXCEPTION 'PARTY dyeing material requires its exact same-company linked use request';
   END IF;
  END IF;
 ELSE
  IF NEW.ownership_type_id=1 AND NEW.ownership_use_request_id IS NOT NULL THEN
   RAISE EXCEPTION 'OWN packing source cannot link a PARTY-use request';
  END IF;
  IF NEW.ownership_type_id=2 AND NEW.ownership_use_request_id IS NOT NULL THEN
   SELECT * INTO req FROM production.ownership_use_requests
   WHERE id=NEW.ownership_use_request_id AND use_module='PACKING'
    AND target_line_id=NEW.id AND owner_party_id=NEW.owner_party_id
    AND requested_quantity=NEW.quantity_pieces;
   IF NOT FOUND OR req.company_id<>NEW.company_id THEN
    RAISE EXCEPTION 'PARTY packing source requires its exact same-company linked use request';
   END IF;
  END IF;
 END IF;
 RETURN NEW;
END; $$;

CREATE OR REPLACE FUNCTION production.guard_ownership_cost_snapshot()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE req production.ownership_use_requests%ROWTYPE; line_company BIGINT;
BEGIN
 IF TG_OP='DELETE' THEN
  IF OLD.ownership_cost_snapshot IS NOT NULL THEN
   RAISE EXCEPTION 'A pinned PARTY-use cost snapshot cannot be deleted';
  END IF;
  RETURN OLD;
 END IF;
 IF OLD.ownership_cost_snapshot IS NOT NULL AND (
   NEW.ownership_cost_snapshot IS DISTINCT FROM OLD.ownership_cost_snapshot
   OR NEW.ownership_policy_version_id IS DISTINCT FROM OLD.ownership_policy_version_id
   OR NEW.ownership_locked_unit_rate IS DISTINCT FROM OLD.ownership_locked_unit_rate
   OR NEW.ownership_cost_total IS DISTINCT FROM OLD.ownership_cost_total
   OR NEW.ownership_cost_snapshotted_at IS DISTINCT FROM OLD.ownership_cost_snapshotted_at
   OR (TG_TABLE_NAME='dyeing_consumption_lines' AND (
       NEW.unit_cost IS DISTINCT FROM OLD.unit_cost
       OR NEW.total_cost IS DISTINCT FROM OLD.total_cost))
 ) THEN
  RAISE EXCEPTION 'An approved PARTY-use cost snapshot and its Dyeing cost fields are immutable';
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
   OR (TG_TABLE_NAME='dyeing_consumption_lines' AND (
       NEW.unit_cost IS DISTINCT FROM NEW.ownership_locked_unit_rate
       OR NEW.total_cost IS DISTINCT FROM NEW.ownership_cost_total))
  THEN
   RAISE EXCEPTION 'PARTY-use cost snapshot does not match its source line';
  END IF;
 END IF;
 RETURN NEW;
END; $$;

CREATE TRIGGER trg_dyeing_party_request_link_delete
BEFORE DELETE ON production.dyeing_consumption_lines
FOR EACH ROW EXECUTE FUNCTION production.guard_ownership_use_request_link();
CREATE TRIGGER trg_packing_party_request_link_delete
BEFORE DELETE ON production.packing_source_allocations
FOR EACH ROW EXECUTE FUNCTION production.guard_ownership_use_request_link();
CREATE TRIGGER trg_dyeing_party_snapshot_delete
BEFORE DELETE ON production.dyeing_consumption_lines
FOR EACH ROW EXECUTE FUNCTION production.guard_ownership_cost_snapshot();
CREATE TRIGGER trg_packing_party_snapshot_delete
BEFORE DELETE ON production.packing_source_allocations
FOR EACH ROW EXECUTE FUNCTION production.guard_ownership_cost_snapshot();
COMMIT;

-- Ali Raza Enterprises ERP
-- 20261106_015_party_dyeing_cost_immutability
-- Keep Dyeing's costing columns aligned with its immutable approved PARTY snapshot.
BEGIN;
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
COMMIT;

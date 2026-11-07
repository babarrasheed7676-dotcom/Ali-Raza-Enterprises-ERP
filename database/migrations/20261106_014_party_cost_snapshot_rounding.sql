-- Ali Raza Enterprises ERP
-- 20261106_014_party_cost_snapshot_rounding
-- Align status-gate totals with numeric(20,6) PostgreSQL rounding.
BEGIN;
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
           OR l.ownership_cost_total IS DISTINCT FROM (round(l.quantity*r.locked_unit_rate,6)))
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
           OR a.ownership_cost_total IS DISTINCT FROM (round(a.quantity_pieces*r.locked_unit_rate,6)))
   ) THEN
    RAISE EXCEPTION 'Packing DRAFT cannot advance: each PARTY allocation requires approved request, locked rate and immutable cost snapshot';
   END IF;
  END IF;
 END IF;
 RETURN NEW;
END; $$;
COMMIT;
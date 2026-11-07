-- Ali Raza Enterprises ERP
-- 20261106_012_party_use_approval_gate
-- Permit controlled PARTY DRAFT capture; block any status advancement until approval.
BEGIN;
DROP TRIGGER IF EXISTS ct_dyeing_party_use_request_link ON production.dyeing_consumption_lines;
DROP TRIGGER IF EXISTS ct_packing_party_use_request_link ON production.packing_source_allocations;
DROP FUNCTION IF EXISTS production.assert_party_use_request_link();

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
           OR r.owner_party_id<>l.owner_party_id OR r.requested_quantity<>l.quantity)
   ) THEN
    RAISE EXCEPTION 'Dyeing DRAFT cannot advance: every PARTY line needs a separately approved use request and locked rate';
   END IF;
  ELSE
   IF EXISTS (
    SELECT 1 FROM production.packing_source_allocations a
    LEFT JOIN production.ownership_use_requests r ON r.id=a.ownership_use_request_id
    WHERE a.packing_order_id=NEW.id AND a.ownership_type_id=2
      AND (r.id IS NULL OR r.use_module<>'PACKING' OR r.target_line_id<>a.id
           OR r.status<>'APPROVED' OR r.locked_unit_rate IS NULL
           OR r.owner_party_id<>a.owner_party_id OR r.requested_quantity<>a.quantity_pieces)
   ) THEN
    RAISE EXCEPTION 'Packing DRAFT cannot advance: every PARTY allocation needs a separately approved use request and locked rate';
   END IF;
  END IF;
 END IF;
 RETURN NEW;
END; $$;
CREATE TRIGGER trg_dyeing_party_use_approval_gate
BEFORE UPDATE OF status ON production.dyeing_orders
FOR EACH ROW EXECUTE FUNCTION production.guard_party_use_approval_before_advance();
CREATE TRIGGER trg_packing_party_use_approval_gate
BEFORE UPDATE OF status ON production.packing_orders
FOR EACH ROW EXECUTE FUNCTION production.guard_party_use_approval_before_advance();
COMMIT;
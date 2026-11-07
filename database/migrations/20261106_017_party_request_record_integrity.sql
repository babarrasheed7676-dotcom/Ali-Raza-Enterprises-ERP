-- Ali Raza Enterprises ERP
-- 20261106_017_party_request_record_integrity
-- Freeze request terms, enforce source unit in PostgreSQL, and retain decision history.
BEGIN;
CREATE OR REPLACE FUNCTION production.guard_ownership_use_request()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
 policy_type VARCHAR(40); policy_key VARCHAR(100); policy_status VARCHAR(20);
 policy_payload JSONB; policy_company BIGINT; expected_key VARCHAR(100);
 target_status VARCHAR(30); target_company BIGINT; target_owner BIGINT;
 target_ownership BIGINT; target_qty NUMERIC; target_date DATE; target_unit BIGINT;
 policy_from DATE; policy_to DATE;
BEGIN
 IF TG_OP='DELETE' THEN
  RAISE EXCEPTION 'PARTY-use request history cannot be deleted';
 END IF;
 IF TG_OP='UPDATE' AND OLD.status IN ('APPROVED','REJECTED') THEN
  RAISE EXCEPTION 'A decided PARTY-use request is immutable';
 END IF;
 IF TG_OP='UPDATE' AND (
  NEW.company_id IS DISTINCT FROM OLD.company_id
  OR NEW.use_module IS DISTINCT FROM OLD.use_module
  OR NEW.target_line_id IS DISTINCT FROM OLD.target_line_id
  OR NEW.ownership_policy_version_id IS DISTINCT FROM OLD.ownership_policy_version_id
  OR NEW.owner_party_id IS DISTINCT FROM OLD.owner_party_id
  OR NEW.requested_quantity IS DISTINCT FROM OLD.requested_quantity
  OR NEW.unit_id IS DISTINCT FROM OLD.unit_id
  OR NEW.currency_code IS DISTINCT FROM OLD.currency_code
  OR NEW.requested_unit_rate IS DISTINCT FROM OLD.requested_unit_rate
  OR NEW.request_reason IS DISTINCT FROM OLD.request_reason
  OR NEW.requested_by IS DISTINCT FROM OLD.requested_by
 ) THEN
  RAISE EXCEPTION 'PARTY-use request terms are immutable after submission';
 END IF;
 expected_key := CASE WHEN NEW.use_module='DYEING' THEN 'DYEING-OWNERSHIP' ELSE 'NALKI-OWNERSHIP' END;
 SELECT config_type,config_key,status,payload,company_id,effective_from,effective_to
 INTO policy_type,policy_key,policy_status,policy_payload,policy_company,policy_from,policy_to
 FROM configuration.config_versions WHERE id=NEW.ownership_policy_version_id FOR SHARE;
 IF NOT FOUND OR policy_type<>'OWNERSHIP_POLICY' OR policy_key<>expected_key
 OR policy_status<>'APPROVED' OR policy_company<>NEW.company_id
 OR NOT COALESCE(policy_payload->'allowed_owners' ? 'PARTY',FALSE)
 OR COALESCE((policy_payload->>'party_rate_required')::boolean,FALSE) IS NOT TRUE
 OR COALESCE((policy_payload->>'party_stock_requires_approval')::boolean,FALSE) IS NOT TRUE THEN
  RAISE EXCEPTION 'An approved PARTY-enabled ownership policy is required';
 END IF;
 IF NEW.use_module='DYEING' THEN
  SELECT o.status,o.company_id,l.owner_party_id,l.ownership_type_id,
         l.quantity,o.dyeing_date,l.unit_id
  INTO target_status,target_company,target_owner,target_ownership,
       target_qty,target_date,target_unit
  FROM production.dyeing_consumption_lines l
  JOIN production.dyeing_orders o ON o.id=l.dyeing_order_id
  WHERE l.id=NEW.target_line_id FOR UPDATE OF l,o;
 ELSE
  SELECT o.status,o.company_id,a.owner_party_id,a.ownership_type_id,
         a.quantity_pieces,o.packing_date,NULL::bigint
  INTO target_status,target_company,target_owner,target_ownership,
       target_qty,target_date,target_unit
  FROM production.packing_source_allocations a
  JOIN production.packing_orders o ON o.id=a.packing_order_id
  WHERE a.id=NEW.target_line_id FOR UPDATE OF a,o;
 END IF;
 IF NOT FOUND OR target_status<>'DRAFT' OR target_company<>NEW.company_id
 OR target_ownership<>2 OR target_owner<>NEW.owner_party_id
 OR target_qty<>NEW.requested_quantity
 OR target_unit IS DISTINCT FROM NEW.unit_id THEN
  RAISE EXCEPTION 'Request must exactly match same-company DRAFT PARTY line, owner, quantity and unit';
 END IF;
 IF target_date IS NULL OR target_date<policy_from
    OR target_date>COALESCE(policy_to,'infinity'::date) THEN
  RAISE EXCEPTION 'Ownership policy is not effective on the source document date';
 END IF;
 IF NEW.status='APPROVED' AND (
    NEW.decided_by IS NULL OR NEW.decided_by=NEW.requested_by
    OR NEW.locked_unit_rate IS DISTINCT FROM NEW.requested_unit_rate) THEN
  RAISE EXCEPTION 'Approval requires a different approver and exact locked rate';
 END IF;
 RETURN NEW;
END; $$;

CREATE OR REPLACE FUNCTION production.reject_ownership_use_request_delete()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 RAISE EXCEPTION 'PARTY-use request history cannot be deleted';
END; $$;
CREATE TRIGGER trg_ownership_use_request_no_delete
BEFORE DELETE ON production.ownership_use_requests
FOR EACH ROW EXECUTE FUNCTION production.reject_ownership_use_request_delete();
COMMIT;
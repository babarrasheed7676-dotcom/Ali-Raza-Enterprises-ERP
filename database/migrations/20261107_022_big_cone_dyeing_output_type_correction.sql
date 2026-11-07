-- Ali Raza Enterprises ERP
-- 20261107_022_big_cone_dyeing_output_type_correction
-- Dyeing output lines use DYED_THREAD (not the generic OUTPUT label).

BEGIN;

CREATE OR REPLACE FUNCTION production.guard_big_cone_source_output_line()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    v_company_id BIGINT;
    v_order_status VARCHAR(30);
    v_header_source_order_id BIGINT;
    v_source_status VARCHAR(30);
    v_source_company_id BIGINT;
    v_source_item_variant_id BIGINT;
    v_source_batch_id BIGINT;
    v_source_ownership_type_id BIGINT;
    v_source_owner_party_id BIGINT;
    v_source_unit_id BIGINT;
    v_source_output_type VARCHAR(30);
    v_source_dyeing_order_id BIGINT;
BEGIN
    SELECT company_id, status, source_dyeing_order_id
      INTO v_company_id, v_order_status, v_header_source_order_id
      FROM production.big_cone_orders
     WHERE id = NEW.big_cone_order_id
     FOR SHARE;

    IF NOT FOUND OR v_order_status <> 'DRAFT' THEN
        RAISE EXCEPTION 'Big Cone material lines can only be changed on a DRAFT order';
    END IF;

    IF NEW.source_dyeing_output_line_id IS NULL THEN
        RAISE EXCEPTION 'Big Cone material line must reference its exact Dyeing output line';
    END IF;

    SELECT o.status, o.company_id, l.item_variant_id, l.batch_id,
           l.ownership_type_id, l.owner_party_id, l.unit_id,
           l.output_type, l.dyeing_order_id
      INTO v_source_status, v_source_company_id, v_source_item_variant_id,
           v_source_batch_id, v_source_ownership_type_id, v_source_owner_party_id,
           v_source_unit_id, v_source_output_type, v_source_dyeing_order_id
      FROM production.dyeing_output_lines l
      JOIN production.dyeing_orders o ON o.id = l.dyeing_order_id
     WHERE l.id = NEW.source_dyeing_output_line_id
     FOR SHARE OF l, o;

    IF NOT FOUND
       OR v_source_status IS DISTINCT FROM 'POSTED'
       OR v_source_company_id IS DISTINCT FROM v_company_id
       OR v_header_source_order_id IS DISTINCT FROM v_source_dyeing_order_id
       OR v_source_output_type IS DISTINCT FROM 'DYED_THREAD'
       OR NEW.item_variant_id IS DISTINCT FROM v_source_item_variant_id
       OR NEW.batch_id IS DISTINCT FROM v_source_batch_id
       OR NEW.ownership_type_id IS DISTINCT FROM v_source_ownership_type_id
       OR NEW.owner_party_id IS DISTINCT FROM v_source_owner_party_id
       OR NEW.unit_id IS DISTINCT FROM v_source_unit_id THEN
        RAISE EXCEPTION 'Big Cone source must match a POSTED same-company Dyeing DYED_THREAD line, including item, batch, ownership, owner and unit';
    END IF;

    RETURN NEW;
END;
$$;

COMMIT;

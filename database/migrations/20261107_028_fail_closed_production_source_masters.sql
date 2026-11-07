-- Ali Raza Enterprises ERP
-- 20261107_028_require_active_single_godown_stage_masters
-- Fail closed when the canonical godown or process-stage masters are missing.

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
    v_source_quantity NUMERIC;
    v_source_location_id BIGINT;
    v_source_stage_id BIGINT;
    v_raw_location_id BIGINT;
    v_dyeing_stage_id BIGINT;
    v_allocated_quantity NUMERIC;
BEGIN
    SELECT company_id,status,source_dyeing_order_id
      INTO v_company_id,v_order_status,v_header_source_order_id
      FROM production.big_cone_orders WHERE id=NEW.big_cone_order_id FOR SHARE;
    IF NOT FOUND OR v_order_status<>'DRAFT' THEN
        RAISE EXCEPTION 'Big Cone material lines can only be changed on a DRAFT order';
    END IF;
    IF NEW.source_dyeing_output_line_id IS NULL THEN
        RAISE EXCEPTION 'Big Cone material line must reference its exact Dyeing output line';
    END IF;

    SELECT o.status,o.company_id,l.item_variant_id,l.batch_id,l.ownership_type_id,
           l.owner_party_id,l.unit_id,l.output_type,l.dyeing_order_id,l.quantity_kg,
           l.location_id,l.process_stage_id
      INTO v_source_status,v_source_company_id,v_source_item_variant_id,v_source_batch_id,
           v_source_ownership_type_id,v_source_owner_party_id,v_source_unit_id,
           v_source_output_type,v_source_dyeing_order_id,v_source_quantity,
           v_source_location_id,v_source_stage_id
      FROM production.dyeing_output_lines l
      JOIN production.dyeing_orders o ON o.id=l.dyeing_order_id
     WHERE l.id=NEW.source_dyeing_output_line_id
     FOR UPDATE OF l;

    SELECT il.id INTO v_raw_location_id
      FROM inventory.locations il JOIN core.locations cl ON cl.id=il.core_location_id
     WHERE cl.company_id=v_company_id AND cl.code='RAW_STORE'
       AND cl.is_active=TRUE AND il.is_active=TRUE AND il.allow_stock=TRUE;
    SELECT id INTO v_dyeing_stage_id FROM master.process_stages
     WHERE company_id=v_company_id AND code='DYEING' AND is_active=TRUE;

    IF v_source_status IS NULL
       OR v_raw_location_id IS NULL
       OR v_dyeing_stage_id IS NULL
       OR v_source_status IS DISTINCT FROM 'POSTED'
       OR v_source_company_id IS DISTINCT FROM v_company_id
       OR v_header_source_order_id IS DISTINCT FROM v_source_dyeing_order_id
       OR v_source_output_type IS DISTINCT FROM 'DYED_THREAD'
       OR NEW.item_variant_id IS DISTINCT FROM v_source_item_variant_id
       OR NEW.batch_id IS DISTINCT FROM v_source_batch_id
       OR NEW.ownership_type_id IS DISTINCT FROM v_source_ownership_type_id
       OR NEW.owner_party_id IS DISTINCT FROM v_source_owner_party_id
       OR NEW.unit_id IS DISTINCT FROM v_source_unit_id
       OR NEW.location_id IS DISTINCT FROM v_source_location_id
       OR v_source_location_id IS DISTINCT FROM v_raw_location_id
       OR v_source_stage_id IS DISTINCT FROM v_dyeing_stage_id
       OR NEW.process_stage_id IS DISTINCT FROM v_dyeing_stage_id THEN
        RAISE EXCEPTION 'Big Cone source must match a POSTED same-company Dyeing DYED_THREAD line at the active single RAW_STORE location and DYEING stage, including item, batch, ownership, owner and unit';
    END IF;

    SELECT COALESCE(SUM(l.quantity_kg),0) INTO v_allocated_quantity
      FROM production.big_cone_material_lines l
      JOIN production.big_cone_orders o ON o.id=l.big_cone_order_id
     WHERE l.source_dyeing_output_line_id=NEW.source_dyeing_output_line_id
       AND l.id IS DISTINCT FROM NEW.id
       AND o.status NOT IN ('CANCELLED','REVERSED');
    IF v_allocated_quantity+NEW.quantity_kg>v_source_quantity THEN
        RAISE EXCEPTION 'Big Cone material allocation exceeds the unallocated Dyeing output quantity';
    END IF;
    RETURN NEW;
END;
$$;

CREATE OR REPLACE FUNCTION production.guard_baby_cone_source_output_line()
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
    v_source_destination_type VARCHAR(30);
    v_source_big_cone_order_id BIGINT;
    v_source_quantity NUMERIC;
    v_source_location_id BIGINT;
    v_source_stage_id BIGINT;
    v_raw_location_id BIGINT;
    v_big_cone_stage_id BIGINT;
    v_allocated_quantity NUMERIC;
BEGIN
    SELECT company_id,status,source_big_cone_order_id
      INTO v_company_id,v_order_status,v_header_source_order_id
      FROM production.baby_cone_orders WHERE id=NEW.baby_cone_order_id FOR SHARE;
    IF NOT FOUND OR v_order_status<>'DRAFT' THEN
        RAISE EXCEPTION 'Baby Cone material lines can only be changed on a DRAFT order';
    END IF;
    IF NEW.source_big_cone_output_line_id IS NULL THEN
        RAISE EXCEPTION 'Baby Cone material line must reference its exact Big Cone output line';
    END IF;

    SELECT o.status,o.company_id,l.item_variant_id,l.batch_id,l.ownership_type_id,
           l.owner_party_id,l.unit_id,l.destination_type,l.big_cone_order_id,
           l.quantity_kg,l.location_id,l.process_stage_id
      INTO v_source_status,v_source_company_id,v_source_item_variant_id,v_source_batch_id,
           v_source_ownership_type_id,v_source_owner_party_id,v_source_unit_id,
           v_source_destination_type,v_source_big_cone_order_id,v_source_quantity,
           v_source_location_id,v_source_stage_id
      FROM production.big_cone_output_lines l
      JOIN production.big_cone_orders o ON o.id=l.big_cone_order_id
     WHERE l.id=NEW.source_big_cone_output_line_id
     FOR UPDATE OF l;

    SELECT il.id INTO v_raw_location_id
      FROM inventory.locations il JOIN core.locations cl ON cl.id=il.core_location_id
     WHERE cl.company_id=v_company_id AND cl.code='RAW_STORE'
       AND cl.is_active=TRUE AND il.is_active=TRUE AND il.allow_stock=TRUE;
    SELECT id INTO v_big_cone_stage_id FROM master.process_stages
     WHERE company_id=v_company_id AND code='BIG_CONE' AND is_active=TRUE;

    IF v_source_status IS NULL
       OR v_raw_location_id IS NULL
       OR v_big_cone_stage_id IS NULL
       OR v_source_status IS DISTINCT FROM 'POSTED'
       OR v_source_company_id IS DISTINCT FROM v_company_id
       OR v_header_source_order_id IS DISTINCT FROM v_source_big_cone_order_id
       OR v_source_destination_type IS DISTINCT FROM 'BABY_CONE'
       OR NEW.item_variant_id IS DISTINCT FROM v_source_item_variant_id
       OR NEW.batch_id IS DISTINCT FROM v_source_batch_id
       OR NEW.ownership_type_id IS DISTINCT FROM v_source_ownership_type_id
       OR NEW.owner_party_id IS DISTINCT FROM v_source_owner_party_id
       OR NEW.unit_id IS DISTINCT FROM v_source_unit_id
       OR NEW.location_id IS DISTINCT FROM v_source_location_id
       OR v_source_location_id IS DISTINCT FROM v_raw_location_id
       OR v_source_stage_id IS DISTINCT FROM v_big_cone_stage_id
       OR NEW.process_stage_id IS DISTINCT FROM v_big_cone_stage_id THEN
        RAISE EXCEPTION 'Baby Cone source must match a POSTED same-company Big Cone BABY_CONE output line at the active single RAW_STORE location and BIG_CONE stage, including item, batch, ownership, owner and unit';
    END IF;

    SELECT COALESCE(SUM(l.quantity_kg),0) INTO v_allocated_quantity
      FROM production.baby_cone_material_lines l
      JOIN production.baby_cone_orders o ON o.id=l.baby_cone_order_id
     WHERE l.source_big_cone_output_line_id=NEW.source_big_cone_output_line_id
       AND l.id IS DISTINCT FROM NEW.id
       AND o.status NOT IN ('CANCELLED','REVERSED');
    IF v_allocated_quantity+NEW.quantity_kg>v_source_quantity THEN
        RAISE EXCEPTION 'Baby Cone material allocation exceeds the unallocated Big Cone output quantity';
    END IF;
    RETURN NEW;
END;
$$;

COMMIT;
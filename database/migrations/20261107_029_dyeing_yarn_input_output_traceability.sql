-- Ali Raza Enterprises ERP
-- 20261107_029_dyeing_yarn_input_output_traceability
-- Link each dyed-thread output to the exact raw-yarn input and the quantity consumed.

BEGIN;

ALTER TABLE production.dyeing_output_lines
    ADD COLUMN source_material_line_id BIGINT NOT NULL,
    ADD COLUMN source_material_quantity_kg NUMERIC NOT NULL;

ALTER TABLE production.dyeing_output_lines
    ADD CONSTRAINT fk_dyeing_output_source_material
        FOREIGN KEY (source_material_line_id)
        REFERENCES production.dyeing_material_lines(id)
        ON DELETE RESTRICT,
    ADD CONSTRAINT chk_dyeing_output_source_quantity
        CHECK (source_material_quantity_kg > 0);

CREATE INDEX ix_dyeing_output_source_material
    ON production.dyeing_output_lines(source_material_line_id);

CREATE OR REPLACE FUNCTION production.guard_dyeing_material_source_line()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    v_company_id BIGINT;
    v_order_status VARCHAR(30);
    v_raw_location_id BIGINT;
    v_purchase_stage_id BIGINT;
    v_own_type_id BIGINT;
    v_kg_unit_id BIGINT;
    v_item_valid BOOLEAN;
BEGIN
    IF TG_OP='DELETE' THEN
        SELECT status INTO v_order_status
          FROM production.dyeing_orders
         WHERE id=OLD.dyeing_order_id
         FOR SHARE;
        IF v_order_status IS DISTINCT FROM 'DRAFT' THEN
            RAISE EXCEPTION 'Dyeing raw-yarn input lines cannot be deleted after DRAFT';
        END IF;
        IF EXISTS (
            SELECT 1 FROM production.dyeing_output_lines
             WHERE source_material_line_id=OLD.id
        ) THEN
            RAISE EXCEPTION 'Dyeing raw-yarn input referenced by output cannot be changed or deleted';
        END IF;
        RETURN OLD;
    END IF;

    SELECT company_id,status INTO v_company_id,v_order_status
      FROM production.dyeing_orders
     WHERE id=NEW.dyeing_order_id
     FOR SHARE;
    IF NOT FOUND OR v_order_status IS DISTINCT FROM 'DRAFT' THEN
        RAISE EXCEPTION 'Dyeing raw-yarn input lines can only be changed on a DRAFT order';
    END IF;

    SELECT il.id INTO v_raw_location_id
      FROM inventory.locations il
      JOIN core.locations cl ON cl.id=il.core_location_id
     WHERE cl.company_id=v_company_id AND cl.code='RAW_STORE'
       AND cl.is_active=TRUE AND il.is_active=TRUE AND il.allow_stock=TRUE;
    SELECT id INTO v_purchase_stage_id FROM master.process_stages
     WHERE company_id=v_company_id AND code='PURCHASE' AND is_active=TRUE;
    SELECT id INTO v_own_type_id FROM master.ownership_types
     WHERE code='OWN' AND is_active=TRUE;
    SELECT id INTO v_kg_unit_id FROM master.units
     WHERE code='KG' AND unit_type='WEIGHT' AND is_active=TRUE;

    SELECT EXISTS (
        SELECT 1
          FROM master.item_variants v
          JOIN master.items i ON i.id=v.item_id
          JOIN master.item_categories c ON c.id=i.item_category_id
         WHERE v.id=NEW.item_variant_id
           AND v.is_active=TRUE
           AND i.company_id=v_company_id
           AND i.is_active=TRUE
           AND i.is_stock_item=TRUE
           AND c.code='YARN'
           AND i.base_unit_id=v_kg_unit_id
    ) INTO v_item_valid;

    IF v_raw_location_id IS NULL OR v_purchase_stage_id IS NULL
       OR v_own_type_id IS NULL OR v_kg_unit_id IS NULL THEN
        RAISE EXCEPTION 'Active RAW_STORE, PURCHASE, OWN and KG masters are required for Dyeing yarn input';
    END IF;
    IF NOT v_item_valid
       OR NEW.location_id IS DISTINCT FROM v_raw_location_id
       OR NEW.process_stage_id IS DISTINCT FROM v_purchase_stage_id
       OR NEW.unit_id IS DISTINCT FROM v_kg_unit_id
       OR NEW.ownership_type_id IS DISTINCT FROM v_own_type_id
       OR NEW.owner_party_id IS NOT NULL THEN
        RAISE EXCEPTION 'Dyeing yarn input must be an active YARN stock item in KG, OWN-owned, at RAW_STORE/PURCHASE stage';
    END IF;

    IF TG_OP='UPDATE' AND EXISTS (
        SELECT 1 FROM production.dyeing_output_lines
         WHERE source_material_line_id=OLD.id
    ) THEN
        RAISE EXCEPTION 'Dyeing raw-yarn input referenced by output cannot be changed or deleted';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_dyeing_material_source_line_guard
BEFORE INSERT OR UPDATE OR DELETE ON production.dyeing_material_lines
FOR EACH ROW EXECUTE FUNCTION production.guard_dyeing_material_source_line();

CREATE OR REPLACE FUNCTION production.guard_dyeing_output_source_material()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    v_company_id BIGINT;
    v_order_status VARCHAR(30);
    v_material_order_id BIGINT;
    v_item_variant_id BIGINT;
    v_batch_id BIGINT;
    v_ownership_type_id BIGINT;
    v_owner_party_id BIGINT;
    v_unit_id BIGINT;
    v_location_id BIGINT;
    v_quantity_kg NUMERIC;
    v_allocated_source_quantity NUMERIC;
    v_raw_location_id BIGINT;
    v_dyeing_stage_id BIGINT;
BEGIN
    IF TG_OP='DELETE' THEN
        SELECT status INTO v_order_status
          FROM production.dyeing_orders
         WHERE id=OLD.dyeing_order_id
         FOR SHARE;
        IF v_order_status IS DISTINCT FROM 'DRAFT' THEN
            RAISE EXCEPTION 'Dyeing output lines cannot be deleted after DRAFT';
        END IF;
        RETURN OLD;
    END IF;

    SELECT company_id,status INTO v_company_id,v_order_status
      FROM production.dyeing_orders
     WHERE id=NEW.dyeing_order_id
     FOR SHARE;
    IF NOT FOUND OR v_order_status IS DISTINCT FROM 'DRAFT' THEN
        RAISE EXCEPTION 'Dyeing output lines can only be changed on a DRAFT order';
    END IF;
    IF NEW.source_material_line_id IS NULL OR NEW.source_material_quantity_kg IS NULL
       OR NEW.source_material_quantity_kg<=0 THEN
        RAISE EXCEPTION 'Dyeing output must reference an exact raw-yarn input line and positive consumed quantity';
    END IF;

    SELECT dyeing_order_id,item_variant_id,batch_id,ownership_type_id,
           owner_party_id,unit_id,location_id,quantity_kg
      INTO v_material_order_id,v_item_variant_id,v_batch_id,v_ownership_type_id,
           v_owner_party_id,v_unit_id,v_location_id,v_quantity_kg
      FROM production.dyeing_material_lines
     WHERE id=NEW.source_material_line_id
     FOR UPDATE;

    SELECT il.id INTO v_raw_location_id
      FROM inventory.locations il
      JOIN core.locations cl ON cl.id=il.core_location_id
     WHERE cl.company_id=v_company_id AND cl.code='RAW_STORE'
       AND cl.is_active=TRUE AND il.is_active=TRUE AND il.allow_stock=TRUE;
    SELECT id INTO v_dyeing_stage_id FROM master.process_stages
     WHERE company_id=v_company_id AND code='DYEING' AND is_active=TRUE;

    IF v_material_order_id IS DISTINCT FROM NEW.dyeing_order_id
       OR v_raw_location_id IS NULL OR v_dyeing_stage_id IS NULL
       OR NEW.item_variant_id IS DISTINCT FROM v_item_variant_id
       OR NEW.batch_id IS DISTINCT FROM v_batch_id
       OR NEW.ownership_type_id IS DISTINCT FROM v_ownership_type_id
       OR NEW.owner_party_id IS DISTINCT FROM v_owner_party_id
       OR NEW.unit_id IS DISTINCT FROM v_unit_id
       OR NEW.location_id IS DISTINCT FROM v_location_id
       OR v_location_id IS DISTINCT FROM v_raw_location_id
       OR NEW.process_stage_id IS DISTINCT FROM v_dyeing_stage_id
       OR NEW.ownership_type_id IS DISTINCT FROM (SELECT id FROM master.ownership_types WHERE code='OWN' AND is_active=TRUE)
       OR NEW.owner_party_id IS NOT NULL THEN
        RAISE EXCEPTION 'Dyeing output must match its same-order raw-yarn input item, batch, OWN ownership, owner, unit and RAW_STORE; output stage must be DYEING';
    END IF;

    SELECT COALESCE(SUM(source_material_quantity_kg),0)
      INTO v_allocated_source_quantity
      FROM production.dyeing_output_lines l
      JOIN production.dyeing_orders o ON o.id=l.dyeing_order_id
     WHERE l.source_material_line_id=NEW.source_material_line_id
       AND l.id IS DISTINCT FROM NEW.id
       AND o.status NOT IN ('CANCELLED','REVERSED');

    IF v_allocated_source_quantity+NEW.source_material_quantity_kg>v_quantity_kg THEN
        RAISE EXCEPTION 'Dyeing output source allocation exceeds its raw-yarn input quantity';
    END IF;

    IF NEW.output_type='DYED_THREAD' AND
       (NEW.actual_shade_id IS NULL OR NEW.shade_match_status IS DISTINCT FROM 'EXACT') THEN
        RAISE EXCEPTION 'DYED_THREAD output requires an exact active shade selection';
    END IF;
    IF NEW.actual_shade_id IS NOT NULL AND NOT EXISTS (
        SELECT 1 FROM master.shades s WHERE s.id=NEW.actual_shade_id AND s.is_active=TRUE
    ) THEN
        RAISE EXCEPTION 'Dyeing output shade must be active';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_dyeing_output_source_material_guard
BEFORE INSERT OR UPDATE OR DELETE ON production.dyeing_output_lines
FOR EACH ROW EXECUTE FUNCTION production.guard_dyeing_output_source_material();

CREATE OR REPLACE FUNCTION production.guard_dyeing_material_output_before_advance()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF OLD.status='DRAFT' AND NEW.status IN ('APPROVED','POSTED') THEN
        IF NOT EXISTS (
            SELECT 1 FROM production.dyeing_material_lines
             WHERE dyeing_order_id=NEW.id
        ) THEN
            RAISE EXCEPTION 'Dyeing cannot be approved without raw-yarn input lines';
        END IF;
        IF NOT EXISTS (
            SELECT 1 FROM production.dyeing_output_lines
             WHERE dyeing_order_id=NEW.id AND output_type='DYED_THREAD'
        ) THEN
            RAISE EXCEPTION 'Dyeing cannot be approved without DYED_THREAD output lines';
        END IF;
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_dyeing_material_output_advance_guard
BEFORE UPDATE OF status ON production.dyeing_orders
FOR EACH ROW EXECUTE FUNCTION production.guard_dyeing_material_output_before_advance();

COMMIT;

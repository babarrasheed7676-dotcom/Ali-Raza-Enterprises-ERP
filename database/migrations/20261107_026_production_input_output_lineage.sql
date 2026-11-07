-- Ali Raza Enterprises ERP
-- 20261107_026_production_input_output_lineage
-- Link every Big Cone/Baby Cone output to the exact material line it transforms.

BEGIN;

ALTER TABLE production.big_cone_output_lines
    ADD COLUMN source_material_line_id BIGINT;

ALTER TABLE production.big_cone_output_lines
    ADD CONSTRAINT fk_big_cone_output_source_material
    FOREIGN KEY (source_material_line_id)
    REFERENCES production.big_cone_material_lines(id)
    ON DELETE RESTRICT;

CREATE INDEX ix_big_cone_output_source_material
    ON production.big_cone_output_lines(source_material_line_id)
    WHERE source_material_line_id IS NOT NULL;

ALTER TABLE production.baby_cone_output_lines
    ADD COLUMN source_material_line_id BIGINT;

ALTER TABLE production.baby_cone_output_lines
    ADD CONSTRAINT fk_baby_cone_output_source_material
    FOREIGN KEY (source_material_line_id)
    REFERENCES production.baby_cone_material_lines(id)
    ON DELETE RESTRICT;

CREATE INDEX ix_baby_cone_output_source_material
    ON production.baby_cone_output_lines(source_material_line_id)
    WHERE source_material_line_id IS NOT NULL;

CREATE OR REPLACE FUNCTION production.guard_big_cone_output_source_material()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    v_order_company BIGINT;
    v_order_status VARCHAR(30);
    v_material_order_id BIGINT;
    v_item BIGINT;
    v_batch BIGINT;
    v_ownership BIGINT;
    v_owner BIGINT;
    v_unit BIGINT;
    v_location BIGINT;
    v_quantity NUMERIC;
    v_allocated NUMERIC;
    v_stage_id BIGINT;
BEGIN
    SELECT company_id,status INTO v_order_company,v_order_status
      FROM production.big_cone_orders WHERE id=NEW.big_cone_order_id FOR SHARE;
    IF NOT FOUND OR v_order_status<>'DRAFT' THEN
        RAISE EXCEPTION 'Big Cone output lines can only be changed on a DRAFT order';
    END IF;
    IF NEW.source_material_line_id IS NULL THEN
        RAISE EXCEPTION 'Big Cone output line must reference its exact material input line';
    END IF;

    SELECT big_cone_order_id,item_variant_id,batch_id,ownership_type_id,
           owner_party_id,unit_id,location_id,quantity_kg
      INTO v_material_order_id,v_item,v_batch,v_ownership,v_owner,
           v_unit,v_location,v_quantity
      FROM production.big_cone_material_lines
     WHERE id=NEW.source_material_line_id
     FOR UPDATE;

    IF NOT FOUND
       OR v_material_order_id IS DISTINCT FROM NEW.big_cone_order_id
       OR NEW.item_variant_id IS DISTINCT FROM v_item
       OR NEW.batch_id IS DISTINCT FROM v_batch
       OR NEW.ownership_type_id IS DISTINCT FROM v_ownership
       OR NEW.owner_party_id IS DISTINCT FROM v_owner
       OR NEW.unit_id IS DISTINCT FROM v_unit
       OR NEW.location_id IS DISTINCT FROM v_location THEN
        RAISE EXCEPTION 'Big Cone output must match its same-order source material line item, batch, ownership, owner, unit and physical godown';
    END IF;

    SELECT id INTO v_stage_id FROM master.process_stages
     WHERE company_id=v_order_company AND code='BIG_CONE' AND is_active=TRUE;
    IF v_stage_id IS NULL OR NEW.process_stage_id IS DISTINCT FROM v_stage_id THEN
        RAISE EXCEPTION 'Big Cone output must use the active BIG_CONE process stage';
    END IF;

    SELECT COALESCE(SUM(quantity_kg),0) INTO v_allocated
      FROM production.big_cone_output_lines l
      JOIN production.big_cone_orders o ON o.id=l.big_cone_order_id
     WHERE l.source_material_line_id=NEW.source_material_line_id
       AND l.id IS DISTINCT FROM NEW.id
       AND o.status NOT IN ('CANCELLED','REVERSED');

    IF v_allocated+NEW.quantity_kg>v_quantity THEN
        RAISE EXCEPTION 'Big Cone output allocation exceeds its source material quantity';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_big_cone_output_source_material
BEFORE INSERT OR UPDATE OF big_cone_order_id,source_material_line_id,
    item_variant_id,batch_id,ownership_type_id,owner_party_id,unit_id,
    location_id,process_stage_id,quantity_kg
ON production.big_cone_output_lines
FOR EACH ROW EXECUTE FUNCTION production.guard_big_cone_output_source_material();

CREATE OR REPLACE FUNCTION production.guard_baby_cone_output_source_material()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    v_order_company BIGINT;
    v_order_status VARCHAR(30);
    v_material_order_id BIGINT;
    v_item BIGINT;
    v_batch BIGINT;
    v_ownership BIGINT;
    v_owner BIGINT;
    v_unit BIGINT;
    v_location BIGINT;
    v_quantity NUMERIC;
    v_allocated NUMERIC;
    v_stage_id BIGINT;
BEGIN
    SELECT company_id,status INTO v_order_company,v_order_status
      FROM production.baby_cone_orders WHERE id=NEW.baby_cone_order_id FOR SHARE;
    IF NOT FOUND OR v_order_status<>'DRAFT' THEN
        RAISE EXCEPTION 'Baby Cone output lines can only be changed on a DRAFT order';
    END IF;
    IF NEW.source_material_line_id IS NULL THEN
        RAISE EXCEPTION 'Baby Cone output line must reference its exact material input line';
    END IF;

    SELECT baby_cone_order_id,item_variant_id,batch_id,ownership_type_id,
           owner_party_id,unit_id,location_id,quantity_kg
      INTO v_material_order_id,v_item,v_batch,v_ownership,v_owner,
           v_unit,v_location,v_quantity
      FROM production.baby_cone_material_lines
     WHERE id=NEW.source_material_line_id
     FOR UPDATE;

    IF NOT FOUND
       OR v_material_order_id IS DISTINCT FROM NEW.baby_cone_order_id
       OR NEW.item_variant_id IS DISTINCT FROM v_item
       OR NEW.batch_id IS DISTINCT FROM v_batch
       OR NEW.ownership_type_id IS DISTINCT FROM v_ownership
       OR NEW.owner_party_id IS DISTINCT FROM v_owner
       OR NEW.unit_id IS DISTINCT FROM v_unit
       OR NEW.location_id IS DISTINCT FROM v_location THEN
        RAISE EXCEPTION 'Baby Cone output must match its same-order source material line item, batch, ownership, owner, unit and physical godown';
    END IF;

    SELECT id INTO v_stage_id FROM master.process_stages
     WHERE company_id=v_order_company AND code='BABY_CONE' AND is_active=TRUE;
    IF v_stage_id IS NULL OR NEW.process_stage_id IS DISTINCT FROM v_stage_id THEN
        RAISE EXCEPTION 'Baby Cone output must use the active BABY_CONE process stage';
    END IF;

    SELECT COALESCE(SUM(quantity_kg),0) INTO v_allocated
      FROM production.baby_cone_output_lines l
      JOIN production.baby_cone_orders o ON o.id=l.baby_cone_order_id
     WHERE l.source_material_line_id=NEW.source_material_line_id
       AND l.id IS DISTINCT FROM NEW.id
       AND o.status NOT IN ('CANCELLED','REVERSED');

    IF v_allocated+NEW.quantity_kg>v_quantity THEN
        RAISE EXCEPTION 'Baby Cone output allocation exceeds its source material quantity';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_baby_cone_output_source_material
BEFORE INSERT OR UPDATE OF baby_cone_order_id,source_material_line_id,
    item_variant_id,batch_id,ownership_type_id,owner_party_id,unit_id,
    location_id,process_stage_id,quantity_kg
ON production.baby_cone_output_lines
FOR EACH ROW EXECUTE FUNCTION production.guard_baby_cone_output_source_material();

CREATE OR REPLACE FUNCTION production.guard_production_source_material_mutation()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF TG_TABLE_NAME='big_cone_material_lines' THEN
        IF EXISTS (SELECT 1 FROM production.big_cone_output_lines
                    WHERE source_material_line_id=OLD.id) THEN
            RAISE EXCEPTION 'Big Cone material line referenced by output cannot be changed or deleted';
        END IF;
    ELSE
        IF EXISTS (SELECT 1 FROM production.baby_cone_output_lines
                    WHERE source_material_line_id=OLD.id) THEN
            RAISE EXCEPTION 'Baby Cone material line referenced by output cannot be changed or deleted';
        END IF;
    END IF;
    IF TG_OP='DELETE' THEN RETURN OLD; END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_big_cone_material_output_source_lock
BEFORE UPDATE OR DELETE ON production.big_cone_material_lines
FOR EACH ROW EXECUTE FUNCTION production.guard_production_source_material_mutation();

CREATE TRIGGER trg_baby_cone_material_output_source_lock
BEFORE UPDATE OR DELETE ON production.baby_cone_material_lines
FOR EACH ROW EXECUTE FUNCTION production.guard_production_source_material_mutation();

CREATE OR REPLACE FUNCTION production.guard_production_output_line_delete()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    v_status VARCHAR(30);
BEGIN
    IF TG_TABLE_NAME='big_cone_output_lines' THEN
        SELECT status INTO v_status FROM production.big_cone_orders
         WHERE id=OLD.big_cone_order_id FOR SHARE;
    ELSE
        SELECT status INTO v_status FROM production.baby_cone_orders
         WHERE id=OLD.baby_cone_order_id FOR SHARE;
    END IF;
    IF v_status IS DISTINCT FROM 'DRAFT' THEN
        RAISE EXCEPTION 'Production output lines cannot be deleted after DRAFT';
    END IF;
    RETURN OLD;
END;
$$;

CREATE TRIGGER trg_big_cone_output_delete_guard
BEFORE DELETE ON production.big_cone_output_lines
FOR EACH ROW EXECUTE FUNCTION production.guard_production_output_line_delete();

CREATE TRIGGER trg_baby_cone_output_delete_guard
BEFORE DELETE ON production.baby_cone_output_lines
FOR EACH ROW EXECUTE FUNCTION production.guard_production_output_line_delete();

COMMIT;
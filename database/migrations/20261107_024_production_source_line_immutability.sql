-- Ali Raza Enterprises ERP
-- 20261107_024_production_source_line_immutability
-- Cover quantity edits, child deletion, and mutation of already-consumed source outputs.

BEGIN;

DROP TRIGGER IF EXISTS trg_big_cone_source_output_line
    ON production.big_cone_material_lines;
CREATE TRIGGER trg_big_cone_source_output_line
BEFORE INSERT OR UPDATE OF big_cone_order_id, source_dyeing_output_line_id,
    item_variant_id, batch_id, ownership_type_id, owner_party_id, unit_id, quantity_kg
ON production.big_cone_material_lines
FOR EACH ROW
EXECUTE FUNCTION production.guard_big_cone_source_output_line();

DROP TRIGGER IF EXISTS trg_baby_cone_source_output_line
    ON production.baby_cone_material_lines;
CREATE TRIGGER trg_baby_cone_source_output_line
BEFORE INSERT OR UPDATE OF baby_cone_order_id, source_big_cone_output_line_id,
    item_variant_id, batch_id, ownership_type_id, owner_party_id, unit_id, quantity_kg
ON production.baby_cone_material_lines
FOR EACH ROW
EXECUTE FUNCTION production.guard_baby_cone_source_output_line();

CREATE OR REPLACE FUNCTION production.guard_production_material_line_delete()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    v_status VARCHAR(30);
BEGIN
    IF TG_TABLE_NAME = 'big_cone_material_lines' THEN
        SELECT status INTO v_status
          FROM production.big_cone_orders
         WHERE id = OLD.big_cone_order_id
         FOR SHARE;
    ELSE
        SELECT status INTO v_status
          FROM production.baby_cone_orders
         WHERE id = OLD.baby_cone_order_id
         FOR SHARE;
    END IF;

    IF v_status IS DISTINCT FROM 'DRAFT' THEN
        RAISE EXCEPTION 'Production material lines cannot be deleted after DRAFT';
    END IF;
    RETURN OLD;
END;
$$;

CREATE TRIGGER trg_big_cone_material_line_delete_guard
BEFORE DELETE ON production.big_cone_material_lines
FOR EACH ROW
EXECUTE FUNCTION production.guard_production_material_line_delete();

CREATE TRIGGER trg_baby_cone_material_line_delete_guard
BEFORE DELETE ON production.baby_cone_material_lines
FOR EACH ROW
EXECUTE FUNCTION production.guard_production_material_line_delete();

CREATE OR REPLACE FUNCTION production.guard_consumed_upstream_output_mutation()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF TG_TABLE_NAME = 'dyeing_output_lines' THEN
        IF EXISTS (
            SELECT 1 FROM production.big_cone_material_lines
             WHERE source_dyeing_output_line_id = OLD.id
        ) THEN
            RAISE EXCEPTION 'A Dyeing output line referenced by Big Cone cannot be changed or deleted';
        END IF;
    ELSE
        IF EXISTS (
            SELECT 1 FROM production.baby_cone_material_lines
             WHERE source_big_cone_output_line_id = OLD.id
        ) THEN
            RAISE EXCEPTION 'A Big Cone output line referenced by Baby Cone cannot be changed or deleted';
        END IF;
    END IF;

    IF TG_OP = 'DELETE' THEN
        RETURN OLD;
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_dyeing_output_source_immutability
BEFORE UPDATE OR DELETE ON production.dyeing_output_lines
FOR EACH ROW
EXECUTE FUNCTION production.guard_consumed_upstream_output_mutation();

CREATE TRIGGER trg_big_cone_output_source_immutability
BEFORE UPDATE OR DELETE ON production.big_cone_output_lines
FOR EACH ROW
EXECUTE FUNCTION production.guard_consumed_upstream_output_mutation();

COMMIT;

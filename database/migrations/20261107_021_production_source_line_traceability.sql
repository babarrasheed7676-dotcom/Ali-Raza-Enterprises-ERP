-- Ali Raza Enterprises ERP
-- 20261107_021_production_source_line_traceability
-- Pin each Big Cone and Baby Cone material line to its exact upstream output line.
-- No existing production records are rewritten.

BEGIN;

ALTER TABLE production.big_cone_material_lines
    ADD COLUMN source_dyeing_output_line_id BIGINT;

ALTER TABLE production.big_cone_material_lines
    ADD CONSTRAINT fk_big_cone_material_source_dyeing_output
    FOREIGN KEY (source_dyeing_output_line_id)
    REFERENCES production.dyeing_output_lines(id)
    ON DELETE RESTRICT;

CREATE INDEX ix_big_cone_material_source_dyeing_output
    ON production.big_cone_material_lines(source_dyeing_output_line_id)
    WHERE source_dyeing_output_line_id IS NOT NULL;

ALTER TABLE production.baby_cone_material_lines
    ADD COLUMN source_big_cone_output_line_id BIGINT;

ALTER TABLE production.baby_cone_material_lines
    ADD CONSTRAINT fk_baby_cone_material_source_big_cone_output
    FOREIGN KEY (source_big_cone_output_line_id)
    REFERENCES production.big_cone_output_lines(id)
    ON DELETE RESTRICT;

CREATE INDEX ix_baby_cone_material_source_big_cone_output
    ON production.baby_cone_material_lines(source_big_cone_output_line_id)
    WHERE source_big_cone_output_line_id IS NOT NULL;

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
       OR v_source_output_type IS DISTINCT FROM 'OUTPUT'
       OR NEW.item_variant_id IS DISTINCT FROM v_source_item_variant_id
       OR NEW.batch_id IS DISTINCT FROM v_source_batch_id
       OR NEW.ownership_type_id IS DISTINCT FROM v_source_ownership_type_id
       OR NEW.owner_party_id IS DISTINCT FROM v_source_owner_party_id
       OR NEW.unit_id IS DISTINCT FROM v_source_unit_id THEN
        RAISE EXCEPTION 'Big Cone source must match a POSTED same-company Dyeing OUTPUT line, including item, batch, ownership, owner and unit';
    END IF;

    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_big_cone_source_output_line
BEFORE INSERT OR UPDATE OF big_cone_order_id, source_dyeing_output_line_id,
    item_variant_id, batch_id, ownership_type_id, owner_party_id, unit_id
ON production.big_cone_material_lines
FOR EACH ROW
EXECUTE FUNCTION production.guard_big_cone_source_output_line();

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
BEGIN
    SELECT company_id, status, source_big_cone_order_id
      INTO v_company_id, v_order_status, v_header_source_order_id
      FROM production.baby_cone_orders
     WHERE id = NEW.baby_cone_order_id
     FOR SHARE;

    IF NOT FOUND OR v_order_status <> 'DRAFT' THEN
        RAISE EXCEPTION 'Baby Cone material lines can only be changed on a DRAFT order';
    END IF;

    IF NEW.source_big_cone_output_line_id IS NULL THEN
        RAISE EXCEPTION 'Baby Cone material line must reference its exact Big Cone output line';
    END IF;

    SELECT o.status, o.company_id, l.item_variant_id, l.batch_id,
           l.ownership_type_id, l.owner_party_id, l.unit_id,
           l.destination_type, l.big_cone_order_id
      INTO v_source_status, v_source_company_id, v_source_item_variant_id,
           v_source_batch_id, v_source_ownership_type_id, v_source_owner_party_id,
           v_source_unit_id, v_source_destination_type, v_source_big_cone_order_id
      FROM production.big_cone_output_lines l
      JOIN production.big_cone_orders o ON o.id = l.big_cone_order_id
     WHERE l.id = NEW.source_big_cone_output_line_id
     FOR SHARE OF l, o;

    IF NOT FOUND
       OR v_source_status IS DISTINCT FROM 'POSTED'
       OR v_source_company_id IS DISTINCT FROM v_company_id
       OR v_header_source_order_id IS DISTINCT FROM v_source_big_cone_order_id
       OR v_source_destination_type IS DISTINCT FROM 'BABY_CONE'
       OR NEW.item_variant_id IS DISTINCT FROM v_source_item_variant_id
       OR NEW.batch_id IS DISTINCT FROM v_source_batch_id
       OR NEW.ownership_type_id IS DISTINCT FROM v_source_ownership_type_id
       OR NEW.owner_party_id IS DISTINCT FROM v_source_owner_party_id
       OR NEW.unit_id IS DISTINCT FROM v_source_unit_id THEN
        RAISE EXCEPTION 'Baby Cone source must match a POSTED same-company Big Cone BABY_CONE output line, including item, batch, ownership, owner and unit';
    END IF;

    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_baby_cone_source_output_line
BEFORE INSERT OR UPDATE OF baby_cone_order_id, source_big_cone_output_line_id,
    item_variant_id, batch_id, ownership_type_id, owner_party_id, unit_id
ON production.baby_cone_material_lines
FOR EACH ROW
EXECUTE FUNCTION production.guard_baby_cone_source_output_line();

CREATE OR REPLACE FUNCTION production.guard_big_cone_source_header_change()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF NEW.source_dyeing_order_id IS DISTINCT FROM OLD.source_dyeing_order_id
       AND EXISTS (
           SELECT 1 FROM production.big_cone_material_lines
            WHERE big_cone_order_id = OLD.id
       ) THEN
        RAISE EXCEPTION 'Big Cone source Dyeing order cannot change after material lines exist';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_big_cone_source_header_change
BEFORE UPDATE OF source_dyeing_order_id
ON production.big_cone_orders
FOR EACH ROW
EXECUTE FUNCTION production.guard_big_cone_source_header_change();

CREATE OR REPLACE FUNCTION production.guard_baby_cone_source_header_change()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF NEW.source_big_cone_order_id IS DISTINCT FROM OLD.source_big_cone_order_id
       AND EXISTS (
           SELECT 1 FROM production.baby_cone_material_lines
            WHERE baby_cone_order_id = OLD.id
       ) THEN
        RAISE EXCEPTION 'Baby Cone source Big Cone order cannot change after material lines exist';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_baby_cone_source_header_change
BEFORE UPDATE OF source_big_cone_order_id
ON production.baby_cone_orders
FOR EACH ROW
EXECUTE FUNCTION production.guard_baby_cone_source_header_change();

COMMIT;
-- Ali Raza Enterprises ERP
-- 20261107_031_dyeing_consumption_source_yarn_lineage
-- Bind every dye/chemical consumption line to one exact raw-Yarn input line.
-- Separate lines can be used when one material is consumed by multiple fibers.

BEGIN;

ALTER TABLE production.dyeing_consumption_lines
    ADD COLUMN source_material_line_id BIGINT;

ALTER TABLE production.dyeing_consumption_lines
    ADD CONSTRAINT fk_dyeing_consumption_source_material
        FOREIGN KEY (source_material_line_id)
        REFERENCES production.dyeing_material_lines(id)
        ON DELETE RESTRICT;

CREATE INDEX ix_dyeing_consumption_source_material
    ON production.dyeing_consumption_lines(source_material_line_id);

CREATE OR REPLACE FUNCTION production.guard_dyeing_consumption_source_material()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    v_order_company_id BIGINT;
    v_order_status VARCHAR(30);
    v_source_order_id BIGINT;
    v_source_company_id BIGINT;
    v_source_item_code VARCHAR(100);
    v_source_category_code VARCHAR(100);
    v_source_unit_code VARCHAR(30);
    v_source_is_stock_item BOOLEAN;
    v_source_ownership_code VARCHAR(30);
    v_source_owner_party_id BIGINT;
    v_source_location_id BIGINT;
    v_source_process_stage_id BIGINT;
    v_raw_location_id BIGINT;
    v_purchase_stage_id BIGINT;
    v_own_type_id BIGINT;
BEGIN
    IF TG_OP='DELETE' THEN
        SELECT status INTO v_order_status
          FROM production.dyeing_orders
         WHERE id=OLD.dyeing_order_id
         FOR SHARE;
        IF v_order_status IS DISTINCT FROM 'DRAFT' THEN
            RAISE EXCEPTION 'Dye/chemical consumption lines cannot be deleted after DRAFT';
        END IF;
        RETURN OLD;
    END IF;

    SELECT company_id,status
      INTO v_order_company_id,v_order_status
      FROM production.dyeing_orders
     WHERE id=NEW.dyeing_order_id
     FOR SHARE;
    IF NOT FOUND OR v_order_status IS DISTINCT FROM 'DRAFT' THEN
        RAISE EXCEPTION 'Dye/chemical consumption lines can only be changed on a DRAFT Dyeing order';
    END IF;

    IF NEW.source_material_line_id IS NULL THEN
        RAISE EXCEPTION 'Every Dye/chemical consumption line must be linked to its exact raw-Yarn input line';
    END IF;

    SELECT m.dyeing_order_id,i.company_id,i.item_code,c.code,
           base.code,i.is_stock_item,own.code,m.owner_party_id,
           m.location_id,m.process_stage_id
      INTO v_source_order_id,v_source_company_id,v_source_item_code,
           v_source_category_code,v_source_unit_code,v_source_is_stock_item,
           v_source_ownership_code,v_source_owner_party_id,
           v_source_location_id,v_source_process_stage_id
      FROM production.dyeing_material_lines m
      JOIN master.item_variants v ON v.id=m.item_variant_id
      JOIN master.items i ON i.id=v.item_id
      JOIN master.item_categories c ON c.id=i.item_category_id
      JOIN master.units base ON base.id=i.base_unit_id
      JOIN master.ownership_types own ON own.id=m.ownership_type_id
     WHERE m.id=NEW.source_material_line_id
     FOR SHARE OF m;

    SELECT il.id INTO v_raw_location_id
      FROM inventory.locations il
      JOIN core.locations cl ON cl.id=il.core_location_id
     WHERE cl.company_id=v_order_company_id AND cl.code='RAW_STORE'
       AND cl.is_active=TRUE AND il.is_active=TRUE AND il.allow_stock=TRUE;
    SELECT id INTO v_purchase_stage_id
      FROM master.process_stages
     WHERE company_id=v_order_company_id AND code='PURCHASE' AND is_active=TRUE;
    SELECT id INTO v_own_type_id
      FROM master.ownership_types WHERE code='OWN' AND is_active=TRUE;

    IF v_source_order_id IS DISTINCT FROM NEW.dyeing_order_id
       OR v_source_company_id IS DISTINCT FROM v_order_company_id
       OR v_source_item_code IS DISTINCT FROM 'YARN'
       OR v_source_category_code IS DISTINCT FROM 'YARN'
       OR v_source_is_stock_item IS NOT TRUE
       OR v_source_unit_code IS DISTINCT FROM 'KG'
       OR v_source_ownership_code IS DISTINCT FROM 'OWN'
       OR v_source_owner_party_id IS NOT NULL
       OR v_source_location_id IS DISTINCT FROM v_raw_location_id
       OR v_source_process_stage_id IS DISTINCT FROM v_purchase_stage_id
       OR v_own_type_id IS NULL THEN
        RAISE EXCEPTION 'Dye/chemical line source must be an OWN YARN input line in the same Dyeing order at RAW_STORE/PURCHASE in KG';
    END IF;

    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_dyeing_consumption_source_material_guard
BEFORE INSERT OR UPDATE OR DELETE ON production.dyeing_consumption_lines
FOR EACH ROW EXECUTE FUNCTION production.guard_dyeing_consumption_source_material();

CREATE OR REPLACE FUNCTION production.guard_dyeing_consumption_source_before_advance()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF OLD.status='DRAFT' AND NEW.status='APPROVED' THEN
        IF NOT EXISTS (
            SELECT 1 FROM production.dyeing_consumption_lines
             WHERE dyeing_order_id=NEW.id
        ) THEN
            RAISE EXCEPTION 'Dyeing cannot be approved without dye/chemical consumption lines';
        END IF;
        IF EXISTS (
            SELECT 1
              FROM production.dyeing_consumption_lines c
              LEFT JOIN production.dyeing_material_lines m
                ON m.id=c.source_material_line_id
               AND m.dyeing_order_id=c.dyeing_order_id
             WHERE c.dyeing_order_id=NEW.id
               AND (c.source_material_line_id IS NULL OR m.id IS NULL)
        ) THEN
            RAISE EXCEPTION 'Dyeing approval requires every dye/chemical line to link to an exact Yarn input line in the same order';
        END IF;
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_dyeing_consumption_source_advance_guard
BEFORE UPDATE OF status ON production.dyeing_orders
FOR EACH ROW EXECUTE FUNCTION production.guard_dyeing_consumption_source_before_advance();

COMMIT;
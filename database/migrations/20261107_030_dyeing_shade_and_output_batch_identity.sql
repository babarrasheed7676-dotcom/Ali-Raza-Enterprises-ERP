-- Ali Raza Enterprises ERP
-- 20261107_030_dyeing_shade_and_output_batch_identity
-- Keep raw Yarn and dyed Yarn stock identities distinct.
-- The new output batch is created only during posting and keeps source_batch_id lineage.

BEGIN;

CREATE OR REPLACE FUNCTION production.guard_dyeing_output_source_material()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    v_company_id BIGINT;
    v_order_status VARCHAR(30);
    v_material_order_id BIGINT;
    v_source_variant_id BIGINT;
    v_source_batch_id BIGINT;
    v_source_item_id BIGINT;
    v_source_yarn_count_id BIGINT;
    v_source_fiber_type_id BIGINT;
    v_ownership_type_id BIGINT;
    v_owner_party_id BIGINT;
    v_unit_id BIGINT;
    v_location_id BIGINT;
    v_quantity_kg NUMERIC;
    v_allocated_source_quantity NUMERIC;
    v_raw_location_id BIGINT;
    v_dyeing_stage_id BIGINT;
    v_shade_brand_id BIGINT;
    v_output_item_id BIGINT;
    v_output_yarn_count_id BIGINT;
    v_output_fiber_type_id BIGINT;
    v_output_brand_id BIGINT;
    v_output_shade_id BIGINT;
    v_output_item_code VARCHAR(100);
    v_own_type_id BIGINT;
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
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Dyeing order does not exist';
    END IF;

    SELECT id INTO v_own_type_id
      FROM master.ownership_types WHERE code='OWN' AND is_active=TRUE;

    SELECT l.dyeing_order_id,l.item_variant_id,l.batch_id,i.id,
           v.yarn_count_id,v.fiber_type_id,l.ownership_type_id,
           l.owner_party_id,l.unit_id,l.location_id,l.quantity_kg
      INTO v_material_order_id,v_source_variant_id,v_source_batch_id,v_source_item_id,
           v_source_yarn_count_id,v_source_fiber_type_id,v_ownership_type_id,
           v_owner_party_id,v_unit_id,v_location_id,v_quantity_kg
      FROM production.dyeing_material_lines l
      JOIN master.item_variants v ON v.id=l.item_variant_id
      JOIN master.items i ON i.id=v.item_id
     WHERE l.id=NEW.source_material_line_id
     FOR UPDATE OF l;

    SELECT il.id INTO v_raw_location_id
      FROM inventory.locations il
      JOIN core.locations cl ON cl.id=il.core_location_id
     WHERE cl.company_id=v_company_id AND cl.code='RAW_STORE'
       AND cl.is_active=TRUE AND il.is_active=TRUE AND il.allow_stock=TRUE;
    SELECT id INTO v_dyeing_stage_id FROM master.process_stages
     WHERE company_id=v_company_id AND code='DYEING' AND is_active=TRUE;

    IF v_material_order_id IS DISTINCT FROM NEW.dyeing_order_id
       OR v_source_item_id IS NULL OR v_raw_location_id IS NULL
       OR v_dyeing_stage_id IS NULL OR v_own_type_id IS NULL
       OR v_ownership_type_id IS DISTINCT FROM v_own_type_id
       OR v_owner_party_id IS NOT NULL
       OR NEW.ownership_type_id IS DISTINCT FROM v_own_type_id
       OR NEW.owner_party_id IS NOT NULL
       OR NEW.unit_id IS DISTINCT FROM v_unit_id
       OR NEW.location_id IS DISTINCT FROM v_location_id
       OR v_location_id IS DISTINCT FROM v_raw_location_id
       OR NEW.location_id IS DISTINCT FROM v_raw_location_id
       OR NEW.process_stage_id IS DISTINCT FROM v_dyeing_stage_id THEN
        RAISE EXCEPTION 'Dyeing output must be OWN-owned at RAW_STORE/DYEING and retain source unit and same-order input lineage';
    END IF;

    IF NEW.output_type='DYED_THREAD' AND
       (NEW.actual_shade_id IS NULL OR NEW.shade_match_status IS DISTINCT FROM 'EXACT') THEN
        RAISE EXCEPTION 'DYED_THREAD output requires an exact active shade selection';
    END IF;

    SELECT brand_id INTO v_shade_brand_id
      FROM master.shades WHERE id=NEW.actual_shade_id AND is_active=TRUE;
    IF NOT FOUND OR v_shade_brand_id IS NULL OR NOT EXISTS (
        SELECT 1 FROM master.brands b
         WHERE b.id=v_shade_brand_id AND b.is_active=TRUE
    ) THEN
        RAISE EXCEPTION 'Dyeing output shade must belong to an active brand';
    END IF;

    SELECT v.item_id,v.yarn_count_id,v.fiber_type_id,v.brand_id,v.shade_id,i.item_code
      INTO v_output_item_id,v_output_yarn_count_id,v_output_fiber_type_id,
           v_output_brand_id,v_output_shade_id,v_output_item_code
      FROM master.item_variants v
      JOIN master.items i ON i.id=v.item_id
     WHERE v.id=NEW.item_variant_id AND v.is_active=TRUE AND i.is_active=TRUE
       AND i.company_id=v_company_id AND i.is_stock_item=TRUE;

    IF NOT FOUND
       OR v_output_item_code IS DISTINCT FROM 'YARN'
       OR v_output_item_id IS DISTINCT FROM v_source_item_id
       OR v_output_yarn_count_id IS DISTINCT FROM v_source_yarn_count_id
       OR v_output_fiber_type_id IS DISTINCT FROM v_source_fiber_type_id THEN
        RAISE EXCEPTION 'DYED_THREAD output must retain its source Yarn item, yarn count and fiber type';
    END IF;

    -- During DRAFT, the input variant may be retained provisionally, or a configured
    -- exact shade variant may be used. Approval requires the exact shade variant.
    IF NEW.item_variant_id IS DISTINCT FROM v_source_variant_id
       AND (v_output_brand_id IS DISTINCT FROM v_shade_brand_id
            OR v_output_shade_id IS DISTINCT FROM NEW.actual_shade_id) THEN
        RAISE EXCEPTION 'Dyed Yarn output variant must match the selected shade brand and shade';
    END IF;

    IF v_order_status='APPROVED' AND TG_OP='UPDATE' THEN
        IF OLD.batch_id IS NOT NULL OR NEW.batch_id IS NULL
           OR NEW.dyeing_order_id IS DISTINCT FROM OLD.dyeing_order_id
           OR NEW.line_no IS DISTINCT FROM OLD.line_no
           OR NEW.item_variant_id IS DISTINCT FROM OLD.item_variant_id
           OR NEW.location_id IS DISTINCT FROM OLD.location_id
           OR NEW.ownership_type_id IS DISTINCT FROM OLD.ownership_type_id
           OR NEW.owner_party_id IS DISTINCT FROM OLD.owner_party_id
           OR NEW.process_stage_id IS DISTINCT FROM OLD.process_stage_id
           OR NEW.output_type IS DISTINCT FROM OLD.output_type
           OR NEW.quantity_kg IS DISTINCT FROM OLD.quantity_kg
           OR NEW.unit_id IS DISTINCT FROM OLD.unit_id
           OR NEW.actual_shade_id IS DISTINCT FROM OLD.actual_shade_id
           OR NEW.shade_match_status IS DISTINCT FROM OLD.shade_match_status
           OR NEW.source_material_line_id IS DISTINCT FROM OLD.source_material_line_id
           OR NEW.source_material_quantity_kg IS DISTINCT FROM OLD.source_material_quantity_kg
           OR NEW.notes IS DISTINCT FROM OLD.notes THEN
            RAISE EXCEPTION 'APPROVED Dyeing output can only receive its generated output batch identity';
        END IF;
        IF NOT EXISTS (
            SELECT 1 FROM inventory.batches b
             WHERE b.id=NEW.batch_id AND b.company_id=v_company_id
               AND b.item_variant_id=NEW.item_variant_id
               AND b.process_stage_id=v_dyeing_stage_id
               AND b.ownership_type_id=v_own_type_id
               AND b.owner_party_id IS NULL
               AND b.source_batch_id IS NOT DISTINCT FROM v_source_batch_id
        ) THEN
            RAISE EXCEPTION 'Dyed output batch must match the shade-specific Yarn variant, DYEING stage and exact source batch';
        END IF;
        RETURN NEW;
    END IF;

    IF v_order_status IS DISTINCT FROM 'DRAFT' THEN
        RAISE EXCEPTION 'Dyeing output lines can only be changed on DRAFT orders, except to assign the generated output batch while APPROVED';
    END IF;
    IF NEW.batch_id IS NOT NULL THEN
        RAISE EXCEPTION 'Dyeing output batch is generated during posting; DRAFT output batch must remain blank';
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

    RETURN NEW;
END;
$$;

CREATE OR REPLACE FUNCTION production.guard_dyeing_material_output_before_advance()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF OLD.status='DRAFT' AND NEW.status='APPROVED' THEN
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
        IF EXISTS (
            SELECT 1
              FROM production.dyeing_material_lines m
              LEFT JOIN inventory.batches source_batch ON source_batch.id=m.batch_id
              LEFT JOIN master.item_variants source_variant ON source_variant.id=m.item_variant_id
             WHERE m.dyeing_order_id=NEW.id
               AND (m.batch_id IS NULL
                    OR source_batch.id IS NULL
                    OR source_batch.company_id IS DISTINCT FROM NEW.company_id
                    OR source_batch.item_variant_id IS DISTINCT FROM m.item_variant_id
                    OR source_batch.process_stage_id IS DISTINCT FROM
                       (SELECT id FROM master.process_stages WHERE company_id=NEW.company_id AND code='PURCHASE' AND is_active=TRUE)
                    OR source_batch.ownership_type_id IS DISTINCT FROM
                       (SELECT id FROM master.ownership_types WHERE code='OWN' AND is_active=TRUE)
                    OR source_batch.owner_party_id IS NOT NULL)
        ) THEN
            RAISE EXCEPTION 'Dyeing approval requires an exact received OWN raw-yarn batch for every input line';
        END IF;
        IF EXISTS (
            SELECT 1
              FROM production.dyeing_material_lines m
              LEFT JOIN production.dyeing_output_lines o ON o.source_material_line_id=m.id
             WHERE m.dyeing_order_id=NEW.id
             GROUP BY m.id,m.quantity_kg
            HAVING COALESCE(SUM(o.source_material_quantity_kg),0)<>m.quantity_kg
        ) THEN
            RAISE EXCEPTION 'Every raw-yarn input KG must be allocated to DYED_THREAD outputs before approval';
        END IF;
        IF EXISTS (
            SELECT 1
              FROM production.dyeing_output_lines o
              JOIN production.dyeing_material_lines m ON m.id=o.source_material_line_id
              JOIN master.item_variants source_v ON source_v.id=m.item_variant_id
              JOIN master.item_variants output_v ON output_v.id=o.item_variant_id
              JOIN master.shades shade ON shade.id=o.actual_shade_id
             WHERE o.dyeing_order_id=NEW.id
               AND (output_v.item_id IS DISTINCT FROM source_v.item_id
                    OR output_v.yarn_count_id IS DISTINCT FROM source_v.yarn_count_id
                    OR output_v.fiber_type_id IS DISTINCT FROM source_v.fiber_type_id
                    OR output_v.brand_id IS DISTINCT FROM shade.brand_id
                    OR output_v.shade_id IS DISTINCT FROM shade.id)
        ) THEN
            RAISE EXCEPTION 'Dyeing approval requires each output to use a configured shade-specific Yarn variant';
        END IF;
        IF EXISTS (
            SELECT 1 FROM production.dyeing_output_lines
             WHERE dyeing_order_id=NEW.id AND batch_id IS NOT NULL
        ) THEN
            RAISE EXCEPTION 'Dyeing output batches must be created at posting, not during DRAFT/approval';
        END IF;
    ELSIF OLD.status='APPROVED' AND NEW.status='POSTED' THEN
        IF EXISTS (
            SELECT 1
              FROM production.dyeing_output_lines o
              JOIN production.dyeing_material_lines m ON m.id=o.source_material_line_id
              LEFT JOIN inventory.batches output_batch ON output_batch.id=o.batch_id
             WHERE o.dyeing_order_id=NEW.id
               AND (output_batch.id IS NULL
                    OR output_batch.company_id IS DISTINCT FROM NEW.company_id
                    OR output_batch.item_variant_id IS DISTINCT FROM o.item_variant_id
                    OR output_batch.process_stage_id IS DISTINCT FROM
                       (SELECT id FROM master.process_stages WHERE company_id=NEW.company_id AND code='DYEING' AND is_active=TRUE)
                    OR output_batch.ownership_type_id IS DISTINCT FROM
                       (SELECT id FROM master.ownership_types WHERE code='OWN' AND is_active=TRUE)
                    OR output_batch.owner_party_id IS NOT NULL
                    OR output_batch.source_batch_id IS DISTINCT FROM m.batch_id)
        ) THEN
            RAISE EXCEPTION 'Dyeing cannot be posted until every DYED_THREAD output has its own DYEING-stage batch linked to the source batch';
        END IF;
    END IF;
    RETURN NEW;
END;
$$;

COMMIT;
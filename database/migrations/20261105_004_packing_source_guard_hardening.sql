-- Harden source allocation guard: enforce stage, location and rejected-return lineage.
BEGIN;
CREATE OR REPLACE FUNCTION production.guard_packing_source_allocation()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    target_order_id BIGINT;
    target_company_id BIGINT;
    target_item_id BIGINT;
    parent_status VARCHAR(20);
    parent_company_id BIGINT;
    item_variant BIGINT;
    source_variant BIGINT;
    source_batch BIGINT;
    source_location BIGINT;
    source_stage BIGINT;
    source_stage_code VARCHAR(60);
    source_lineage BIGINT;
    source_ownership BIGINT;
    source_owner BIGINT;
    source_cost NUMERIC(20,6);
    source_quality VARCHAR(30);
    source_kind VARCHAR(30);
    source_order_company BIGINT;
    source_order_status VARCHAR(30);
BEGIN
    IF TG_OP = 'DELETE' THEN
        target_order_id := OLD.packing_order_id;
        target_company_id := OLD.company_id;
        target_item_id := OLD.packing_order_item_id;
    ELSE
        target_order_id := NEW.packing_order_id;
        target_company_id := NEW.company_id;
        target_item_id := NEW.packing_order_item_id;
    END IF;

    IF TG_OP = 'UPDATE' AND (
        NEW.packing_order_id <> OLD.packing_order_id
        OR NEW.packing_order_item_id <> OLD.packing_order_item_id
        OR NEW.company_id <> OLD.company_id
    ) THEN
        RAISE EXCEPTION 'Packing source allocations cannot be moved between orders or companies';
    END IF;

    SELECT status, company_id INTO parent_status, parent_company_id
      FROM production.packing_orders
     WHERE id = target_order_id
     FOR UPDATE;

    IF parent_status IS DISTINCT FROM 'DRAFT'
       OR parent_company_id IS DISTINCT FROM target_company_id THEN
        RAISE EXCEPTION 'Source allocations may only be changed on a same-company DRAFT packing order';
    END IF;

    IF TG_OP = 'DELETE' THEN
        RETURN OLD;
    END IF;

    SELECT item_variant_id INTO item_variant
      FROM production.packing_order_items
     WHERE id = NEW.packing_order_item_id
       AND packing_order_id = NEW.packing_order_id
     FOR UPDATE;

    IF item_variant IS DISTINCT FROM NEW.item_variant_id THEN
        RAISE EXCEPTION 'Packing source variant does not match its packing item';
    END IF;

    IF NEW.source_type = 'FRESH_NALKI' THEN
        SELECT ol.item_variant_id, ol.batch_id, ol.location_id,
               ol.process_stage_id, ps.code, NULL::bigint, ol.ownership_type_id, ol.owner_party_id,
               ol.unit_cost, ol.quality_status, ol.output_type,
               no.company_id, no.status
          INTO source_variant, source_batch, source_location, source_stage,
               source_stage_code, source_lineage, source_ownership, source_owner,
               source_cost, source_quality, source_kind, source_order_company, source_order_status
          FROM production.nalki_output_lines ol
          JOIN production.nalki_orders no ON no.id = ol.nalki_order_id
          JOIN master.process_stages ps ON ps.id=ol.process_stage_id
         WHERE ol.id = NEW.nalki_output_line_id;
        IF NOT FOUND OR source_order_company IS DISTINCT FROM NEW.company_id
           OR source_order_status <> 'POSTED'
           OR source_kind <> 'GOOD' OR source_quality <> 'ACCEPTED'
           OR source_location IS NULL OR source_stage_code NOT IN ('NALKI','LABELING') THEN
            RAISE EXCEPTION 'Fresh Nalki source line is not an accepted posted output for this company';
        END IF;
    ELSE
        SELECT rl.item_variant_id, rl.batch_id, rl.location_id,
               rl.process_stage_id, ps.code, rl.source_nalki_line_id,
               rl.ownership_type_id, rl.owner_party_id,
               rl.unit_cost, rl.quality_status, rl.return_status,
               lo.company_id, lo.status
          INTO source_variant, source_batch, source_location, source_stage,
               source_stage_code, source_lineage, source_ownership, source_owner,
               source_cost, source_quality, source_kind, source_order_company, source_order_status
          FROM production.outside_labeling_return_lines rl
          JOIN production.outside_labeling_orders lo
            ON lo.id = rl.outside_labeling_order_id
          JOIN master.process_stages ps ON ps.id=rl.process_stage_id
         WHERE rl.id = NEW.outside_labeling_return_line_id;
        IF NOT FOUND OR source_order_company IS DISTINCT FROM NEW.company_id
           OR source_order_status NOT IN ('PARTIAL_RETURN','RETURNED')
           OR source_kind <> 'ACCEPTED' OR source_quality <> 'ACCEPTED'
           OR source_stage IS NULL OR source_location IS NULL
           OR source_stage_code NOT IN ('NALKI','LABELING')
           OR source_lineage IS NULL OR source_ownership <> 2 OR source_owner IS NULL THEN
            RAISE EXCEPTION 'Outside-labeling return source is not an accepted, staged return for this company';
        END IF;
    END IF;

    IF source_variant IS DISTINCT FROM NEW.item_variant_id
       OR source_batch IS DISTINCT FROM NEW.batch_id
       OR source_location IS DISTINCT FROM NEW.location_id
       OR source_stage IS DISTINCT FROM NEW.process_stage_id
       OR source_ownership IS DISTINCT FROM NEW.ownership_type_id
       OR source_owner IS DISTINCT FROM NEW.owner_party_id
       OR source_cost IS DISTINCT FROM NEW.source_unit_cost
       OR source_cost IS NULL THEN
        RAISE EXCEPTION 'Packing source allocation snapshot does not match its production source line';
    END IF;

    RETURN NEW;
END;
$$;
COMMIT;
-- Ali Raza Enterprises ERP
-- 20261107_019_dyeing_conversion_snapshot_integrity
-- Close NULL-permissive CHECK gaps and harden JSON/configuration pin comparisons.
BEGIN;

ALTER TABLE production.dyeing_unit_conversion_snapshots
    DROP CONSTRAINT ck_dyeing_unit_conversion_status;

ALTER TABLE production.dyeing_unit_conversion_snapshots
    ADD CONSTRAINT ck_dyeing_unit_conversion_status CHECK (
        (status = 'NOT_REQUIRED'
         AND source_unit_code = target_unit_code
         AND source_unit_id = target_unit_id
         AND converted_quantity IS NOT NULL
         AND converted_quantity = source_quantity
         AND conversion_factor IS NOT NULL
         AND conversion_factor = 1
         AND configuration_version_id IS NULL
         AND rounding_places IS NULL
         AND rounding_mode = 'ROUND_HALF_UP')
        OR
        (status = 'APPROVED'
         AND source_unit_code <> target_unit_code
         AND source_unit_id <> target_unit_id
         AND converted_quantity IS NOT NULL AND converted_quantity > 0
         AND conversion_factor IS NOT NULL AND conversion_factor > 0
         AND configuration_version_id IS NOT NULL
         AND rounding_places BETWEEN 0 AND 6
         AND rounding_mode = 'ROUND_HALF_UP')
        OR
        (status = 'PENDING_CONFIGURATION'
         AND source_unit_code <> target_unit_code
         AND source_unit_id <> target_unit_id
         AND converted_quantity IS NULL
         AND configuration_version_id IS NULL
         AND conversion_factor IS NULL
         AND rounding_places IS NULL
         AND rounding_mode = 'ROUND_HALF_UP')
        OR
        (status = 'BLOCKED_PRECISION'
         AND source_unit_code <> target_unit_code
         AND source_unit_id <> target_unit_id
         AND converted_quantity IS NULL
         AND conversion_factor IS NOT NULL AND conversion_factor > 0
         AND configuration_version_id IS NOT NULL
         AND rounding_places BETWEEN 0 AND 6
         AND rounding_mode = 'ROUND_HALF_UP')
    );

CREATE OR REPLACE FUNCTION production.guard_dyeing_unit_conversion_snapshot()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
    line_company BIGINT;
    line_date DATE;
    line_status VARCHAR(30);
    line_quantity NUMERIC(18,6);
    line_unit_id BIGINT;
    base_unit_id BIGINT;
    source_code VARCHAR(30);
    target_code VARCHAR(30);
    source_type VARCHAR(30);
    target_type VARCHAR(30);
    cfg configuration.config_versions%ROWTYPE;
BEGIN
    IF TG_OP <> 'INSERT' THEN
        RAISE EXCEPTION 'Dyeing unit-conversion snapshots are immutable';
    END IF;

    SELECT o.company_id, o.dyeing_date, o.status, l.quantity, l.unit_id,
           i.base_unit_id, su.code, bu.code, su.unit_type, bu.unit_type
      INTO line_company, line_date, line_status, line_quantity, line_unit_id,
           base_unit_id, source_code, target_code, source_type, target_type
      FROM production.dyeing_consumption_lines l
      JOIN production.dyeing_orders o ON o.id = l.dyeing_order_id
      JOIN master.item_variants v ON v.id = l.item_variant_id
      JOIN master.items i ON i.id = v.item_id
      JOIN master.units su ON su.id = l.unit_id
      JOIN master.units bu ON bu.id = i.base_unit_id
     WHERE l.id = NEW.consumption_line_id
       AND su.is_active = TRUE AND bu.is_active = TRUE
     FOR SHARE OF l, o, su, bu;

    IF NOT FOUND OR line_status IS DISTINCT FROM 'DRAFT'
       OR line_company IS DISTINCT FROM NEW.company_id
       OR line_date IS DISTINCT FROM NEW.effective_on
       OR line_quantity IS DISTINCT FROM NEW.source_quantity
       OR line_unit_id IS DISTINCT FROM NEW.source_unit_id
       OR base_unit_id IS DISTINCT FROM NEW.target_unit_id
       OR source_code IS DISTINCT FROM NEW.source_unit_code
       OR target_code IS DISTINCT FROM NEW.target_unit_code
       OR source_type IS DISTINCT FROM target_type THEN
        RAISE EXCEPTION 'Conversion snapshot must exactly match an active same-company DRAFT Dyeing line and its base unit';
    END IF;

    IF NEW.snapshot->>'status' IS DISTINCT FROM NEW.status
       OR NEW.snapshot->>'source_unit_code' IS DISTINCT FROM NEW.source_unit_code
       OR NEW.snapshot->>'target_unit_code' IS DISTINCT FROM NEW.target_unit_code
       OR (NEW.snapshot->>'source_quantity')::numeric IS DISTINCT FROM NEW.source_quantity
       OR NEW.snapshot->>'effective_on' IS DISTINCT FROM NEW.effective_on::text
       OR NEW.snapshot->>'rounding_mode' IS DISTINCT FROM NEW.rounding_mode THEN
        RAISE EXCEPTION 'Conversion snapshot JSON does not match its pinned columns';
    END IF;

    IF NEW.status = 'NOT_REQUIRED' THEN
        IF NEW.snapshot->>'factor' IS DISTINCT FROM '1'
           OR (NEW.snapshot->>'converted_quantity')::numeric IS DISTINCT FROM NEW.converted_quantity
           OR NEW.conversion_factor IS DISTINCT FROM 1 THEN
            RAISE EXCEPTION 'Same-unit snapshot must pin factor 1 and unchanged quantity';
        END IF;
    ELSIF NEW.status = 'PENDING_CONFIGURATION' THEN
        IF NEW.snapshot->>'source' IS DISTINCT FROM 'NO_APPROVED_EFFECTIVE_RULE'
           OR NEW.snapshot->>'converted_quantity' IS NOT NULL
           OR NEW.snapshot->>'factor' IS NOT NULL
           OR NEW.snapshot->>'configuration_version_id' IS NOT NULL THEN
            RAISE EXCEPTION 'Pending conversion must not contain an unapproved factor or converted quantity';
        END IF;
    ELSE
        IF NEW.snapshot->>'factor' IS NULL
           OR (NEW.snapshot->>'factor')::numeric IS DISTINCT FROM NEW.conversion_factor
           OR (NEW.snapshot->>'rounding_places')::integer IS DISTINCT FROM NEW.rounding_places
           OR NEW.snapshot->>'rounding_mode' IS DISTINCT FROM NEW.rounding_mode
           OR (NEW.snapshot->>'configuration_version_id')::bigint IS DISTINCT FROM NEW.configuration_version_id THEN
            RAISE EXCEPTION 'Approved conversion JSON must exactly match its pinned factor, precision and version';
        END IF;
    END IF;

    IF NEW.configuration_version_id IS NOT NULL THEN
        SELECT * INTO cfg
          FROM configuration.config_versions
         WHERE id = NEW.configuration_version_id
         FOR SHARE;
        IF NOT FOUND OR cfg.company_id IS DISTINCT FROM NEW.company_id
           OR cfg.config_type IS DISTINCT FROM 'UNIT_CONVERSION'
           OR cfg.status IS DISTINCT FROM 'APPROVED'
           OR cfg.config_key IS DISTINCT FROM upper(NEW.source_unit_code) || '-TO-' || upper(NEW.target_unit_code)
           OR cfg.effective_from > NEW.effective_on
           OR (cfg.effective_to IS NOT NULL AND cfg.effective_to < NEW.effective_on)
           OR cfg.payload->>'from_unit_code' IS DISTINCT FROM NEW.source_unit_code
           OR cfg.payload->>'to_unit_code' IS DISTINCT FROM NEW.target_unit_code
           OR (cfg.payload->>'factor')::numeric IS DISTINCT FROM NEW.conversion_factor
           OR (cfg.payload->>'rounding_places')::integer IS DISTINCT FROM NEW.rounding_places
           OR COALESCE((cfg.payload->>'active')::boolean, FALSE) IS NOT TRUE
           OR (NEW.snapshot->>'configuration_version_id')::bigint IS DISTINCT FROM NEW.configuration_version_id THEN
            RAISE EXCEPTION 'Pinned unit-conversion version is not the exact approved effective rule';
        END IF;
    ELSIF NEW.status IN ('APPROVED', 'BLOCKED_PRECISION') THEN
        RAISE EXCEPTION 'Approved or precision-blocked conversion requires its exact configuration version';
    END IF;

    RETURN NEW;
END;
$$;

COMMIT;
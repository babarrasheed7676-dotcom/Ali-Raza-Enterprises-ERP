BEGIN;

CREATE TABLE production.baby_cone_measurements (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    company_id bigint NOT NULL REFERENCES core.company(id) ON DELETE RESTRICT,
    baby_cone_output_line_id bigint NOT NULL REFERENCES production.baby_cone_output_lines(id) ON DELETE RESTRICT,
    configuration_snapshot_id bigint NOT NULL REFERENCES production.baby_cone_configuration_snapshots(id) ON DELETE RESTRICT,
    gross_weight_grams numeric NOT NULL CHECK (gross_weight_grams > 0),
    empty_core_tare_grams numeric NOT NULL CHECK (empty_core_tare_grams >= 0),
    net_yarn_grams numeric NOT NULL CHECK (net_yarn_grams > 0),
    measured_yards numeric NOT NULL CHECK (measured_yards > 0),
    grams_per_yard numeric NOT NULL CHECK (grams_per_yard > 0),
    required_yards numeric NULL CHECK (required_yards > 0),
    required_yarn_kg numeric NULL CHECK (required_yarn_kg > 0),
    operator_code varchar(60) NULL,
    requires_approval boolean NOT NULL,
    created_by bigint NOT NULL REFERENCES core.users(id) ON DELETE RESTRICT,
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_baby_cone_measurement_output_line UNIQUE (baby_cone_output_line_id),
    CONSTRAINT chk_baby_cone_measurement_net CHECK (gross_weight_grams > empty_core_tare_grams AND net_yarn_grams = gross_weight_grams - empty_core_tare_grams),
    CONSTRAINT chk_baby_cone_measurement_required CHECK (
        (required_yards IS NULL AND required_yarn_kg IS NULL)
        OR (required_yards IS NOT NULL AND required_yarn_kg IS NOT NULL)
    )
);

CREATE OR REPLACE FUNCTION production.guard_baby_cone_measurement_draft()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    parent_company bigint;
    parent_status text;
    output_variant_code text;
    snapshot_company bigint;
    snapshot_line bigint;
    snapshot_payload jsonb;
BEGIN
    IF TG_OP = 'DELETE' THEN
        SELECT o.status INTO parent_status
          FROM production.baby_cone_output_lines l
          JOIN production.baby_cone_orders o ON o.id=l.baby_cone_order_id
         WHERE l.id=OLD.baby_cone_output_line_id;
        IF parent_status IS DISTINCT FROM 'DRAFT' THEN
            RAISE EXCEPTION 'Baby Cone measurements can only be deleted while the order is DRAFT.';
        END IF;
        RETURN OLD;
    END IF;

    SELECT o.company_id,o.status,v.variant_code
      INTO parent_company,parent_status,output_variant_code
      FROM production.baby_cone_output_lines l
      JOIN production.baby_cone_orders o ON o.id=l.baby_cone_order_id
      JOIN master.item_variants v ON v.id=l.item_variant_id
     WHERE l.id=NEW.baby_cone_output_line_id
     FOR SHARE OF l,o;

    IF NOT FOUND OR parent_company IS DISTINCT FROM NEW.company_id THEN
        RAISE EXCEPTION 'Baby Cone measurement company/output-line mismatch.';
    END IF;
    IF parent_status <> 'DRAFT' THEN
        RAISE EXCEPTION 'Baby Cone measurements can only be saved while the order is DRAFT.';
    END IF;

    SELECT company_id,baby_cone_output_line_id,payload_snapshot
      INTO snapshot_company,snapshot_line,snapshot_payload
      FROM production.baby_cone_configuration_snapshots
     WHERE id=NEW.configuration_snapshot_id
     FOR SHARE;

    IF NOT FOUND
       OR snapshot_company IS DISTINCT FROM NEW.company_id
       OR snapshot_line IS DISTINCT FROM NEW.baby_cone_output_line_id
       OR upper(snapshot_payload->>'variant_code') IS DISTINCT FROM upper(output_variant_code)
       OR NEW.requires_approval IS DISTINCT FROM (snapshot_payload->>'requires_approval')::boolean
       OR ((snapshot_payload->>'requires_operator')::boolean AND coalesce(trim(NEW.operator_code),'')='') THEN
        RAISE EXCEPTION 'Baby Cone measurement does not satisfy its pinned approved profile.';
    END IF;

    NEW.updated_at := CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_guard_baby_cone_measurement_draft
BEFORE INSERT OR UPDATE OR DELETE ON production.baby_cone_measurements
FOR EACH ROW EXECUTE FUNCTION production.guard_baby_cone_measurement_draft();

COMMIT;
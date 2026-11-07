BEGIN;

CREATE TABLE production.baby_cone_configuration_snapshots (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    company_id bigint NOT NULL REFERENCES core.company(id) ON DELETE RESTRICT,
    baby_cone_output_line_id bigint NOT NULL REFERENCES production.baby_cone_output_lines(id) ON DELETE RESTRICT,
    config_type varchar(60) NOT NULL CHECK (config_type='MEASUREMENT_PROFILE'),
    config_key varchar(120) NOT NULL,
    configuration_version_id bigint NOT NULL REFERENCES configuration.config_versions(id) ON DELETE RESTRICT,
    source varchar(30) NOT NULL CHECK (source='APPROVED_VERSION'),
    effective_on date NOT NULL,
    payload_snapshot jsonb NOT NULL CHECK (jsonb_typeof(payload_snapshot)='object'),
    created_by bigint NOT NULL REFERENCES core.users(id) ON DELETE RESTRICT,
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_baby_cone_configuration_snapshot
        UNIQUE (baby_cone_output_line_id,config_type,config_key)
);

CREATE OR REPLACE FUNCTION production.guard_baby_cone_configuration_snapshot()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    parent_company_id bigint;
    parent_status text;
    parent_creator bigint;
    parent_date date;
    output_variant_code text;
    version_company_id bigint;
    version_type text;
    version_key text;
    version_status text;
    version_from date;
    version_to date;
    version_payload jsonb;
BEGIN
    IF TG_OP IN ('UPDATE','DELETE') THEN
        RAISE EXCEPTION 'Baby Cone configuration snapshots are immutable.';
    END IF;

    SELECT o.company_id,o.status,o.created_by,o.baby_cone_date,v.variant_code
      INTO parent_company_id,parent_status,parent_creator,parent_date,output_variant_code
      FROM production.baby_cone_output_lines l
      JOIN production.baby_cone_orders o ON o.id=l.baby_cone_order_id
      JOIN master.item_variants v ON v.id=l.item_variant_id
     WHERE l.id=NEW.baby_cone_output_line_id
     FOR SHARE OF l,o;

    IF NOT FOUND OR parent_company_id IS DISTINCT FROM NEW.company_id THEN
        RAISE EXCEPTION 'Baby Cone snapshot company/output-line mismatch.';
    END IF;
    IF parent_status <> 'DRAFT' THEN
        RAISE EXCEPTION 'Measurement profile can only be attached to a DRAFT Baby Cone output line.';
    END IF;
    IF NEW.created_by IS DISTINCT FROM parent_creator OR NEW.effective_on IS DISTINCT FROM parent_date THEN
        RAISE EXCEPTION 'Baby Cone snapshot creator/date must match its order.';
    END IF;

    SELECT company_id,config_type,config_key,status,effective_from,effective_to,payload
      INTO version_company_id,version_type,version_key,version_status,
           version_from,version_to,version_payload
      FROM configuration.config_versions
     WHERE id=NEW.configuration_version_id
     FOR SHARE;

    IF NOT FOUND
       OR version_company_id IS DISTINCT FROM NEW.company_id
       OR version_type IS DISTINCT FROM NEW.config_type
       OR version_key IS DISTINCT FROM NEW.config_key
       OR version_status <> 'APPROVED'
       OR version_from > NEW.effective_on
       OR (version_to IS NOT NULL AND version_to < NEW.effective_on)
       OR version_payload IS DISTINCT FROM NEW.payload_snapshot
       OR upper(version_payload->>'variant_code') IS DISTINCT FROM upper(output_variant_code)
       OR NEW.payload_snapshot->>'method' <> 'weight_per_length'
       OR NEW.payload_snapshot->>'active' IS DISTINCT FROM 'true' THEN
        RAISE EXCEPTION 'Baby Cone measurement profile is not approved/effective or its variant/payload snapshot is invalid.';
    END IF;

    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_guard_baby_cone_configuration_snapshot
BEFORE INSERT OR UPDATE OR DELETE ON production.baby_cone_configuration_snapshots
FOR EACH ROW EXECUTE FUNCTION production.guard_baby_cone_configuration_snapshot();

COMMIT;
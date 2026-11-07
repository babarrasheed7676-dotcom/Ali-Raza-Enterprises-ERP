BEGIN;

CREATE TABLE production.packing_configuration_snapshots (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    company_id bigint NOT NULL REFERENCES core.company(id) ON DELETE RESTRICT,
    packing_order_id bigint NOT NULL REFERENCES production.packing_orders(id) ON DELETE RESTRICT,
    config_type varchar(60) NOT NULL,
    config_key varchar(120) NOT NULL,
    configuration_version_id bigint NULL REFERENCES configuration.config_versions(id) ON DELETE RESTRICT,
    source varchar(30) NOT NULL CHECK (source IN ('APPROVED_VERSION','SYSTEM_DEFAULT')),
    effective_on date NOT NULL,
    payload_snapshot jsonb NOT NULL CHECK (jsonb_typeof(payload_snapshot) = 'object'),
    created_by bigint NOT NULL REFERENCES core.users(id) ON DELETE RESTRICT,
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_packing_configuration_snapshot UNIQUE (packing_order_id, config_type, config_key),
    CONSTRAINT chk_packing_configuration_source_version CHECK (
        (source = 'APPROVED_VERSION' AND configuration_version_id IS NOT NULL)
        OR (source = 'SYSTEM_DEFAULT' AND configuration_version_id IS NULL)
    )
);

CREATE OR REPLACE FUNCTION production.guard_packing_configuration_snapshot()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    parent_company_id bigint;
    parent_status text;
    version_company_id bigint;
    version_type text;
    version_key text;
    version_status text;
    version_from date;
    version_to date;
    version_payload jsonb;
BEGIN
    IF TG_OP IN ('UPDATE','DELETE') THEN
        RAISE EXCEPTION 'Packing configuration snapshots are immutable.';
    END IF;

    SELECT company_id,status
      INTO parent_company_id,parent_status
      FROM production.packing_orders
     WHERE id=NEW.packing_order_id
     FOR SHARE;

    IF NOT FOUND OR parent_company_id <> NEW.company_id THEN
        RAISE EXCEPTION 'Packing configuration snapshot company/order mismatch.';
    END IF;
    IF parent_status <> 'DRAFT' THEN
        RAISE EXCEPTION 'Configuration snapshot can only be attached to a DRAFT packing order.';
    END IF;

    IF NEW.source='APPROVED_VERSION' THEN
        SELECT company_id,config_type,config_key,status,effective_from,effective_to,payload
          INTO version_company_id,version_type,version_key,version_status,version_from,version_to,version_payload
          FROM configuration.config_versions
         WHERE id=NEW.configuration_version_id
         FOR SHARE;

        IF NOT FOUND
           OR version_company_id <> NEW.company_id
           OR version_type <> NEW.config_type
           OR version_key <> NEW.config_key
           OR version_status <> 'APPROVED'
           OR version_from > NEW.effective_on
           OR (version_to IS NOT NULL AND version_to < NEW.effective_on)
           OR version_payload IS DISTINCT FROM NEW.payload_snapshot THEN
            RAISE EXCEPTION 'Configuration version is not approved/effective or its payload snapshot does not match.';
        END IF;
    ELSIF NEW.source='SYSTEM_DEFAULT' THEN
        IF NEW.configuration_version_id IS NOT NULL THEN
            RAISE EXCEPTION 'SYSTEM_DEFAULT snapshot cannot reference a configuration version.';
        END IF;
    ELSE
        RAISE EXCEPTION 'Unsupported packing configuration snapshot source.';
    END IF;

    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_guard_packing_configuration_snapshot
BEFORE INSERT OR UPDATE OR DELETE ON production.packing_configuration_snapshots
FOR EACH ROW EXECUTE FUNCTION production.guard_packing_configuration_snapshot();

COMMIT;

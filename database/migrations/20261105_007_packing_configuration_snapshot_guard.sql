BEGIN;

CREATE OR REPLACE FUNCTION production.guard_packing_configuration_snapshot()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    parent_company_id bigint;
    parent_status text;
    parent_created_by bigint;
    parent_packing_date date;
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

    SELECT company_id,status,created_by,packing_date
      INTO parent_company_id,parent_status,parent_created_by,parent_packing_date
      FROM production.packing_orders
     WHERE id=NEW.packing_order_id
     FOR SHARE;

    IF NOT FOUND OR parent_company_id <> NEW.company_id THEN
        RAISE EXCEPTION 'Packing configuration snapshot company/order mismatch.';
    END IF;
    IF parent_status <> 'DRAFT' THEN
        RAISE EXCEPTION 'Configuration snapshot can only be attached to a DRAFT packing order.';
    END IF;
    IF NEW.created_by IS DISTINCT FROM parent_created_by
       OR NEW.effective_on IS DISTINCT FROM parent_packing_date THEN
        RAISE EXCEPTION 'Packing configuration snapshot actor/date must match its parent order.';
    END IF;

    IF NEW.config_type <> 'PACKAGING_RULE'
       OR NEW.config_key <> 'NALKI-FINISHED-WALL-BOX' THEN
        RAISE EXCEPTION 'Unsupported packing configuration rule identity.';
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
        IF NEW.configuration_version_id IS NOT NULL
           OR NEW.payload_snapshot->>'product_type' IS DISTINCT FROM 'Nalki'
           OR NEW.payload_snapshot->>'product_code' IS DISTINCT FROM 'NALKI'
           OR NEW.payload_snapshot->>'packaging_code' IS DISTINCT FROM 'FINISHED-WALL-BOX'
           OR NEW.payload_snapshot->>'base_unit_code' IS DISTINCT FROM 'PCS'
           OR NEW.payload_snapshot->>'units_per_pack' IS DISTINCT FROM '100'
           OR NEW.payload_snapshot->>'inner_packaging_code' IS DISTINCT FROM 'PACK_BOX-STD'
           OR NEW.payload_snapshot->>'inner_packs_per_pack' IS DISTINCT FROM '10'
           OR NEW.payload_snapshot->>'active' IS DISTINCT FROM 'true' THEN
            RAISE EXCEPTION 'SYSTEM_DEFAULT snapshot does not match the approved Nalki packaging baseline.';
        END IF;
    ELSE
        RAISE EXCEPTION 'Unsupported packing configuration snapshot source.';
    END IF;

    RETURN NEW;
END;
$$;

COMMIT;
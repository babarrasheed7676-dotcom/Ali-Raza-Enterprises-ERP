BEGIN;

CREATE TABLE purchasing.purchase_configuration_snapshots (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    company_id bigint NOT NULL REFERENCES core.company(id) ON DELETE RESTRICT,
    purchase_receipt_id bigint NOT NULL REFERENCES purchasing.purchase_receipts(id) ON DELETE RESTRICT,
    purchase_receipt_line_id bigint NOT NULL REFERENCES purchasing.purchase_receipt_lines(id) ON DELETE RESTRICT,
    config_type varchar(60) NOT NULL CHECK (config_type IN ('PRODUCT_DEFINITION','UNIT_DEFINITION')),
    config_key varchar(120) NOT NULL,
    configuration_version_id bigint NULL REFERENCES configuration.config_versions(id) ON DELETE RESTRICT,
    source varchar(40) NOT NULL CHECK (source IN ('APPROVED_VERSION','SYSTEM_DEFAULT_MASTER')),
    effective_on date NOT NULL,
    payload_snapshot jsonb NOT NULL CHECK (jsonb_typeof(payload_snapshot)='object'),
    created_by bigint NOT NULL REFERENCES core.users(id) ON DELETE RESTRICT,
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_purchase_configuration_snapshot UNIQUE (purchase_receipt_line_id,config_type,config_key),
    CONSTRAINT chk_purchase_configuration_source_version CHECK (
      (source='APPROVED_VERSION' AND configuration_version_id IS NOT NULL)
      OR (source='SYSTEM_DEFAULT_MASTER' AND configuration_version_id IS NULL)
    )
);

CREATE OR REPLACE FUNCTION purchasing.guard_purchase_configuration_snapshot()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
  parent_company bigint;
  parent_status text;
  parent_creator bigint;
  parent_date date;
  line_receipt bigint;
  version_company bigint;
  version_type text;
  version_key text;
  version_status text;
  version_from date;
  version_to date;
  version_payload jsonb;
  master_id bigint;
  master_code text;
  master_name text;
  master_precision integer;
BEGIN
  IF TG_OP IN ('UPDATE','DELETE') THEN
    RAISE EXCEPTION 'Purchase configuration snapshots are immutable.';
  END IF;

  SELECT r.company_id,r.status,r.created_by,r.receipt_date,l.purchase_receipt_id
    INTO parent_company,parent_status,parent_creator,parent_date,line_receipt
    FROM purchasing.purchase_receipts r
    JOIN purchasing.purchase_receipt_lines l ON l.purchase_receipt_id=r.id
   WHERE r.id=NEW.purchase_receipt_id AND l.id=NEW.purchase_receipt_line_id
   FOR SHARE OF r,l;

  IF NOT FOUND OR line_receipt IS DISTINCT FROM NEW.purchase_receipt_id
     OR parent_company IS DISTINCT FROM NEW.company_id THEN
    RAISE EXCEPTION 'Purchase configuration snapshot receipt/line/company mismatch.';
  END IF;
  IF parent_status <> 'DRAFT' THEN
    RAISE EXCEPTION 'Purchase configuration snapshot can only be attached to a DRAFT receipt.';
  END IF;
  IF NEW.created_by IS DISTINCT FROM parent_creator OR NEW.effective_on IS DISTINCT FROM parent_date THEN
    RAISE EXCEPTION 'Purchase configuration snapshot creator/date must match its receipt.';
  END IF;

  IF NEW.source='APPROVED_VERSION' THEN
    SELECT company_id,config_type,config_key,status,effective_from,effective_to,payload
      INTO version_company,version_type,version_key,version_status,version_from,version_to,version_payload
      FROM configuration.config_versions WHERE id=NEW.configuration_version_id FOR SHARE;
    IF NOT FOUND OR version_company IS DISTINCT FROM NEW.company_id
       OR version_type IS DISTINCT FROM NEW.config_type
       OR version_key IS DISTINCT FROM NEW.config_key
       OR version_status <> 'APPROVED'
       OR version_from > NEW.effective_on
       OR (version_to IS NOT NULL AND version_to < NEW.effective_on)
       OR version_payload IS DISTINCT FROM NEW.payload_snapshot
       OR NEW.payload_snapshot->>'code' IS DISTINCT FROM NEW.config_key THEN
      RAISE EXCEPTION 'Purchase configuration version is not approved/effective or payload/key mismatch.';
    END IF;
  ELSIF NEW.source='SYSTEM_DEFAULT_MASTER' THEN
    IF NEW.configuration_version_id IS NOT NULL
       OR NEW.payload_snapshot->>'code' IS DISTINCT FROM NEW.config_key THEN
      RAISE EXCEPTION 'Invalid system-master purchase configuration snapshot.';
    END IF;
    master_id := NULLIF(NEW.payload_snapshot->>'master_id','')::bigint;
    IF NEW.config_type='PRODUCT_DEFINITION' THEN
      SELECT item_code,item_name INTO master_code,master_name
        FROM master.items WHERE id=master_id AND company_id=NEW.company_id AND is_active;
      IF NOT FOUND OR master_code IS DISTINCT FROM NEW.config_key
         OR master_name IS DISTINCT FROM NEW.payload_snapshot->>'name' THEN
        RAISE EXCEPTION 'Product master snapshot does not match an active company item.';
      END IF;
    ELSIF NEW.config_type='UNIT_DEFINITION' THEN
      SELECT code,name,decimal_places INTO master_code,master_name,master_precision
        FROM master.units WHERE id=master_id AND is_active;
      IF NOT FOUND OR master_code IS DISTINCT FROM NEW.config_key
         OR master_name IS DISTINCT FROM NEW.payload_snapshot->>'name'
         OR master_precision::text IS DISTINCT FROM NEW.payload_snapshot->>'decimal_places' THEN
        RAISE EXCEPTION 'Unit master snapshot does not match an active unit.';
      END IF;
    ELSE
      RAISE EXCEPTION 'Unsupported purchase configuration type.';
    END IF;
  ELSE
    RAISE EXCEPTION 'Unsupported purchase configuration snapshot source.';
  END IF;
  RETURN NEW;
END;
$$;

CREATE TRIGGER trg_guard_purchase_configuration_snapshot
BEFORE INSERT OR UPDATE OR DELETE ON purchasing.purchase_configuration_snapshots
FOR EACH ROW EXECUTE FUNCTION purchasing.guard_purchase_configuration_snapshot();

COMMIT;

-- PROPOSAL ONLY — DO NOT EXECUTE ON THE LIVE DATABASE.
-- Baby Cone cost/loss child-row lifecycle guard.
-- Reviewed design: lock the parent header first, then require status='DRAFT'.
-- Application service must perform the same company-scoped lock/status check.
-- Apply only after migration review, backup, maintenance approval, and tests.

BEGIN;

CREATE OR REPLACE FUNCTION production.guard_baby_cone_cost_loss_draft()
RETURNS trigger
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = pg_catalog, production
AS $function$
DECLARE
    v_order_id bigint;
    v_status text;
BEGIN
    IF TG_OP = 'UPDATE' THEN
        IF NEW.baby_cone_order_id IS DISTINCT FROM OLD.baby_cone_order_id THEN
            RAISE EXCEPTION 'Baby Cone child rows cannot be moved between parent documents.'
                USING ERRCODE = '55000';
        END IF;
        v_order_id := OLD.baby_cone_order_id;
    ELSIF TG_OP = 'DELETE' THEN
        v_order_id := OLD.baby_cone_order_id;
    ELSE
        v_order_id := NEW.baby_cone_order_id;
    END IF;

    -- Serializes child writes against a concurrent parent status transition.
    SELECT o.status
      INTO v_status
      FROM production.baby_cone_orders AS o
     WHERE o.id = v_order_id
     FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Baby Cone parent document % was not found.', v_order_id
            USING ERRCODE = '23503';
    END IF;

    IF v_status IS DISTINCT FROM 'DRAFT' THEN
        RAISE EXCEPTION
            'Baby Cone cost/loss rows are editable only while the parent document is DRAFT (document %, status %).',
            v_order_id, v_status
            USING ERRCODE = '55000';
    END IF;

    IF TG_OP = 'DELETE' THEN
        RETURN OLD;
    END IF;
    RETURN NEW;
END;
$function$;

DROP TRIGGER IF EXISTS trg_baby_cone_cost_lines_draft_guard
    ON production.baby_cone_cost_lines;
CREATE TRIGGER trg_baby_cone_cost_lines_draft_guard
BEFORE INSERT OR UPDATE OR DELETE
ON production.baby_cone_cost_lines
FOR EACH ROW
EXECUTE FUNCTION production.guard_baby_cone_cost_loss_draft();

DROP TRIGGER IF EXISTS trg_baby_cone_loss_lines_draft_guard
    ON production.baby_cone_loss_lines;
CREATE TRIGGER trg_baby_cone_loss_lines_draft_guard
BEFORE INSERT OR UPDATE OR DELETE
ON production.baby_cone_loss_lines
FOR EACH ROW
EXECUTE FUNCTION production.guard_baby_cone_cost_loss_draft();

-- Row triggers do not fire for TRUNCATE. Explicitly reject it on these child tables.
CREATE OR REPLACE FUNCTION production.reject_baby_cone_cost_loss_truncate()
RETURNS trigger
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = pg_catalog, production
AS $function$
BEGIN
    RAISE EXCEPTION 'TRUNCATE is not permitted on Baby Cone cost/loss child tables.'
        USING ERRCODE = '55000';
END;
$function$;

DROP TRIGGER IF EXISTS trg_baby_cone_cost_lines_no_truncate
    ON production.baby_cone_cost_lines;
CREATE TRIGGER trg_baby_cone_cost_lines_no_truncate
BEFORE TRUNCATE
ON production.baby_cone_cost_lines
FOR EACH STATEMENT
EXECUTE FUNCTION production.reject_baby_cone_cost_loss_truncate();

DROP TRIGGER IF EXISTS trg_baby_cone_loss_lines_no_truncate
    ON production.baby_cone_loss_lines;
CREATE TRIGGER trg_baby_cone_loss_lines_no_truncate
BEFORE TRUNCATE
ON production.baby_cone_loss_lines
FOR EACH STATEMENT
EXECUTE FUNCTION production.reject_baby_cone_cost_loss_truncate();

COMMIT;

-- ROLLBACK / DOWN MIGRATION (run separately, only if approved):
-- BEGIN;
-- DROP TRIGGER IF EXISTS trg_baby_cone_cost_lines_draft_guard ON production.baby_cone_cost_lines;
-- DROP TRIGGER IF EXISTS trg_baby_cone_loss_lines_draft_guard ON production.baby_cone_loss_lines;
-- DROP TRIGGER IF EXISTS trg_baby_cone_cost_lines_no_truncate ON production.baby_cone_cost_lines;
-- DROP TRIGGER IF EXISTS trg_baby_cone_loss_lines_no_truncate ON production.baby_cone_loss_lines;
-- DROP FUNCTION IF EXISTS production.guard_baby_cone_cost_loss_draft();
-- DROP FUNCTION IF EXISTS production.reject_baby_cone_cost_loss_truncate();
-- COMMIT;

-- Important limitations:
-- 1. This is a proposal, not an applied migration.
-- 2. The trigger checks parent lifecycle status; it does not validate business cost/loss semantics.
-- 3. The app must additionally scope the parent lookup by authenticated company_id,
--    enforce production.create + CSRF, and write audit records in the same transaction.
-- 4. A DB superuser/table owner can disable triggers or alter schema. The runtime DB role
--    must not own these tables or have DDL/trigger-disable privileges for this to be a
--    meaningful defence-in-depth control.
-- 5. Validate the current table names, key column, status type, and trigger privileges
--    against a fresh backup/restore test environment before any live application.

-- 6. Additional live-environment finding (7 Nov 2026): read-only inspection showed
--    the application DSN connects as current_user=postgres and the three Baby Cone
--    tables are owned by postgres. This role has TRIGGER and TRUNCATE privileges.
--    Therefore these triggers alone are NOT a security boundary in the current
--    configuration: postgres can disable triggers, alter them, or bypass ordinary
--    safeguards. Do not describe this proposal as enforcement-ready until a dedicated
--    least-privilege application role is designed, provisioned, tested, and the app
--    DSN is deliberately migrated with rollback access preserved.
-- 7. Do not change the current DB role/DSN as part of this proposal. Role migration
--    is a separate security change requiring a privilege inventory across all ERP
--    modules, explicit approval, backup, staged connection test, and rollback plan.

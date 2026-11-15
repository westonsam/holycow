BEGIN;
ALTER FUNCTION cattle.immutable_history() SET search_path='';
ALTER FUNCTION cattle.guard_run_insert() SET search_path='';
COMMIT;

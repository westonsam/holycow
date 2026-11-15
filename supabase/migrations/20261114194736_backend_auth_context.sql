BEGIN;
-- Read the verified per-request subject without granting access to auth.users or credentials.
GRANT USAGE ON SCHEMA auth TO cattle_backend_user;
GRANT EXECUTE ON FUNCTION auth.uid() TO cattle_backend_user;
COMMIT;

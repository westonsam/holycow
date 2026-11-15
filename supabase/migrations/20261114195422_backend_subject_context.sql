BEGIN;
-- Trusted backend verifies the JWT first, then supplies request.jwt.claims transaction-locally.
-- No credentials, auth.users access or inherited broad provider role is needed.
CREATE FUNCTION cattle.request_user_id() RETURNS uuid
LANGUAGE sql STABLE SECURITY INVOKER SET search_path='' AS $$
 SELECT nullif(nullif(current_setting('request.jwt.claims',true),'')::jsonb->>'sub','')::uuid
$$;
REVOKE ALL ON FUNCTION cattle.request_user_id() FROM PUBLIC,anon,authenticated;
GRANT EXECUTE ON FUNCTION cattle.request_user_id() TO cattle_backend_user,service_role;
CREATE OR REPLACE FUNCTION cattle.has_org_role(target_org uuid,
  allowed_roles text[] DEFAULT ARRAY['owner','admin','operator','reviewer','viewer'])
RETURNS boolean LANGUAGE sql STABLE SECURITY INVOKER SET search_path='' AS $$
 SELECT EXISTS(SELECT 1 FROM cattle.membership m WHERE m.org_id=target_org
   AND m.user_id=(SELECT cattle.request_user_id()) AND m.role=ANY(allowed_roles))
$$;
ALTER POLICY membership_self ON cattle.membership
 USING(user_id=(SELECT cattle.request_user_id()));
COMMIT;

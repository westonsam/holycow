-- Chosen architecture: frontend -> application backend -> database.
-- This is a NOLOGIN group, not a credential for the browser or a ready application login.
BEGIN;
CREATE ROLE cattle_backend_user NOLOGIN NOINHERIT NOBYPASSRLS;
GRANT cattle_backend_user TO postgres;
GRANT USAGE ON SCHEMA cattle,extensions TO cattle_backend_user;
GRANT SELECT ON ALL TABLES IN SCHEMA cattle TO cattle_backend_user;
GRANT EXECUTE ON FUNCTION cattle.has_org_role(uuid,text[]),cattle.can_read_evidence(text),
 cattle.review_finding(uuid,uuid,uuid,text,text),
 cattle.correct_track_identity(uuid,uuid,uuid,uuid,text,text,uuid[]) TO cattle_backend_user;
ALTER POLICY membership_self ON cattle.membership TO cattle_backend_user;
DO $$ DECLARE t record; BEGIN
 FOR t IN SELECT tablename FROM pg_tables WHERE schemaname='cattle' AND tablename<>'membership' LOOP
  EXECUTE format('ALTER POLICY member_read ON cattle.%I TO cattle_backend_user',t.tablename);
 END LOOP;
END $$;
REVOKE ALL ON SCHEMA cattle FROM anon,authenticated;
REVOKE ALL ON ALL TABLES IN SCHEMA cattle FROM anon,authenticated;
REVOKE EXECUTE ON ALL FUNCTIONS IN SCHEMA cattle FROM anon,authenticated;
-- Evidence is authorized by the backend; browser roles cannot list/download bucket objects directly.
DROP POLICY cattle_evidence_read ON storage.objects;
ALTER POLICY cattle_evidence_read_guard ON storage.objects
 USING(bucket_id<>'cattle-evidence');
COMMIT;

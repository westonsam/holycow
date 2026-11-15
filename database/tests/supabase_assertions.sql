-- Included by build_supabase.py inside the synthetic fixture transaction.
-- SQL session claim injection is test-only; the backend must verify JWTs before setting claims.
SET LOCAL search_path=cattle,extensions,public;
DO $$ BEGIN
 IF (SELECT count(*) FROM media_asset)<>2 THEN RAISE EXCEPTION 'retry duplicated media'; END IF;
 IF (SELECT count(*) FROM inference_run)<>2 THEN RAISE EXCEPTION 'rerun not retained'; END IF;
 IF (SELECT count(*) FROM model_measurement)<>2 THEN RAISE EXCEPTION 'model conflict lost'; END IF;
 IF (SELECT id FROM latest_animal_location WHERE animal_id=pg_temp.uid(21))<>pg_temp.uid(120) THEN
  RAISE EXCEPTION 'late older point replaced newer observation'; END IF;
 IF (SELECT count(*) FROM active_location WHERE animal_id IS NULL)<>1 THEN RAISE EXCEPTION 'anonymous location missing'; END IF;
 IF NOT (SELECT requires_recompute FROM current_survey) THEN RAISE EXCEPTION 'survey correction not flagged'; END IF;
 IF (SELECT effective_state FROM current_alert)<>'invalidated' THEN RAISE EXCEPTION 'review rejection not applied'; END IF;
 IF NOT ST_DWithin(ST_SetSRID(ST_Point(-120,37),4326)::geography,ST_SetSRID(ST_Point(-120.001,37),4326)::geography,100)
  OR ST_DWithin(ST_SetSRID(ST_Point(-120,37),4326)::geography,ST_SetSRID(ST_Point(-120.001,37),4326)::geography,10) THEN
  RAISE EXCEPTION 'meter distance semantics incorrect'; END IF;
 IF NOT (SELECT ST_DWithin(ST_SetSRID(ST_Point(-120,37.005),4326)::geography,
   ST_Boundary(geom)::geography,5) FROM boundary_version) THEN RAISE EXCEPTION 'boundary uncertainty contact'; END IF;
 BEGIN
  INSERT INTO flight(org_id,drone_id,ranch_id,source_key,started_at)
   VALUES(pg_temp.uid(1),pg_temp.uid(230),pg_temp.uid(10),'cross-tenant-test',now());
  RAISE EXCEPTION 'cross-tenant FK unexpectedly accepted';
 EXCEPTION WHEN foreign_key_violation THEN NULL; END;
 BEGIN
  UPDATE model_output SET score=0 WHERE id=pg_temp.uid(80);
  RAISE EXCEPTION 'evidence update unexpectedly accepted';
 EXCEPTION WHEN object_not_in_prerequisite_state THEN NULL; END;
END $$;

SET LOCAL ROLE authenticated;
SELECT set_config('request.jwt.claims','{"sub":"00000000-0000-0000-0000-000000000901","role":"authenticated"}',true);
DO $$ BEGIN
 IF (SELECT count(*) FROM organization)<>1 OR (SELECT count(*) FROM membership)<>1 THEN RAISE EXCEPTION 'reviewer tenant visibility'; END IF;
 IF (SELECT count(*) FROM animal)<>2 THEN RAISE EXCEPTION 'reviewer animal visibility'; END IF;
 IF (SELECT count(*) FROM latest_animal_location)<>1 THEN RAISE EXCEPTION 'invoker location view'; END IF;
 IF NOT cattle.can_read_evidence(pg_temp.uid(1)::text||'/flight1/clip1/200.jpg') THEN RAISE EXCEPTION 'own evidence unavailable'; END IF;
 IF cattle.can_read_evidence(pg_temp.uid(2)::text||'/flight1/clip1/200.jpg') THEN RAISE EXCEPTION 'other tenant evidence leaked'; END IF;
 BEGIN
  INSERT INTO membership VALUES(pg_temp.uid(2),pg_temp.uid(901),'owner');
  RAISE EXCEPTION 'self-escalation unexpectedly accepted';
 EXCEPTION WHEN insufficient_privilege THEN NULL; END;
 BEGIN
  UPDATE model_output SET score=0;
  RAISE EXCEPTION 'direct browser write unexpectedly accepted';
 EXCEPTION WHEN insufficient_privilege THEN NULL; END;
END $$;
-- An arbitrary tenant GUC must not influence Supabase authorization.
SELECT set_config('app.org_id','00000000-0000-0000-0000-000000000002',true);
DO $$ BEGIN
 IF EXISTS(SELECT 1 FROM animal WHERE org_id=pg_temp.uid(2)) THEN RAISE EXCEPTION 'tenant GUC bypassed Auth policy'; END IF;
END $$;

-- Reverse fixture review rejection, then test identity-dependent alerts separately.
SELECT cattle.review_finding(pg_temp.uid(1),pg_temp.uid(130),pg_temp.uid(143),'accepted','Synthetic verification only');
RESET ROLE;
INSERT INTO alert(org_id,rule_version_id,basis_identity_decision_id,finding_id,dedupe_key)
 VALUES(pg_temp.uid(1),pg_temp.uid(140),pg_temp.uid(111),pg_temp.uid(130),'identity-bound-verification');
SET LOCAL ROLE authenticated;
SELECT cattle.correct_track_identity(pg_temp.uid(1),pg_temp.uid(100),pg_temp.uid(111),pg_temp.uid(20),
 'accepted','Synthetic identity correction',ARRAY[pg_temp.uid(80)]);
DO $$ BEGIN
 IF (SELECT animal_id FROM latest_animal_location)<>pg_temp.uid(20) THEN RAISE EXCEPTION 'identity correction view failed'; END IF;
 IF (SELECT resolved_animal_id FROM resolved_finding)<>pg_temp.uid(20) THEN RAISE EXCEPTION 'finding correction view failed'; END IF;
 IF (SELECT count(*) FROM identity_decision)<>3 THEN RAISE EXCEPTION 'correction erased history'; END IF;
 IF (SELECT effective_state FROM current_alert WHERE dedupe_key='identity-bound-verification')<>'invalidated' THEN
  RAISE EXCEPTION 'identity-bound alert not invalidated'; END IF;
 IF NOT EXISTS(SELECT 1 FROM audit_event WHERE action='identity_correction' AND actor=cattle.request_user_id()::text) THEN
  RAISE EXCEPTION 'signed-in reviewer attribution missing'; END IF;
 BEGIN
  PERFORM cattle.correct_track_identity(pg_temp.uid(1),pg_temp.uid(100),pg_temp.uid(111),pg_temp.uid(20),
   'accepted','Stale head',ARRAY[pg_temp.uid(80)]);
  RAISE EXCEPTION 'stale correction unexpectedly accepted';
 EXCEPTION WHEN serialization_failure THEN NULL; END;
END $$;

-- Other tenant viewer cannot read original tenant or invoke review RPCs.
SELECT set_config('request.jwt.claims','{"sub":"00000000-0000-0000-0000-000000000902","role":"authenticated"}',true);
DO $$ BEGIN
 IF (SELECT count(*) FROM animal)<>1 OR EXISTS(SELECT 1 FROM animal WHERE org_id=pg_temp.uid(1)) THEN
  RAISE EXCEPTION 'other tenant read isolation'; END IF;
 IF cattle.can_read_evidence(pg_temp.uid(1)::text||'/flight1/clip1/200.jpg') THEN RAISE EXCEPTION 'cross-tenant storage authorization'; END IF;
 BEGIN
  PERFORM cattle.review_finding(pg_temp.uid(2),pg_temp.uid(130),NULL,'accepted','Viewer forbidden');
  RAISE EXCEPTION 'viewer review unexpectedly accepted';
 EXCEPTION WHEN insufficient_privilege THEN NULL; END;
 BEGIN
  PERFORM cattle.correct_track_identity(pg_temp.uid(1),pg_temp.uid(100),NULL,pg_temp.uid(20),
    'accepted','Other tenant forbidden',ARRAY[pg_temp.uid(80)]);
  RAISE EXCEPTION 'cross-tenant correction unexpectedly accepted';
 EXCEPTION WHEN insufficient_privilege THEN NULL; END;
END $$;
SELECT set_config('request.jwt.claims','{"sub":"00000000-0000-0000-0000-000000000903","role":"authenticated"}',true);
DO $$ BEGIN
 IF EXISTS(SELECT 1 FROM organization) OR EXISTS(SELECT 1 FROM latest_animal_location) THEN
  RAISE EXCEPTION 'nonmember data leaked'; END IF;
END $$;
SELECT set_config('request.jwt.claims','{}',true);
DO $$ BEGIN
 IF EXISTS(SELECT 1 FROM animal) THEN RAISE EXCEPTION 'missing identity not fail-closed'; END IF;
END $$;
RESET ROLE;
-- Verify the Storage policy contract, without faking any Storage object metadata/blob upload.
DO $$ BEGIN
 IF (SELECT public FROM storage.buckets WHERE id='cattle-evidence') IS DISTINCT FROM false THEN RAISE EXCEPTION 'bucket not private'; END IF;
 IF (SELECT count(*) FROM pg_policies WHERE schemaname='storage' AND tablename='objects'
  AND policyname LIKE 'cattle_evidence_%' AND permissive='RESTRICTIVE')<>5 THEN RAISE EXCEPTION 'storage guards missing'; END IF;
 IF has_table_privilege('authenticated','cattle.membership','INSERT') THEN RAISE EXCEPTION 'browser membership grant'; END IF;
 IF has_schema_privilege('authenticated','cattle','USAGE') THEN RAISE EXCEPTION 'browser cattle schema grant'; END IF;
 IF has_table_privilege('authenticated','cattle.animal','SELECT') THEN RAISE EXCEPTION 'browser direct cattle read grant'; END IF;
 IF has_function_privilege('authenticated','cattle.review_finding(uuid,uuid,uuid,text,text)','EXECUTE') THEN RAISE EXCEPTION 'browser direct review grant'; END IF;
 IF has_function_privilege('anon','cattle.review_finding(uuid,uuid,uuid,text,text)','EXECUTE') THEN RAISE EXCEPTION 'anonymous RPC grant'; END IF;
END $$;
ROLLBACK;
SELECT 'PASS: integrity, delayed events, conflicts, corrections, backend user-context RLS, browser isolation, role gates and Storage authorization; fixture rolled back' AS verification;

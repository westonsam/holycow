\set ON_ERROR_STOP on
\ir ../queries/website.sql
BEGIN;
CREATE OR REPLACE FUNCTION pg_temp.uid(n integer) RETURNS uuid LANGUAGE sql IMMUTABLE AS
$$ SELECT ('00000000-0000-0000-0000-'||lpad(n::text,12,'0'))::uuid $$;
CREATE FUNCTION pg_temp.assert(ok boolean,msg text) RETURNS void LANGUAGE plpgsql AS
$$ BEGIN IF ok IS DISTINCT FROM true THEN RAISE EXCEPTION 'ASSERTION: %',msg; END IF; END $$;
CREATE FUNCTION pg_temp.reject(sql text, expected text) RETURNS void LANGUAGE plpgsql AS
$$ BEGIN
 BEGIN EXECUTE sql;
 EXCEPTION WHEN OTHERS THEN
   IF SQLSTATE=expected THEN RETURN; END IF;
   RAISE EXCEPTION 'expected %, got %: %',expected,SQLSTATE,SQLERRM;
 END;
 RAISE EXCEPTION 'expected rejection %, query succeeded',expected;
END $$;
GRANT USAGE ON SCHEMA pg_temp TO cattle_reader;
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA pg_temp TO cattle_reader;
SELECT set_config('app.org_id',pg_temp.uid(1)::text,true);
SET LOCAL ROLE cattle_reader;
SELECT pg_temp.assert((SELECT count(*)=1 FROM cattle.organization),'tenant read isolation');
SELECT pg_temp.assert((SELECT count(*)=2 FROM cattle.media_asset),'exact upload retry dedup');
SELECT pg_temp.assert((SELECT count(*)=2 FROM cattle.inference_run),'intentional rerun retained');
SELECT pg_temp.assert((SELECT count(*)=2 FROM cattle.model_measurement),'conflicting measures retained');
SELECT pg_temp.assert((SELECT count(*)=1 FROM cattle.active_location WHERE animal_id IS NULL),'anonymous not-assessable location');
SELECT pg_temp.assert((SELECT id=pg_temp.uid(120) FROM cattle.latest_animal_location WHERE animal_id=pg_temp.uid(21)),'late event cannot replace newer current point');
SELECT pg_temp.assert((SELECT count(*)=0 FROM cattle.latest_animal_location WHERE animal_id=pg_temp.uid(20)),'wrong identity cleared');
SELECT pg_temp.assert((SELECT count(*)=2 FROM cattle.identity_decision),'identity history remains');
SELECT pg_temp.assert((SELECT effective_state='invalidated' AND lifecycle_state='open' FROM cattle.current_alert),'rejected finding suppresses alert, preserves lifecycle');
SELECT pg_temp.assert((SELECT requires_recompute FROM cattle.current_survey),'identity correction invalidates count');
SELECT pg_temp.assert(ST_DWithin(ST_SetSRID(ST_Point(-120,37),4326)::geography,
 ST_SetSRID(ST_Point(-120.001,37),4326)::geography,100),'radius uses meters (~89m)');
SELECT pg_temp.assert(NOT ST_DWithin(ST_SetSRID(ST_Point(-120,37),4326)::geography,
 ST_SetSRID(ST_Point(-120.001,37),4326)::geography,10),'10 meters is not .001 degrees');
SELECT pg_temp.assert(ST_DWithin(ST_SetSRID(ST_Point(-120,37.005),4326)::geography,
 ST_Boundary(geom)::geography,5),'boundary point indeterminate with uncertainty') FROM cattle.boundary_version;
SELECT pg_temp.reject('UPDATE cattle.model_output SET score=0','42501');
SELECT set_config('app.org_id',pg_temp.uid(2)::text,true);
SELECT pg_temp.assert((SELECT count(*)=0 FROM cattle.latest_animal_location),'view obeys invoker RLS');
SELECT set_config('app.org_id','',true);
SELECT pg_temp.assert((SELECT count(*)=0 FROM cattle.animal),'missing tenant is fail closed');
SELECT set_config('app.org_id',pg_temp.uid(1)::text,true);
RESET ROLE;
SET LOCAL ROLE cattle_worker;
SELECT pg_temp.reject($q$INSERT INTO cattle.flight(org_id,drone_id,ranch_id,source_key,started_at)
 VALUES(pg_temp.uid(1),pg_temp.uid(230),pg_temp.uid(10),'cross-tenant-fk',now())$q$,'23503');
SELECT pg_temp.reject($q$INSERT INTO cattle.drone(org_id,source_key,name)
 VALUES(pg_temp.uid(2),'bad-tenant','bad')$q$,'42501');
INSERT INTO cattle.media_asset SELECT * FROM cattle.media_asset WHERE id=pg_temp.uid(40)
ON CONFLICT(org_id,flight_id,source_key) DO NOTHING;
SELECT pg_temp.assert((SELECT count(*)=2 FROM cattle.media_asset),'worker retry dedup');
SELECT pg_temp.reject($q$UPDATE cattle.inference_run SET status='running' WHERE id=pg_temp.uid(70)$q$,'P0001');
RESET ROLE;
SET LOCAL ROLE cattle_operator;
SELECT pg_temp.reject($q$INSERT INTO cattle.herd_membership(org_id,animal_id,herd_id,valid_during)
 VALUES(pg_temp.uid(1),pg_temp.uid(20),pg_temp.uid(13),'[2026-02-01,infinity)')$q$,'23P01');
RESET ROLE;
SET LOCAL ROLE cattle_reviewer;
SELECT pg_temp.reject($q$INSERT INTO cattle.finding(org_id,event_at,label,severity,assessment,policy_version,actor)
 VALUES(pg_temp.uid(1),now(),'invalid','info','suspected','test','test')$q$,'23514');
-- Isolate identity-dependent invalidation from review rejection (rolled back below).
INSERT INTO cattle.finding_review(org_id,finding_id,supersedes,decision,actor,reason)
VALUES(pg_temp.uid(1),pg_temp.uid(130),pg_temp.uid(143),'accepted','test','test-only review reversal');
INSERT INTO cattle.alert(org_id,rule_version_id,basis_identity_decision_id,finding_id,dedupe_key)
VALUES(pg_temp.uid(1),pg_temp.uid(140),pg_temp.uid(111),pg_temp.uid(130),'identity-dependent-test');
SELECT pg_temp.assert((SELECT effective_state='open' FROM cattle.current_alert WHERE dedupe_key='identity-dependent-test'),'identity-basis initially current');
EXECUTE correct_identity('00000000-0000-0000-0000-000000000001','00000000-0000-0000-0000-000000000100',
 '00000000-0000-0000-0000-000000000111','00000000-0000-0000-0000-000000000020','test-reviewer','test correction');
SELECT pg_temp.assert((SELECT animal_id=pg_temp.uid(20) FROM cattle.latest_animal_location),'correction updates current view immediately');
SELECT pg_temp.assert((SELECT resolved_animal_id=pg_temp.uid(20) FROM cattle.resolved_finding),'finding follows corrected identity');
SELECT pg_temp.assert((SELECT effective_state='invalidated' FROM cattle.current_alert WHERE dedupe_key='identity-dependent-test'),'identity-dependent alert invalidated by correction');
SELECT pg_temp.assert((SELECT count(*)=3 FROM cattle.identity_decision),'all three decisions retained');
SELECT pg_temp.reject($q$INSERT INTO cattle.identity_decision(org_id,track_id,supersedes,animal_id,decision,method_version,actor,reason)
 VALUES(pg_temp.uid(1),pg_temp.uid(100),pg_temp.uid(111),pg_temp.uid(20),'accepted','test','test','competing successor')$q$,'23505');
RESET ROLE;
SET LOCAL ROLE cattle_reader;
-- Query compilation + representative bindings. Results printed for review.
EXECUTE herd_locations('00000000-0000-0000-0000-000000000001','00000000-0000-0000-0000-000000000013','2026-11-14T18:00Z','1 hour');
EXECUTE unresolved_locations('00000000-0000-0000-0000-000000000001','00000000-0000-0000-0000-000000000031');
EXECUTE animal_trail('00000000-0000-0000-0000-000000000001','00000000-0000-0000-0000-000000000020','2026-11-14','2026-11-15');
EXECUTE open_alerts('00000000-0000-0000-0000-000000000001','infinity','ffffffff-ffff-ffff-ffff-ffffffffffff',50);
EXECUTE alert_evidence('00000000-0000-0000-0000-000000000001','00000000-0000-0000-0000-000000000141');
EXECUTE nearby_locations('00000000-0000-0000-0000-000000000001',-120.005,37.005,1000,'2026-11-14','2026-11-15');
EXECUTE pasture_observations('00000000-0000-0000-0000-000000000001','00000000-0000-0000-0000-000000000011','2026-11-14','2026-11-15');
EXECUTE flight_summary('00000000-0000-0000-0000-000000000001','00000000-0000-0000-0000-000000000031');
EXECUTE herd_as_of('00000000-0000-0000-0000-000000000001','00000000-0000-0000-0000-000000000013','2026-11-14T17:00Z','infinity');
EXECUTE compare_models('00000000-0000-0000-0000-000000000001','00000000-0000-0000-0000-000000000070','00000000-0000-0000-0000-000000000071');
EXECUTE correction_impact('00000000-0000-0000-0000-000000000001','00000000-0000-0000-0000-000000000100');
ROLLBACK;
\echo 'Integrity assertions and query smoke checks passed (transaction rolled back).'

BEGIN;
SET LOCAL search_path = cattle, public;

-- Deployment groups; LOGIN credentials and grants to the trusted backend are external.
CREATE ROLE cattle_reader NOLOGIN NOBYPASSRLS;
CREATE ROLE cattle_worker NOLOGIN NOBYPASSRLS;
CREATE ROLE cattle_reviewer NOLOGIN NOBYPASSRLS;
CREATE ROLE cattle_operator NOLOGIN NOBYPASSRLS;
CREATE ROLE cattle_admin NOLOGIN NOBYPASSRLS;
GRANT cattle_reader TO cattle_worker, cattle_reviewer, cattle_operator, cattle_admin;
GRANT USAGE ON SCHEMA cattle TO cattle_reader;
REVOKE ALL ON SCHEMA cattle FROM PUBLIC;

CREATE FUNCTION tenant_id() RETURNS uuid LANGUAGE sql STABLE
AS $$ SELECT nullif(current_setting('app.org_id',true),'')::uuid $$;
-- No SECURITY DEFINER functions or client-accessible tenant-switching API.
DO $$ DECLARE t record; BEGIN
  FOR t IN SELECT tablename FROM pg_tables WHERE schemaname='cattle' LOOP
    EXECUTE format('ALTER TABLE cattle.%I ENABLE ROW LEVEL SECURITY',t.tablename);
    EXECUTE format('ALTER TABLE cattle.%I FORCE ROW LEVEL SECURITY',t.tablename);
    IF t.tablename='organization' THEN
      EXECUTE 'CREATE POLICY tenant ON cattle.organization USING (id=cattle.tenant_id()) WITH CHECK (id=cattle.tenant_id())';
    ELSE
      EXECUTE format('CREATE POLICY tenant ON cattle.%I USING (org_id=cattle.tenant_id()) WITH CHECK (org_id=cattle.tenant_id())',t.tablename);
    END IF;
  END LOOP;
END $$;

CREATE FUNCTION immutable_history() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN RAISE EXCEPTION 'append-only history: %',TG_TABLE_NAME USING ERRCODE='55000'; END $$;
DO $$ DECLARE t text; BEGIN
  FOREACH t IN ARRAY ARRAY['model_version','model_output','model_measurement','output_input','detection','track','clip',
    'track_detection','identity_decision','identity_evidence','location_observation','finding',
    'finding_evidence','finding_review','survey','survey_input','alert_rule_version','alert',
    'alert_event','audit_event','frame','telemetry','run_input'] LOOP
    EXECUTE format('CREATE TRIGGER immutable BEFORE UPDATE OR DELETE ON cattle.%I FOR EACH ROW EXECUTE FUNCTION cattle.immutable_history()',t);
  END LOOP;
END $$;

CREATE FUNCTION check_frame() RETURNS trigger LANGUAGE plpgsql SET search_path=cattle,public AS $$
DECLARE a media_asset;
BEGIN
 SELECT * INTO STRICT a FROM media_asset WHERE org_id=NEW.org_id AND id=NEW.asset_id;
 IF (a.kind='image' AND NEW.offset_ms<>0) OR (a.kind='video' AND NEW.offset_ms>=a.duration_ms) THEN
   RAISE EXCEPTION 'frame offset outside media duration' USING ERRCODE='23514';
 END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER frame_bounds BEFORE INSERT ON frame FOR EACH ROW EXECUTE FUNCTION check_frame();

CREATE FUNCTION guard_run() RETURNS trigger LANGUAGE plpgsql SET search_path=cattle,public AS $$
BEGIN
 IF OLD.status IN ('succeeded','failed') THEN RAISE EXCEPTION 'terminal run is immutable; use a new run'; END IF;
 IF (to_jsonb(NEW)-ARRAY['status','started_at','ended_at']) IS DISTINCT FROM
    (to_jsonb(OLD)-ARRAY['status','started_at','ended_at']) THEN
   RAISE EXCEPTION 'run identity/config is immutable';
 END IF;
 IF NOT ((OLD.status='queued' AND NEW.status IN ('running','failed')) OR
         (OLD.status='running' AND NEW.status IN ('succeeded','failed'))) THEN
   RAISE EXCEPTION 'invalid run transition';
 END IF;
 IF NEW.status='succeeded' AND (NOT EXISTS(SELECT 1 FROM run_input WHERE org_id=NEW.org_id AND run_id=NEW.id)
   OR EXISTS(SELECT 1 FROM run_input i JOIN frame f ON (f.org_id,f.id)=(i.org_id,i.frame_id)
     JOIN media_asset a ON (a.org_id,a.id)=(f.org_id,f.asset_id)
     WHERE i.org_id=NEW.org_id AND i.run_id=NEW.id AND a.state<>'ready')) THEN
   RAISE EXCEPTION 'run publication requires ready inputs';
 END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER run_transition BEFORE UPDATE ON inference_run FOR EACH ROW EXECUTE FUNCTION guard_run();
CREATE FUNCTION guard_run_insert() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF NEW.status<>'queued' OR NEW.started_at IS NOT NULL OR NEW.ended_at IS NOT NULL THEN
   RAISE EXCEPTION 'new runs must be queued';
 END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER run_insert BEFORE INSERT ON inference_run FOR EACH ROW EXECUTE FUNCTION guard_run_insert();

-- Row locking serializes publication against concurrent producers under READ COMMITTED.
CREATE FUNCTION guard_output() RETURNS trigger LANGUAGE plpgsql SET search_path=cattle,public AS $$
DECLARE s text;
BEGIN
 SELECT status INTO STRICT s FROM inference_run WHERE org_id=NEW.org_id AND id=NEW.run_id FOR UPDATE;
 IF s NOT IN ('queued','running') THEN RAISE EXCEPTION 'cannot add inputs/outputs to terminal run'; END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER output_open BEFORE INSERT ON model_output FOR EACH ROW EXECUTE FUNCTION guard_output();
CREATE TRIGGER input_open BEFORE INSERT ON run_input FOR EACH ROW EXECUTE FUNCTION guard_output();
CREATE TRIGGER track_open BEFORE INSERT ON track FOR EACH ROW EXECUTE FUNCTION guard_output();
CREATE TRIGGER detection_open BEFORE INSERT ON detection FOR EACH ROW EXECUTE FUNCTION guard_output();
CREATE TRIGGER association_open BEFORE INSERT ON track_detection FOR EACH ROW EXECUTE FUNCTION guard_output();
CREATE FUNCTION guard_output_edge() RETURNS trigger LANGUAGE plpgsql SET search_path=cattle,public AS $$
DECLARE s text;
BEGIN
 SELECT r.status INTO STRICT s FROM model_output o JOIN inference_run r ON (r.org_id,r.id)=(o.org_id,o.run_id)
   WHERE o.org_id=NEW.org_id AND o.id=NEW.output_id FOR UPDATE OF r;
 IF s NOT IN ('queued','running') THEN RAISE EXCEPTION 'cannot add lineage to terminal output'; END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER edge_open BEFORE INSERT ON output_input FOR EACH ROW EXECUTE FUNCTION guard_output_edge();
CREATE FUNCTION check_detection() RETURNS trigger LANGUAGE plpgsql SET search_path=cattle,public AS $$
BEGIN
 IF NOT EXISTS(SELECT 1 FROM model_output WHERE org_id=NEW.org_id AND id=NEW.output_id AND kind='detection') THEN
   RAISE EXCEPTION 'detection requires detection output';
 END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER detection_kind BEFORE INSERT ON detection FOR EACH ROW EXECUTE FUNCTION check_detection();
CREATE FUNCTION check_measurement() RETURNS trigger LANGUAGE plpgsql SET search_path=cattle,public AS $$
BEGIN
 IF NOT EXISTS(SELECT 1 FROM model_output WHERE org_id=NEW.org_id AND id=NEW.output_id AND kind='measurement') THEN
   RAISE EXCEPTION 'measurement requires measurement output';
 END IF;
 PERFORM 1 FROM inference_run r JOIN model_output o ON (o.org_id,o.run_id)=(r.org_id,r.id)
   WHERE o.org_id=NEW.org_id AND o.id=NEW.output_id AND r.status IN ('queued','running') FOR UPDATE OF r;
 IF NOT FOUND THEN RAISE EXCEPTION 'measurement run already terminal'; END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER measurement_kind BEFORE INSERT ON model_measurement FOR EACH ROW EXECUTE FUNCTION check_measurement();

CREATE FUNCTION check_location() RETURNS trigger LANGUAGE plpgsql SET search_path=cattle,public AS $$
BEGIN
 IF NOT EXISTS(SELECT 1 FROM track t JOIN inference_run r ON (r.org_id,r.id)=(t.org_id,t.run_id)
     WHERE t.org_id=NEW.org_id AND t.id=NEW.track_id AND r.status='succeeded')
 OR NOT EXISTS(SELECT 1 FROM model_output o JOIN inference_run r ON (r.org_id,r.id)=(o.org_id,o.run_id)
     WHERE o.org_id=NEW.org_id AND o.id=NEW.output_id AND r.status='succeeded') THEN
   RAISE EXCEPTION 'resolved location requires completed source and track runs';
 END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER location_published BEFORE INSERT ON location_observation FOR EACH ROW EXECUTE FUNCTION check_location();

CREATE VIEW current_identity WITH (security_invoker=true) AS
 SELECT d.* FROM identity_decision d WHERE NOT EXISTS
 (SELECT 1 FROM identity_decision n WHERE n.org_id=d.org_id AND n.supersedes=d.id);
CREATE VIEW active_location WITH (security_invoker=true) AS
 SELECT l.*, CASE WHEN i.decision='accepted' THEN i.animal_id END AS animal_id,
   i.id AS identity_decision_id, i.score AS identity_score
 FROM location_observation l LEFT JOIN current_identity i ON (i.org_id,i.track_id)=(l.org_id,l.track_id)
 WHERE NOT EXISTS(SELECT 1 FROM location_observation n WHERE n.org_id=l.org_id AND n.supersedes=l.id);
CREATE VIEW latest_animal_location WITH (security_invoker=true) AS
 SELECT DISTINCT ON(org_id,animal_id) l.*, now()-event_at AS observation_age
 FROM active_location l WHERE animal_id IS NOT NULL AND assessment='accepted'
 ORDER BY org_id,animal_id,event_at DESC,id DESC;
CREATE VIEW current_review WITH (security_invoker=true) AS
 SELECT r.* FROM finding_review r WHERE NOT EXISTS
 (SELECT 1 FROM finding_review n WHERE n.org_id=r.org_id AND n.supersedes=r.id);
CREATE VIEW resolved_finding WITH (security_invoker=true) AS
 SELECT f.*, coalesce(f.animal_id,i.animal_id) AS resolved_animal_id,
   coalesce(f.track_id,td.track_id) AS resolved_track_id,
   i.id AS identity_decision_id, r.decision AS review_state, r.id AS review_id
 FROM finding f
 LEFT JOIN track_detection td ON td.org_id=f.org_id AND td.detection_id=f.detection_id
 LEFT JOIN current_identity i ON i.org_id=f.org_id AND i.track_id=coalesce(f.track_id,td.track_id) AND i.decision='accepted'
 LEFT JOIN current_review r ON (r.org_id,r.finding_id)=(f.org_id,f.id);
CREATE VIEW current_alert WITH (security_invoker=true) AS
 SELECT a.*, coalesce(e.state,'open') AS lifecycle_state,
   CASE WHEN f.review_state='rejected' OR f.assessment<>'suspected' THEN 'invalidated'
        WHEN a.basis_identity_decision_id IS NOT NULL
          AND a.basis_identity_decision_id IS DISTINCT FROM f.identity_decision_id THEN 'invalidated'
        ELSE coalesce(e.state,'open') END AS effective_state,
   f.resolved_animal_id, f.severity, f.review_state, f.identity_decision_id
 FROM alert a JOIN resolved_finding f ON (f.org_id,f.id)=(a.org_id,a.finding_id)
 LEFT JOIN alert_event e ON e.org_id=a.org_id AND e.alert_id=a.id
   AND NOT EXISTS(SELECT 1 FROM alert_event n WHERE n.org_id=e.org_id AND n.supersedes=e.id);
CREATE VIEW current_survey WITH (security_invoker=true) AS
 SELECT s.*,
   EXISTS(SELECT 1 FROM survey_input si JOIN track t ON (t.org_id,t.run_id)=(si.org_id,si.run_id)
     JOIN identity_decision d ON (d.org_id,d.track_id)=(t.org_id,t.id)
     WHERE si.org_id=s.org_id AND si.survey_id=s.id AND d.supersedes IS NOT NULL
       AND d.decided_at>=s.recorded_at) AS requires_recompute
 FROM survey s WHERE NOT EXISTS(SELECT 1 FROM survey n WHERE n.org_id=s.org_id AND n.supersedes=s.id);

-- Core edits get database audit; correction tables already record actor+reason.
CREATE FUNCTION audit_core_edit() RETURNS trigger LANGUAGE plpgsql SET search_path=cattle,public AS $$
BEGIN
 INSERT INTO audit_event(org_id,actor,action,detail_schema,detail)
 VALUES(coalesce(NEW.org_id,OLD.org_id),coalesce(nullif(current_setting('app.actor',true),''),session_user),
 TG_TABLE_NAME||':'||TG_OP,'core-edit/1',jsonb_build_object('old',to_jsonb(OLD),'new',to_jsonb(NEW)));
 RETURN coalesce(NEW,OLD);
END $$;
DO $$ DECLARE t text; BEGIN
 FOREACH t IN ARRAY ARRAY['animal_identifier','herd_membership','boundary_version','media_asset','inference_run'] LOOP
  EXECUTE format('CREATE TRIGGER audit_edit AFTER UPDATE OR DELETE ON cattle.%I FOR EACH ROW EXECUTE FUNCTION cattle.audit_core_edit()',t);
 END LOOP;
END $$;

GRANT SELECT ON ALL TABLES IN SCHEMA cattle TO cattle_reader;
GRANT INSERT ON drone,flight,telemetry,clip,media_asset,frame,inference_run,run_input,model_output,
  model_measurement,output_input,detection,track,track_detection,model_version,audit_event TO cattle_worker;
GRANT UPDATE(status,started_at,ended_at) ON inference_run TO cattle_worker;
GRANT UPDATE(state) ON media_asset TO cattle_worker;
GRANT INSERT ON identity_decision,identity_evidence,location_observation,finding,finding_evidence,
  finding_review,survey,survey_input,alert,alert_event,audit_event TO cattle_reviewer;
GRANT INSERT,UPDATE ON ranch,pasture,herd,animal,animal_identifier,herd_membership,boundary_version TO cattle_operator;
GRANT INSERT ON audit_event TO cattle_operator;
GRANT INSERT,UPDATE,DELETE ON membership TO cattle_admin;
GRANT INSERT ON alert_rule_version,audit_event TO cattle_admin;
REVOKE EXECUTE ON ALL FUNCTIONS IN SCHEMA cattle FROM PUBLIC;
GRANT EXECUTE ON FUNCTION tenant_id() TO cattle_reader;
COMMIT;

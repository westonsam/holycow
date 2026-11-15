-- Supabase-specific authorization. Browser writes go through explicit reviewed RPCs.
BEGIN;
SET LOCAL search_path=cattle,extensions,public;
REVOKE ALL ON SCHEMA cattle FROM PUBLIC,anon,authenticated;
REVOKE ALL ON ALL TABLES IN SCHEMA cattle FROM PUBLIC,anon,authenticated;
REVOKE EXECUTE ON ALL FUNCTIONS IN SCHEMA cattle FROM PUBLIC,anon,authenticated;
GRANT USAGE ON SCHEMA cattle,extensions TO authenticated,service_role;
GRANT SELECT ON ALL TABLES IN SCHEMA cattle TO authenticated;

CREATE FUNCTION cattle.has_org_role(target_org uuid,
  allowed_roles text[] DEFAULT ARRAY['owner','admin','operator','reviewer','viewer'])
RETURNS boolean LANGUAGE sql STABLE SECURITY INVOKER SET search_path='' AS $$
 SELECT EXISTS(SELECT 1 FROM cattle.membership m WHERE m.org_id=target_org
   AND m.user_id=(SELECT auth.uid()) AND m.role=ANY(allowed_roles))
$$;
REVOKE ALL ON FUNCTION cattle.has_org_role(uuid,text[]) FROM PUBLIC,anon;
GRANT EXECUTE ON FUNCTION cattle.has_org_role(uuid,text[]) TO authenticated,service_role;

-- Membership reads are self-only: helpers query it without recursive membership policies.
ALTER TABLE membership ENABLE ROW LEVEL SECURITY;
ALTER TABLE membership FORCE ROW LEVEL SECURITY;
CREATE POLICY membership_self ON membership FOR SELECT TO authenticated
 USING(user_id=(SELECT auth.uid()));
DO $$ DECLARE t record; BEGIN
 FOR t IN SELECT tablename FROM pg_tables WHERE schemaname='cattle' AND tablename<>'membership' LOOP
  EXECUTE format('ALTER TABLE cattle.%I ENABLE ROW LEVEL SECURITY',t.tablename);
  EXECUTE format('ALTER TABLE cattle.%I FORCE ROW LEVEL SECURITY',t.tablename);
  EXECUTE format('CREATE POLICY member_read ON cattle.%I FOR SELECT TO authenticated USING (cattle.has_org_role(%I))',
    t.tablename,CASE WHEN t.tablename='organization' THEN 'id' ELSE 'org_id' END);
 END LOOP;
END $$;

-- Trusted processing service only: this Supabase role bypasses RLS. Keep its key server-side.
GRANT SELECT ON ALL TABLES IN SCHEMA cattle TO service_role;
GRANT INSERT ON organization,membership,ranch,pasture,boundary_version,herd,animal,animal_identifier,
 herd_membership,drone,flight,telemetry,clip,media_asset,frame,model_version,inference_run,run_input,
 model_output,output_input,model_measurement,detection,track,track_detection,identity_decision,
 identity_evidence,location_observation,finding,finding_evidence,finding_review,survey,survey_input,
 alert_rule_version,alert,alert_event,audit_event TO service_role;
GRANT UPDATE ON membership,ranch,pasture,boundary_version,herd,animal,animal_identifier,herd_membership,flight TO service_role;
GRANT UPDATE(state) ON media_asset TO service_role;
GRANT UPDATE(status,started_at,ended_at) ON inference_run TO service_role;
-- No evidence deletes; member removal is a server-side administration operation.
GRANT DELETE ON membership TO service_role;

CREATE FUNCTION cattle.review_finding(target_org uuid,target_finding uuid,expected_head uuid,
  review_decision text,review_reason text) RETURNS uuid
LANGUAGE plpgsql SECURITY DEFINER SET search_path='' AS $$
DECLARE new_id uuid; actual_head uuid;
BEGIN
 IF auth.uid() IS NULL OR NOT cattle.has_org_role(target_org,ARRAY['owner','admin','reviewer']) THEN
  RAISE EXCEPTION 'review permission required' USING ERRCODE='42501';
 END IF;
 IF review_decision NOT IN ('accepted','rejected','needs_review') OR review_decision IS NULL
   OR review_reason IS NULL OR length(btrim(review_reason))=0 THEN
  RAISE EXCEPTION 'valid decision and nonempty reason required' USING ERRCODE='22023';
 END IF;
 PERFORM 1 FROM cattle.finding WHERE org_id=target_org AND id=target_finding;
 IF NOT FOUND THEN RAISE EXCEPTION 'finding unavailable' USING ERRCODE='22023'; END IF;
 SELECT id INTO actual_head FROM cattle.current_review WHERE org_id=target_org AND finding_id=target_finding;
 IF actual_head IS DISTINCT FROM expected_head THEN
  RAISE EXCEPTION 'review changed; reload before retrying' USING ERRCODE='40001';
 END IF;
 INSERT INTO cattle.finding_review(org_id,finding_id,supersedes,decision,actor,reason)
 VALUES(target_org,target_finding,expected_head,review_decision,auth.uid()::text,review_reason) RETURNING id INTO new_id;
 INSERT INTO cattle.audit_event(org_id,actor,action,detail_schema,detail)
 VALUES(target_org,auth.uid()::text,'finding_review','supabase-review/1',
   jsonb_build_object('finding_id',target_finding,'old_head',expected_head,'new_head',new_id));
 RETURN new_id;
END $$;

CREATE FUNCTION cattle.correct_track_identity(target_org uuid,target_track uuid,expected_head uuid,
 target_animal uuid,identity_decision text,correction_reason text,supporting_output_ids uuid[])
RETURNS uuid LANGUAGE plpgsql SECURITY DEFINER SET search_path='' AS $$
DECLARE new_id uuid; actual_head uuid; target_flight uuid;
BEGIN
 IF auth.uid() IS NULL OR NOT cattle.has_org_role(target_org,ARRAY['owner','admin','reviewer']) THEN
  RAISE EXCEPTION 'identity review permission required' USING ERRCODE='42501';
 END IF;
 IF identity_decision IS NULL OR identity_decision NOT IN ('accepted','unresolved','rejected')
   OR correction_reason IS NULL OR length(btrim(correction_reason))=0
   OR coalesce(cardinality(supporting_output_ids),0)=0 THEN
  RAISE EXCEPTION 'valid decision, reason and evidence required' USING ERRCODE='22023';
 END IF;
 SELECT flight_id INTO target_flight FROM cattle.track WHERE org_id=target_org AND id=target_track;
 IF target_flight IS NULL THEN RAISE EXCEPTION 'track unavailable' USING ERRCODE='22023'; END IF;
 IF EXISTS(SELECT 1 FROM unnest(supporting_output_ids) x(id)
   LEFT JOIN cattle.model_output o ON o.org_id=target_org AND o.id=x.id
   LEFT JOIN cattle.inference_run r ON r.org_id=o.org_id AND r.id=o.run_id
   WHERE o.id IS NULL OR o.flight_id<>target_flight OR r.status<>'succeeded') THEN
  RAISE EXCEPTION 'evidence must belong to completed runs in the track flight' USING ERRCODE='22023';
 END IF;
 SELECT id INTO actual_head FROM cattle.current_identity WHERE org_id=target_org AND track_id=target_track;
 IF actual_head IS DISTINCT FROM expected_head THEN
  RAISE EXCEPTION 'identity changed; reload before retrying' USING ERRCODE='40001';
 END IF;
 INSERT INTO cattle.identity_decision(org_id,track_id,supersedes,animal_id,decision,method_version,actor,reason)
 VALUES(target_org,target_track,expected_head,target_animal,identity_decision,
   'supabase-human-rfid-review/1',auth.uid()::text,correction_reason) RETURNING id INTO new_id;
 INSERT INTO cattle.identity_evidence(org_id,decision_id,output_id)
 SELECT target_org,new_id,x FROM (SELECT DISTINCT unnest(supporting_output_ids) x) evidence;
 INSERT INTO cattle.audit_event(org_id,actor,action,detail_schema,detail)
 VALUES(target_org,auth.uid()::text,'identity_correction','supabase-identity/1',
   jsonb_build_object('track_id',target_track,'old_head',expected_head,'new_head',new_id,'animal_id',target_animal));
 RETURN new_id;
END $$;
REVOKE ALL ON FUNCTION cattle.review_finding(uuid,uuid,uuid,text,text),
 cattle.correct_track_identity(uuid,uuid,uuid,uuid,text,text,uuid[]) FROM PUBLIC,anon,service_role;
GRANT EXECUTE ON FUNCTION cattle.review_finding(uuid,uuid,uuid,text,text),
 cattle.correct_track_identity(uuid,uuid,uuid,uuid,text,text,uuid[]) TO authenticated;

-- Only verified, ready media under the owning tenant prefix can be downloaded.
CREATE FUNCTION cattle.can_read_evidence(object_name text) RETURNS boolean
LANGUAGE sql STABLE SECURITY INVOKER SET search_path='' AS $$
 SELECT EXISTS(SELECT 1 FROM cattle.media_asset a WHERE a.object_key=object_name AND a.state='ready'
   AND a.org_id::text=split_part(object_name,'/',1) AND cattle.has_org_role(a.org_id))
$$;
REVOKE ALL ON FUNCTION cattle.can_read_evidence(text) FROM PUBLIC,anon;
GRANT EXECUTE ON FUNCTION cattle.can_read_evidence(text) TO authenticated;
INSERT INTO storage.buckets(id,name,public,file_size_limit,allowed_mime_types)
 VALUES('cattle-evidence','cattle-evidence',false,52428800,ARRAY['image/jpeg','image/png','image/webp','video/mp4']);
CREATE POLICY cattle_evidence_read ON storage.objects FOR SELECT TO authenticated
 USING(bucket_id='cattle-evidence' AND cattle.can_read_evidence(name));
-- Restrictive policies defend this bucket even if another bucket has broad permissive policies.
CREATE POLICY cattle_evidence_read_guard ON storage.objects AS RESTRICTIVE FOR SELECT TO authenticated
 USING(bucket_id<>'cattle-evidence' OR cattle.can_read_evidence(name));
CREATE POLICY cattle_evidence_anon_guard ON storage.objects AS RESTRICTIVE FOR ALL TO anon
 USING(bucket_id<>'cattle-evidence') WITH CHECK(bucket_id<>'cattle-evidence');
CREATE POLICY cattle_evidence_insert_guard ON storage.objects AS RESTRICTIVE FOR INSERT TO authenticated
 WITH CHECK(bucket_id<>'cattle-evidence');
CREATE POLICY cattle_evidence_update_guard ON storage.objects AS RESTRICTIVE FOR UPDATE TO authenticated
 USING(bucket_id<>'cattle-evidence') WITH CHECK(bucket_id<>'cattle-evidence');
CREATE POLICY cattle_evidence_delete_guard ON storage.objects AS RESTRICTIVE FOR DELETE TO authenticated
 USING(bucket_id<>'cattle-evidence');
-- Future objects must opt in to grants rather than inheriting API access.
ALTER DEFAULT PRIVILEGES IN SCHEMA cattle REVOKE ALL ON TABLES FROM PUBLIC,anon,authenticated;
ALTER DEFAULT PRIVILEGES IN SCHEMA cattle REVOKE EXECUTE ON FUNCTIONS FROM PUBLIC,anon,authenticated;
COMMIT;

-- psql -v ON_ERROR_STOP=1 -f website.sql defines parameterized statements.
-- EVERY execution: BEGIN; SET LOCAL ROLE cattle_reader; SELECT set_config('app.org_id',verified_org,true);
-- Bind values with driver parameters; COMMIT/ROLLBACK always before returning pool connection.
SET search_path=cattle,public;

-- 1. Current herd roster, known locations, age and current membership semantics.
PREPARE herd_locations(uuid,uuid,timestamptz,interval) AS
SELECT a.id,a.display_name,l.position,l.event_at,$3-l.event_at AS age,
 CASE WHEN l.id IS NULL THEN 'unobserved' WHEN $3-l.event_at>$4 THEN 'stale' ELSE 'last_observed' END AS visibility,
 l.uncertainty_m,l.identity_score,l.identity_decision_id,l.output_id,l.track_id
FROM herd_membership m JOIN animal a ON (a.org_id,a.id)=(m.org_id,m.animal_id)
LEFT JOIN latest_animal_location l ON (l.org_id,l.animal_id)=(a.org_id,a.id)
WHERE m.org_id=$1 AND m.herd_id=$2 AND m.valid_during @> $3 ORDER BY a.id;
-- Anonymous objects cannot truthfully be assigned to a herd without additional evidence.
PREPARE unresolved_locations(uuid,uuid) AS
SELECT DISTINCT ON(l.track_id) l.*,now()-l.event_at AS age
FROM active_location l WHERE l.org_id=$1 AND l.flight_id=$2 AND l.animal_id IS NULL
ORDER BY l.track_id,l.event_at DESC,l.id DESC;

-- 2. Trail: latest identity interpretation, active location revision, including assessment gaps.
PREPARE animal_trail(uuid,uuid,timestamptz,timestamptz) AS
SELECT l.*,l.event_at-lag(l.event_at) OVER(ORDER BY l.event_at,l.id) AS observation_gap
FROM active_location l WHERE l.org_id=$1 AND l.animal_id=$2 AND l.event_at >= $3 AND l.event_at < $4
ORDER BY l.event_at,l.id;

-- 3. Open alerts: severity, review and lifecycle are independent; no automatic diagnosis.
PREPARE open_alerts(uuid,timestamptz,uuid,integer) AS
SELECT * FROM current_alert WHERE org_id=$1 AND effective_state IN ('open','acknowledged')
 AND (opened_at,id)<($2,$3) ORDER BY opened_at DESC,id DESC LIMIT $4;
PREPARE alert_evidence(uuid,uuid) AS
SELECT a.id AS alert_id,f.*,o.id AS output_id,o.kind,o.payload,o.score,r.id AS run_id,
 r.config,r.processing_version,m.model_name,m.version,m.artifact_sha256,m.score_meaning,m.calibration_version,
 fr.id AS frame_id,fr.captured_at,fr.offset_ms,ma.object_key,ma.state AS media_state,
 ma.width_px,ma.height_px,i.output_id AS identity_evidence_output_id
FROM current_alert a JOIN resolved_finding f ON (f.org_id,f.id)=(a.org_id,a.finding_id)
JOIN finding_evidence e ON (e.org_id,e.finding_id)=(f.org_id,f.id)
JOIN model_output o ON (o.org_id,o.id)=(e.org_id,e.output_id)
JOIN inference_run r ON (r.org_id,r.id)=(o.org_id,o.run_id)
JOIN model_version m ON (m.org_id,m.id)=(r.org_id,r.model_version_id)
JOIN frame fr ON (fr.org_id,fr.id)=(o.org_id,o.frame_id)
JOIN media_asset ma ON (ma.org_id,ma.id)=(fr.org_id,fr.asset_id)
LEFT JOIN identity_evidence i ON i.org_id=f.org_id AND i.decision_id=f.identity_decision_id
WHERE a.org_id=$1 AND a.id=$2 ORDER BY o.id,i.output_id;

-- 4a. Radius uses geography meters, never degrees. Positive radius checked by API.
PREPARE nearby_locations(uuid,double precision,double precision,double precision,timestamptz,timestamptz) AS
SELECT * FROM active_location WHERE org_id=$1 AND assessment='accepted'
 AND event_at >= $5 AND event_at < $6
 AND ST_DWithin(position,ST_SetSRID(ST_Point($2,$3),4326)::geography,$4)
ORDER BY event_at,id;
-- 4b. Boundaries effective at observation time; uncertainty touching boundary => indeterminate.
PREPARE pasture_observations(uuid,uuid,timestamptz,timestamptz) AS
SELECT l.*,b.id AS boundary_version_id,
 CASE WHEN l.assessment<>'accepted' OR l.position IS NULL OR l.uncertainty_m IS NULL THEN 'indeterminate'
 WHEN ST_DWithin(l.position,ST_Boundary(b.geom)::geography,l.uncertainty_m) THEN 'indeterminate'
 WHEN ST_Covers(b.geom,l.position::geometry) THEN 'inside' ELSE 'outside' END AS classification
FROM active_location l JOIN boundary_version b ON b.org_id=l.org_id AND b.pasture_id=$2 AND b.valid_during @> l.event_at
WHERE l.org_id=$1 AND l.event_at >= $3 AND l.event_at < $4 ORDER BY l.event_at,l.id;

-- 5. Independent subqueries avoid multiplication of detections by findings/runs.
PREPARE flight_summary(uuid,uuid) AS
SELECT f.id,f.started_at,f.ended_at,f.coverage,f.coverage_method,
 (SELECT jsonb_agg(jsonb_build_object('id',r.id,'status',r.status,'model_version_id',r.model_version_id))
   FROM inference_run r WHERE r.org_id=f.org_id AND r.flight_id=f.id) AS processing,
 (SELECT jsonb_agg(to_jsonb(s)) FROM current_survey s WHERE s.org_id=f.org_id AND s.flight_id=f.id) AS herd_estimates,
 (SELECT count(*) FROM track t JOIN inference_run r ON (r.org_id,r.id)=(t.org_id,t.run_id)
   LEFT JOIN current_identity i ON (i.org_id,i.track_id)=(t.org_id,t.id)
   WHERE t.org_id=f.org_id AND t.flight_id=f.id AND r.status='succeeded' AND i.decision IS DISTINCT FROM 'accepted') AS unresolved_tracks,
 (SELECT count(DISTINCT x.id) FROM finding x JOIN finding_evidence e ON (e.org_id,e.finding_id)=(x.org_id,x.id)
   JOIN model_output o ON (o.org_id,o.id)=(e.org_id,e.output_id) WHERE o.org_id=f.org_id AND o.flight_id=f.id) AS findings
FROM flight f WHERE f.org_id=$1 AND f.id=$2;

-- 6. Historical membership + observations known by knowledge cutoff $4.
-- Decisions corrected after $4 do not alter this historical reconstruction.
PREPARE herd_as_of(uuid,uuid,timestamptz,timestamptz) AS
WITH identity_at AS (
 SELECT d.* FROM identity_decision d WHERE d.org_id=$1 AND d.decided_at<=$4
 AND NOT EXISTS(SELECT 1 FROM identity_decision n WHERE n.org_id=d.org_id AND n.supersedes=d.id AND n.decided_at<=$4)
), locations_at AS (
 SELECT l.*,i.animal_id FROM location_observation l JOIN identity_at i ON (i.org_id,i.track_id)=(l.org_id,l.track_id)
 WHERE l.org_id=$1 AND i.decision='accepted' AND l.assessment='accepted' AND l.event_at<=$3 AND l.recorded_at<=$4
 AND NOT EXISTS(SELECT 1 FROM location_observation n WHERE n.org_id=l.org_id AND n.supersedes=l.id AND n.recorded_at<=$4)
)
SELECT m.animal_id,l.id AS location_id,l.position,l.event_at,l.output_id
FROM herd_membership m LEFT JOIN LATERAL
 (SELECT * FROM locations_at x WHERE x.org_id=m.org_id AND x.animal_id=m.animal_id ORDER BY event_at DESC,id DESC LIMIT 1) l ON true
WHERE m.org_id=$1 AND m.herd_id=$2 AND m.valid_during @> $3 ORDER BY m.animal_id;

-- 7. Deliberate diagnostic comparison, not input to current maps/counts.
PREPARE compare_models(uuid,uuid,uuid) AS
SELECT o.frame_id,o.source_key,o.run_id,m.model_name,m.version,o.kind,o.score,o.payload,
 v.metric_code,v.value,v.unit,v.scale_version
FROM model_output o JOIN inference_run r ON (r.org_id,r.id)=(o.org_id,o.run_id)
JOIN model_version m ON (m.org_id,m.id)=(r.org_id,r.model_version_id)
LEFT JOIN model_measurement v ON (v.org_id,v.output_id)=(o.org_id,o.id)
WHERE o.org_id=$1 AND o.run_id IN ($2,$3) AND r.status='succeeded'
 AND EXISTS(SELECT 1 FROM run_input a JOIN run_input b ON a.org_id=b.org_id AND a.frame_id=b.frame_id
   WHERE a.org_id=$1 AND a.run_id=$2 AND b.run_id=$3 AND a.frame_id=o.frame_id)
ORDER BY o.frame_id,o.source_key,o.run_id;

-- 8. Reviewer-only. Compare-and-swap via the unique supersedes FK. Bind CURRENT head as $3.
-- In one transaction: capture affected views, append correction+evidence, append audit/alert events,
-- reread locations/findings/surveys and return their differences. Retry whole txn on SQLSTATE 23505.
PREPARE correct_identity(uuid,uuid,uuid,uuid,text,text) AS
INSERT INTO identity_decision(org_id,track_id,supersedes,animal_id,decision,method_version,actor,reason)
SELECT $1,$2,$3,$4,'accepted','human-rfid-reconcile/1',$5,$6
FROM current_identity WHERE org_id=$1 AND track_id=$2 AND id=$3 RETURNING *;
PREPARE correction_impact(uuid,uuid) AS
SELECT 'location' AS kind,l.id,l.animal_id AS resolved_animal_id FROM active_location l WHERE l.org_id=$1 AND l.track_id=$2
UNION ALL SELECT 'finding',f.id,f.resolved_animal_id FROM resolved_finding f WHERE f.org_id=$1 AND f.resolved_track_id=$2
UNION ALL SELECT 'alert',a.id,a.resolved_animal_id FROM current_alert a JOIN resolved_finding f
 ON (f.org_id,f.id)=(a.org_id,a.finding_id) WHERE a.org_id=$1 AND f.resolved_track_id=$2
UNION ALL SELECT 'survey_recompute',s.id,NULL::uuid FROM current_survey s
WHERE s.org_id=$1 AND s.requires_recompute AND EXISTS(SELECT 1 FROM survey_input si JOIN track t
 ON (t.org_id,t.run_id)=(si.org_id,si.run_id) WHERE si.org_id=s.org_id AND si.survey_id=s.id AND t.id=$2);

# Design, assumptions and tradeoffs

Provider follow-up: the user selected Supabase and explicitly chose frontend → backend/control layer → database isolation. See [the active Supabase setup](../supabase/README.md) for deployed role/policy differences. The standalone role scheme below is retained as the original proposal, not the hosted migration recipe.

## Confirmed and unresolved facts

Confirmed by the brief: website, drone source evidence, multiple AI vision models, observation history. Confirmed by the user's follow-up: RFID ear tags; cow ID based parsing; 10–15 second clips stored as images at 30 fps; ground coordinates; model versioning; gait/locomotion (lameness) and estrus/heat behavior scores, with other metrics expected. Sample model payloads are being developed. Heat here means reproductive behavior, **not temperature**.

Decisions made provisionally:

| Decision | Assumption and consequence |
|---|---|
| Both individuals and unresolved tracks | RFID supports identifiers, but tag-to-image association still needs evidence. Parsed cow IDs remain claims until resolved. No animal is created for every frame. |
| PostgreSQL/PostGIS | No existing DB/provider/ORM to preserve. Confirm extension support before choosing hosting. Raw SQL handles spatial types, temporal exclusions, triggers, grants and RLS. |
| One tenant per organization | Composite PK/FKs prevent cross-tenant links. One shared database is sufficient initially. |
| One herd at an instant | Half-open membership intervals cannot overlap for the same animal. An animal can have no herd. Ranch is a herd's administrative home; it is not proof of animal presence. |
| Image sequence first | Each clip groups 300–450 image objects; each image has a frame at offset zero. Optional video support is compatible but original video retention is not assumed. |
| Optional animal ground position | Store supplied WGS84 coordinates and their method/uncertainty; unknown accuracy remains NULL. Drone GPS/altitude remain separate telemetry. |
| Immutable outputs, explicit policy selection | Reruns coexist. Current state reads resolved observations, never every model row. Score fusion needs an explicit versioned policy. |
| Versioned score scale | `model_measurement` keeps raw gait/estrus/other values with unit, scale version and optional bounds. `model_output.score` is a separate 0–1 model confidence, not the metric value. Non-normalized confidence goes in payload until an adapter defines its semantics. |
| Backend-only DB access | Trusted backend verifies identity/tenant membership and chooses DB role. Browser/mobile/drone clients do not receive database credentials. No password store is added. |
| Batch processing | Queued/running/succeeded/failed runs; terminal attempts are immutable. Real-time streaming is deferred. |

Material unanswered questions:

1. How is RFID associated with a clip: synchronized reader, collar/reader telemetry, manual mapping, or a parser filename? What time alignment and reader ambiguity are possible? RFID is not automatically readable from RGB imagery.
2. Provide gait and estrus score scales, direction, units, taxonomy, confidence/calibration meaning, clip/window scope, and sample payloads. Are ground coordinates per cow per frame, per clip, or another cadence? What CRS and uncertainty definition apply?
3. How many cow clips per flight, flights/day, image resolution/compression, analyzed frames/second, model passes, organizations, and retention days? Is full 30 fps inference required or only storage? Is original video kept?
4. Which auth/provider/storage service, member onboarding, and review permissions will be used? What review thresholds and alert actions should operators approve?

The schema can be reviewed without those answers. Do not enable score thresholds, geofences, or not-seen alarms as validated product behavior before confirming their policies.

## Evidence to application state

`flight → clip → media_asset → frame → run_input → model_output` records capture and processing provenance. `model_version` contains immutable model name/version, artifact digest, taxonomy, score meaning and optional calibration reference. The run stores versioned config and processing version; its input list is explicit. `output_input` records cross-model/derived-output lineage. An adapter rejects cycles and requires declared inputs to predate dependent outputs; the MVP database prevents self-links but does not recursively enforce acyclicity.

`detection` indexes normalized boxes and class labels. Coordinates are `(x_min,y_min,x_max,y_max)`, top-left origin, normalized to [0,1], half-open box convention. Image dimensions are on the asset. Masks live in private storage. `track.local_key` is scoped to a producing run; association constraints prevent mixing runs or putting one detection in two tracks in that run.

`model_measurement` extracts fields used for score filtering/comparison; arbitrary additional details remain schema-versioned JSONB. Metric codes start with `gait_locomotion` and `estrus_behavior` as proposed names. Adding another numeric metric needs an adapter/schema definition, not an arbitrary core EAV table or new animal column. Non-numeric observations use typed finding payloads. Scale values in examples are explicitly synthetic, not clinical standards.

`identity_decision` is an append-only chain for each track. Accepted decisions require an animal; unresolved/rejected decisions may retain an animal candidate for traceability. `identity_evidence` links outputs, including RFID association claims. Original RFID reader facts/clock alignment may live in versioned capture/output payloads initially; a dedicated reader-event integration is deferred pending hardware details. External RFID values use a tenant-scoped namespace and effective interval, allowing documented later reuse. A permanent UUID survives tag changes.

`location_observation` is an immutable resolved interpretation, not a raw geolocation prediction. A track and event time have one root revision; corrections supersede that revision. A correction of timestamp or subject requires rejecting the old event and adding the corrected event, rather than mutating event identity. Position may be unknown. `accepted` requires a point; `not_assessable` has no point. NULL uncertainty means unknown, never zero meters.

`finding` records a triage interpretation under a policy/version, with exactly one FK-backed subject: detection, track, animal or herd. `finding_evidence` can link conflicting models or multiple outputs used in fusion. Label/severity/assessment remain fixed. `finding_review` appends reviewer decisions/reasons; to replace a misclassified finding, reject it and create a new finding with an audit link. Reviews are not veterinarian diagnoses. Confirmed clinical events and treatments are deferred.

Track- or detection-scoped findings follow current identity. Animal-scoped findings intentionally remain attached to that animal; correction requires an explicit rejection/replacement. Reviewer attribution is an external auth subject or versioned algorithm identity, not an FK to a membership that might later be removed. Backend authorization and logs must validate that attribution; a string field is not an authentication mechanism.

`survey` stores a documented deduplicated count estimate and bounds, coverage and source run list. A count may be unknown. A survey must not count each detection, each model pass, or each clip as a different cow. Use accepted IDs first, cross-clip track overlap/re-identification only under a documented policy, and unresolved-track uncertainty bounds. A simple track dedupe is only an example. Survey totals with unknown herd attribution cannot be assigned to a named herd as fact.

`alert_rule_version` freezes policy; `alert` has a scoped dedupe key and a finding; `alert_event` records open/acknowledged/resolved/invalidated history independently of severity/review. For an identity-dependent rule, bind `basis_identity_decision_id` to the decision used during evaluation; changed identity invalidates the effective alert rather than silently transferring that conclusion. Rejected or non-suspected findings are also excluded by `current_alert.effective_state`. Delivery attempts, notifications, automatic geofence and not-seen evaluation are deferred; no email/SMS service is added.

## Current state, corrections and time

All instants use `timestamptz`; clients exchange UTC timestamps. Event/capture time is distinct from ingest, processing and decision times. Rational frame offsets are represented through image index and clip fps; a 30 fps image timestamp need not be rounded to integer milliseconds. Frame video offsets are integer milliseconds if videos are used. Clock quality and synchronization details must be supplied, not invented. Ingest validates impossible future timestamps against the declared clock tolerance and flags uncertain clocks for review.

`current_identity`, `active_location`, `current_review`, `resolved_finding`, `current_alert`, and `current_survey` are ordinary invoker-security views, requiring no cache refresh. The latest accepted animal location sorts by **event time descending, UUID descending**. UUID is a deterministic tie-breaker, not a quality ranking. A late upload cannot replace a more recent position. A latest not-assessable attempt does not erase a prior last-known accepted position; APIs should expose the latest attempt separately alongside its age. No prior accepted observation means unobserved, not healthy or absent.

Changing identity reassigns the full temporary track and its locations/track findings immediately in those views. Correcting animal A to B can remove A's current position and expose A's next-oldest valid position, and can change B's latest point. `correction_impact` lists affected records; the API captures before/after results in one transaction. `current_survey.requires_recompute` conservatively flags any post-survey identity correction among its source runs; suppress such estimates from authoritative dashboard totals until a replacement survey supersedes them. It is a safety flag, not an automated recount. Location changes or membership amendments must also queue recomputation through the trusted correction service/audit workflow.

Automatic source corrections use database-generated decision timestamps. Only a migration/import administrator may backdate history. Same-chain unique successor/root constraints serialize competing edits; a loser gets a uniqueness error or a zero-row compare-and-swap result and must reload/review the new head. The application must not silently retry with a different identity decision.

Track merge/split is deferred as a dedicated feature. MVP correction procedure: create a distinct versioned tracking run with replacement tracks, resolve them, append rejected revisions to obsolete locations, reject obsolete findings and invalidate their alerts, and supersede surveys in one resolver transaction. An audit event lists old/new IDs and merge/split method. Original outputs/tracks remain. Do not claim a track has been physically merged by updating its key.

Historical queries distinguish effective time from knowledge time. `herd_as_of` uses effective membership at `$3` and identity/location interpretations known by `$4`. Membership and boundary amendments are audited but not fully bitemporal: that query uses currently corrected effective membership history. Exact reconstruction of the roster/boundary *as originally known* requires replaying audit events or a future append-only membership/boundary revision design. Current membership and historical membership are not interchangeable.

## Spatial behavior and UI contract

WGS84 interchange is **longitude, latitude**. Point positions use `geography(Point,4326)`; polygons use `geometry(MultiPolygon,4326)` with GiST indexes. Use geography casts for product distances in meters. Boundary versions use nonoverlapping half-open effective ranges; on a version change the new boundary applies at its lower bound. No active boundary means no classification.

For small ranch polygons away from the antimeridian/poles, `ST_Covers` determines nominal containment, but any uncertainty radius touching a boundary is indeterminate. Unknown position or uncertainty is also indeterminate. `pasture_observations` intentionally returns inside/outside/indeterminate; filter for nominal containment or robust `inside` as the UI needs. A location accuracy value must have a documented conservative radius interpretation before using this policy; a one-sigma error is not automatically such a radius. Large/antimeridian geographies need an appropriate regional geometry policy and dedicated tests.

“Not seen” requires a covered survey window, elapsed-time threshold, identity capability and a documented detection-recall policy. Missing uploads, partial coverage and anonymous tracks cannot prove absence. No not-seen rule is enabled in this MVP.

The mockup's red/yellow/green categories are triage display rules to configure, not health diagnoses. Blue/unable-to-assess and unobserved must remain distinct. Counts come from compatible survey estimates or roster counts with clear labels. “Cows accounted for” requires a deduplication policy and denominator; do not derive it from detection row count. Battery is the latest timestamped telemetry, and is stale when no new telemetry arrives. A polygon outline is not proof of flight coverage. “Last observed” and observation age must accompany locations; no live-tracking claim.

## Query and indexing choices

[website.sql](queries/website.sql) includes prepared statements for all eight requested questions plus evidence, uncertainty and impact drilldowns. Bind tenant UUID even with RLS. Select role/context inside the transaction before execution. Restrict time windows and result limits in the API. The alert query uses descending `(opened_at,id)` keyset pagination; first cursor is infinity/max UUID. Trails and nearby queries are bounded intervals; paginate with `(event_at,id) > (last_time,last_id)` if large. Herd rosters can page by animal UUID. Comparisons use common frame inputs and keep model scores separate.

B-tree indexes support tenant/track/time, flight/time, output/frame, finding/time and run status. GiST supports point radius and boundary searches, plus effective-time exclusion constraints. Add child FK indexes when measured delete/maintenance or query plans justify them; all referenced composite keys are indexed. No blanket JSONB indexes, vector DB, time-series extension, materialized current projection or partitioning is introduced. Measure representative `EXPLAIN (ANALYZE,BUFFERS)` plans and ingest rates on staging before promising latency.

## Capacity examples (not confirmed project scale)

Stored image cadence is confirmed at 30 fps; inference cadence is not. Use:

`detections/day = flights/day × analyzed minutes/flight × 60 × analyzed fps × avg detections/frame × detection-producing passes`.

For cow clips, analyzed minutes/flight below means **sum of selected clip durations**, not necessarily flight wall time; overlapping/repeated clips must not be interpreted as unique cows. Other models that annotate a detector's outputs do not multiply detector rows.

| Assumed quantity | Small example | Larger example |
|---|---:|---:|
| Flights/day; clips/flight; clip length | 2; 50; 12s | 10; 200; 12s |
| Flight wall duration; summed clip minutes/flight | 15 min; 10 min | 30 min; 40 min |
| Stored images/day at 30 fps | 36,000 | 720,000 |
| Media/day at **assumed 250 kB/image** | 9 GB | 180 GB |
| Analyzed fps; cattle/frame; detector passes | 2; 1; 1 | 5; 1; 2 |
| Detection rows/day | 2,400 | 240,000 |
| Two measurement models, one output/analyzed frame each | 4,800/day | 240,000/day |
| Raw prediction rows/day (detections + measurements) | 7,200 | 480,000 |
| Telemetry at assumed 1 Hz across flight wall time | 1,800/day | 18,000/day |
| 30-day image objects; media bytes | 1.08 million; 270 GB | 21.6 million; 5.4 TB |
| 90-day raw prediction rows | 648,000 | 43.2 million |

Decimal GB/TB, excludes replicas/backups, masks, thumbnails, object request costs and original video. Assume roughly 1–3 kB per indexed prediction row for initial planning only: 0.65–1.94 GB versus 43–130 GB across 90 days, plus detection/measurement rows, frame/assets/clip metadata, location histories, indexes, bloat and WAL. At assumed 0.5–1.5 kB per indexed asset+frame pair, 30-day image metadata adds ~0.54–1.62 GB versus 10.8–32.4 GB. Measure actual row/index sizes and JPEG sizes; storage-object count and request charges may dominate before prediction rows do.

Start unpartitioned. Larger workloads justify benchmarking time partitioning on output/event tables or tiered metadata retention. PostgreSQL partition keys affect uniqueness and referenceable keys: a time-partitioned output table generally needs the partition key in unique/FK contracts, changing retry keys and downstream FKs. Do not retrofit partition drops into this FK-rich history without redesigning retention boundaries. A separate warehouse is deferred.

## MVP and later scope

MVP: organizations/memberships; ranch/herd/pasture versions; cattle/RFID history; cow clips/image frames; versioned model runs/outputs and numeric metrics; anonymous tracks; reviewed identity/location/finding interpretations; survey estimates; in-app alerts/reviews; audit and tenant isolation.

Later, once requirements justify them: reader/sensor registries and synchronized RFID event ingestion, automated cross-run tracking and merge/split UI, clinical events/treatments, notification delivery, rule execution workers, ingestion queue leasing/outbox, exact bitemporal membership history, retention workflow automation, partitioning, calibrated fusion and projections. The current schema supports design review and an ingestion adapter; it does not claim those services are implemented.

Technical mechanics checked against [PostgreSQL constraints](https://www.postgresql.org/docs/current/ddl-constraints.html), [row security](https://www.postgresql.org/docs/current/ddl-rowsecurity.html), and [PostGIS ST_DWithin](https://postgis.net/docs/ST_DWithin.html). Composite constraints, invoker views and geography meters inform the implementation; the cattle domain policy is this proposal, not a vendor recommendation.

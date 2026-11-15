# Data dictionary

Generated from `migrations/001_core.sql`; regenerate with `tools/check_artifacts.py --write-dictionary`.

All rows are owned by `org_id`, directly or through tenant-composite parents. Organization itself is the tenant root. All FK deletion behavior is NO ACTION; no domain cascades. UUID IDs default to `gen_random_uuid()`. NULL means unknown/not applicable, never an implicit zero. Every real instant is timezone-aware.

SQL declarations below include type, NULL/default rules and column constraints. Table constraints follow each table. Composite primary-key columns are NOT NULL even where the column declaration omits that keyword. Provenance/link fields reference the owning tenant. Publication/immutability/access rules are in migration 002 and OPERATIONS.md.

## organization

Tenant root; provisioned by a controlled onboarding administrator.

| Field / SQL declaration | Meaning, units and provenance |
|---|---|
| `id uuid PRIMARY KEY DEFAULT gen_random_uuid()` | Stable internal UUID; database-generated unless a durable source mapping supplies it. |
| `name text NOT NULL` | Human-readable editable name; not an identity or uniqueness guarantee. |
| `created_at timestamptz NOT NULL DEFAULT now()` | Creation instant (timestamptz, UTC interchange). |

## membership

External authenticated principal membership and product role. No passwords.

| Field / SQL declaration | Meaning, units and provenance |
|---|---|
| `org_id uuid NOT NULL REFERENCES organization (id)` | Owning organization UUID; part of every tenant-scoped key/FK and RLS context. |
| `issuer text NOT NULL` | Verified external authentication issuer; used with subject. |
| `subject text NOT NULL` | External authentication subject; unique only within issuer. |
| `role text NOT NULL CHECK (role IN ('owner', 'admin', 'operator', 'reviewer', 'viewer'))` | Product authorization role, mapped by trusted backend to deployment role groups. |

Table constraints:

- `PRIMARY KEY (org_id, issuer, subject)`

## ranch

Administrative ranch/site, not a location observation.

| Field / SQL declaration | Meaning, units and provenance |
|---|---|
| `org_id uuid NOT NULL REFERENCES organization (id)` | Owning organization UUID; part of every tenant-scoped key/FK and RLS context. |
| `id uuid NOT NULL DEFAULT gen_random_uuid()` | Stable internal UUID; database-generated unless a durable source mapping supplies it. |
| `name text NOT NULL` | Human-readable editable name; not an identity or uniqueness guarantee. |

Table constraints:

- `PRIMARY KEY (org_id, id)`

## pasture

Stable pasture identity; geometry is effective-dated separately.

| Field / SQL declaration | Meaning, units and provenance |
|---|---|
| `org_id uuid NOT NULL` | Owning organization UUID; part of every tenant-scoped key/FK and RLS context. |
| `id uuid NOT NULL DEFAULT gen_random_uuid()` | Stable internal UUID; database-generated unless a durable source mapping supplies it. |
| `ranch_id uuid NOT NULL` | Tenant-scoped administrative ranch reference. |
| `name text NOT NULL` | Human-readable editable name; not an identity or uniqueness guarantee. |

Table constraints:

- `PRIMARY KEY (org_id, id)`
- `FOREIGN KEY (org_id, ranch_id) REFERENCES ranch (org_id, id)`

## boundary_version

Nonoverlapping effective pasture boundaries and versioned geofence policy.

| Field / SQL declaration | Meaning, units and provenance |
|---|---|
| `org_id uuid NOT NULL` | Owning organization UUID; part of every tenant-scoped key/FK and RLS context. |
| `id uuid NOT NULL DEFAULT gen_random_uuid()` | Stable internal UUID; database-generated unless a durable source mapping supplies it. |
| `pasture_id uuid NOT NULL` | Stable pasture reference. |
| `valid_during tstzrange NOT NULL` | Effective UTC half-open [start,end) interval; nonempty, bounded start. |
| `geom geometry(multipolygon, 4326) NOT NULL` | Valid nonempty EPSG:4326 MultiPolygon pasture boundary; lon/lat degrees. |
| `policy_version text NOT NULL` | Versioned interpretation/fusion/geofence policy identifier. |
| `recorded_at timestamptz NOT NULL DEFAULT now()` | Interpretation recording instant (timestamptz, UTC interchange). |

Table constraints:

- `PRIMARY KEY (org_id, id)`
- `FOREIGN KEY (org_id, pasture_id) REFERENCES pasture (org_id, id)`
- `CHECK (NOT isempty(valid_during) AND lower(valid_during) IS NOT NULL AND lower_inc(valid_during) AND NOT upper_inc(valid_during))`
- `CHECK (st_isvalid(geom) AND NOT st_isempty(geom))`
- `EXCLUDE USING gist (org_id WITH OPERATOR(=), pasture_id WITH OPERATOR(=), valid_during WITH OPERATOR(&&))`

## herd

Stable managed herd with an administrative ranch.

| Field / SQL declaration | Meaning, units and provenance |
|---|---|
| `org_id uuid NOT NULL` | Owning organization UUID; part of every tenant-scoped key/FK and RLS context. |
| `id uuid NOT NULL DEFAULT gen_random_uuid()` | Stable internal UUID; database-generated unless a durable source mapping supplies it. |
| `ranch_id uuid NOT NULL` | Tenant-scoped administrative ranch reference. |
| `name text NOT NULL` | Human-readable editable name; not an identity or uniqueness guarantee. |

Table constraints:

- `PRIMARY KEY (org_id, id)`
- `FOREIGN KEY (org_id, ranch_id) REFERENCES ranch (org_id, id)`

## animal

Permanent cattle identity, independent of external tag changes.

| Field / SQL declaration | Meaning, units and provenance |
|---|---|
| `org_id uuid NOT NULL REFERENCES organization (id)` | Owning organization UUID; part of every tenant-scoped key/FK and RLS context. |
| `id uuid NOT NULL DEFAULT gen_random_uuid()` | Stable internal UUID; database-generated unless a durable source mapping supplies it. |
| `display_name text` | Optional editable cattle label, distinct from permanent identity/tag namespace. |
| `retired_at timestamptz` | Optional animal retirement instant; evidence is preserved (timestamptz, UTC interchange). |

Table constraints:

- `PRIMARY KEY (org_id, id)`

## animal_identifier

Namespaced RFID/other external identifier; temporal reuse allowed.

| Field / SQL declaration | Meaning, units and provenance |
|---|---|
| `org_id uuid NOT NULL` | Owning organization UUID; part of every tenant-scoped key/FK and RLS context. |
| `id uuid NOT NULL DEFAULT gen_random_uuid()` | Stable internal UUID; database-generated unless a durable source mapping supplies it. |
| `animal_id uuid NOT NULL` | Permanent cattle reference; identity acceptance requires a value. |
| `namespace text NOT NULL` | External identifier scope, e.g. rfid:ranch-reader-domain. |
| `value text NOT NULL` | External identifier text or numeric model metric; see owning table/unit/scale. |
| `valid_during tstzrange NOT NULL` | Effective UTC half-open [start,end) interval; nonempty, bounded start. |

Table constraints:

- `PRIMARY KEY (org_id, id)`
- `FOREIGN KEY (org_id, animal_id) REFERENCES animal (org_id, id)`
- `CHECK (NOT isempty(valid_during) AND lower(valid_during) IS NOT NULL AND lower_inc(valid_during) AND NOT upper_inc(valid_during))`
- `EXCLUDE USING gist (org_id WITH OPERATOR(=), namespace WITH OPERATOR(=), value WITH OPERATOR(=), valid_during WITH OPERATOR(&&))`

## herd_membership

One herd per animal at an instant, enforced by temporal exclusion.

| Field / SQL declaration | Meaning, units and provenance |
|---|---|
| `org_id uuid NOT NULL` | Owning organization UUID; part of every tenant-scoped key/FK and RLS context. |
| `id uuid NOT NULL DEFAULT gen_random_uuid()` | Stable internal UUID; database-generated unless a durable source mapping supplies it. |
| `animal_id uuid NOT NULL` | Permanent cattle reference; identity acceptance requires a value. |
| `herd_id uuid NOT NULL` | Tenant-scoped herd subject/assignment reference. |
| `valid_during tstzrange NOT NULL` | Effective UTC half-open [start,end) interval; nonempty, bounded start. |

Table constraints:

- `PRIMARY KEY (org_id, id)`
- `FOREIGN KEY (org_id, animal_id) REFERENCES animal (org_id, id)`
- `FOREIGN KEY (org_id, herd_id) REFERENCES herd (org_id, id)`
- `CHECK (NOT isempty(valid_during) AND lower(valid_during) IS NOT NULL AND lower_inc(valid_during) AND NOT upper_inc(valid_during))`
- `EXCLUDE USING gist (org_id WITH OPERATOR(=), animal_id WITH OPERATOR(=), valid_during WITH OPERATOR(&&))`

## drone

Tenant source device identity.

| Field / SQL declaration | Meaning, units and provenance |
|---|---|
| `org_id uuid NOT NULL REFERENCES organization (id)` | Owning organization UUID; part of every tenant-scoped key/FK and RLS context. |
| `id uuid NOT NULL DEFAULT gen_random_uuid()` | Stable internal UUID; database-generated unless a durable source mapping supplies it. |
| `source_key text NOT NULL` | Stable upstream idempotency key; scope is defined by UNIQUE constraints. |
| `name text NOT NULL` | Human-readable editable name; not an identity or uniqueness guarantee. |

Table constraints:

- `PRIMARY KEY (org_id, id)`
- `UNIQUE (org_id, source_key)`

## flight

Source capture session and optional actual coverage footprint.

| Field / SQL declaration | Meaning, units and provenance |
|---|---|
| `org_id uuid NOT NULL` | Owning organization UUID; part of every tenant-scoped key/FK and RLS context. |
| `id uuid NOT NULL DEFAULT gen_random_uuid()` | Stable internal UUID; database-generated unless a durable source mapping supplies it. |
| `drone_id uuid NOT NULL` | Source drone reference, separate from an animal. |
| `ranch_id uuid NOT NULL` | Tenant-scoped administrative ranch reference. |
| `source_key text NOT NULL` | Stable upstream idempotency key; scope is defined by UNIQUE constraints. |
| `started_at timestamptz NOT NULL` | Capture/processing start instant (timestamptz, UTC interchange). |
| `ended_at timestamptz` | Capture/processing completion instant (timestamptz, UTC interchange). |
| `ingested_at timestamptz NOT NULL DEFAULT now()` | Database ingestion instant (timestamptz, UTC interchange). |
| `coverage geometry(multipolygon, 4326)` | Optional actual flight coverage MultiPolygon in EPSG:4326; NULL is unknown. |
| `coverage_method text` | Provenance/version for actual coverage estimation, required with footprint. |

Table constraints:

- `PRIMARY KEY (org_id, id)`
- `UNIQUE (org_id, source_key)`
- `FOREIGN KEY (org_id, drone_id) REFERENCES drone (org_id, id)`
- `FOREIGN KEY (org_id, ranch_id) REFERENCES ranch (org_id, id)`
- `CHECK (ended_at IS NULL OR ended_at >= started_at)`
- `CHECK (coverage IS NULL OR (st_isvalid(coverage) AND NOT st_isempty(coverage)))`
- `CHECK (coverage IS NULL OR coverage_method IS NOT NULL)`

## telemetry

Timestamped drone state; never a cow ground location.

| Field / SQL declaration | Meaning, units and provenance |
|---|---|
| `org_id uuid NOT NULL` | Owning organization UUID; part of every tenant-scoped key/FK and RLS context. |
| `id uuid NOT NULL DEFAULT gen_random_uuid()` | Stable internal UUID; database-generated unless a durable source mapping supplies it. |
| `flight_id uuid NOT NULL` | Capture flight reference; repeated in composite keys to prevent mixed-flight lineage. |
| `source_key text NOT NULL` | Stable upstream idempotency key; scope is defined by UNIQUE constraints. |
| `observed_at timestamptz NOT NULL` | Telemetry event instant (timestamptz, UTC interchange). |
| `ingested_at timestamptz NOT NULL DEFAULT now()` | Database ingestion instant (timestamptz, UTC interchange). |
| `drone_position geography(point, 4326)` | Drone point, geography EPSG:4326; never substitute as cow location. |
| `altitude_m double precision` | Optional drone altitude in meters; reference datum must be in payload. |
| `battery_percent numeric` | Optional drone battery percent 0–100; not current without observation age. |
| `clock_quality text NOT NULL` | Declared synchronization/clock quality; details in associated payload/capture. |
| `payload_schema text NOT NULL` | Schema version for telemetry payload. |
| `payload jsonb NOT NULL` | Original nonsecret schema-versioned telemetry/prediction object; unknowns explicit. |

Table constraints:

- `PRIMARY KEY (org_id, id)`
- `UNIQUE (org_id, flight_id, source_key)`
- `FOREIGN KEY (org_id, flight_id) REFERENCES flight (org_id, id)`
- `CHECK (battery_percent BETWEEN 0 AND 100)`
- `CHECK (jsonb_typeof(payload) = 'object')`

## clip

Cow-parsed image sequence manifest; parsed identity remains a claim.

| Field / SQL declaration | Meaning, units and provenance |
|---|---|
| `org_id uuid NOT NULL` | Owning organization UUID; part of every tenant-scoped key/FK and RLS context. |
| `id uuid NOT NULL DEFAULT gen_random_uuid()` | Stable internal UUID; database-generated unless a durable source mapping supplies it. |
| `flight_id uuid NOT NULL` | Capture flight reference; repeated in composite keys to prevent mixed-flight lineage. |
| `source_key text NOT NULL` | Stable upstream idempotency key; scope is defined by UNIQUE constraints. |
| `parsed_animal_id uuid` | Optional candidate cattle UUID from cow-based parsing; not accepted identity. |
| `parsed_identifier text` | Original cow-ID/RFID claim from parser for reconciliation. |
| `started_at timestamptz NOT NULL` | Capture/processing start instant (timestamptz, UTC interchange). |
| `duration_ms bigint NOT NULL CHECK (duration_ms > 0)` | Positive clip/video duration in milliseconds; NULL for image assets. |
| `fps numeric NOT NULL CHECK (fps > 0)` | Positive image cadence (frames/second); initially 30 by user requirement. |
| `expected_image_count integer NOT NULL CHECK (expected_image_count > 0)` | Positive clip manifest count, initially 300–450; uploader verifies completion. |

Table constraints:

- `PRIMARY KEY (org_id, id)`
- `UNIQUE (org_id, flight_id, source_key)`
- `UNIQUE (org_id, id, flight_id)`
- `FOREIGN KEY (org_id, flight_id) REFERENCES flight (org_id, id)`
- `FOREIGN KEY (org_id, parsed_animal_id) REFERENCES animal (org_id, id)`

## media_asset

Private image/video object and upload verification state.

| Field / SQL declaration | Meaning, units and provenance |
|---|---|
| `org_id uuid NOT NULL` | Owning organization UUID; part of every tenant-scoped key/FK and RLS context. |
| `id uuid NOT NULL DEFAULT gen_random_uuid()` | Stable internal UUID; database-generated unless a durable source mapping supplies it. |
| `flight_id uuid NOT NULL` | Capture flight reference; repeated in composite keys to prevent mixed-flight lineage. |
| `source_key text NOT NULL` | Stable upstream idempotency key; scope is defined by UNIQUE constraints. |
| `clip_id uuid` | Optional parsed clip grouping; must share flight with asset. |
| `image_index integer CHECK (image_index >= 0)` | Zero-based image sequence index; unique within clip. |
| `kind text NOT NULL CHECK (kind IN ('image', 'video'))` | Constrained source type or prediction output discriminator; see CHECK. |
| `object_key text NOT NULL` | Durable private storage key, tenant-unique; never an expiring signed URL. |
| `sha256 text NOT NULL CHECK (sha256 ~ '^[a-f0-9]{64}$')` | Lowercase hexadecimal SHA-256 of media content; uploader verifies actual bytes. |
| `size_bytes bigint NOT NULL CHECK (size_bytes > 0)` | Positive object size in bytes, compared with uploaded content. |
| `state text NOT NULL DEFAULT 'pending' CHECK (state IN ('pending', 'ready', 'failed', 'purged'))` | Upload lifecycle or alert lifecycle, depending on table; see CHECK. |
| `captured_at timestamptz NOT NULL` | Source capture instant (timestamptz, UTC interchange). |
| `ingested_at timestamptz NOT NULL DEFAULT now()` | Database ingestion instant (timestamptz, UTC interchange). |
| `width_px integer NOT NULL CHECK (width_px > 0)` | Positive source image/video width in pixels. |
| `height_px integer NOT NULL CHECK (height_px > 0)` | Positive source height in pixels. |
| `duration_ms bigint` | Positive clip/video duration in milliseconds; NULL for image assets. |
| `sensor_key text NOT NULL` | Source camera/sensor identifier; capture payload carries calibration/pose as available. |
| `capture_schema text NOT NULL` | Schema version defining capture metadata. |
| `capture jsonb NOT NULL` | Capture metadata JSON (pose/calibration/clock claims if supplied); no fabricated capabilities. |

Table constraints:

- `PRIMARY KEY (org_id, id)`
- `UNIQUE (org_id, flight_id, source_key)`
- `UNIQUE (org_id, object_key)`
- `UNIQUE (org_id, id, flight_id)`
- `FOREIGN KEY (org_id, flight_id) REFERENCES flight (org_id, id)`
- `FOREIGN KEY (org_id, clip_id, flight_id) REFERENCES clip (org_id, id, flight_id)`
- `UNIQUE (org_id, clip_id, image_index)`
- `CHECK ((clip_id IS NULL AND image_index IS NULL) OR (clip_id IS NOT NULL AND image_index IS NOT NULL AND kind = 'image'))`
- `CHECK ((kind = 'video' AND duration_ms > 0) OR (kind = 'image' AND duration_ms IS NULL))`
- `CHECK (jsonb_typeof(capture) = 'object')`

## frame

Captured image or video offset; source evidence input.

| Field / SQL declaration | Meaning, units and provenance |
|---|---|
| `org_id uuid NOT NULL` | Owning organization UUID; part of every tenant-scoped key/FK and RLS context. |
| `id uuid NOT NULL DEFAULT gen_random_uuid()` | Stable internal UUID; database-generated unless a durable source mapping supplies it. |
| `asset_id uuid NOT NULL` | Source object reference; frame offset is relative to this asset. |
| `flight_id uuid NOT NULL` | Capture flight reference; repeated in composite keys to prevent mixed-flight lineage. |
| `offset_ms bigint NOT NULL CHECK (offset_ms >= 0)` | Nonnegative milliseconds into video; zero for an independent image. |
| `captured_at timestamptz NOT NULL` | Source capture instant (timestamptz, UTC interchange). |
| `clock_quality text NOT NULL` | Declared synchronization/clock quality; details in associated payload/capture. |

Table constraints:

- `PRIMARY KEY (org_id, id)`
- `UNIQUE (org_id, asset_id, offset_ms)`
- `UNIQUE (org_id, id, flight_id)`
- `FOREIGN KEY (org_id, asset_id, flight_id) REFERENCES media_asset (org_id, id, flight_id)`

## model_version

Immutable model artifact, taxonomy and confidence semantics.

| Field / SQL declaration | Meaning, units and provenance |
|---|---|
| `org_id uuid NOT NULL REFERENCES organization (id)` | Owning organization UUID; part of every tenant-scoped key/FK and RLS context. |
| `id uuid NOT NULL DEFAULT gen_random_uuid()` | Stable internal UUID; database-generated unless a durable source mapping supplies it. |
| `model_name text NOT NULL` | Stable descriptive model family name, tenant-scoped. |
| `version text NOT NULL` | Immutable model/policy version text; unique within named family/key. |
| `artifact_sha256 text NOT NULL CHECK (artifact_sha256 ~ '^[a-f0-9]{64}$')` | Lowercase hexadecimal model artifact SHA-256; immutable version provenance. |
| `taxonomy_version text NOT NULL` | Class/label taxonomy definition version for output interpretation. |
| `score_meaning text NOT NULL` | Meaning of confidence; not a guarantee of calibrated probability. |
| `calibration_version text` | Optional calibration reference; NULL means unavailable/unasserted. |

Table constraints:

- `PRIMARY KEY (org_id, id)`
- `UNIQUE (org_id, model_name, version)`

## inference_run

Versioned processing attempt and explicit publication state.

| Field / SQL declaration | Meaning, units and provenance |
|---|---|
| `org_id uuid NOT NULL` | Owning organization UUID; part of every tenant-scoped key/FK and RLS context. |
| `id uuid NOT NULL DEFAULT gen_random_uuid()` | Stable internal UUID; database-generated unless a durable source mapping supplies it. |
| `flight_id uuid NOT NULL` | Capture flight reference; repeated in composite keys to prevent mixed-flight lineage. |
| `model_version_id uuid NOT NULL` | Immutable artifact/version/taxonomy/confidence definition. |
| `request_key text NOT NULL` | Tenant-scoped exact processing request key; new attempt requires a new key. |
| `retry_of uuid` | Optional prior failed attempt UUID; does not reuse its outputs or request key. |
| `config_schema text NOT NULL` | Schema version for model configuration JSON. |
| `config jsonb NOT NULL` | Complete nonsecret config/thresholds for reproducibility; JSON object. |
| `processing_version text NOT NULL` | Version of adapter/preprocessing/postprocessing pipeline. |
| `status text NOT NULL DEFAULT 'queued' CHECK (status IN ('queued', 'running', 'succeeded', 'failed'))` | Queued/running/succeeded/failed attempt state; terminal results are frozen. |
| `created_at timestamptz NOT NULL DEFAULT now()` | Creation instant (timestamptz, UTC interchange). |
| `started_at timestamptz` | Capture/processing start instant (timestamptz, UTC interchange). |
| `ended_at timestamptz` | Capture/processing completion instant (timestamptz, UTC interchange). |

Table constraints:

- `PRIMARY KEY (org_id, id)`
- `UNIQUE (org_id, request_key)`
- `UNIQUE (org_id, id, flight_id)`
- `FOREIGN KEY (org_id, flight_id) REFERENCES flight (org_id, id)`
- `FOREIGN KEY (org_id, model_version_id) REFERENCES model_version (org_id, id)`
- `FOREIGN KEY (org_id, retry_of) REFERENCES inference_run (org_id, id)`
- `CHECK (retry_of IS DISTINCT FROM id)`
- `CHECK (jsonb_typeof(config) = 'object')`
- `CHECK (ended_at IS NULL OR (started_at IS NOT NULL AND ended_at >= started_at))`
- `CHECK (status NOT IN ('succeeded', 'failed') OR ended_at IS NOT NULL)`

## run_input

Exact same-flight frame inputs for one inference run.

| Field / SQL declaration | Meaning, units and provenance |
|---|---|
| `org_id uuid NOT NULL` | Owning organization UUID; part of every tenant-scoped key/FK and RLS context. |
| `run_id uuid NOT NULL` | Producing or contributing inference attempt reference. |
| `frame_id uuid NOT NULL` | Specific source image/frame reference, also declared in run inputs. |
| `flight_id uuid NOT NULL` | Capture flight reference; repeated in composite keys to prevent mixed-flight lineage. |

Table constraints:

- `PRIMARY KEY (org_id, run_id, frame_id)`
- `FOREIGN KEY (org_id, run_id, flight_id) REFERENCES inference_run (org_id, id, flight_id)`
- `FOREIGN KEY (org_id, frame_id, flight_id) REFERENCES frame (org_id, id, flight_id)`

## model_output

Immutable original schema-versioned prediction, including conflicting runs.

| Field / SQL declaration | Meaning, units and provenance |
|---|---|
| `org_id uuid NOT NULL` | Owning organization UUID; part of every tenant-scoped key/FK and RLS context. |
| `id uuid NOT NULL DEFAULT gen_random_uuid()` | Stable internal UUID; database-generated unless a durable source mapping supplies it. |
| `run_id uuid NOT NULL` | Producing or contributing inference attempt reference. |
| `frame_id uuid NOT NULL` | Specific source image/frame reference, also declared in run inputs. |
| `flight_id uuid NOT NULL` | Capture flight reference; repeated in composite keys to prevent mixed-flight lineage. |
| `source_key text NOT NULL` | Stable upstream idempotency key; scope is defined by UNIQUE constraints. |
| `kind text NOT NULL CHECK (kind IN ('detection', 'identity', 'location', 'measurement', 'finding', 'survey'))` | Constrained source type or prediction output discriminator; see CHECK. |
| `schema_version text NOT NULL` | Schema version defining original model payload and variable details. |
| `payload jsonb NOT NULL` | Original nonsecret schema-versioned telemetry/prediction object; unknowns explicit. |
| `score double precision` | Optional model/identity confidence 0–1; distinct from metric value and geolocation accuracy. |

Table constraints:

- `PRIMARY KEY (org_id, id)`
- `UNIQUE (org_id, run_id, source_key)`
- `UNIQUE (org_id, id, flight_id)`
- `UNIQUE (org_id, id, run_id, frame_id)`
- `FOREIGN KEY (org_id, run_id, frame_id) REFERENCES run_input (org_id, run_id, frame_id)`
- `FOREIGN KEY (org_id, run_id, flight_id) REFERENCES inference_run (org_id, id, flight_id)`
- `CHECK (jsonb_typeof(payload) = 'object')`
- `CHECK (score >= 0 AND score <= 1)`

## output_input

Declared model-output provenance edges; adapter prevents multi-edge cycles.

| Field / SQL declaration | Meaning, units and provenance |
|---|---|
| `org_id uuid NOT NULL` | Owning organization UUID; part of every tenant-scoped key/FK and RLS context. |
| `output_id uuid NOT NULL` | Original supporting/producing model output reference. |
| `input_output_id uuid NOT NULL` | Input prediction consumed by another output; not an unconstrained polymorphic ID. |

Table constraints:

- `PRIMARY KEY (org_id, output_id, input_output_id)`
- `CHECK (output_id <> input_output_id)`
- `FOREIGN KEY (org_id, output_id) REFERENCES model_output (org_id, id)`
- `FOREIGN KEY (org_id, input_output_id) REFERENCES model_output (org_id, id)`

## model_measurement

Numeric model metric with versioned scale, separate from confidence.

| Field / SQL declaration | Meaning, units and provenance |
|---|---|
| `org_id uuid NOT NULL` | Owning organization UUID; part of every tenant-scoped key/FK and RLS context. |
| `id uuid NOT NULL DEFAULT gen_random_uuid()` | Stable internal UUID; database-generated unless a durable source mapping supplies it. |
| `output_id uuid NOT NULL` | Original supporting/producing model output reference. |
| `metric_code text NOT NULL` | Filterable numeric metric, initially gait_locomotion or estrus_behavior; extensible. |
| `value numeric NOT NULL` | External identifier text or numeric model metric; see owning table/unit/scale. |
| `unit text NOT NULL` | Explicit metric unit, e.g. ordinal_score; estrus behavior is not temperature. |
| `scale_version text NOT NULL` | Immutable scoring-scale definition reference; no cross-scale comparison by default. |
| `scale_min numeric` | Optional numeric score lower bound; both bounds must be present together. |
| `scale_max numeric` | Optional numeric score upper bound; raw value must lie within known bounds. |

Table constraints:

- `PRIMARY KEY (org_id, id)`
- `UNIQUE (org_id, output_id, metric_code)`
- `FOREIGN KEY (org_id, output_id) REFERENCES model_output (org_id, id)`
- `CHECK (value NOT IN (CAST('NaN' AS numeric), CAST('Infinity' AS numeric), CAST('-Infinity' AS numeric)))`
- `CHECK ((scale_min IS NULL AND scale_max IS NULL) OR (scale_min IS NOT NULL AND scale_max IS NOT NULL AND scale_min < scale_max AND value BETWEEN scale_min AND scale_max))`

## detection

Indexed per-frame detection and normalized pixel box.

| Field / SQL declaration | Meaning, units and provenance |
|---|---|
| `org_id uuid NOT NULL` | Owning organization UUID; part of every tenant-scoped key/FK and RLS context. |
| `id uuid NOT NULL DEFAULT gen_random_uuid()` | Stable internal UUID; database-generated unless a durable source mapping supplies it. |
| `output_id uuid NOT NULL` | Original supporting/producing model output reference. |
| `run_id uuid NOT NULL` | Producing or contributing inference attempt reference. |
| `frame_id uuid NOT NULL` | Specific source image/frame reference, also declared in run inputs. |
| `class_label text NOT NULL` | Model taxonomy class label; source model version supplies taxonomy. |
| `x_min double precision NOT NULL` | Normalized left box edge [0,1], top-left origin, half-open convention. |
| `y_min double precision NOT NULL` | Normalized top box edge [0,1]. |
| `x_max double precision NOT NULL` | Normalized right edge (x_min,1]. |
| `y_max double precision NOT NULL` | Normalized bottom edge (y_min,1]. |
| `mask_object_key text` | Optional private mask object key; uploader verifies storage authorization. |

Table constraints:

- `PRIMARY KEY (org_id, id)`
- `UNIQUE (org_id, output_id)`
- `UNIQUE (org_id, id, run_id)`
- `FOREIGN KEY (org_id, output_id, run_id, frame_id) REFERENCES model_output (org_id, id, run_id, frame_id)`
- `CHECK (x_min >= 0 AND y_min >= 0 AND x_max <= 1 AND y_max <= 1 AND x_min < x_max AND y_min < y_max)`

## track

Temporary run-local object, not a permanent animal.

| Field / SQL declaration | Meaning, units and provenance |
|---|---|
| `org_id uuid NOT NULL` | Owning organization UUID; part of every tenant-scoped key/FK and RLS context. |
| `id uuid NOT NULL DEFAULT gen_random_uuid()` | Stable internal UUID; database-generated unless a durable source mapping supplies it. |
| `run_id uuid NOT NULL` | Producing or contributing inference attempt reference. |
| `flight_id uuid NOT NULL` | Capture flight reference; repeated in composite keys to prevent mixed-flight lineage. |
| `local_key text NOT NULL` | Temporary track ID, unique within producing run. |

Table constraints:

- `PRIMARY KEY (org_id, id)`
- `UNIQUE (org_id, run_id, local_key)`
- `UNIQUE (org_id, id, run_id)`
- `UNIQUE (org_id, id, flight_id)`
- `FOREIGN KEY (org_id, run_id, flight_id) REFERENCES inference_run (org_id, id, flight_id)`

## track_detection

A detection belongs to at most one track in its producing run.

| Field / SQL declaration | Meaning, units and provenance |
|---|---|
| `org_id uuid NOT NULL` | Owning organization UUID; part of every tenant-scoped key/FK and RLS context. |
| `track_id uuid NOT NULL` | Temporary track subject/reference; identity may be unresolved. |
| `detection_id uuid NOT NULL` | FK-backed detection subject or association. |
| `run_id uuid NOT NULL` | Producing or contributing inference attempt reference. |

Table constraints:

- `PRIMARY KEY (org_id, track_id, detection_id)`
- `UNIQUE (org_id, detection_id)`
- `FOREIGN KEY (org_id, track_id, run_id) REFERENCES track (org_id, id, run_id)`
- `FOREIGN KEY (org_id, detection_id, run_id) REFERENCES detection (org_id, id, run_id)`

## identity_decision

Immutable track identity acceptance/rejection/unresolved chain.

| Field / SQL declaration | Meaning, units and provenance |
|---|---|
| `org_id uuid NOT NULL` | Owning organization UUID; part of every tenant-scoped key/FK and RLS context. |
| `id uuid NOT NULL DEFAULT gen_random_uuid()` | Stable internal UUID; database-generated unless a durable source mapping supplies it. |
| `track_id uuid NOT NULL` | Temporary track subject/reference; identity may be unresolved. |
| `animal_id uuid` | Permanent cattle reference; identity acceptance requires a value. |
| `supersedes uuid` | Previous same-subject revision; NULL means root, at most one successor/root. |
| `decision text NOT NULL CHECK (decision IN ('accepted', 'unresolved', 'rejected'))` | Identity/reviewer outcome; rejected/unresolved is not accepted. |
| `method_version text NOT NULL` | Versioned identity/geolocation/count algorithm or manual reconciliation method. |
| `score double precision CHECK (score >= 0 AND score <= 1)` | Optional model/identity confidence 0–1; distinct from metric value and geolocation accuracy. |
| `actor text NOT NULL` | Verified backend assertion of external auth identity or versioned processing identity. |
| `reason text NOT NULL` | Required explanation for correction, missing evidence or review/lifecycle action. |
| `decided_at timestamptz NOT NULL DEFAULT now()` | Identity decision recording instant (timestamptz, UTC interchange). |

Table constraints:

- `PRIMARY KEY (org_id, id)`
- `UNIQUE (org_id, id, track_id)`
- `UNIQUE (org_id, supersedes)`
- `FOREIGN KEY (org_id, track_id) REFERENCES track (org_id, id)`
- `FOREIGN KEY (org_id, animal_id) REFERENCES animal (org_id, id)`
- `FOREIGN KEY (org_id, supersedes, track_id) REFERENCES identity_decision (org_id, id, track_id)`
- `CHECK (supersedes IS DISTINCT FROM id)`
- `CHECK (decision <> 'accepted' OR animal_id IS NOT NULL)`

## identity_evidence

Original outputs supporting identity decisions, including RFID alignment.

| Field / SQL declaration | Meaning, units and provenance |
|---|---|
| `org_id uuid NOT NULL` | Owning organization UUID; part of every tenant-scoped key/FK and RLS context. |
| `decision_id uuid NOT NULL` | Identity decision being supported by evidence. |
| `output_id uuid NOT NULL` | Original supporting/producing model output reference. |

Table constraints:

- `PRIMARY KEY (org_id, decision_id, output_id)`
- `FOREIGN KEY (org_id, decision_id) REFERENCES identity_decision (org_id, id)`
- `FOREIGN KEY (org_id, output_id) REFERENCES model_output (org_id, id)`

## location_observation

Resolved ground interpretation revisions per track/event; anonymous allowed.

| Field / SQL declaration | Meaning, units and provenance |
|---|---|
| `org_id uuid NOT NULL` | Owning organization UUID; part of every tenant-scoped key/FK and RLS context. |
| `id uuid NOT NULL DEFAULT gen_random_uuid()` | Stable internal UUID; database-generated unless a durable source mapping supplies it. |
| `track_id uuid NOT NULL` | Temporary track subject/reference; identity may be unresolved. |
| `flight_id uuid NOT NULL` | Capture flight reference; repeated in composite keys to prevent mixed-flight lineage. |
| `output_id uuid NOT NULL` | Original supporting/producing model output reference. |
| `supersedes uuid` | Previous same-subject revision; NULL means root, at most one successor/root. |
| `event_at timestamptz NOT NULL` | Animal/survey/finding event instant (timestamptz, UTC interchange). |
| `recorded_at timestamptz NOT NULL DEFAULT now()` | Interpretation recording instant (timestamptz, UTC interchange). |
| `position geography(point, 4326)` | Estimated cow ground point, geography EPSG:4326 lon/lat; may be unknown. |
| `uncertainty_m double precision CHECK (uncertainty_m >= 0)` | Optional nonnegative horizontal radius in meters; method defines interpretation. |
| `assessment text NOT NULL CHECK (assessment IN ('accepted', 'not_assessable', 'rejected'))` | Location acceptance or triage assessability, independently of health review. |
| `method_version text NOT NULL` | Versioned identity/geolocation/count algorithm or manual reconciliation method. |
| `actor text NOT NULL` | Verified backend assertion of external auth identity or versioned processing identity. |
| `reason text NOT NULL` | Required explanation for correction, missing evidence or review/lifecycle action. |

Table constraints:

- `PRIMARY KEY (org_id, id)`
- `UNIQUE (org_id, id, track_id, event_at)`
- `UNIQUE (org_id, supersedes)`
- `FOREIGN KEY (org_id, track_id, flight_id) REFERENCES track (org_id, id, flight_id)`
- `FOREIGN KEY (org_id, output_id, flight_id) REFERENCES model_output (org_id, id, flight_id)`
- `FOREIGN KEY (org_id, supersedes, track_id, event_at) REFERENCES location_observation (org_id, id, track_id, event_at)`
- `CHECK (supersedes IS DISTINCT FROM id)`
- `CHECK (assessment <> 'accepted' OR position IS NOT NULL)`
- `CHECK (assessment <> 'not_assessable' OR position IS NULL)`

## finding

Resolved triage assessment with exactly one FK-backed subject.

| Field / SQL declaration | Meaning, units and provenance |
|---|---|
| `org_id uuid NOT NULL` | Owning organization UUID; part of every tenant-scoped key/FK and RLS context. |
| `id uuid NOT NULL DEFAULT gen_random_uuid()` | Stable internal UUID; database-generated unless a durable source mapping supplies it. |
| `detection_id uuid` | FK-backed detection subject or association. |
| `track_id uuid` | Temporary track subject/reference; identity may be unresolved. |
| `animal_id uuid` | Permanent cattle reference; identity acceptance requires a value. |
| `herd_id uuid` | Tenant-scoped herd subject/assignment reference. |
| `event_at timestamptz NOT NULL` | Animal/survey/finding event instant (timestamptz, UTC interchange). |
| `label text NOT NULL` | Finding taxonomy label; suspected score-based issue is not confirmed disease. |
| `severity text NOT NULL CHECK (severity IN ('info', 'review', 'priority'))` | Info/review/priority triage severity, separate from review and alert lifecycle. |
| `assessment text NOT NULL CHECK (assessment IN ('suspected', 'assessed_negative', 'not_assessable'))` | Location acceptance or triage assessability, independently of health review. |
| `policy_version text NOT NULL` | Versioned interpretation/fusion/geofence policy identifier. |
| `actor text NOT NULL` | Verified backend assertion of external auth identity or versioned processing identity. |
| `recorded_at timestamptz NOT NULL DEFAULT now()` | Interpretation recording instant (timestamptz, UTC interchange). |

Table constraints:

- `PRIMARY KEY (org_id, id)`
- `CHECK (num_nonnulls(detection_id, track_id, animal_id, herd_id) = 1)`
- `FOREIGN KEY (org_id, detection_id) REFERENCES detection (org_id, id)`
- `FOREIGN KEY (org_id, track_id) REFERENCES track (org_id, id)`
- `FOREIGN KEY (org_id, animal_id) REFERENCES animal (org_id, id)`
- `FOREIGN KEY (org_id, herd_id) REFERENCES herd (org_id, id)`

## finding_evidence

Inputs used by the finding policy, preserving conflicts/fusion lineage.

| Field / SQL declaration | Meaning, units and provenance |
|---|---|
| `org_id uuid NOT NULL` | Owning organization UUID; part of every tenant-scoped key/FK and RLS context. |
| `finding_id uuid NOT NULL` | Resolved finding reference. |
| `output_id uuid NOT NULL` | Original supporting/producing model output reference. |

Table constraints:

- `PRIMARY KEY (org_id, finding_id, output_id)`
- `FOREIGN KEY (org_id, finding_id) REFERENCES finding (org_id, id)`
- `FOREIGN KEY (org_id, output_id) REFERENCES model_output (org_id, id)`

## finding_review

Append-only reviewer decision chain; not a confirmed veterinary event.

| Field / SQL declaration | Meaning, units and provenance |
|---|---|
| `org_id uuid NOT NULL` | Owning organization UUID; part of every tenant-scoped key/FK and RLS context. |
| `id uuid NOT NULL DEFAULT gen_random_uuid()` | Stable internal UUID; database-generated unless a durable source mapping supplies it. |
| `finding_id uuid NOT NULL` | Resolved finding reference. |
| `supersedes uuid` | Previous same-subject revision; NULL means root, at most one successor/root. |
| `decision text NOT NULL CHECK (decision IN ('accepted', 'rejected', 'needs_review'))` | Identity/reviewer outcome; rejected/unresolved is not accepted. |
| `actor text NOT NULL` | Verified backend assertion of external auth identity or versioned processing identity. |
| `reason text NOT NULL` | Required explanation for correction, missing evidence or review/lifecycle action. |
| `reviewed_at timestamptz NOT NULL DEFAULT now()` | Review recording instant (timestamptz, UTC interchange). |

Table constraints:

- `PRIMARY KEY (org_id, id)`
- `UNIQUE (org_id, id, finding_id)`
- `UNIQUE (org_id, supersedes)`
- `FOREIGN KEY (org_id, finding_id) REFERENCES finding (org_id, id)`
- `FOREIGN KEY (org_id, supersedes, finding_id) REFERENCES finding_review (org_id, id, finding_id)`
- `CHECK (supersedes IS DISTINCT FROM id)`

## survey

Resolved deduplicated herd estimate with uncertainty and supersession.

| Field / SQL declaration | Meaning, units and provenance |
|---|---|
| `org_id uuid NOT NULL` | Owning organization UUID; part of every tenant-scoped key/FK and RLS context. |
| `id uuid NOT NULL DEFAULT gen_random_uuid()` | Stable internal UUID; database-generated unless a durable source mapping supplies it. |
| `herd_id uuid NOT NULL` | Tenant-scoped herd subject/assignment reference. |
| `flight_id uuid NOT NULL` | Capture flight reference; repeated in composite keys to prevent mixed-flight lineage. |
| `event_at timestamptz NOT NULL` | Animal/survey/finding event instant (timestamptz, UTC interchange). |
| `supersedes uuid` | Previous same-subject revision; NULL means root, at most one successor/root. |
| `estimate integer CHECK (estimate >= 0)` | Optional deduplicated cow count estimate; not number of output rows. |
| `lower_count integer CHECK (lower_count >= 0)` | Optional conservative lower count bound; present with estimate. |
| `upper_count integer` | Optional upper count bound; estimate lies between the bounds. |
| `coverage_fraction double precision CHECK (coverage_fraction BETWEEN 0 AND 1)` | Optional surveyed/target area fraction 0–1; NULL is unknown. |
| `surveyed_area geometry(multipolygon, 4326)` | Optional EPSG:4326 MultiPolygon representing surveyed ground area. |
| `method_version text NOT NULL` | Versioned identity/geolocation/count algorithm or manual reconciliation method. |
| `uncertainty_note text NOT NULL` | Required count uncertainty/missingness explanation, including dedupe assumptions. |
| `actor text NOT NULL` | Verified backend assertion of external auth identity or versioned processing identity. |
| `recorded_at timestamptz NOT NULL DEFAULT now()` | Interpretation recording instant (timestamptz, UTC interchange). |

Table constraints:

- `PRIMARY KEY (org_id, id)`
- `UNIQUE (org_id, id, herd_id, flight_id)`
- `UNIQUE (org_id, supersedes)`
- `FOREIGN KEY (org_id, herd_id) REFERENCES herd (org_id, id)`
- `FOREIGN KEY (org_id, flight_id) REFERENCES flight (org_id, id)`
- `FOREIGN KEY (org_id, supersedes, herd_id, flight_id) REFERENCES survey (org_id, id, herd_id, flight_id)`
- `CHECK (supersedes IS DISTINCT FROM id)`
- `CHECK ((estimate IS NULL AND lower_count IS NULL AND upper_count IS NULL) OR (estimate IS NOT NULL AND lower_count IS NOT NULL AND upper_count IS NOT NULL AND lower_count <= estimate AND estimate <= upper_count))`
- `CHECK (surveyed_area IS NULL OR (st_isvalid(surveyed_area) AND NOT st_isempty(surveyed_area)))`

## survey_input

Declared run set used by a survey; resolver verifies scope and publication.

| Field / SQL declaration | Meaning, units and provenance |
|---|---|
| `org_id uuid NOT NULL` | Owning organization UUID; part of every tenant-scoped key/FK and RLS context. |
| `survey_id uuid NOT NULL` | Resolved survey reference. |
| `run_id uuid NOT NULL` | Producing or contributing inference attempt reference. |

Table constraints:

- `PRIMARY KEY (org_id, survey_id, run_id)`
- `FOREIGN KEY (org_id, survey_id) REFERENCES survey (org_id, id)`
- `FOREIGN KEY (org_id, run_id) REFERENCES inference_run (org_id, id)`

## alert_rule_version

Immutable alert policy version; execution/delivery service deferred.

| Field / SQL declaration | Meaning, units and provenance |
|---|---|
| `org_id uuid NOT NULL REFERENCES organization (id)` | Owning organization UUID; part of every tenant-scoped key/FK and RLS context. |
| `id uuid NOT NULL DEFAULT gen_random_uuid()` | Stable internal UUID; database-generated unless a durable source mapping supplies it. |
| `rule_key text NOT NULL` | Stable tenant-scoped alert policy name. |
| `version text NOT NULL` | Immutable model/policy version text; unique within named family/key. |
| `policy jsonb NOT NULL` | Nonsecret alert configuration JSON object, frozen with version. |

Table constraints:

- `PRIMARY KEY (org_id, id)`
- `UNIQUE (org_id, rule_key, version)`
- `CHECK (jsonb_typeof(policy) = 'object')`

## alert

Deduplicated in-app alert instance, supported by a finding.

| Field / SQL declaration | Meaning, units and provenance |
|---|---|
| `org_id uuid NOT NULL` | Owning organization UUID; part of every tenant-scoped key/FK and RLS context. |
| `id uuid NOT NULL DEFAULT gen_random_uuid()` | Stable internal UUID; database-generated unless a durable source mapping supplies it. |
| `rule_version_id uuid NOT NULL` | Frozen alert policy reference. |
| `basis_identity_decision_id uuid` | Optional frozen identity decision used by an identity-dependent alert; a changed current decision invalidates effective alert state. |
| `finding_id uuid NOT NULL` | Resolved finding reference. |
| `dedupe_key text NOT NULL` | Tenant-scoped semantic alert key to prevent duplicate alert creation. |
| `opened_at timestamptz NOT NULL DEFAULT now()` | Alert creation instant (timestamptz, UTC interchange). |

Table constraints:

- `PRIMARY KEY (org_id, id)`
- `UNIQUE (org_id, dedupe_key)`
- `FOREIGN KEY (org_id, rule_version_id) REFERENCES alert_rule_version (org_id, id)`
- `FOREIGN KEY (org_id, basis_identity_decision_id) REFERENCES identity_decision (org_id, id)`
- `FOREIGN KEY (org_id, finding_id) REFERENCES finding (org_id, id)`

## alert_event

Append-only lifecycle chain independent of finding severity/review.

| Field / SQL declaration | Meaning, units and provenance |
|---|---|
| `org_id uuid NOT NULL` | Owning organization UUID; part of every tenant-scoped key/FK and RLS context. |
| `id uuid NOT NULL DEFAULT gen_random_uuid()` | Stable internal UUID; database-generated unless a durable source mapping supplies it. |
| `alert_id uuid NOT NULL` | Alert instance reference. |
| `supersedes uuid` | Previous same-subject revision; NULL means root, at most one successor/root. |
| `state text NOT NULL CHECK (state IN ('open', 'acknowledged', 'resolved', 'invalidated'))` | Upload lifecycle or alert lifecycle, depending on table; see CHECK. |
| `actor text NOT NULL` | Verified backend assertion of external auth identity or versioned processing identity. |
| `reason text NOT NULL` | Required explanation for correction, missing evidence or review/lifecycle action. |
| `happened_at timestamptz NOT NULL DEFAULT now()` | Audit/alert lifecycle recording instant (timestamptz, UTC interchange). |

Table constraints:

- `PRIMARY KEY (org_id, id)`
- `UNIQUE (org_id, id, alert_id)`
- `UNIQUE (org_id, supersedes)`
- `FOREIGN KEY (org_id, alert_id) REFERENCES alert (org_id, id)`
- `FOREIGN KEY (org_id, supersedes, alert_id) REFERENCES alert_event (org_id, id, alert_id)`
- `CHECK (supersedes IS DISTINCT FROM id)`

## audit_event

Attribution and recovery/correction/maintenance record; no secrets.

| Field / SQL declaration | Meaning, units and provenance |
|---|---|
| `org_id uuid NOT NULL REFERENCES organization (id)` | Owning organization UUID; part of every tenant-scoped key/FK and RLS context. |
| `id uuid NOT NULL DEFAULT gen_random_uuid()` | Stable internal UUID; database-generated unless a durable source mapping supplies it. |
| `actor text NOT NULL` | Verified backend assertion of external auth identity or versioned processing identity. |
| `action text NOT NULL` | Audit action name; targets in versioned detail are audit descriptors, not domain FKs. |
| `happened_at timestamptz NOT NULL DEFAULT now()` | Audit/alert lifecycle recording instant (timestamptz, UTC interchange). |
| `detail_schema text NOT NULL` | Schema version for audit detail. |
| `detail jsonb NOT NULL` | Nonsecret audit JSON: old/new values, correction/deletion manifests as appropriate. |

Table constraints:

- `PRIMARY KEY (org_id, id)`
- `CHECK (jsonb_typeof(detail) = 'object')`

## Additional integrity rules

Temporal exclusions and spatial indexes are in migration 001. Partial unique indexes enforce one root per identity/review/location/survey/alert chain. Each successor is unique by `(org_id,supersedes)`. Migration 002 guards frame offsets, detection/measurement kind, run transitions/publication, append-only evidence and resolved location source status. Semantic JSON validation, exact-content retry comparison, RFID alignment, scale registration, geolocation uncertainty meaning and survey dedupe are trusted-adapter responsibilities.

## Rebuildable views

`current_identity`: current track decision. `active_location`: unsuperseded location revisions under current identity. `latest_animal_location`: newest accepted point by event time/UUID, with age and identity provenance. `current_review`: current finding review. `resolved_finding`: dynamic subject identity and review. `current_alert`: recorded lifecycle versus effective visibility. `current_survey`: current estimate with identity-recompute flag.

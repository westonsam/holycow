"""Static SQL/PLpgSQL parse, FK/key checks, fixture JSON and Python syntax.
Requires pglast. --write-dictionary regenerates dictionary+ER from 001_core.sql.
Does not connect to PostgreSQL or certify runtime semantics.
"""
import ast as python_ast
import json
from pathlib import Path
import sys
from pglast import ast, parse_sql, parse_plpgsql
from pglast.stream import RawStream

ROOT = Path(__file__).resolve().parents[1]
def render(node):
    return RawStream()(node)
tables = {}
descriptions = {
 'organization':'Tenant root; provisioned by a controlled onboarding administrator.',
 'membership':'External authenticated principal membership and product role. No passwords.',
 'ranch':'Administrative ranch/site, not a location observation.',
 'pasture':'Stable pasture identity; geometry is effective-dated separately.',
 'boundary_version':'Nonoverlapping effective pasture boundaries and versioned geofence policy.',
 'herd':'Stable managed herd with an administrative ranch.',
 'animal':'Permanent cattle identity, independent of external tag changes.',
 'animal_identifier':'Namespaced RFID/other external identifier; temporal reuse allowed.',
 'herd_membership':'One herd per animal at an instant, enforced by temporal exclusion.',
 'drone':'Tenant source device identity.',
 'flight':'Source capture session and optional actual coverage footprint.',
 'telemetry':'Timestamped drone state; never a cow ground location.',
 'clip':'Cow-parsed image sequence manifest; parsed identity remains a claim.',
 'media_asset':'Private image/video object and upload verification state.',
 'frame':'Captured image or video offset; source evidence input.',
 'model_version':'Immutable model artifact, taxonomy and confidence semantics.',
 'inference_run':'Versioned processing attempt and explicit publication state.',
 'run_input':'Exact same-flight frame inputs for one inference run.',
 'model_output':'Immutable original schema-versioned prediction, including conflicting runs.',
 'output_input':'Declared model-output provenance edges; adapter prevents multi-edge cycles.',
 'model_measurement':'Numeric model metric with versioned scale, separate from confidence.',
 'detection':'Indexed per-frame detection and normalized pixel box.',
 'track':'Temporary run-local object, not a permanent animal.',
 'track_detection':'A detection belongs to at most one track in its producing run.',
 'identity_decision':'Immutable track identity acceptance/rejection/unresolved chain.',
 'identity_evidence':'Original outputs supporting identity decisions, including RFID alignment.',
 'location_observation':'Resolved ground interpretation revisions per track/event; anonymous allowed.',
 'finding':'Resolved triage assessment with exactly one FK-backed subject.',
 'finding_evidence':'Inputs used by the finding policy, preserving conflicts/fusion lineage.',
 'finding_review':'Append-only reviewer decision chain; not a confirmed veterinary event.',
 'survey':'Resolved deduplicated herd estimate with uncertainty and supersession.',
 'survey_input':'Declared run set used by a survey; resolver verifies scope and publication.',
 'alert_rule_version':'Immutable alert policy version; execution/delivery service deferred.',
 'alert':'Deduplicated in-app alert instance, supported by a finding.',
 'alert_event':'Append-only lifecycle chain independent of finding severity/review.',
 'audit_event':'Attribution and recovery/correction/maintenance record; no secrets.'
}
meaning = {
 'org_id':'Owning organization UUID; part of every tenant-scoped key/FK and RLS context.',
 'id':'Stable internal UUID; database-generated unless a durable source mapping supplies it.',
 'name':'Human-readable editable name; not an identity or uniqueness guarantee.',
 'issuer':'Verified external authentication issuer; used with subject.',
 'subject':'External authentication subject; unique only within issuer.',
 'role':'Product authorization role, mapped by trusted backend to deployment role groups.',
 'ranch_id':'Tenant-scoped administrative ranch reference.', 'pasture_id':'Stable pasture reference.',
 'herd_id':'Tenant-scoped herd subject/assignment reference.',
 'animal_id':'Permanent cattle reference; identity acceptance requires a value.',
 'drone_id':'Source drone reference, separate from an animal.',
 'flight_id':'Capture flight reference; repeated in composite keys to prevent mixed-flight lineage.',
 'asset_id':'Source object reference; frame offset is relative to this asset.',
 'frame_id':'Specific source image/frame reference, also declared in run inputs.',
 'run_id':'Producing or contributing inference attempt reference.',
 'model_version_id':'Immutable artifact/version/taxonomy/confidence definition.',
 'output_id':'Original supporting/producing model output reference.',
 'input_output_id':'Input prediction consumed by another output; not an unconstrained polymorphic ID.',
 'detection_id':'FK-backed detection subject or association.',
 'track_id':'Temporary track subject/reference; identity may be unresolved.',
 'decision_id':'Identity decision being supported by evidence.',
 'finding_id':'Resolved finding reference.', 'survey_id':'Resolved survey reference.',
 'rule_version_id':'Frozen alert policy reference.', 'alert_id':'Alert instance reference.',
 'basis_identity_decision_id':'Optional frozen identity decision used by an identity-dependent alert; a changed current decision invalidates effective alert state.',
 'clip_id':'Optional parsed clip grouping; must share flight with asset.',
 'supersedes':'Previous same-subject revision; NULL means root, at most one successor/root.',
 'source_key':'Stable upstream idempotency key; scope is defined by UNIQUE constraints.',
 'request_key':'Tenant-scoped exact processing request key; new attempt requires a new key.',
 'local_key':'Temporary track ID, unique within producing run.',
 'namespace':'External identifier scope, e.g. rfid:ranch-reader-domain.',
 'value':'External identifier text or numeric model metric; see owning table/unit/scale.',
 'valid_during':'Effective UTC half-open [start,end) interval; nonempty, bounded start.',
 'geom':'Valid nonempty EPSG:4326 MultiPolygon pasture boundary; lon/lat degrees.',
 'coverage':'Optional actual flight coverage MultiPolygon in EPSG:4326; NULL is unknown.',
 'coverage_method':'Provenance/version for actual coverage estimation, required with footprint.',
 'surveyed_area':'Optional EPSG:4326 MultiPolygon representing surveyed ground area.',
 'position':'Estimated cow ground point, geography EPSG:4326 lon/lat; may be unknown.',
 'drone_position':'Drone point, geography EPSG:4326; never substitute as cow location.',
 'altitude_m':'Optional drone altitude in meters; reference datum must be in payload.',
 'uncertainty_m':'Optional nonnegative horizontal radius in meters; method defines interpretation.',
 'battery_percent':'Optional drone battery percent 0–100; not current without observation age.',
 'width_px':'Positive source image/video width in pixels.', 'height_px':'Positive source height in pixels.',
 'offset_ms':'Nonnegative milliseconds into video; zero for an independent image.',
 'duration_ms':'Positive clip/video duration in milliseconds; NULL for image assets.',
 'fps':'Positive image cadence (frames/second); initially 30 by user requirement.',
 'expected_image_count':'Positive clip manifest count, initially 300–450; uploader verifies completion.',
 'image_index':'Zero-based image sequence index; unique within clip.',
 'parsed_animal_id':'Optional candidate cattle UUID from cow-based parsing; not accepted identity.',
 'parsed_identifier':'Original cow-ID/RFID claim from parser for reconciliation.',
 'sensor_key':'Source camera/sensor identifier; capture payload carries calibration/pose as available.',
 'object_key':'Durable private storage key, tenant-unique; never an expiring signed URL.',
 'mask_object_key':'Optional private mask object key; uploader verifies storage authorization.',
 'sha256':'Lowercase hexadecimal SHA-256 of media content; uploader verifies actual bytes.',
 'artifact_sha256':'Lowercase hexadecimal model artifact SHA-256; immutable version provenance.',
 'size_bytes':'Positive object size in bytes, compared with uploaded content.',
 'kind':'Constrained source type or prediction output discriminator; see CHECK.',
 'state':'Upload lifecycle or alert lifecycle, depending on table; see CHECK.',
 'status':'Queued/running/succeeded/failed attempt state; terminal results are frozen.',
 'retry_of':'Optional prior failed attempt UUID; does not reuse its outputs or request key.',
 'model_name':'Stable descriptive model family name, tenant-scoped.',
 'version':'Immutable model/policy version text; unique within named family/key.',
 'taxonomy_version':'Class/label taxonomy definition version for output interpretation.',
 'score_meaning':'Meaning of confidence; not a guarantee of calibrated probability.',
 'calibration_version':'Optional calibration reference; NULL means unavailable/unasserted.',
 'score':'Optional model/identity confidence 0–1; distinct from metric value and geolocation accuracy.',
 'metric_code':'Filterable numeric metric, initially gait_locomotion or estrus_behavior; extensible.',
 'unit':'Explicit metric unit, e.g. ordinal_score; estrus behavior is not temperature.',
 'scale_version':'Immutable scoring-scale definition reference; no cross-scale comparison by default.',
 'scale_min':'Optional numeric score lower bound; both bounds must be present together.',
 'scale_max':'Optional numeric score upper bound; raw value must lie within known bounds.',
 'processing_version':'Version of adapter/preprocessing/postprocessing pipeline.',
 'config_schema':'Schema version for model configuration JSON.',
 'config':'Complete nonsecret config/thresholds for reproducibility; JSON object.',
 'payload_schema':'Schema version for telemetry payload.',
 'schema_version':'Schema version defining original model payload and variable details.',
 'capture_schema':'Schema version defining capture metadata.',
 'capture':'Capture metadata JSON (pose/calibration/clock claims if supplied); no fabricated capabilities.',
 'payload':'Original nonsecret schema-versioned telemetry/prediction object; unknowns explicit.',
 'detail_schema':'Schema version for audit detail.',
 'detail':'Nonsecret audit JSON: old/new values, correction/deletion manifests as appropriate.',
 'class_label':'Model taxonomy class label; source model version supplies taxonomy.',
 'x_min':'Normalized left box edge [0,1], top-left origin, half-open convention.',
 'y_min':'Normalized top box edge [0,1].', 'x_max':'Normalized right edge (x_min,1].',
 'y_max':'Normalized bottom edge (y_min,1].',
 'assessment':'Location acceptance or triage assessability, independently of health review.',
 'decision':'Identity/reviewer outcome; rejected/unresolved is not accepted.',
 'severity':'Info/review/priority triage severity, separate from review and alert lifecycle.',
 'label':'Finding taxonomy label; suspected score-based issue is not confirmed disease.',
 'method_version':'Versioned identity/geolocation/count algorithm or manual reconciliation method.',
 'policy_version':'Versioned interpretation/fusion/geofence policy identifier.',
 'actor':'Verified backend assertion of external auth identity or versioned processing identity.',
 'reason':'Required explanation for correction, missing evidence or review/lifecycle action.',
 'estimate':'Optional deduplicated cow count estimate; not number of output rows.',
 'lower_count':'Optional conservative lower count bound; present with estimate.',
 'upper_count':'Optional upper count bound; estimate lies between the bounds.',
 'coverage_fraction':'Optional surveyed/target area fraction 0–1; NULL is unknown.',
 'uncertainty_note':'Required count uncertainty/missingness explanation, including dedupe assumptions.',
 'rule_key':'Stable tenant-scoped alert policy name.',
 'policy':'Nonsecret alert configuration JSON object, frozen with version.',
 'dedupe_key':'Tenant-scoped semantic alert key to prevent duplicate alert creation.',
 'clock_quality':'Declared synchronization/clock quality; details in associated payload/capture.',
 'display_name':'Optional editable cattle label, distinct from permanent identity/tag namespace.',
 'action':'Audit action name; targets in versioned detail are audit descriptors, not domain FKs.'
}
times = {
 'created_at':'Creation instant', 'recorded_at':'Interpretation recording instant',
 'captured_at':'Source capture instant', 'observed_at':'Telemetry event instant',
 'event_at':'Animal/survey/finding event instant', 'ingested_at':'Database ingestion instant',
 'started_at':'Capture/processing start instant', 'ended_at':'Capture/processing completion instant',
 'decided_at':'Identity decision recording instant', 'reviewed_at':'Review recording instant',
 'happened_at':'Audit/alert lifecycle recording instant', 'opened_at':'Alert creation instant',
 'retired_at':'Optional animal retirement instant; evidence is preserved'
}
meaning.update({k:v+' (timestamptz, UTC interchange).' for k,v in times.items()})

statement_count = 0
body_count = 0
for path in sorted(ROOT.rglob('*.sql')):
    sql = '\n'.join(line for line in path.read_text(encoding='utf-8').splitlines()
                    if not line.startswith('\\'))
    nodes = parse_sql(sql)
    statement_count += len(nodes)
    for node in nodes:
        stmt = node.stmt
        if isinstance(stmt,(ast.CreateFunctionStmt,ast.DoStmt)):
            parse_plpgsql(render(stmt))
            body_count += 1
        if path.name == '001_core.sql' and isinstance(stmt,ast.CreateStmt):
            tables[stmt.relation.relname] = stmt

keys, fks = {}, []
for name, table in tables.items():
    keys[name] = set()
    for element in table.tableElts:
        if isinstance(element,ast.ColumnDef):
            constraints = element.constraints or ()
            for c in constraints:
                if c.contype.name in ('CONSTR_PRIMARY','CONSTR_UNIQUE'):
                    keys[name].add((element.colname,))
                if c.contype.name == 'CONSTR_FOREIGN':
                    fks.append((name,(element.colname,),c.pktable.relname,tuple(x.sval for x in c.pk_attrs)))
        elif isinstance(element,ast.Constraint):
            c = element
            if c.contype.name in ('CONSTR_PRIMARY','CONSTR_UNIQUE'):
                keys[name].add(tuple(x.sval for x in c.keys))
            if c.contype.name == 'CONSTR_FOREIGN':
                fks.append((name,tuple(x.sval for x in c.fk_attrs),c.pktable.relname,tuple(x.sval for x in c.pk_attrs)))
for child, columns, parent, target in fks:
    assert target in keys[parent], f'FK lacks declared unique target: {child} -> {parent}{target}'
    assert all(c in [x.colname for x in tables[child].tableElts if isinstance(x,ast.ColumnDef)] for c in columns)
    if parent != 'organization':
        assert 'org_id' in columns and 'org_id' in target, f'FK missing tenant: {child}->{parent}'

data = json.loads((ROOT/'examples/ingestion.json').read_text(encoding='utf-8'))
assert {x['kind'] for x in data['outputs']} == {'detection','identity','location','measurement','finding','survey'}
assert data['clip_upload']['expected_image_count'] == data['clip_upload']['fps']*data['clip_upload']['duration_ms']/1000
python_ast.parse((ROOT/'tests/concurrency.py').read_text(encoding='utf-8'))
assert set(tables) == set(descriptions), 'table dictionary descriptions incomplete'

if '--write-dictionary' in sys.argv:
    lines = ['# Data dictionary', '',
      'Generated from `migrations/001_core.sql`; regenerate with `tools/check_artifacts.py --write-dictionary`.', '',
      'All rows are owned by `org_id`, directly or through tenant-composite parents. Organization itself is the tenant root. '
      'All FK deletion behavior is NO ACTION; no domain cascades. UUID IDs default to `gen_random_uuid()`. '
      'NULL means unknown/not applicable, never an implicit zero. Every real instant is timezone-aware.', '',
      'SQL declarations below include type, NULL/default rules and column constraints. Table constraints follow each table. '
      'Composite primary-key columns are NOT NULL even where the column declaration omits that keyword. '
      'Provenance/link fields reference the owning tenant. Publication/immutability/access rules are in migration 002 and OPERATIONS.md.', '']
    for name, table in tables.items():
        lines += [f'## {name}', '',descriptions[name],'','| Field / SQL declaration | Meaning, units and provenance |','|---|---|']
        for col in table.tableElts:
            if isinstance(col,ast.ColumnDef):
                assert col.colname in meaning, f'field description missing: {name}.{col.colname}'
                lines.append(f'| `{render(col)}` | {meaning[col.colname]} |')
        constraints = [f'- `{render(c)}`' for c in table.tableElts if isinstance(c,ast.Constraint)]
        lines += ['','Table constraints:','',*constraints,''] if constraints else ['']
    lines += ['## Additional integrity rules','','Temporal exclusions and spatial indexes are in migration 001. Partial unique indexes enforce '
      'one root per identity/review/location/survey/alert chain. Each successor is unique by `(org_id,supersedes)`. '
      'Migration 002 guards frame offsets, detection/measurement kind, run transitions/publication, append-only evidence and resolved location source status. '
      'Semantic JSON validation, exact-content retry comparison, RFID alignment, scale registration, geolocation uncertainty meaning and survey dedupe are trusted-adapter responsibilities.', '',
      '## Rebuildable views','','`current_identity`: current track decision. `active_location`: unsuperseded location revisions under current identity. '
      '`latest_animal_location`: newest accepted point by event time/UUID, with age and identity provenance. '
      '`current_review`: current finding review. `resolved_finding`: dynamic subject identity and review. '
      '`current_alert`: recorded lifecycle versus effective visibility. `current_survey`: current estimate with identity-recompute flag.', '']
    (ROOT/'DATA_DICTIONARY.md').write_text('\n'.join(lines),encoding='utf-8')
    diagram=['# Entity relationship diagram','','Generated FK graph from migration 001. Each relationship is an actual foreign key. '
       'Multiple FK paths between the same tables are grouped. Cardinality on the child side is zero-to-many; '
       'nullable parent references and one-to-one uniqueness are detailed in the dictionary.','','```mermaid','erDiagram']
    for name, table in tables.items():
        diagram.append(f'    {name} {{')
        for col in table.tableElts:
            if isinstance(col,ast.ColumnDef) and col.colname in ('org_id','id','issuer','subject'):
                diagram.append(f'        {render(col.typeName)} {col.colname}')
        diagram.append('    }')
    for child,parent in sorted({(c,p) for c,_,p,_ in fks}):
        diagram.append(f'    {parent} ||--o{{ {child} : references')
    diagram += ['```','']
    (ROOT/'ERD.md').write_text('\n'.join(diagram),encoding='utf-8')
print(f'PASS: {statement_count} SQL statements, {body_count} function/DO bodies, '
      f'{len(tables)} tables, {len(fks)} FK targets/tenant scopes, example JSON, Python syntax.')
print('Static validation only: no PostgreSQL execution, role integration or benchmark.')

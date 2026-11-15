# Entity relationship diagram

Generated FK graph from migration 001. Each relationship is an actual foreign key. Multiple FK paths between the same tables are grouped. Cardinality on the child side is zero-to-many; nullable parent references and one-to-one uniqueness are detailed in the dictionary.

```mermaid
erDiagram
    organization {
        uuid id
    }
    membership {
        uuid org_id
        text issuer
        text subject
    }
    ranch {
        uuid org_id
        uuid id
    }
    pasture {
        uuid org_id
        uuid id
    }
    boundary_version {
        uuid org_id
        uuid id
    }
    herd {
        uuid org_id
        uuid id
    }
    animal {
        uuid org_id
        uuid id
    }
    animal_identifier {
        uuid org_id
        uuid id
    }
    herd_membership {
        uuid org_id
        uuid id
    }
    drone {
        uuid org_id
        uuid id
    }
    flight {
        uuid org_id
        uuid id
    }
    telemetry {
        uuid org_id
        uuid id
    }
    clip {
        uuid org_id
        uuid id
    }
    media_asset {
        uuid org_id
        uuid id
    }
    frame {
        uuid org_id
        uuid id
    }
    model_version {
        uuid org_id
        uuid id
    }
    inference_run {
        uuid org_id
        uuid id
    }
    run_input {
        uuid org_id
    }
    model_output {
        uuid org_id
        uuid id
    }
    output_input {
        uuid org_id
    }
    model_measurement {
        uuid org_id
        uuid id
    }
    detection {
        uuid org_id
        uuid id
    }
    track {
        uuid org_id
        uuid id
    }
    track_detection {
        uuid org_id
    }
    identity_decision {
        uuid org_id
        uuid id
    }
    identity_evidence {
        uuid org_id
    }
    location_observation {
        uuid org_id
        uuid id
    }
    finding {
        uuid org_id
        uuid id
    }
    finding_evidence {
        uuid org_id
    }
    finding_review {
        uuid org_id
        uuid id
    }
    survey {
        uuid org_id
        uuid id
    }
    survey_input {
        uuid org_id
    }
    alert_rule_version {
        uuid org_id
        uuid id
    }
    alert {
        uuid org_id
        uuid id
    }
    alert_event {
        uuid org_id
        uuid id
    }
    audit_event {
        uuid org_id
        uuid id
    }
    alert_rule_version ||--o{ alert : references
    finding ||--o{ alert : references
    identity_decision ||--o{ alert : references
    alert ||--o{ alert_event : references
    alert_event ||--o{ alert_event : references
    organization ||--o{ alert_rule_version : references
    organization ||--o{ animal : references
    animal ||--o{ animal_identifier : references
    organization ||--o{ audit_event : references
    pasture ||--o{ boundary_version : references
    animal ||--o{ clip : references
    flight ||--o{ clip : references
    model_output ||--o{ detection : references
    organization ||--o{ drone : references
    animal ||--o{ finding : references
    detection ||--o{ finding : references
    herd ||--o{ finding : references
    track ||--o{ finding : references
    finding ||--o{ finding_evidence : references
    model_output ||--o{ finding_evidence : references
    finding ||--o{ finding_review : references
    finding_review ||--o{ finding_review : references
    drone ||--o{ flight : references
    ranch ||--o{ flight : references
    media_asset ||--o{ frame : references
    ranch ||--o{ herd : references
    animal ||--o{ herd_membership : references
    herd ||--o{ herd_membership : references
    animal ||--o{ identity_decision : references
    identity_decision ||--o{ identity_decision : references
    track ||--o{ identity_decision : references
    identity_decision ||--o{ identity_evidence : references
    model_output ||--o{ identity_evidence : references
    flight ||--o{ inference_run : references
    inference_run ||--o{ inference_run : references
    model_version ||--o{ inference_run : references
    location_observation ||--o{ location_observation : references
    model_output ||--o{ location_observation : references
    track ||--o{ location_observation : references
    clip ||--o{ media_asset : references
    flight ||--o{ media_asset : references
    organization ||--o{ membership : references
    model_output ||--o{ model_measurement : references
    inference_run ||--o{ model_output : references
    run_input ||--o{ model_output : references
    organization ||--o{ model_version : references
    model_output ||--o{ output_input : references
    ranch ||--o{ pasture : references
    organization ||--o{ ranch : references
    frame ||--o{ run_input : references
    inference_run ||--o{ run_input : references
    flight ||--o{ survey : references
    herd ||--o{ survey : references
    survey ||--o{ survey : references
    inference_run ||--o{ survey_input : references
    survey ||--o{ survey_input : references
    flight ||--o{ telemetry : references
    inference_run ||--o{ track : references
    detection ||--o{ track_detection : references
    track ||--o{ track_detection : references
```

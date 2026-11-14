# Stage 2: Sydney dataset and leakage audit

Status: **cow-grouped research split prepared and tested; stage 2 is conditional, not fully cleared for model training**. The score-to-presentation numbering was audited in stage 1, but exact video boundaries and independence of original source recordings remain unresolved. Do not extract or train on the candidate intervals until those gates are addressed.

## Dataset and outcome

The primary source comprises 100 numbered presentations, 50 unique passings, and 34 cows. Each passing is shown twice; 13 cows have multiple passings. The first round contains presentation numbers 0–49 and the second 50–99. Scores consist of five observers scoring each presentation on a 0–3 ordinal scale. All original scores are retained in `ml/data/manifests/sydney_absolute_score_rows.csv`.

For this exploratory experiment, the predeclared passing-level target is the arithmetic mean of the ten original observer ratings: five observers for each of two presentations. It is a continuous summary in the range 0–3, not an individual observer's ordinal score or a diagnosis. No binary threshold or clinical alert level is defined. Analysis and models must support this target; the existing binary-only model and ROC/PR pipeline cannot be used as-is. The study describes several scoring protocols; this mean must not be represented as its preliminary expert-mode score. The choice was recorded before any model fitting or held-out evaluation.

Source study: https://www.journalofdairyscience.org/article/S0022-0302%2821%2900207-1/fulltext.

## Proposed locked split

`ml/splits/sydney_passing_split.csv` contains one row per passing, with its cow ID, both presentation numbers, and one split. Assignment is deterministic with seed 42, uses the existing `group_holdout` routine at nominal proportions 60/20/20, and does not use scores to assign groups. One cow may have multiple passings; all its passings and presentations stay in the same partition. No frames or clips were extracted.

| Split | Cows | Passings | Presentations | Observed passing-mean range |
| --- | ---: | ---: | ---: | ---: |
| Train | 18 | 30 | 60 | 0.0–3.0 |
| Validation | 8 | 10 | 20 | 0.4–3.0 |
| Test | 8 | 10 | 20 | 0.1–2.8 |

These are sample and score counts, not model performance. `sydney_split_audit.json` records the input and split SHA-256 values and per-split descriptive score distributions. The output files are versionable metadata; original footage stays git-ignored. The generator refuses to overwrite existing split artifacts. Repeated generation in a temporary directory produced a byte-identical split.

## Leakage and limitations

- Assertions confirm no cow, passing, or repeated presentation appears in more than one partition. Missing or inconsistent repeated identities raise errors. Assignment was also tested to be independent of score values.
- All presentations come from the same *compiled* video. Grouping by that container would put the entire dataset in one group, making a holdout impossible. Original recording identifiers beyond cow and passing are not established; therefore zero overlap between unknown source recordings cannot be asserted. Some animals and shared camera/background conditions may correlate across groups. The source is one dairy farm using a fixed camera, so this is not an external-farm, drone, pasture, or beef-cattle validation.
- Footage comes from three recording dates. Day/scene differences need to be checked during later robustness evaluation; the present split does not hold out a date or location.
- Presentation numbers are burned into the top-right of the video. They can leak identity/label information. Any future frame extraction must consistently remove this overlay and the unused black lower half while preserving usable views, and verify that preprocessing does not introduce new shortcuts. The IDs in the split CSV are for bookkeeping, not model input.
- The numbered presentation at each sampled midpoint was visually verified. Automated matching subsequently checked both endpoints for all 99 candidate transitions, with eight low-margin cases visually reviewed. The sampled label changes agree with the expected order, but these are not frame-exact timestamps and do not verify that the correct cow is visible throughout. Clip extraction, seek accuracy, margins, and overlay removal remain to be validated before training.
- The CattleLameness clips have unknown cow and source-video identities and therefore are excluded from this split and any leakage-safe comparison. Treat their original YouTube-sourced clips as restricted to research use; do not redistribute them without appropriate rights.
- The user verified commercial clearance for Sydney footage, but exact license/attribution details remain undocumented. No claim is made about commercial rights to the scoring spreadsheets or other datasets.

## Validation

Run `python3 -m unittest discover -s ml/tests -v` from the repo root. The stage 2 tests check deterministic assignment, repeated-identity grouping, bad or missing repeats, and independence from the score values. A separate check on the saved split verified the 50 passing IDs, 100 presentation IDs and 34 cow IDs are disjoint between partitions. `python3 -m ml.src.stage2_audit` creates the artifacts only if they do not already exist; use temporary output paths to reproduce without replacing the locked split.

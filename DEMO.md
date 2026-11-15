# Cow motion video demo

The Flight log now uses the supplied **trimmed-raw-demo.mov** through a YOLO11n
segmentation + APT-36K ViTPose pipeline adapted from the supplied Streamlit app.
The original app and README are preserved in `ml/reference/` for provenance;
Streamlit is not required by the dashboard service.

## Run the public demo

After publishing the updated frontend, double-click **Start Demo Backend.cmd**,
wait for CONNECTED, then open Flight log on the public dashboard.
Choose **Process cow video** and either load saved results or run fresh inference.
Stop with Ctrl+C, or double-click **Stop Demo Backend.cmd**.
The dashboard stays online when the laptop backend is disconnected.

## What is shown

- The raw MOV is normalized to silent H.264, 1280x720, 10 fps for browser playback
  and a repeatable CPU workload. This prepared copy is 10.1 seconds / 101 frames.
- Actual YOLO cow boxes/masks and APT-36K 17-point skeletons overlay that exact
  prepared input. A CPU pass in this workspace took about 42 seconds and produced
  ten temporary tracks; runtime and counts can vary with library/model versions.
- The 0-5 per-track values come from the supplied app's fixed illustrative list.
  They are not measured gait scores, lameness estimates or veterinary diagnoses.
- Video track IDs are short-term spatial associations, not registered cow tags.
- The supplied **cow-side-demo.mp4** is available as a separate annotated reference
  player. It has its own timing; its frames are not used to place interactive boxes.
- Saved-results mode loads genuine saved predictions. It never simulates inference.
- Reviews stay in SQLite at `ml/motion-demo-state/`. The old scene's database and
  assets remain inactive after restart, so old reviews cannot overlay the new video.
- The Telegram demo clip and dashboard cattle registry are separate and unchanged.

## Prepare on another machine

Use Python 3.11, then install `ml/requirements.txt` in the ML environment.
Copy the raw MOV to `ml/motion-demo-assets/source.mov` and the supplied annotated
MP4 to `ml/motion-demo-assets/provided-annotated.mp4` (media is ignored by Git).

```powershell
../.cow-vision-venv/Scripts/python.exe -m pip install -r ml/requirements.txt
../.cow-vision-venv/Scripts/python.exe ml/prepare_motion_demo.py --analyze
```

The first run downloads YOLO11n segmentation and ViTPose-small APT-36K weights
into `ml/models/motion/`. Later runs work offline with those local files.
`manifest.json` records source/playback hashes. `prepared.json` contains actual
boxes, segmentation polygons, keypoints, model description and timing.

To run only the HTTP service:

```powershell
../.cow-vision-venv/Scripts/python.exe ml/demo_service.py --port 8765
```

The service defaults to the prepared motion video; `HOLYCOW_DEMO_SOURCE`, if set,
must point to that exact matching prepared playback. It does not accept arbitrary
paths from browser requests. The existing same-origin Worker proxy, authenticated
laptop tunnel, idempotent jobs, progress, byte-range streaming and append-only
reviews remain in place.

## Verification

```powershell
../.cow-vision-venv/Scripts/python.exe -m unittest discover -s ml -p test_demo_service.py
npm --prefix web run typecheck
```

With a local Worker proxy connected to an isolated service, run
`npm --prefix web run test:demo` with TEST_ORIGIN set to that Worker URL.

Ultralytics and model/dependency licensing from the supplied prototype still
applies. This prototype is a visualization, not 3D reconstruction or a validated
health-assessment system.

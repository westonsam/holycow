# Cow segmentation demo

For the end-to-end dashboard workflow, read [DEMO.md](../DEMO.md). `demo_service.py` wraps this pipeline over loopback HTTP with background jobs and SQLite review history. `prepare_demo.py` prepares playback and compact boxes from actual pipeline output; the labeled precomputed mode runs without inference or ML imports. The browser accesses it only through the web control layer.

For the prepared Windows environment, run `./run-demo.ps1` from this directory.
It renders boxes and masks, then validates the resulting video and prediction
coordinates. Pass `-Source`, `-Output`, or `-Python` to override its defaults.
The model is specific to the supplied clip; a new source needs retraining.

See [DATASETS.md](DATASETS.md) for an assessment of the four suggested links,
their annotation types, and a training path for a model that handles new flights.
The linked datasets were not used to train the bundled scene model.

This prototype segments individual light-colored cattle in the supplied Pexels
drone clip and renders green bounding boxes. It runs locally on CPU, processes
every frame by default, and exports approximate instance polygons and temporary
track IDs. No footage is uploaded.

## Run

Python 3.11 is recommended. From this directory:

```powershell
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements.txt
.venv/Scripts/python.exe cow_segment.py "C:/Users/fbook/Downloads/13277315-uhd_3840_2160_25fps.mp4"
```

The prepared environment for this workspace is also available at
`C:/SchoolProjects/holycow/.cow-vision-venv/Scripts/python.exe`.

Outputs are `outputs/cows-boxed.mp4`, `outputs/cows-boxed.jsonl`, metadata, and
preview JPEGs. The MP4 is silent H.264 at 1920x1080 and the original 25 fps. Use
`--output-width 0` for original 4K output, `--masks` to display masks as well as
boxes, and `--start 16 --duration 2` for a short excerpt. JSON coordinates always
refer to the original source pixels. Each row specifies whether predictions came
from the model or optical flow (`--stride N` enables optional interpolation).

To render an existing prediction file with masks, without repeating inference:

```powershell
.venv/Scripts/python.exe render_predictions.py "C:/Users/fbook/Downloads/13277315-uhd_3840_2160_25fps.mp4" outputs/cows-boxed.jsonl --output outputs/cows-segmented.mp4 --masks
.venv/Scripts/python.exe validate_output.py outputs/cows-boxed.mp4
```

## Saved model

`weights/scene-cattle/cattle-pixels.xml` is a trained OpenCV random forest with
32 trees. `cattle-color-lut.npy` accelerates inference using a quantized color
lookup table. `model.json` records the training settings and annotations.

Training uses 23 reviewed rectangles on the first frame, GrabCut weak foreground
masks, and sampled background pixels. It learns foreground colors in BGR, Lab,
and HSV. Connected-component filtering, interior-core splitting, temporal seeds,
and fragment joining turn the pixel predictions into approximate instances.
The rectangles are training annotations; boxes on subsequent frames are computed
from model predictions, not fixed coordinates or keyframed animations.

To reproduce training on the **original 3840x2160 clip**, run:

```powershell
.venv/Scripts/python.exe scene_model.py "C:/Users/fbook/Downloads/13277315-uhd_3840_2160_25fps.mp4"
```

`outputs/training-masks.jpg` shows the generated training masks for review.
Changing the source requires new annotations and retraining; bundled coordinates
apply only to this exact video. The model is color-based and does **not** recognize
cow species. General-purpose COCO Mask R-CNN and YOLO11 segmentation were tested
but frequently confused these small overhead animals with birds or sheep; they
are not dependencies of the delivered pipeline.

## Limits and validation

This is a scene-specific demo, not a general drone cattle model. Similar-colored
grass, road details, dark animals, touching bodies, and partial animals at frame
edges can cause false positives, missed detections, merged instances, or changing
IDs. Masks are approximate; fragment joining may fill gaps with a convex hull.
Forest vote fractions are not calibrated confidence scores. IDs are geometric
video tracks, not livestock registry identities. The displayed number is the
number of current predictions, not a verified herd census.

The output is visually checked at representative points and mechanically checked
for frame count, dimensions, timing, and valid box/polygon coordinates. There is
no held-out annotated dataset or measured generalization accuracy. Training-frame
performance is not independent validation.

For a production model, label masks on multiple drone flights and breeds, split
training/validation by flight, and fine-tune an instance segmentation network.
Keep the stock-footage license with demo assets; describe the footage as a demo
input rather than footage captured by the startup's own drone.

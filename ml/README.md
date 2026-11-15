# Machine learning workflows

## Active dashboard motion demo

The active pipeline is documented in [DEMO.md](../DEMO.md).
`motion_pipeline.py` adapts the supplied Streamlit prototype into timestamped
YOLO segmentation and ViTPose results for the dashboard. `motion_tracking.py`
retains its short-term IoU tracker. The original source is preserved in
`reference/herd_motion_streamlit.py`.

The dashboard launcher continues to use `ml/demo_service.py` and the motion
assets at `ml/motion-demo-assets/`. Install its dependencies from
`ml/requirements.txt`. The displayed scores are illustrative, not measured gait
or lameness scores.

## Top-view segmentation

For the earlier scene-specific cow segmentation demo, setup, and inference
instructions, see [top-view/README.md](top-view/README.md). Its service, model
files and saved predictions live separately under `top-view/` and are not
selected by the dashboard launcher.

## Side-view pose training

For the cattle pose training workflow, see [side-view/README.md](side-view/README.md)
and [cattle_keypoint_detection.ipynb](side-view/cattle_keypoint_detection.ipynb).
It uses the reference livestock dataset and the Python 3.11/PyTorch environment.

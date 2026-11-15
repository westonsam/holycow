# Herd motion prototype

A local image/video demo: YOLO11 segmentation detects cows, and an APT-36K animal pose model draws a 17-point skeleton on each detected cow. The 0–5 numbers are **fictional demo values**; they do not measure or correlate reliably with lameness. Cow IDs and illustrative scores use simple short-term box matching and can switch when cows overlap or disappear. This is 2D pose visualization, not 3D triangulation or a gait analysis model.

## Run

Requires Python 3.9–3.12 and internet on the first run to install packages and download pretrained weights. In Terminal, from this folder:

```sh
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

Choose an image or video, then click RUN ANALYSIS. Video defaults to the 7–20 second segment; adjust the start and end in the sidebar. Download the resulting PNG or MP4. Video processing can be slow on CPU, especially with several cows; start with a short side-view clip. Browser video preview is not guaranteed for the MP4 codec, but the file can be opened in a local player. Overlapping, distant, or obscured cows may be missed or have inaccurate keypoints.

Models: [Ultralytics YOLO11 segmentation](https://docs.ultralytics.com/tasks/segment/) and [rtmlib animal pose](https://github.com/Tau-J/rtmlib). Ultralytics is AGPL-3.0 or commercial; check all model and dependency licenses before product or commercial use.

Example output uses the public-domain image [Holstein cow](https://commons.wikimedia.org/wiki/File:Holstein_cow_(1).jpg).

On this computer, the dependencies have already been installed. From Terminal run:

```sh
cd /Users/sam/Documents/Codex/2026-11-14/okay
TORCH_HOME="$PWD/work/model-cache" YOLO_CONFIG_DIR="$PWD/work/yolo-config" work/venv/bin/streamlit run outputs/cow-demo/app.py
```

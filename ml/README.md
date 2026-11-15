# Motion pipeline

The active pipeline is documented in ../DEMO.md. `motion_pipeline.py` adapts the
user-supplied Streamlit prototype into a CLI that writes timestamped JSON for the
existing dashboard HTTP service. `motion_tracking.py` retains its short-term
IoU tracker. `reference/herd_motion_streamlit.py` preserves the supplied source.

The former scene-specific `cow_segment.py` and `demo-assets/` are legacy assets
and are no longer selected by the launcher or service defaults.

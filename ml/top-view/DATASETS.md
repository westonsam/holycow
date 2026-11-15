# Dataset assessment for the supplied drone video

The delivered weights are the existing scene-specific random forest trained from
frame-zero rectangles and GrabCut weak masks. None of the external datasets below
were used to train these weights. Predictions are approximate cow instances,
not evidence of a general-purpose cattle recognition model.

| Source | Labels and setting | Role in a future model |
| --- | --- | --- |
| [Cattle Detection and Counting in UAV Images](https://datasetninja.com/cattle-detection-and-counting-in-uav-images) | Outdoor UAV bounding boxes with cattle IDs and quality labels | Closest viewpoint for detector fine-tuning and counting; no pixel masks supplied by this listing. Listing states CC BY-NC-ND 4.0. |
| [Francesco/aerial-cows](https://huggingface.co/datasets/Francesco/aerial-cows) | Aerial object detection; image objects contain bounding boxes and categories | Additional small-object detection examples. The card's generic `cc` license label needs clarification from the original source before reuse. The displayed schema does not establish individual identities. |
| [Bristol Cows2021](https://data.bris.ac.uk/data/dataset/4vnrca7qw1642qlwxjadp87h7) | Detection/localisation, identification and pretrained weights; indoor overhead Holstein footage | Useful for identification research, with a substantial appearance/background difference from this outdoor clip. Non-Commercial Government Licence. |
| [Dataset Ninja Cows2021](https://datasetninja.com/cows2021) | A repackaging of Cows2021, with boxes around cattle torsos | Same underlying source as the Bristol link, not an independent dataset. This mirror contains images; obtain videos from the original source. |

For the original Cows2021 description, see the
[authors' paper](https://arxiv.org/abs/2105.01938). It describes 10,402 RGB images
and 301 videos, top-down in-barn, and oriented bounding boxes for tracklets.
Do not assume mirror image counts represent additional independent examples.

## Training beyond this clip

1. Use aerial bounding boxes to fine-tune a detector. Preserve background-only
   images and distinguish genuinely empty images from missing annotations.
2. Label or review pixel masks on representative drone frames to train an
   instance segmentation network. Rectangle corners are not segmentation masks.
   Include dark animals, touching cows, shadows, partial bodies and empty pasture.
3. Split by flight/video/herd before frame extraction or tiling; random adjacent
   frame splits would leak nearly identical cows/backgrounds into validation.
4. Evaluate box and mask precision/recall and AP on held-out flights, then check
   count error and ID switches on annotated videos. Temporary tracking IDs are
   separate from recognizing an animal across flights.

The current sample video is not an independent test set because its first frame
provided the training supervision. Mechanical output validation checks video and
coordinate integrity, not detection accuracy. Review source licenses before
training or distributing a commercial model.

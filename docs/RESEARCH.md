# Research notes

ChronoSpace sits next to three existing lines of work and does not claim to replace them.

**Single-image depth.** Depth Anything V2 (Yang et al., 2024) predicts relative depth from one RGB image. The Small checkpoint, quantized to ONNX by the `onnx-community` export, is the estimator used here. The project does not fine-tune it and does not report metric accuracy. MiDaS and related relative-depth models are the same family of idea: useful parallax, not a measured room.

**Promptable segmentation.** The Segment Anything line (Kirillov et al., 2023, and later SAM releases) separates “find this thing” from “name every pixel with a closed taxonomy.” SAM 3.1 on the Meta Model API is the integration point. The local heuristic segmenter exists so the product still runs, and so the demo can be scored against masks this repo painted. Those scores are not SAM scores.

**Single-view novel view and Gaussian splatting.** Methods that predict 3D Gaussians or multi-view images from one photo can look complete while inventing unseen surfaces. ChronoSpace does not run such a model. Disoccluded pixels stay unresolved unless a person asks for a hypothesis, and that hypothesis is stored as generative.

**Epistemic distinction.** The engineering contribution in this repository is the record that travels with the mesh: observed pixels, vision estimates, generated pixels, and human testimony are different objects in the JSON and different treatments in the shader. Provenance is not a confidence score. Model-native scores are kept only when a model emits them, with calibration marked `not_calibrated` unless a documented calibration exists. None does.

**What was not done.** No literature review is offered as a priority claim. No competitor is scored. Muse Spark Open was not trained, adapted, or served. No 4D Gaussian optimization was run.

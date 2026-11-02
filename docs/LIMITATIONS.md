# Limitations

- One photograph does not determine the hidden sides of a room. The camera is clamped. The view is a depth-displaced image, not a complete 3D scan and not a 360° reconstruction.
- Depth Anything V2 Small here is a quantized ONNX file running on CPU. Its values are relative. They are not meters, and they are not calibrated.
- The default segmenter is classical. Its labels (cupboard, sofa, record player, and the rest) are shape and color rules. They fail on photographs that do not match those rules. SAM 3.1 replaces a region only after a real API response.
- The painted references are drawings made for a known-answer demo and for the IoU table. They are labeled as painted references in the interface. They are not family photographs and they have no capture date.
- Cross-photo links use a shared heuristic label plus an HSV histogram correlation. They are proposals. There is no geometric verification, and confirming a link is a human act.
- A timeline of capture times appears only when at least two memories carry an authorized EXIF time or a date a person typed. Upload order is not history.
- Procedural hypothesis sketches are illustrations. Muse Image output, when present, is still a hypothesis and is clipped to the unobserved mask.
- Sound is a browser synthesizer chosen from labels or, if Muse Spark actually returns them, from a validated name list. It is not a reconstruction of room acoustics.
- Curtain and foliage motion is a sine displacement on a mask. It is not a fluid simulation. People are not animated because the segmenter does not attach motion to them; the shader only moves the motion mask.
- Gaussian splatting is not performed. Muse Spark Open is not hosted. No confidence number in the interface is a calibrated probability.
- This build was not able to call the Meta API: `MODEL_API_KEY` was unset. Live badges stay off until a call succeeds.

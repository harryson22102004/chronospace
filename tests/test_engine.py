import io

import numpy as np
import pytest
from PIL import Image

from services.epistemic.agent import local_turn
from services.epistemic.evaluate import run
from services.epistemic.pipeline import read_upload
from services.epistemic.samples import living_room
from services.epistemic.store import load_memory


def test_invalid_upload_is_rejected():
    with pytest.raises(ValueError):
        read_upload(b"not an image", False)


def test_exif_is_dropped_unless_authorized():
    image = Image.new("RGB", (80, 80), (20, 40, 60))
    exif = Image.Exif()
    exif[36867] = "1981:04:02 10:00:00"
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", exif=exif)
    raw = buffer.getvalue()
    _, capture, reliability = read_upload(raw, False)
    assert capture is None
    assert reliability == "unknown"
    _, capture_yes, reliability_yes = read_upload(raw, True)
    assert capture_yes == "1981:04:02 10:00:00"
    assert reliability_yes == "exif"
    saved = io.BytesIO()
    rgb, _, _ = read_upload(raw, True)
    Image.fromarray(rgb).save(saved, format="JPEG", quality=92)
    reopened = Image.open(io.BytesIO(saved.getvalue()))
    assert not reopened.getexif().get(36867)


def test_painted_room_measurements_and_agent():
    report = run()
    iou = report["segmentation_iou"]
    assert iou["window"]["iou"] > 0.8
    assert iou["window"]["matched_label"] == "window"
    assert iou["cupboard"]["matched_label"] == "cupboard"
    assert iou["record player"]["iou"] > 0.5
    assert iou["unobserved corner"]["matched_label"] == "unobserved corner"
    assert report["depth"]["model_id"] == "depth-anything-v2-small-q4"
    assert report["reconstruction"]["frontal_max_abs_channel_diff"] == 0
    assert report["provenance"]["hypothesis_preserves_pixels_outside_mask"] is True
    assert report["provenance"]["lineage_completeness"] == 1
    assert 0 < report["reconstruction"]["disocclusion_hole_fraction_dav2_shift18"] < 0.5

    memory = load_memory(
        next(
            path.parent.name
            for path in __import__("pathlib").Path(__import__("os").environ["CHRONOSPACE_DATA"]).glob("memories/*/memory.json")
        )
    )
    show = local_turn(memory, "Show me the old record player.")
    assert any(action["type"] == "focus_camera" and action["label"] == "record player" for action in show["actions"])
    assert "not calibrated" in show["narration"]

    hidden = local_turn(load_memory(memory["id"]), "What is behind this cupboard?")
    assert "unknown" in hidden["narration"].lower()
    assert "piano" not in hidden["narration"].lower()

    claim = local_turn(load_memory(memory["id"]), "My grandmother remembers a piano being next to the window.")
    assert "testimony" in claim["narration"].lower()
    assert "neither shows it nor proves it was absent" in claim["narration"]
    assert any(action["type"] == "offer_hypothesis" for action in claim["actions"])

    meters = local_turn(load_memory(memory["id"]), "How many meters from the sofa to the window?")
    assert "no distance in meters" in meters["narration"]

    year = local_turn(load_memory(memory["id"]), "What year was this taken?")
    assert "will not invent" in year["narration"]

    rgb, _ = living_room()
    assert rgb.shape[0] > 100
    assert np.isfinite(report["depth"]["spearman_vs_bottom_closer_dav2"])

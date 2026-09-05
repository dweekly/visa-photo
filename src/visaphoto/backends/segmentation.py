"""Crown and silhouette measurement from a person matte.

Segmentation is used here to MEASURE, which is always permitted. Using it to alter pixels is a
separate decision governed by each channel's operation policy - New Zealand prohibits placing a
cut-out head on a plain background outright. See requirements.py.

Model choice is pinned deliberately. rembg's current default is BRIA RMBG-2.0, whose weights
require a paid commercial agreement, so the model is never left to default. birefnet-general
(MIT weights) is used because u2net and isnet-general-use both erased a light-coloured jacket
on the reference photo. See NEGATIVE_RESULTS.md.
"""

from __future__ import annotations

from pathlib import Path

from ..measurements import Confidence, Measurement, MeasurementSet, Status
from ..thresholds import MATTE_BORDER_TOUCH_FRACTION

MODEL_NAME = "birefnet-general"

# Alpha above which a pixel counts as subject. Our own choice: high enough that the soft edge
# around hair does not inflate the silhouette, low enough not to erode it.
ALPHA_SOLID = 200

# A row must contain at least this many subject pixels to count as the top of the head, so a
# few stray matte specks cannot be mistaken for a crown.
MIN_ROW_PIXELS = 8


def measure(image_rgb, result: MeasurementSet) -> None:
    """Add matte-derived measurements to `result`. Never raises for a bad matte - it records
    the measurement as unavailable, because geometry from landmarks is still useful."""
    try:
        import numpy as np
        import rembg
    except Exception as exc:  # noqa: BLE001
        _unavailable(result, f"segmentation dependencies unavailable: {exc!r}")
        return

    result.backends["rembg"] = getattr(rembg, "__version__", "unknown")
    result.backends["segmentation_model"] = MODEL_NAME

    try:
        session = rembg.new_session(MODEL_NAME)
        cut = rembg.remove(image_rgb, session=session)
        alpha = np.array(cut)[:, :, 3]
    except Exception as exc:  # noqa: BLE001
        _unavailable(result, f"segmentation failed: {exc!r}")
        return

    solid = alpha > ALPHA_SOLID
    per_row = solid.sum(axis=1)
    rows = np.where(per_row >= MIN_ROW_PIXELS)[0]

    if rows.size == 0:
        _unavailable(result, "the matte contains no solid subject region")
        return

    top = int(rows.min())
    width = solid.shape[1]

    # A head that continues past the top of the frame is truncated, not measured. Reporting the
    # image edge as the crown would silently produce a confident, wrong head height.
    if top == 0 and per_row[0] > width * MATTE_BORDER_TOUCH_FRACTION:
        _unavailable(
            result,
            "the subject reaches the top edge of the image; the crown is outside the frame "
            "or the photo is cropped too tightly to measure it",
        )
    else:
        result.add(Measurement(
            name="crown_y",
            definition=(
                "Topmost row of the person matte, i.e. the top of the head including hair. "
                "No face-landmark model locates this; it can only come from segmentation."
            ),
            status=Status.AVAILABLE, value=float(top), unit="px",
            backend=f"rembg/{MODEL_NAME}", confidence=Confidence.MEASURED,
        ))

    # Silhouette width measured across the head, not the shoulders: sample between the crown
    # and a quarter of the way down the subject, where the head is widest and the torso has
    # not yet entered.
    bottom = int(rows.max())
    head_band_end = top + max(1, (bottom - top) // 4)
    band = solid[top:head_band_end]
    widths = [
        int(np.where(r)[0].max() - np.where(r)[0].min() + 1) for r in band if r.any()
    ]
    if widths:
        result.add(Measurement(
            name="head_width_silhouette",
            definition=(
                "Widest horizontal extent of the matte across the upper quarter of the "
                "subject, INCLUDING hair. This is the quantity China's diagram appears to "
                "measure. It is not ICAO's ear-to-ear head width."
            ),
            status=Status.AVAILABLE, value=float(max(widths)), unit="px",
            backend=f"rembg/{MODEL_NAME}", confidence=Confidence.MEASURED,
        ))
    else:
        result.add(Measurement(
            name="head_width_silhouette",
            definition="Widest horizontal extent of the matte across the head.",
            status=Status.UNAVAILABLE, reason="no solid matte rows in the head band",
        ))


def _unavailable(result: MeasurementSet, reason: str) -> None:
    for name, definition in (
        ("crown_y", "Topmost row of the person matte (top of head including hair)."),
        ("head_width_silhouette", "Widest horizontal extent of the matte across the head."),
    ):
        result.add(Measurement(
            name=name, definition=definition, status=Status.UNAVAILABLE, reason=reason
        ))

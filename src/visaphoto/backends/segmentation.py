"""Person-matte fitting via rembg. Fit only - no gates, no measurements.

Segmentation is used to MEASURE, which is always permitted. Using it to alter pixels is a
separate decision governed by each channel's operation policy - New Zealand prohibits placing a
cut-out head on a plain background outright. See requirements.py.

Model choice is pinned deliberately. rembg's current default is BRIA RMBG-2.0, whose weights
require a paid commercial agreement, so the model is never left to default. birefnet-general
(MIT weights) is used because u2net and isnet-general-use both erased a light-coloured jacket
on the reference photo. See NEGATIVE_RESULTS.md.

The pure helpers at the bottom operate on a boolean matte and return values plus a status; they
are what the gate evaluators call. They never touch a MeasurementSet.
"""

from __future__ import annotations

import os
import pathlib
from dataclasses import dataclass

from ..thresholds import HEAD_WIDTH_BAND_BELOW_EYES

MODEL_NAME = "birefnet-general"

# Alpha above which a pixel counts as subject. Our own choice: high enough that the soft edge
# around hair does not inflate the silhouette, low enough not to erode it.
ALPHA_SOLID = 200

# A row must contain at least this many subject pixels to count as part of the head, so a few
# stray matte specks cannot be mistaken for a crown. This is the ONLY noise floor on the top
# edge: a component whose top row is row 0 is treated as touching the edge, full stop.
MIN_ROW_PIXELS = 8


def model_path() -> pathlib.Path:
    """Where rembg caches the segmentation weights.

    Mirrors rembg's own resolution order (REMBG_HOME, else XDG_DATA_HOME/rembg, else
    ~/.rembg), with U2NET_HOME still winning when set, as rembg does.
    """
    if os.getenv("U2NET_HOME"):
        home = pathlib.Path(os.path.expanduser(os.getenv("U2NET_HOME")))
    elif os.getenv("REMBG_HOME"):
        home = pathlib.Path(os.path.expanduser(os.getenv("REMBG_HOME")))
    elif os.getenv("XDG_DATA_HOME"):
        home = pathlib.Path(os.getenv("XDG_DATA_HOME")) / "rembg"
    else:
        home = pathlib.Path.home() / ".rembg"
    return home / "models" / MODEL_NAME / f"{MODEL_NAME}.onnx"


@dataclass(frozen=True)
class MatteFit:
    attempted: bool
    weights_present: bool | None
    alpha: object | None
    """uint8 alpha array (H, W), or None."""
    version: str | None = None
    error: str | None = None


NOT_ATTEMPTED = MatteFit(attempted=False, weights_present=None, alpha=None)


def fit(image_rgb) -> MatteFit:
    """Run segmentation if - and only if - the weights are already on disk.

    Never downloads. rembg fetches weights lazily inside new_session(), which would turn
    "measure this photo" into an unannounced network request and a long wait, and contradict
    the promise that processing works offline once installed. Fetching is `--fetch-models`.
    """
    try:
        import numpy as np
        import rembg
    except Exception as exc:  # noqa: BLE001
        return MatteFit(True, None, None, None, f"segmentation dependencies unavailable: {exc!r}")

    version = getattr(rembg, "__version__", "unknown")
    weights = model_path()
    if not weights.is_file():
        return MatteFit(True, False, None, version,
                        f"segmentation weights are not present at {weights}; run "
                        "'visa-photo --fetch-models' once")
    try:
        session = rembg.new_session(MODEL_NAME)
        cut = rembg.remove(image_rgb, session=session)
        alpha = np.array(cut)[:, :, 3]
    except Exception as exc:  # noqa: BLE001
        return MatteFit(True, True, None, version, f"segmentation failed: {exc!r}")
    return MatteFit(True, True, alpha, version)


# --- pure matte helpers, called by gate evaluators -----------------------------------------


def solid_mask(alpha):
    return alpha > ALPHA_SOLID


def face_component(solid, eye_xy: tuple[float, float] | None):
    """Return (component_mask, satisfied, detail) for the connected region under the eyes.

    Segmentation noise is not anatomy: one detached pixel near the frame edge inflated a
    measured head width from 200 px to 291 px. Every failure to isolate is *reported*, never
    silently substituted with the whole matte - which is what the Stage 1 helper did on five
    separate paths.
    """
    if eye_xy is None:
        return None, None, "eye position unavailable, so the face's component cannot be chosen"
    try:
        from scipy import ndimage
    except Exception as exc:  # noqa: BLE001
        return None, None, f"scipy unavailable ({exc!r}); connected components cannot be labelled"
    labels, count = ndimage.label(solid)
    row, col = int(round(eye_xy[1])), int(round(eye_xy[0]))
    if not (0 <= row < labels.shape[0] and 0 <= col < labels.shape[1]):
        return None, None, "eye midpoint lies outside the image"
    label = labels[row, col]
    if label == 0:
        return None, False, (
            "the pixel under the eyes is matte background; the matte does not contain the face"
        )
    return labels == label, True, f"component {label} of {count} selected under the eyes"


def top_row(solid) -> int | None:
    """Topmost row with at least MIN_ROW_PIXELS solid pixels, or None if there is none."""
    import numpy as np

    rows = np.where(solid.sum(axis=1) >= MIN_ROW_PIXELS)[0]
    return int(rows.min()) if rows.size else None


def head_band(solid, top: int, eye_line_y: float, chin_y: float):
    """Rows of the matte between the top and part-way from the eye line to the chin.

    Stops above the chin because the collar enters the silhouette before the chin row -
    measured on the reference photo, the widest row between crown and chin was the chin row
    itself, at 1236 px against a true head width of 1078. See HEAD_WIDTH_BAND_BELOW_EYES.
    Returns (band, detail) or (None, detail).
    """
    band_end = eye_line_y + (chin_y - eye_line_y) * HEAD_WIDTH_BAND_BELOW_EYES
    bottom = min(int(round(band_end)), solid.shape[0])
    if bottom <= top:
        return None, f"the band end (y={bottom}) is not below the matte top (y={top})"
    return solid[top:bottom], f"rows {top}-{bottom}"


def widest_row(band) -> int | None:
    import numpy as np

    widths = [int(np.where(r)[0].max() - np.where(r)[0].min() + 1) for r in band if r.any()]
    return max(widths) if widths else None

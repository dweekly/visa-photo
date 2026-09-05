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
from ..thresholds import HEAD_WIDTH_BAND_BELOW_EYES, MATTE_BORDER_TOUCH_FRACTION

MODEL_NAME = "birefnet-general"


def model_path() -> "pathlib.Path":
    """Where rembg caches the segmentation weights.

    Mirrors rembg's own resolution order (REMBG_HOME, else XDG_DATA_HOME/rembg, else
    ~/.rembg), with U2NET_HOME still winning when set, as rembg does.
    """
    import os
    import pathlib

    if os.getenv("U2NET_HOME"):
        home = pathlib.Path(os.path.expanduser(os.getenv("U2NET_HOME")))
    elif os.getenv("REMBG_HOME"):
        home = pathlib.Path(os.path.expanduser(os.getenv("REMBG_HOME")))
    elif os.getenv("XDG_DATA_HOME"):
        home = pathlib.Path(os.getenv("XDG_DATA_HOME")) / "rembg"
    else:
        home = pathlib.Path.home() / ".rembg"
    return home / "models" / MODEL_NAME / f"{MODEL_NAME}.onnx"

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

    # Never download during photo processing. rembg fetches weights lazily inside
    # new_session(), which would turn "measure this photo" into an unannounced network
    # request and a long wait - and contradict this project's promise that processing works
    # offline once installed. Fetching is a separate, explicit step.
    weights = model_path()
    if not weights.is_file():
        _unavailable(
            result,
            f"segmentation weights are not present at {weights}. Fetch them once with "
            "'visa-photo fetch-models'; photo processing never downloads anything.",
        )
        return

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

    width_px, reason = head_width_between(
        solid, top, result.value("eye_line_y"), result.value("chin_y_landmark")
    )
    if width_px is None:
        result.add(Measurement(
            name="head_width_silhouette",
            definition=HEAD_WIDTH_DEFINITION,
            status=Status.UNAVAILABLE,
            reason=reason or "the head width could not be measured",
        ))
    else:
        result.add(Measurement(
            name="head_width_silhouette",
            definition=HEAD_WIDTH_DEFINITION,
            status=Status.AVAILABLE, value=float(width_px), unit="px",
            backend=f"rembg/{MODEL_NAME}", confidence=Confidence.MEASURED,
        ))


HEAD_WIDTH_DEFINITION = (
    "Widest horizontal extent of the matte between the crown and the chin, INCLUDING hair. "
    "This is the quantity China's diagram appears to measure. It is not ICAO's ear-to-ear "
    "head width."
)


def _face_component(solid, result: MeasurementSet):
    """Keep only the connected foreground region containing the face.

    Segmentation noise is not anatomy. A single detached foreground pixel near the frame
    edge spans the row-width calculation and inflates a measured head width - reproduced at
    200px -> 291px by one stray pixel. Restricting to the component under the eyes removes
    that whole class.

    Falls back to the unmodified matte if the face position is unknown or the component
    cannot be identified; the caller's other guards still apply.
    """
    eye_x, eye_y = result.value("eye_mid_x"), result.value("eye_line_y")
    if eye_x is None or eye_y is None:
        return solid
    try:
        from scipy import ndimage
    except Exception:  # noqa: BLE001
        return solid
    labels, count = ndimage.label(solid)
    if count <= 1:
        return solid
    row, col = int(round(eye_y)), int(round(eye_x))
    if not (0 <= row < labels.shape[0] and 0 <= col < labels.shape[1]):
        return solid
    face_label = labels[row, col]
    if face_label == 0:
        return solid
    return labels == face_label


def head_width_between(
    solid, top: int, eye_line_y: float | None, chin_y: float | None
):
    """Widest run of subject pixels between the crown and the chin.

    Returns (width, None) or (None, reason).

    Bounded by the head, never by a fraction of the subject's height. A fraction is not a
    head: on a full-length photo the identical head yields shoulder width, and the result
    still looks like a confident measurement.

    The band stops part-way between the eye line and the chin rather than at the chin,
    because the collar enters the silhouette above the chin row - measured on the reference
    photo, the widest row between crown and chin was the chin row itself, at 1236 px against
    a true head width of 1078. See thresholds.HEAD_WIDTH_BAND_BELOW_EYES.
    """
    import numpy as np

    if chin_y is None or eye_line_y is None:
        return None, (
            "the chin or eye-line position is unavailable, so a head-only region of the matte "
            "cannot be isolated; a fraction of subject height would measure the torso instead"
        )
    # Stop above the chin: the collar and shoulders enter the silhouette before the chin row.
    band_end = eye_line_y + (chin_y - eye_line_y) * HEAD_WIDTH_BAND_BELOW_EYES
    head_bottom = min(int(round(band_end)), solid.shape[0])
    if head_bottom <= top:
        return None, (
            f"the chin (y={chin_y:.0f}) is not below the crown (y={top}); the matte and the "
            "landmarks disagree about where the head is"
        )
    band = solid[top:head_bottom]
    widths = [
        int(np.where(r)[0].max() - np.where(r)[0].min() + 1) for r in band if r.any()
    ]
    if not widths:
        return None, "the matte has no solid rows between the crown and the chin"

    # A head running off the side of the frame has no measurable width. Reporting the
    # clipped extent as a measurement is the same error as reporting the image edge as the
    # crown: confident, and wrong by an unknown amount.
    if band[:, 0].any() or band[:, -1].any():
        return None, (
            "the head touches the left or right edge of the image, so its full width is "
            "outside the frame and cannot be measured"
        )
    return max(widths), None


def _unavailable(result: MeasurementSet, reason: str) -> None:
    for name, definition in (
        ("crown_y", "Topmost row of the person matte (top of head including hair)."),
        ("head_width_silhouette", "Widest horizontal extent of the matte across the head."),
    ):
        result.add(Measurement(
            name=name, definition=definition, status=Status.UNAVAILABLE, reason=reason
        ))

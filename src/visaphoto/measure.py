"""Orchestration: source photo in, measurements plus a pre-flight report out.

Three passes, in this order and never interleaved:

1. **Fit** - run the landmarker and the segmenter; keep raw output only.
2. **Gates** - evaluate every precondition into a frozen record.
3. **Emit** - build every registry measurement by looking its gates up.

Nothing is emitted before its gates are known. See docs/STAGE1B-PRECONDITIONS.md.
"""

from __future__ import annotations

import os
from pathlib import Path

from . import preflight as preflight_mod
from .backends import landmarks, segmentation
from .evaluate import measure_all

MODEL_FILENAME = "face_landmarker.task"
MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/face_landmarker/"
    "face_landmarker/float16/1/face_landmarker.task"
)


class MeasurementError(RuntimeError):
    """The photo could not be measured at all: unreadable image, or no model bundle."""


def default_model_path() -> Path:
    """Where the landmarker bundle is cached. Overridable for tests and offline use."""
    override = os.environ.get("VISAPHOTO_MODEL")
    if override:
        return Path(override)
    cache = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "visa-photo"
    return cache / MODEL_FILENAME


def load_rgb(photo: Path):
    """Decode `photo` to an RGB PIL image.

    Decoding happens here, once, rather than letting each backend open the file itself.
    MediaPipe's own loader cannot read HEIC - which is what phones produce, so it is the
    common case, not an edge case - and registering the HEIF opener only helps Pillow.
    EXIF orientation is applied so every downstream measurement shares one coordinate frame.
    """
    from PIL import Image, ImageOps

    try:
        import pillow_heif

        pillow_heif.register_heif_opener()
    except Exception:  # noqa: BLE001 - HEIC support is optional
        pass
    with Image.open(photo) as image:
        return ImageOps.exif_transpose(image).convert("RGB")


def measure_photo(
    photo: Path,
    model: Path | None = None,
    jurisdiction: str | None = None,
    segmentation_enabled: bool = True,
):
    """Measure `photo` and run pre-flight checks.

    Raises MeasurementError only when nothing can start: the image is unreadable or the model
    bundle is absent. Everything else - no face, several faces, a failed model, an unusable
    matte - is recorded in the gate record and reflected as unavailable measurements, so the
    caller always receives the complete set and can say precisely what was and was not
    established.
    """
    import numpy as np

    model_path = model or default_model_path()
    if not model_path.is_file():
        raise MeasurementError(
            f"landmark model not found at {model_path}. Run 'visa-photo --fetch-models' "
            "or set VISAPHOTO_MODEL."
        )
    try:
        image = load_rgb(photo)
    except Exception as exc:  # noqa: BLE001
        raise MeasurementError(f"could not read {photo}: {exc}") from exc

    pixels = np.asarray(image)
    lm = landmarks.fit(image, model_path)
    matte = segmentation.fit(image) if segmentation_enabled else segmentation.NOT_ATTEMPTED

    result = measure_all(pixels, lm, matte, source=str(photo),
                         segmentation_attempted=segmentation_enabled)
    report = preflight_mod.run(result, dict(lm.blendshapes or {}), jurisdiction=jurisdiction)
    return result, report

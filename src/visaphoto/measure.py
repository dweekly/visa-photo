"""Orchestration: source photo in, measurements plus a pre-flight report out.

Three passes, in this order and never interleaved:

1. **Fit** - run the landmarker and the segmenter; keep raw output only.
2. **Gates** - evaluate every precondition into a frozen record.
3. **Emit** - build every registry measurement by looking its gates up.

Nothing is emitted before its gates are known. See docs/STAGE1B-PRECONDITIONS.md.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

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


@dataclass
class Source:
    """One decoded photograph, the snapshot every stage of an invocation works from.

    `native` is orientation-normalized and still in the file's own mode with its `info` intact
    (the embedded ICC profile, if any): rendering converts colour from it. `rgb` is the RGB view
    of the same pixels, which is what measurement reads.
    """

    native: Any
    rgb: Any


def load_source(photo: Path) -> Source:
    """Decode `photo` once.

    Decoding happens here rather than letting each backend open the file itself. MediaPipe's
    own loader cannot read HEIC - which is what phones produce, so it is the common case, not
    an edge case - and registering the HEIF opener only helps Pillow. EXIF orientation is
    applied so every downstream measurement shares one coordinate frame. Raises
    MeasurementError when the file cannot be decoded.
    """
    from PIL import Image, ImageOps

    try:
        import pillow_heif

        pillow_heif.register_heif_opener()
    except Exception:  # noqa: BLE001 - HEIC support is optional
        pass
    try:
        with Image.open(photo) as image:
            native = ImageOps.exif_transpose(image)
    except Exception as exc:  # noqa: BLE001 - any decode failure is the same to the caller
        raise MeasurementError(f"could not read {photo}: {exc}") from exc
    rgb = native if native.mode == "RGB" else native.convert("RGB")
    return Source(native=native, rgb=rgb)


def load_rgb(photo: Path):
    """The RGB view of `photo`, decoded once. See `load_source`."""
    return load_source(photo).rgb


def measure_photo(
    photo: Path,
    model: Path | None = None,
    jurisdiction: str | None = None,
    segmentation_enabled: bool = True,
    source: Source | None = None,
):
    """Measure `photo` and run pre-flight checks.

    `source` is the decoded snapshot when the caller already holds one (the CLI decodes once and
    renders from the same pixels); otherwise the photo is decoded here.

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
    image = (source or load_source(photo)).rgb

    pixels = np.asarray(image)
    lm = landmarks.fit(image, model_path)
    matte = segmentation.fit(image) if segmentation_enabled else segmentation.NOT_ATTEMPTED

    result = measure_all(pixels, lm, matte, source=str(photo),
                         segmentation_attempted=segmentation_enabled)
    report = preflight_mod.run(result, dict(lm.blendshapes or {}), jurisdiction=jurisdiction)
    return result, report

"""Orchestration: source photo in, measurements plus a pre-flight report out."""

from __future__ import annotations

import os
from pathlib import Path

from . import preflight as preflight_mod
from .backends import landmarks
from .measurements import MeasurementSet

MODEL_FILENAME = "face_landmarker.task"
MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/face_landmarker/"
    "face_landmarker/float16/1/face_landmarker.task"
)


class MeasurementError(RuntimeError):
    """The photo could not be measured at all. Distinct from a measurement being unavailable."""


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
    segmentation: bool = True,
):
    """Measure `photo` and run pre-flight checks.

    Raises MeasurementError when nothing meaningful can be produced - no face, several faces,
    an unreadable image, or a missing model bundle. Individual measurements that cannot be
    made are recorded as unavailable rather than raising.
    """
    model_path = model or default_model_path()
    if not model_path.is_file():
        raise MeasurementError(
            f"landmark model not found at {model_path}. Download it from {MODEL_URL} "
            "or set VISAPHOTO_MODEL."
        )

    try:
        image = load_rgb(photo)
    except Exception as exc:  # noqa: BLE001
        raise MeasurementError(f"could not read {photo}: {exc}") from exc

    result = MeasurementSet(
        source=str(photo), image_width=image.width, image_height=image.height
    )

    try:
        blendshapes = landmarks.measure(image, model_path, result)
    except landmarks.LandmarkError as exc:
        raise MeasurementError(str(exc)) from exc

    if segmentation:
        _segmentation_measure(image, result)

    report = preflight_mod.run(result, blendshapes, jurisdiction=jurisdiction)
    return result, report


def _segmentation_measure(image, result: MeasurementSet) -> None:
    from .backends import segmentation as seg

    seg.measure(image, result)

"""Face landmark fitting via MediaPipe. Fit only - no gates, no measurements.

This module runs the model and returns what it returned. Deciding what any of it means happens
in `evaluate.py`, after every gate has been evaluated, so that nothing here can emit a value
before its preconditions are known. That ordering was the structural cause of Stage 1's
repeated defect.

Version pin: mediapipe must be on the 0.10 line for macOS. 1.0.x aborts inside a Metal helper
during graph setup there, on both an unsupported and a supported Python. It works on Linux once
libGLESv2 is installed, and both produce identical values. See NEGATIVE_RESULTS.md.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Mapping

# Indices into MediaPipe's 478-point mesh. Topology is defined by canonical_face_model.obj in
# google-ai-edge/mediapipe (Apache-2.0). 468 and 473 are the iris centres, present only with
# the iris-refined bundle; 152 is the chin; 234/454 are the face-oval extremes. Conventional
# rather than formally specified; `evaluate.py` sanity-checks chin-below-eyes on every image.
IDX_CHIN = 152
IDX_IRIS_LEFT = 468
IDX_IRIS_RIGHT = 473
IDX_OVAL_LEFT = 234
IDX_OVAL_RIGHT = 454

LANDMARKS_WITH_IRIS = 478

# MediaPipe's num_faces is a MAXIMUM. Detecting with 1 cannot establish that only one face is
# present; this is set well above one so "exactly one" is a finding of an unrestricted search.
MAX_FACES_TO_DETECT = 4


@dataclass(frozen=True)
class LandmarkFit:
    """Raw model output for one image, in EXIF-normalized pixel coordinates."""

    faces: int
    """Faces found. -1 when the model itself failed to run; `error` says why."""
    points: tuple[tuple[float, float], ...] | None
    """(x, y) in pixels for the first face, or None when faces != 1."""
    blendshapes: Mapping[str, float] | None
    matrix: tuple[tuple[float, ...], ...] | None
    """The 4x4 facial transformation matrix, or None if the model returned none."""
    version: str
    error: str | None = None


def fit(image_rgb, model: Path) -> LandmarkFit:
    """Run the landmarker. Never raises for image content; model failures are recorded."""
    import numpy as np

    try:
        import mediapipe as mp
        from mediapipe.tasks import python as mp_python
        from mediapipe.tasks.python import vision
    except Exception as exc:  # noqa: BLE001
        return LandmarkFit(-1, None, None, None, "unavailable", f"mediapipe import failed: {exc!r}")

    version = getattr(mp, "__version__", "unknown")
    try:
        landmarker = vision.FaceLandmarker.create_from_options(
            vision.FaceLandmarkerOptions(
                base_options=mp_python.BaseOptions(model_asset_path=str(model)),
                output_face_blendshapes=True,
                output_facial_transformation_matrixes=True,
                num_faces=MAX_FACES_TO_DETECT,
            )
        )
        # Built from an array, not a path: MediaPipe's own loader cannot read HEIC.
        image = mp.Image(image_format=mp.ImageFormat.SRGB, data=np.asarray(image_rgb))
        detection = landmarker.detect(image)
    except Exception as exc:  # noqa: BLE001
        return LandmarkFit(-1, None, None, None, version, f"landmarker failed: {exc!r}")

    faces = len(detection.face_landmarks)
    if faces != 1:
        return LandmarkFit(faces, None, None, None, version)

    width, height = image.width, image.height
    marks = detection.face_landmarks[0]
    points = tuple((m.x * width, m.y * height) for m in marks)
    blendshapes = (
        MappingProxyType({c.category_name: float(c.score) for c in detection.face_blendshapes[0]})
        if detection.face_blendshapes else None
    )
    matrix = None
    if detection.facial_transformation_matrixes:
        raw = np.asarray(detection.facial_transformation_matrixes[0], dtype=float)
        matrix = tuple(tuple(float(x) for x in row) for row in raw)
    return LandmarkFit(faces, points, blendshapes, matrix, version)

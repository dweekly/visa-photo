"""Face landmark, pose and expression measurement via MediaPipe.

Version pin: mediapipe must be on the 0.10 line for macOS. 1.0.x aborts inside a Metal helper
during graph setup there, on both an unsupported and a supported Python. It works on Linux once
libGLESv2 is installed, and both produce identical values. See NEGATIVE_RESULTS.md.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

from ..measurements import Confidence, Measurement, MeasurementSet, Status

# Indices into MediaPipe's 478-point mesh. Topology is defined by canonical_face_model.obj in
# google-ai-edge/mediapipe (Apache-2.0). 468 and 473 are the iris centres, present only with
# the iris-refined bundle; 152 is the chin. These are conventional rather than formally
# specified, so `_sanity_check` verifies them against the image rather than trusting them.
IDX_CHIN = 152
IDX_IRIS_LEFT = 468
IDX_IRIS_RIGHT = 473
# Extremes of the face oval. NOT ICAO's ear-lobe reference points - see head_width note below.
IDX_OVAL_LEFT = 234
IDX_OVAL_RIGHT = 454

LANDMARKS_WITH_IRIS = 478


class LandmarkError(RuntimeError):
    pass


def _euler_degrees(matrix: Any) -> tuple[float, float, float]:
    """Decompose the 4x4 facial transformation matrix into (pitch, yaw, roll) in degrees.

    MediaPipe documents this matrix as a canonical-face-to-detected-face transform for applying
    effects; it is not documented as a calibrated pose estimate. Two backends disagreed by up to
    2.6 degrees on one image against an ICAO tolerance of +/-5. Hence Confidence.ADVISORY.
    """
    import numpy as np

    m = np.asarray(matrix)
    sy = math.sqrt(float(m[0, 0]) ** 2 + float(m[1, 0]) ** 2)
    if sy < 1e-6:  # gimbal lock
        return (
            math.degrees(math.atan2(-float(m[1, 2]), float(m[1, 1]))),
            math.degrees(math.atan2(-float(m[2, 0]), sy)),
            0.0,
        )
    return (
        math.degrees(math.atan2(float(m[2, 1]), float(m[2, 2]))),
        math.degrees(math.atan2(-float(m[2, 0]), sy)),
        math.degrees(math.atan2(float(m[1, 0]), float(m[0, 0]))),
    )


def measure(image_rgb, model: Path, result: MeasurementSet) -> dict[str, float]:
    """Add landmark-derived measurements to `result`. Returns the blendshape scores.

    Raises LandmarkError when no usable face is present - that is a hard stop for the whole
    pipeline, not an unavailable measurement, because nothing downstream is meaningful.
    """
    import numpy as np

    import mediapipe as mp
    from mediapipe.tasks import python as mp_python
    from mediapipe.tasks.python import vision

    result.backends["mediapipe"] = mp.__version__

    landmarker = vision.FaceLandmarker.create_from_options(
        vision.FaceLandmarkerOptions(
            base_options=mp_python.BaseOptions(model_asset_path=str(model)),
            output_face_blendshapes=True,
            output_facial_transformation_matrixes=True,
            num_faces=2,  # detect 2 so we can REPORT "more than one face", not silently take one
        )
    )
    # Built from an array, not a path: MediaPipe's own loader cannot read HEIC.
    image = mp.Image(image_format=mp.ImageFormat.SRGB, data=np.asarray(image_rgb))
    detection = landmarker.detect(image)

    faces = len(detection.face_landmarks)
    if faces == 0:
        raise LandmarkError("no face detected in the source image")
    if faces > 1:
        raise LandmarkError(
            f"{faces} faces detected; every specification surveyed requires the applicant alone"
        )

    marks = detection.face_landmarks[0]
    if len(marks) < LANDMARKS_WITH_IRIS:
        raise LandmarkError(
            f"model returned {len(marks)} landmarks, need {LANDMARKS_WITH_IRIS} "
            "(bundle lacks iris refinement)"
        )

    width, height = image.width, image.height

    def point(index: int) -> tuple[float, float]:
        return marks[index].x * width, marks[index].y * height

    chin_x, chin_y = point(IDX_CHIN)
    left_x, left_y = point(IDX_IRIS_LEFT)
    right_x, right_y = point(IDX_IRIS_RIGHT)
    eye_line = (left_y + right_y) / 2.0
    eye_mid_x = (left_x + right_x) / 2.0
    ied = math.hypot(right_x - left_x, right_y - left_y)

    _sanity_check(chin_y, eye_line, ied)

    add = result.add
    add(Measurement(
        name="chin_y_landmark",
        definition=(
            "Vertical position of the chin as fitted by the face mesh (anatomical chin "
            "contour). On a bearded subject this sits ABOVE the visible beard edge."
        ),
        status=Status.AVAILABLE, value=chin_y, unit="px",
        backend="mediapipe", confidence=Confidence.MEASURED,
    ))
    add(Measurement(
        name="chin_y_visible",
        definition=(
            "Vertical position of the lowest visible point of the chin or beard, as a "
            "specification measuring 'the base of the chin' on a bearded subject might mean."
        ),
        status=Status.UNSUPPORTED,
        reason=(
            "No backend here can isolate it. The person matte merges beard, neck and collar "
            "into one foreground region, so its lower boundary is the clothing, not the chin. "
            "Measured by hand on one image, this differed from the landmark chin by 85 px."
        ),
    ))
    add(Measurement(
        name="eye_line_y",
        definition="Mean vertical position of the two iris centres.",
        status=Status.AVAILABLE, value=eye_line, unit="px",
        backend="mediapipe", confidence=Confidence.MEASURED,
    ))
    add(Measurement(
        name="eye_mid_x",
        definition="Horizontal midpoint between the two iris centres.",
        status=Status.AVAILABLE, value=eye_mid_x, unit="px",
        backend="mediapipe", confidence=Confidence.MEASURED,
    ))
    add(Measurement(
        name="inter_eye_distance",
        definition="Euclidean distance between the two iris centres (ICAO IED).",
        status=Status.AVAILABLE, value=ied, unit="px",
        backend="mediapipe", confidence=Confidence.MEASURED,
    ))
    add(Measurement(
        name="head_width_face_oval",
        definition=(
            "Horizontal extent of the face-mesh oval (approximately temple to temple). This is "
            "NOT ICAO's head width, which is measured between the ear lobes, and NOT China's, "
            "whose diagram spans the hair. Do not compare it to either band."
        ),
        status=Status.AVAILABLE,
        value=abs(point(IDX_OVAL_RIGHT)[0] - point(IDX_OVAL_LEFT)[0]),
        unit="px", backend="mediapipe", confidence=Confidence.MEASURED,
    ))
    add(Measurement(
        name="head_width_ear_to_ear",
        definition=(
            "ICAO head width W: distance between lines through the upper and lower lobes of "
            "each ear (ISO/IEC 14496-2 feature points 10.1/10.2/10.5/10.6)."
        ),
        status=Status.UNSUPPORTED,
        reason=(
            "The face mesh has no landmarks we can justify mapping to ear-lobe feature points. "
            "Reporting the face-oval width under this name would silently answer a different "
            "question than ICAO asks."
        ),
    ))

    if detection.facial_transformation_matrixes:
        pitch, yaw, roll = _euler_degrees(detection.facial_transformation_matrixes[0])
        for name, value, axis in (
            ("pose_pitch", pitch, "up/down"),
            ("pose_yaw", yaw, "left/right turn"),
            ("pose_roll", roll, "in-plane tilt"),
        ):
            add(Measurement(
                name=name,
                definition=f"Head rotation, {axis}, from the facial transformation matrix.",
                status=Status.AVAILABLE, value=value, unit="deg",
                backend="mediapipe", confidence=Confidence.ADVISORY,
            ))
    else:
        for name in ("pose_pitch", "pose_yaw", "pose_roll"):
            add(Measurement(
                name=name, definition="Head rotation.", status=Status.UNAVAILABLE,
                reason="the model returned no facial transformation matrix",
            ))

    scores: dict[str, float] = {}
    if detection.face_blendshapes:
        scores = {c.category_name: float(c.score) for c in detection.face_blendshapes[0]}
    return scores


def _sanity_check(chin_y: float, eye_line: float, ied: float) -> None:
    """Catch a silently re-indexed landmark set, which would otherwise poison everything."""
    if chin_y <= eye_line:
        raise LandmarkError(
            f"chin (y={chin_y:.0f}) is not below the eye line (y={eye_line:.0f}); "
            "landmark indices may not mean what this build assumes"
        )
    if ied < 1.0:
        raise LandmarkError(f"degenerate inter-eye distance ({ied:.2f} px)")

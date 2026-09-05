#!/usr/bin/env python3
"""Stage 0 diagnostic: prove MediaPipe face landmarking runs and returns usable geometry.

This is a permanent reproducible diagnostic, not scaffolding. Run it when a dependency,
OS or machine changes, before trusting any measurement this project produces.

Why it exists
-------------
mediapipe 1.0.x could not be used at all on the development machine: FaceLandmarker aborts
during graph setup inside a Metal helper on macOS, and fails to load on headless Linux for
want of libGLESv2. mediapipe 0.10.x works. See NEGATIVE_RESULTS.md for traces and the
conditions each was observed under. That is why the dependency is pinned to the 0.10 line:
a documented failure, not a stylistic preference.

Usage
-----
    python tools/spikes/mediapipe_smoke.py PHOTO.jpg [--model face_landmarker.task]

Exits 0 only if a single face was found and every reported quantity was computed.
Exits 1 on any failure, with the reason on stderr. A silent success is not a pass:
the numbers are printed so a human can sanity-check them against the image.
"""

from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

# Landmark indices into MediaPipe's 478-point face mesh.
#
# Provenance: the canonical face model that defines this topology is
# mediapipe/modules/face_geometry/data/canonical_face_model.obj in google-ai-edge/mediapipe
# (Apache-2.0). Indices 468-477 are the iris points, present only when the model bundle
# includes iris refinement (the 478-point variant); 468 and 473 are the left and right iris
# centres. Index 152 is the chin.
#
# These indices are conventional rather than formally specified by Google, so they are
# verified empirically by --self-check below rather than trusted outright.
IDX_CHIN = 152
IDX_IRIS_LEFT = 468
IDX_IRIS_RIGHT = 473

# Minimum landmark count that indicates the iris-refined model is loaded. A 468-point result
# means the bundle lacks iris refinement and IDX_IRIS_* would be out of range or meaningless.
LANDMARKS_WITH_IRIS = 478


def euler_from_transform(matrix) -> tuple[float, float, float]:
    """Decompose MediaPipe's 4x4 facial transformation matrix into degrees (pitch, yaw, roll).

    CAUTION: MediaPipe documents this matrix as a canonical-face-to-detected-face transform
    intended for applying effects. It is not documented as a calibrated pose estimate, and two
    landmark models disagreed by up to 2.6 degrees on one test image (NEGATIVE_RESULTS.md).
    Treat the output as advisory until an acceptance gate against known angles has passed.
    """
    import numpy as np

    m = np.asarray(matrix)
    # Standard XYZ Euler extraction from a rotation matrix. sy guards the gimbal-lock branch.
    sy = math.sqrt(m[0, 0] ** 2 + m[1, 0] ** 2)
    if sy < 1e-6:
        return (
            math.degrees(math.atan2(-m[1, 2], m[1, 1])),
            math.degrees(math.atan2(-m[2, 0], sy)),
            0.0,
        )
    return (
        math.degrees(math.atan2(m[2, 1], m[2, 2])),
        math.degrees(math.atan2(-m[2, 0], sy)),
        math.degrees(math.atan2(m[1, 0], m[0, 0])),
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("photo", type=Path, help="portrait image to measure")
    parser.add_argument(
        "--model",
        type=Path,
        default=Path("face_landmarker.task"),
        help="path to the face_landmarker .task bundle",
    )
    args = parser.parse_args()

    if not args.photo.is_file():
        print(f"FAIL: no such image: {args.photo}", file=sys.stderr)
        return 1
    if not args.model.is_file():
        print(
            f"FAIL: no such model bundle: {args.model}\n"
            "Fetch it from "
            "https://storage.googleapis.com/mediapipe-models/face_landmarker/"
            "face_landmarker/float16/1/face_landmarker.task",
            file=sys.stderr,
        )
        return 1

    try:
        import mediapipe as mp
        from mediapipe.tasks import python as mp_python
        from mediapipe.tasks.python import vision
    except Exception as exc:  # noqa: BLE001 - we want the raw reason
        print(f"FAIL: mediapipe did not import: {exc!r}", file=sys.stderr)
        return 1

    print(f"mediapipe {mp.__version__}")

    try:
        landmarker = vision.FaceLandmarker.create_from_options(
            vision.FaceLandmarkerOptions(
                base_options=mp_python.BaseOptions(model_asset_path=str(args.model)),
                output_facial_transformation_matrixes=True,
                num_faces=1,
            )
        )
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL: could not create FaceLandmarker: {exc!r}", file=sys.stderr)
        return 1
    # NOTE: mediapipe 1.0.x does not raise here - it calls abort() and takes the process
    # with it, so this except block cannot catch that failure. The pinned 0.10.x line is
    # what makes this code path reachable at all.

    image = mp.Image.create_from_file(str(args.photo))
    result = landmarker.detect(image)

    faces = len(result.face_landmarks)
    if faces != 1:
        print(f"FAIL: expected exactly 1 face, found {faces}", file=sys.stderr)
        return 1

    landmarks = result.face_landmarks[0]
    if len(landmarks) < LANDMARKS_WITH_IRIS:
        print(
            f"FAIL: got {len(landmarks)} landmarks, need {LANDMARKS_WITH_IRIS} "
            "(model bundle lacks iris refinement)",
            file=sys.stderr,
        )
        return 1

    width, height = image.width, image.height

    def point(index: int) -> tuple[float, float]:
        return landmarks[index].x * width, landmarks[index].y * height

    chin_x, chin_y = point(IDX_CHIN)
    left_x, left_y = point(IDX_IRIS_LEFT)
    right_x, right_y = point(IDX_IRIS_RIGHT)
    eye_line = (left_y + right_y) / 2
    ied = math.hypot(right_x - left_x, right_y - left_y)

    print(f"image           {width} x {height}")
    print(f"landmarks       {len(landmarks)}")
    print(f"chin            x={chin_x:.0f} y={chin_y:.0f}")
    print(f"iris left       x={left_x:.0f} y={left_y:.0f}")
    print(f"iris right      x={right_x:.0f} y={right_y:.0f}")
    print(f"eye line        y={eye_line:.0f}")
    print(f"inter-eye dist  {ied:.0f} px")

    if not result.facial_transformation_matrixes:
        print("FAIL: no facial transformation matrix returned", file=sys.stderr)
        return 1
    pitch, yaw, roll = euler_from_transform(result.facial_transformation_matrixes[0])
    print(f"pose (advisory) pitch={pitch:.1f} yaw={yaw:.1f} roll={roll:.1f} deg")

    # Sanity checks that would catch a mis-indexed landmark set, which is the failure this
    # diagnostic is most likely to miss otherwise. A chin above the eyes, or eyes on top of
    # each other, means the indices no longer mean what the constants above claim.
    problems = []
    if chin_y <= eye_line:
        problems.append(f"chin (y={chin_y:.0f}) is not below the eye line (y={eye_line:.0f})")
    if ied < 1:
        problems.append(f"inter-eye distance is degenerate ({ied:.2f} px)")
    if problems:
        for problem in problems:
            print(f"FAIL: {problem}", file=sys.stderr)
        return 1

    print("OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())

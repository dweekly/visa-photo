"""Gates, then measurements. The second and third passes of `measure()`.

Given the raw fits, evaluate every gate in `gates.GATE_SPECS` order into a frozen record, then
build every registry measurement by looking its gates up. No value is emitted before its gates
are known; no gate reads an emitted value. See docs/STAGE1B-PRECONDITIONS.md.

Candidate values are computed here from the raw fits, but they only become measurements
through `registry.build`, which decides availability. A candidate computed on a photo whose
gates fail is simply discarded.
"""

from __future__ import annotations

import math
from typing import Mapping

from . import gates as G
from . import registry
from .backends import segmentation as seg
from .backends.landmarks import (
    IDX_CHIN, IDX_IRIS_LEFT, IDX_IRIS_RIGHT, IDX_OVAL_LEFT, IDX_OVAL_RIGHT,
    LANDMARKS_WITH_IRIS, LandmarkFit,
)
from .measurements import MeasurementSet
from .thresholds import (
    CHEEK_PATCH_DOWN_FRACTION, CHEEK_PATCH_OUTWARD_FRACTION, CHEEK_PATCH_SIZE_FRACTION,
    EYE_CLOSED_SCORE, EYE_PATCH_HALF_FRACTION, EYES_OBSCURED_RATIO, MIN_CHEEK_LUMINANCE,
    MIN_RAW_EYE_SEPARATION_PX, POSE_MEASUREMENT_LIMIT_DEG,
)

NEAR_WHITE = 240
"""Channel value at which a pixel counts as a specular highlight rather than skin or iris."""

_LANDMARK_INDEX = {
    "chin_152": IDX_CHIN, "iris_468": IDX_IRIS_LEFT, "iris_473": IDX_IRIS_RIGHT,
    "oval_234": IDX_OVAL_LEFT, "oval_454": IDX_OVAL_RIGHT,
}
_SIDE_IRIS = {"left": IDX_IRIS_LEFT, "right": IDX_IRIS_RIGHT}


def _luminance(patch) -> float:
    import numpy as np

    p = patch.astype(float)
    return float(np.mean(0.2126 * p[..., 0] + 0.7152 * p[..., 1] + 0.0722 * p[..., 2]))


def _euler(matrix) -> tuple[bool, tuple[float, float, float] | None, str]:
    """(valid, (pitch, yaw, roll) in degrees, detail).

    MediaPipe documents this matrix as a canonical-face-to-detected-face transform for applying
    effects; it is not documented as a calibrated pose estimate. Hence Confidence.ADVISORY on
    the pose measurements. A degenerate decomposition is reported as invalid, never as 0.0.
    """
    import numpy as np

    m = np.asarray(matrix, dtype=float)
    if m.shape != (4, 4):
        return False, None, f"matrix has shape {m.shape}, expected (4, 4)"
    if not np.all(np.isfinite(m)):
        return False, None, "matrix contains non-finite values"
    r = m[:3, :3]
    det = float(np.linalg.det(r))
    if not (0.5 < abs(det) < 2.0):
        return False, None, f"rotation block determinant {det:.3f} is not near +/-1"
    sy = math.sqrt(float(r[0, 0]) ** 2 + float(r[1, 0]) ** 2)
    if sy < 1e-6:
        return False, None, "gimbal lock: roll is undefined for this matrix"
    pitch = math.degrees(math.atan2(float(r[2, 1]), float(r[2, 2])))
    yaw = math.degrees(math.atan2(-float(r[2, 0]), sy))
    roll = math.degrees(math.atan2(float(r[1, 0]), float(r[0, 0])))
    return True, (pitch, yaw, roll), f"pitch {pitch:+.1f}, yaw {yaw:+.1f}, roll {roll:+.1f} deg"


class _Raw:
    """Everything the evaluators and candidates need, computed once and shared."""

    def __init__(self, pixels, lm: LandmarkFit, matte: seg.MatteFit):
        self.pixels = pixels
        self.height, self.width = pixels.shape[:2]
        self.lm = lm
        self.matte = matte
        self.pose = _euler(lm.matrix) if lm.matrix is not None else (False, None, "no matrix")
        self._solid = None
        self._component = None  # (mask, satisfied, detail)

    # --- landmarks ---------------------------------------------------------------------------
    def point(self, index: int) -> tuple[float, float] | None:
        if self.lm.points is None or index >= len(self.lm.points):
            return None
        return self.lm.points[index]

    def in_frame(self, index: int) -> bool | None:
        p = self.point(index)
        if p is None:
            return None
        return 0.0 <= p[0] < self.width and 0.0 <= p[1] < self.height

    @property
    def raw_eye_separation(self) -> float | None:
        a, b = self.point(IDX_IRIS_LEFT), self.point(IDX_IRIS_RIGHT)
        if a is None or b is None:
            return None
        return math.hypot(b[0] - a[0], b[1] - a[1])

    @property
    def eye_line(self) -> float | None:
        a, b = self.point(IDX_IRIS_LEFT), self.point(IDX_IRIS_RIGHT)
        return None if a is None or b is None else (a[1] + b[1]) / 2.0

    @property
    def eye_mid_x(self) -> float | None:
        a, b = self.point(IDX_IRIS_LEFT), self.point(IDX_IRIS_RIGHT)
        return None if a is None or b is None else (a[0] + b[0]) / 2.0

    # --- patches -----------------------------------------------------------------------------
    def eye_patch_bounds(self, side: str):
        p, d = self.point(_SIDE_IRIS[side]), self.raw_eye_separation
        if p is None or d is None:
            return None
        half = int(d * EYE_PATCH_HALF_FRACTION)
        if half < 1:
            return None
        return int(p[1]) - half, int(p[1]) + half, int(p[0]) - half, int(p[0]) + half

    def cheek_patch_bounds(self, side: str):
        p, d, mid = self.point(_SIDE_IRIS[side]), self.raw_eye_separation, self.eye_mid_x
        if p is None or d is None or mid is None:
            return None
        outward = 1.0 if p[0] >= mid else -1.0
        cx = p[0] + outward * CHEEK_PATCH_OUTWARD_FRACTION * d
        cy = p[1] + CHEEK_PATCH_DOWN_FRACTION * d
        half = int(d * CHEEK_PATCH_SIZE_FRACTION / 2.0)
        if half < 1:
            return None
        return int(cy) - half, int(cy) + half, int(cx) - half, int(cx) + half

    def bounds_in_frame(self, b) -> bool:
        top, bottom, left, right = b
        return top >= 0 and left >= 0 and bottom <= self.height and right <= self.width

    def patch(self, b):
        top, bottom, left, right = b
        return self.pixels[top:bottom, left:right]

    # --- matte -------------------------------------------------------------------------------
    @property
    def solid(self):
        if self._solid is None and self.matte.alpha is not None:
            self._solid = seg.solid_mask(self.matte.alpha)
        return self._solid

    def component(self):
        if self._component is None:
            if self.solid is None:
                self._component = (None, None, "no matte")
            else:
                eye = (self.eye_mid_x, self.eye_line)
                eye_xy = None if eye[0] is None or eye[1] is None else eye
                self._component = seg.face_component(self.solid, eye_xy)
        return self._component


def _evaluators(raw: _Raw, segmentation_attempted: bool) -> dict[str, G.Evaluator]:
    """One evaluator per gate that has evidence in this build. Each returns (satisfied, detail)."""
    ev: dict[str, G.Evaluator] = {}

    ev["image_decoded"] = lambda g: (True, f"{raw.width}x{raw.height} RGB")

    def face_detected_one(g):
        if raw.lm.faces < 0:
            return None, raw.lm.error or "the landmarker did not run"
        if raw.lm.faces == 1:
            return True, "exactly one face found in a search permitted to find several"
        return False, f"{raw.lm.faces} faces found"
    ev["face_detected_one"] = face_detected_one

    def landmarks_478(g):
        n = len(raw.lm.points or ())
        return n >= LANDMARKS_WITH_IRIS, f"{n} landmarks"
    ev["landmarks_478"] = landmarks_478

    for name, index in _LANDMARK_INDEX.items():
        def in_frame(g, index=index, name=name):
            ok = raw.in_frame(index)
            p = raw.point(index)
            if ok is None:
                return None, "landmark absent"
            return ok, f"{name} at ({p[0]:.0f}, {p[1]:.0f}) in {raw.width}x{raw.height}"
        ev[f"landmark_in_frame:{name}"] = in_frame

    def raw_sep(g):
        d = raw.raw_eye_separation
        if d is None:
            return None, "iris candidates absent"
        return d >= MIN_RAW_EYE_SEPARATION_PX, f"{d:.1f} px against {MIN_RAW_EYE_SEPARATION_PX}"
    ev["raw_eye_separation_usable"] = raw_sep

    def pose_valid(g):
        # No matrix is "not evaluated", not "invalid": the model made no claim to reject.
        if raw.lm.matrix is None:
            return None, "the model returned no facial transformation matrix"
        valid, _, detail = raw.pose
        return valid, detail
    ev["pose_decomposition_valid"] = pose_valid

    for i, axis in enumerate(("pitch", "yaw", "roll")):
        def within(g, i=i, axis=axis):
            angle = raw.pose[1][i]
            return (abs(angle) <= POSE_MEASUREMENT_LIMIT_DEG,
                    f"{axis} {angle:+.1f} deg against +/-{POSE_MEASUREMENT_LIMIT_DEG}")
        ev[f"{axis}_within_measurement_limit"] = within

    ev["blendshapes_present"] = lambda g: (
        raw.lm.blendshapes is not None, f"{len(raw.lm.blendshapes or {})} blendshapes")

    for side, key in (("left", "eyeBlinkLeft"), ("right", "eyeBlinkRight")):
        def eye_open(g, key=key):
            score = raw.lm.blendshapes.get(key)
            if score is None:
                return None, f"{key} not reported"
            return score <= EYE_CLOSED_SCORE, f"{key} {score:.3f} against {EYE_CLOSED_SCORE}"
        ev[f"eye_open:{side}"] = eye_open

    for side in ("left", "right"):
        def eye_patch(g, side=side):
            b = raw.eye_patch_bounds(side)
            if b is None:
                return None, "patch could not be sized"
            return raw.bounds_in_frame(b), f"rows {b[0]}-{b[1]}, cols {b[2]}-{b[3]}"
        ev[f"eye_patch_in_frame:{side}"] = eye_patch

        def cheek_patch(g, side=side):
            b = raw.cheek_patch_bounds(side)
            if b is None:
                return None, "patch could not be sized"
            return raw.bounds_in_frame(b), f"rows {b[0]}-{b[1]}, cols {b[2]}-{b[3]}"
        ev[f"cheek_patch_in_frame:{side}"] = cheek_patch

        def cheek_denominator(g, side=side):
            patch = raw.patch(raw.cheek_patch_bounds(side))
            if patch.size == 0:
                return False, "empty patch"
            lum = _luminance(patch)
            return lum > MIN_CHEEK_LUMINANCE, f"mean luminance {lum:.1f}"
        ev[f"cheek_denominator_valid:{side}"] = cheek_denominator

        def eye_unobscured(g, side=side):
            ratio = _luminance(raw.patch(raw.eye_patch_bounds(side))) / _luminance(
                raw.patch(raw.cheek_patch_bounds(side)))
            return ratio >= EYES_OBSCURED_RATIO, f"ratio {ratio:.3f} against {EYES_OBSCURED_RATIO}"
        ev[f"eye_unobscured:{side}"] = eye_unobscured

    ev["eyes_open_both"] = lambda g: (True, "both eyes open")
    ev["eyes_unobscured_both"] = lambda g: (True, "both eyes unobscured")

    def matte_present(g):
        if not segmentation_attempted:
            return None, "segmentation not attempted in this run"
        if raw.matte.alpha is None:
            return None, raw.matte.error or "no matte"
        return True, f"matte {raw.matte.alpha.shape[1]}x{raw.matte.alpha.shape[0]}"
    ev["matte_present"] = matte_present

    def matte_has_subject(g):
        top = seg.top_row(raw.solid)
        return top is not None, "solid rows present" if top is not None else "no solid rows"
    ev["matte_has_subject"] = matte_has_subject

    def isolated(g):
        _, ok, detail = raw.component()
        return ok, detail
    ev["face_component_isolated"] = isolated

    def clear_top(g):
        top = seg.top_row(raw.component()[0])
        if top is None:
            return None, "component has no solid rows"
        return top > 0, f"component top row {top}"
    ev["matte_clear_of_top_edge"] = clear_top

    def band(g):
        mask = raw.component()[0]
        top = seg.top_row(mask)
        chin = raw.point(IDX_CHIN)
        if top is None or chin is None or raw.eye_line is None:
            return None
        return seg.head_band(mask, top, raw.eye_line, chin[1])

    for edge, col in (("left", 0), ("right", -1)):
        def clear_side(g, col=col):
            result = band(g)
            if result is None or result[0] is None:
                return None, "head band unavailable"
            b, detail = result
            touches = bool(b[:, col].any())
            return not touches, f"{detail}; column {'0' if col == 0 else 'W-1'} {'touched' if touches else 'clear'}"
        ev[f"matte_clear_of_{edge}_edge"] = clear_side

    return ev


def _candidates(raw: _Raw) -> dict[str, float | None]:
    """Candidate values for every registry measurement. Only used where gates pass."""
    c: dict[str, float | None] = {}
    left, right = raw.point(IDX_IRIS_LEFT), raw.point(IDX_IRIS_RIGHT)
    chin, ol, orr = raw.point(IDX_CHIN), raw.point(IDX_OVAL_LEFT), raw.point(IDX_OVAL_RIGHT)

    c["eye_line_y"] = raw.eye_line
    c["eye_mid_x"] = raw.eye_mid_x
    c["inter_eye_distance"] = raw.raw_eye_separation
    c["raw_eye_separation"] = raw.raw_eye_separation
    c["chin_landmark_y"] = None if chin is None else chin[1]
    c["anatomical_chin_y"] = c["chin_landmark_y"]
    c["head_width_face_oval"] = None if ol is None or orr is None else abs(orr[0] - ol[0])

    if raw.pose[0]:
        pitch, yaw, roll = raw.pose[1]
        c["pose_pitch"], c["pose_yaw"], c["pose_roll"] = pitch, yaw, roll
    else:
        c["pose_pitch"] = c["pose_yaw"] = c["pose_roll"] = None

    for side in ("left", "right"):
        eb, cb = raw.eye_patch_bounds(side), raw.cheek_patch_bounds(side)
        ratio = spec = None
        if eb is not None and raw.bounds_in_frame(eb):
            eye = raw.patch(eb)
            spec = float((eye.max(axis=2) > NEAR_WHITE).mean()) if eye.size else None
            if cb is not None and raw.bounds_in_frame(cb):
                cheek = raw.patch(cb)
                denom = _luminance(cheek) if cheek.size else 0.0
                ratio = _luminance(eye) / denom if denom > 0 else None
        c[f"patch_brightness_ratio:{side}"] = ratio
        c[f"eye_specular_fraction:{side}"] = spec

    mask, ok, _ = raw.component()
    top = seg.top_row(mask) if mask is not None else None
    c["matte_top_row"] = None if top is None else float(top)
    c["anatomical_crown_y"] = c["matte_top_row"]
    width = None
    if top is not None and chin is not None and raw.eye_line is not None:
        b, _ = seg.head_band(mask, top, raw.eye_line, chin[1])
        width = seg.widest_row(b) if b is not None else None
    c["head_width_silhouette"] = None if width is None else float(width)
    return c


_MATTE_MEASUREMENTS = ("matte_top_row", "head_width_silhouette", "anatomical_crown_y")


def measure_all(pixels, lm: LandmarkFit, matte: seg.MatteFit, *, source: str,
                segmentation_attempted: bool) -> MeasurementSet:
    """Evaluate every gate, then emit every registry measurement. The complete set, always."""
    raw = _Raw(pixels, lm, matte)
    record = G.evaluate(source, _evaluators(raw, segmentation_attempted))
    candidates = _candidates(raw)

    result = MeasurementSet(source=source, image_width=raw.width, image_height=raw.height,
                            gate_record=record)
    result.backends["mediapipe"] = lm.version
    if matte.version:
        result.backends["rembg"] = matte.version
        result.backends["segmentation_model"] = seg.MODEL_NAME

    for name in registry.REGISTRY:
        if name in _MATTE_MEASUREMENTS and not segmentation_attempted:
            result.add(registry.not_attempted(name, "segmentation disabled for this run"))
            continue
        result.add(registry.build(name, candidates.get(name), record))
    return result

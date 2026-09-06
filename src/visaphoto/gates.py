"""Gates: the conditions that must hold before a measurement may be called available.

A gate is evaluated once per image, from raw model output and other gates, into a record that
is then frozen. Measurements are built afterwards by looking gates up; they never compute or
revise one. See docs/STAGE1B-PRECONDITIONS.md for the graph as a table, and PLAN.md ->
Measurement for why the design is inverted this way.

Three rules that this module makes structural rather than conventional:

* A gate is ``True`` only when its evidence was actually obtained and passed. A detector that
  could not run is ``None`` (not evaluated), never ``True``. ``not sunglasses_detected`` is not
  ``eyes_unobscured``.
* A gate whose prerequisite is ``None`` is ``None``, with the cause recorded.
* ``satisfied`` is exactly ``True`` / ``False`` / ``None``, checked by identity. Truthiness would
  let an empty string or a zero pass as "not evaluated" and a stray 1 pass as "true".
"""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Callable, Mapping

Evaluator = Callable[[Mapping[str, "Gate"]], tuple["bool | None", str]]

# Landmarks a measurement may depend on being inside the frame. Indices are MediaPipe's
# 478-point mesh (see backends/landmarks.py for provenance).
FRAME_LANDMARKS: tuple[str, ...] = ("chin_152", "iris_468", "iris_473", "oval_234", "oval_454")

_SIDES = ("left", "right")


@dataclass(frozen=True)
class GateSpec:
    """What a gate establishes, how, and what it needs first."""

    id: str
    method: str
    prerequisites: tuple[str, ...] = ()
    always_none: bool = False
    """True for conditions no evidence in this build can evaluate. They exist so the report
    shows the gap; they are never quietly assumed satisfied."""


def _spec(id: str, method: str, *prereqs: str, always_none: bool = False) -> GateSpec:
    return GateSpec(id=id, method=method, prerequisites=tuple(prereqs), always_none=always_none)


def _per_side(id_template: str, method: str, *prereq_templates: str) -> list[GateSpec]:
    return [
        _spec(id_template.format(side=s), method, *(p.format(side=s) for p in prereq_templates))
        for s in _SIDES
    ]


# Evaluation order is definition order. Each gate's prerequisites appear above it, so a single
# forward pass is a topological evaluation; `check_acyclic` asserts that at import time.
GATE_SPECS: tuple[GateSpec, ...] = (
    _spec("image_decoded", "Pillow decoded the file to RGB after EXIF transpose"),
    _spec("face_detected_one",
          "landmarker run with num_faces=4 returned exactly one face", "image_decoded"),
    _spec("landmarks_478", "result carries the iris-refined 478-point set", "face_detected_one"),
    *[
        _spec(f"landmark_in_frame:{name}",
              "0 <= x < W and 0 <= y < H in EXIF-normalized coordinates, before integer conversion",
              "landmarks_478")
        for name in FRAME_LANDMARKS
    ],
    _spec("raw_eye_separation_usable",
          "distance between iris centres >= MIN_RAW_EYE_SEPARATION_PX; diagnostic only",
          "landmark_in_frame:iris_468", "landmark_in_frame:iris_473"),
    _spec("pose_decomposition_valid",
          "matrix present, 4x4, finite, rotation block non-singular, Euler decomposition succeeded",
          "face_detected_one"),
    *[
        _spec(f"{axis}_within_measurement_limit",
              f"|{axis}| <= POSE_MEASUREMENT_LIMIT_DEG (a heuristic operating condition, not a "
              "destination's legal tolerance)",
              "pose_decomposition_valid")
        for axis in ("pitch", "yaw", "roll")
    ],
    _spec("blendshapes_present", "result carries the 52 blendshapes", "face_detected_one"),
    *_per_side("eye_open:{side}", "eyeBlink for that eye <= EYE_CLOSED_SCORE",
               "blendshapes_present"),
    *_per_side("eye_patch_in_frame:{side}", "that eye's patch rectangle lies wholly inside the image",
               "raw_eye_separation_usable"),
    *_per_side("cheek_patch_in_frame:{side}",
               "that eye's cheek patch lies wholly inside the image (no clipping permitted)",
               "raw_eye_separation_usable"),
    *_per_side("cheek_denominator_valid:{side}",
               "cheek patch non-empty and mean luminance > MIN_CHEEK_LUMINANCE",
               "cheek_patch_in_frame:{side}"),
    *_per_side("eye_unobscured:{side}",
               "that eye's brightness ratio >= EYES_OBSCURED_RATIO",
               "eye_patch_in_frame:{side}", "cheek_denominator_valid:{side}"),
    _spec("eyes_open_both", "both per-eye gates True", "eye_open:left", "eye_open:right"),
    _spec("eyes_unobscured_both", "both per-eye gates True",
          "eye_unobscured:left", "eye_unobscured:right"),
    _spec("matte_present", "segmentation ran with weights already on disk", "image_decoded"),
    _spec("matte_has_subject", "some row has >= MIN_ROW_PIXELS solid pixels", "matte_present"),
    _spec("face_component_isolated",
          "scipy available; eye midpoint inside frame; that pixel is foreground; its component "
          "selected. False when the eye pixel is background; None when scipy is missing",
          "matte_has_subject", "landmark_in_frame:iris_468", "landmark_in_frame:iris_473"),
    _spec("matte_clear_of_top_edge",
          "selected component's top row > 0 (top == 0 alone; MIN_ROW_PIXELS already excludes specks)",
          "face_component_isolated"),
    _spec("matte_clear_of_left_edge", "no solid pixel in column 0 within the head band",
          "face_component_isolated", "landmark_in_frame:chin_152",
          "landmark_in_frame:iris_468", "landmark_in_frame:iris_473"),
    _spec("matte_clear_of_right_edge", "no solid pixel in column W-1 within the head band",
          "face_component_isolated", "landmark_in_frame:chin_152",
          "landmark_in_frame:iris_468", "landmark_in_frame:iris_473"),
    # Conditions no evidence in this build can evaluate. Always None. They gate the anatomical
    # tier so that the gap between "where the matte ends" and "the top of the head" is visible.
    _spec("no_headwear", "no evidence available in this build", always_none=True),
    *[
        _spec(f"cheek_patch_on_skin:{s}", "no evidence available in this build", always_none=True)
        for s in _SIDES
    ],
    _spec("chin_landmark_is_anatomical",
          "no evidence available in this build (a beard hides the visible chin)", always_none=True),
)

GATE_BY_ID: Mapping[str, GateSpec] = MappingProxyType({g.id: g for g in GATE_SPECS})


def check_acyclic() -> None:
    """Every prerequisite must be defined earlier in GATE_SPECS. Enforced at import."""
    seen: set[str] = set()
    for spec in GATE_SPECS:
        for prereq in spec.prerequisites:
            if prereq not in seen:
                raise ValueError(
                    f"gate {spec.id!r} depends on {prereq!r}, which is not defined before it"
                )
        if spec.id in seen:
            raise ValueError(f"duplicate gate id {spec.id!r}")
        seen.add(spec.id)


check_acyclic()


@dataclass(frozen=True)
class Gate:
    """One evaluated gate."""

    id: str
    satisfied: bool | None
    detail: str

    def __post_init__(self) -> None:
        if self.id not in GATE_BY_ID:
            raise ValueError(f"unknown gate id {self.id!r}")
        if self.satisfied is not True and self.satisfied is not False and self.satisfied is not None:
            raise TypeError(
                f"{self.id}: satisfied must be exactly True, False or None, got {self.satisfied!r}"
            )
        if not self.detail:
            raise ValueError(f"{self.id}: an evaluated gate needs a detail")


class GateRecord:
    """The frozen result of evaluating every gate for one image.

    Built once by `evaluate`, which visits GATE_SPECS in order. Storage is private and the
    mapping exposed is read-only, so nothing downstream can add, remove or flip a gate.
    """

    __slots__ = ("_gates", "image_id")

    def __init__(self, image_id: str, gates: Mapping[str, Gate]):
        missing = [g.id for g in GATE_SPECS if g.id not in gates]
        extra = [k for k in gates if k not in GATE_BY_ID]
        if missing or extra:
            raise ValueError(f"gate record incomplete: missing={missing} extra={extra}")
        self.image_id = image_id
        self._gates: Mapping[str, Gate] = MappingProxyType(dict(gates))

    @property
    def gates(self) -> Mapping[str, Gate]:
        return self._gates

    def __getitem__(self, gate_id: str) -> Gate:
        return self._gates[gate_id]

    def to_dict(self) -> dict:
        return {
            "image_id": self.image_id,
            "gates": {
                k: {"satisfied": g.satisfied, "detail": g.detail} for k, g in self._gates.items()
            },
        }


def evaluate(image_id: str, evaluators: Mapping[str, "Evaluator"]) -> GateRecord:
    """Run every gate in topological order.

    ``evaluators`` maps a gate id to a callable taking the gates evaluated so far and returning
    ``(satisfied, detail)``. A gate with no evaluator, or one whose prerequisite is not ``True``,
    is recorded as ``None`` with the cause. A gate marked ``always_none`` is never called.
    """
    done: dict[str, Gate] = {}
    for spec in GATE_SPECS:
        if spec.always_none:
            done[spec.id] = Gate(spec.id, None, "no evidence available in this build")
            continue
        blocked = [p for p in spec.prerequisites if done[p].satisfied is not True]
        if blocked:
            causes = "; ".join(f"{p} is {done[p].satisfied}" for p in blocked)
            done[spec.id] = Gate(spec.id, None, f"prerequisite not satisfied: {causes}")
            continue
        evaluator = evaluators.get(spec.id)
        if evaluator is None:
            done[spec.id] = Gate(spec.id, None, "no evaluator ran for this gate")
            continue
        satisfied, detail = evaluator(MappingProxyType(done))
        done[spec.id] = Gate(spec.id, satisfied, detail)
    return GateRecord(image_id, done)


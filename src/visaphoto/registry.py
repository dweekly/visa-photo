"""The registry: which gates each measurement requires, and the only way to build one.

An emitter supplies a measurement *name* and a *candidate value*. This module looks up the
required gate ids, resolves each against a frozen `GateRecord`, and decides the status. Emitters
never assemble their own evidence, so a measurement and its requirements cannot drift apart in
two places at once - which is how Stage 1 shipped the same defect six times.

Tiers, from docs/STAGE1B-PRECONDITIONS.md:

* OBSERVED    - named for what was observed; available on a good photo; what profiles bind to.
* DIAGNOSTIC  - inputs to gates; recorded, never consumed by profiles.
* ANATOMICAL  - additionally gated on conditions no evidence here can evaluate; always
                unavailable in this build unless recorded human evidence supplies the gate.
"""

from __future__ import annotations

import enum
import math
from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping

from .gates import GATE_BY_ID, GateRecord
from .measurements import Confidence, Measurement, Precondition, Status


class Tier(enum.Enum):
    OBSERVED = "observed"
    DIAGNOSTIC = "diagnostic"
    ANATOMICAL = "anatomical"


@dataclass(frozen=True)
class MeasurementSpec:
    name: str
    definition: str
    unit: str
    tier: Tier
    backend: str
    confidence: Confidence
    gates: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.gates:
            raise ValueError(f"{self.name}: a measurement must declare at least one gate")
        unknown = [g for g in self.gates if g not in GATE_BY_ID]
        if unknown:
            raise ValueError(f"{self.name}: unknown gate ids {unknown}")
        if len(set(self.gates)) != len(self.gates):
            raise ValueError(f"{self.name}: duplicate gate ids")


_IRIS_IN_FRAME = ("landmark_in_frame:iris_468", "landmark_in_frame:iris_473")
_EYES_USABLE = (*_IRIS_IN_FRAME, "eyes_open_both", "eyes_unobscured_both")
_HORIZONTAL_POSE = ("yaw_within_measurement_limit", "roll_within_measurement_limit")
_MATTE_TOP = (
    "matte_present", "matte_has_subject", "face_component_isolated", "matte_clear_of_top_edge",
)


def _m(name, definition, unit, tier, backend, confidence, *gates) -> MeasurementSpec:
    return MeasurementSpec(name, definition, unit, tier, backend, confidence, tuple(gates))


_SPECS: tuple[MeasurementSpec, ...] = (
    # --- observed ---------------------------------------------------------------------------
    _m("eye_line_y", "Mean vertical position of the two iris centres.", "px",
       Tier.OBSERVED, "mediapipe", Confidence.MEASURED,
       "landmarks_478", *_EYES_USABLE, "pitch_within_measurement_limit"),
    _m("eye_mid_x", "Horizontal midpoint between the two iris centres.", "px",
       Tier.OBSERVED, "mediapipe", Confidence.MEASURED,
       "landmarks_478", *_EYES_USABLE, "pitch_within_measurement_limit", *_HORIZONTAL_POSE),
    _m("inter_eye_distance", "Euclidean distance between the two iris centres (ICAO IED).", "px",
       Tier.OBSERVED, "mediapipe", Confidence.MEASURED,
       *_EYES_USABLE, *_HORIZONTAL_POSE),
    _m("chin_landmark_y",
       "Vertical position of mesh vertex 152 - where the model placed the chin contour. On a "
       "bearded subject this sits above the visible beard edge; see anatomical_chin_y.", "px",
       Tier.OBSERVED, "mediapipe", Confidence.MEASURED,
       "landmarks_478", "landmark_in_frame:chin_152", "pitch_within_measurement_limit"),
    _m("head_width_face_oval",
       "Horizontal extent of the face-mesh oval (temple to temple). NOT ICAO's ear-to-ear width "
       "and NOT China's hair-inclusive width; do not compare to either band.", "px",
       Tier.OBSERVED, "mediapipe", Confidence.MEASURED,
       "landmark_in_frame:oval_234", "landmark_in_frame:oval_454", *_HORIZONTAL_POSE),
    *[
        _m(f"pose_{axis}", f"Head rotation, {desc}, from the facial transformation matrix.", "deg",
           Tier.OBSERVED, "mediapipe", Confidence.ADVISORY,
           "face_detected_one", "pose_decomposition_valid")
        for axis, desc in (("pitch", "up/down"), ("yaw", "left/right turn"), ("roll", "in-plane tilt"))
    ],
    _m("matte_top_row",
       "Topmost row of the selected person-matte component: the top of the head including hair. "
       "What China's diagram measures as the crown. Not the anatomical crown.", "px",
       Tier.OBSERVED, "rembg/birefnet-general", Confidence.MEASURED, *_MATTE_TOP),
    _m("head_width_silhouette",
       "Widest extent of the matte between its top row and halfway from the eye line to the chin, "
       "including hair. Not ICAO's ear-to-ear width.", "px",
       Tier.OBSERVED, "rembg/birefnet-general", Confidence.MEASURED,
       *_MATTE_TOP, "landmark_in_frame:chin_152", *_IRIS_IN_FRAME, "eyes_unobscured_both",
       "matte_clear_of_left_edge", "matte_clear_of_right_edge", *_HORIZONTAL_POSE),
    # --- diagnostic -------------------------------------------------------------------------
    _m("raw_eye_separation",
       "Distance between iris candidates, used only to size patches. Never a substitute for "
       "inter_eye_distance.", "px",
       Tier.DIAGNOSTIC, "mediapipe", Confidence.ADVISORY, "raw_eye_separation_usable"),
    *[
        _m(f"patch_brightness_ratio:{s}",
           f"Mean luminance of the {s} eye patch over the {s} cheek patch. Input to eye_unobscured:{s}.",
           "ratio", Tier.DIAGNOSTIC, "mediapipe+pixels", Confidence.ADVISORY,
           f"eye_patch_in_frame:{s}", f"cheek_denominator_valid:{s}")
        for s in ("left", "right")
    ],
    *[
        _m(f"eye_specular_fraction:{s}",
           f"Fraction of the {s} eye patch brighter than NEAR_WHITE: glare or a reflective lens.",
           "fraction", Tier.DIAGNOSTIC, "mediapipe+pixels", Confidence.ADVISORY,
           f"eye_patch_in_frame:{s}")
        for s in ("left", "right")
    ],
    # --- anatomical -------------------------------------------------------------------------
    _m("anatomical_crown_y", "Top of the head. Requires evidence that the matte top is not headwear.",
       "px", Tier.ANATOMICAL, "rembg/birefnet-general", Confidence.MEASURED,
       *_MATTE_TOP, "no_headwear"),
    _m("anatomical_chin_y", "Base of the chin. Requires evidence that vertex 152 is the chin.",
       "px", Tier.ANATOMICAL, "mediapipe", Confidence.MEASURED,
       "landmarks_478", "landmark_in_frame:chin_152", "pitch_within_measurement_limit",
       "chin_landmark_is_anatomical"),
)

REGISTRY: Mapping[str, MeasurementSpec] = MappingProxyType({s.name: s for s in _SPECS})


def build(name: str, candidate: float | None, record: GateRecord) -> Measurement:
    """The only path that produces an AVAILABLE or UNAVAILABLE measurement.

    ``candidate`` is what the emitter computed; it is used only if every required gate is True.
    A missing candidate with all gates True is an emitter bug and is rejected, not papered over.
    """
    spec = REGISTRY.get(name)
    if spec is None:
        raise KeyError(f"no measurement named {name!r} in the registry")
    preconditions = tuple(
        Precondition(id=g, satisfied=record[g].satisfied, detail=record[g].detail)
        for g in spec.gates
    )
    if all(p.satisfied is True for p in preconditions):
        if candidate is None or not math.isfinite(candidate):
            raise ValueError(
                f"{name}: every gate is satisfied but the candidate value is {candidate!r}"
            )
        return Measurement(
            name=name, definition=spec.definition, unit=spec.unit, backend=spec.backend,
            confidence=spec.confidence, status=Status.AVAILABLE, value=float(candidate),
            preconditions=preconditions,
        )
    return Measurement(
        name=name, definition=spec.definition, unit=spec.unit, backend=spec.backend,
        confidence=spec.confidence, status=Status.UNAVAILABLE, value=None,
        preconditions=preconditions,
    )


def not_attempted(name: str, why: str) -> Measurement:
    """A measurement this run chose not to make. Distinct from one it tried and could not."""
    spec = REGISTRY.get(name)
    if spec is None:
        raise KeyError(f"no measurement named {name!r} in the registry")
    return Measurement(
        name=name, definition=spec.definition, unit=spec.unit, backend=spec.backend,
        confidence=spec.confidence, status=Status.NOT_ATTEMPTED, value=None,
        preconditions=(), not_attempted_reason=why,
    )


def capabilities() -> list[dict]:
    """The capability matrix, generated. Needs no model weights."""
    rows = []
    for spec in _SPECS:
        gate_specs = [GATE_BY_ID[g] for g in spec.gates]
        rows.append({
            "measurement": spec.name,
            "tier": spec.tier.value,
            "definition": spec.definition,
            "unit": spec.unit,
            "backend": spec.backend,
            "confidence": spec.confidence.value,
            "required_gates": list(spec.gates),
            "always_unknown_gates": [g.id for g in gate_specs if g.always_none],
            "available_in_this_build": not any(g.always_none for g in gate_specs),
        })
    return rows

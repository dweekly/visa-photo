"""Pre-flight: check the SOURCE photo before any effort is spent cropping it.

No crop fixes a smile, sunglasses or closed eyes. This runs first, applies the qualitative
requirements transcribed in requirements.py, and reports one outcome per requirement.

Three modes, and the mode is always stated in the report:

* ``jurisdiction`` - the user told us where the photo is going and we have transcribed,
  cited requirements for it.
* ``generic``      - the user did not say. We report only what commonly causes a formal photo
  to be rejected across the jurisdictions we transcribed, and claim conformance with nothing.
* ``unseeded``     - the user named somewhere we have not transcribed. We say so plainly
  rather than guessing; a runtime lookup, if performed, is marked unverified.

An outcome is never invented. If we cannot assess something, that is what the report says.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass
from typing import Any

from .measurements import Flag, MeasurementSet
from .requirements import GENERIC_ADVISORIES, Check, Requirement, for_jurisdiction
from .thresholds import (
    EYE_CLOSED_SCORE,
    JAW_OPEN_SCORE,
    MIN_IED_PIXELS,
    SMILE_SCORE,
)


class Outcome(enum.Enum):
    LIKELY_OK = "likely_ok"
    """An advisory signal was checked and did not fire. NOT a statement of compliance."""

    WARN = "warn"
    """An advisory signal fired. The photo may need retaking; a human should look."""

    NOT_EVALUATED = "not_evaluated"
    """We have no signal for this requirement. Explicitly not a pass."""

    ATTESTATION_REQUIRED = "attestation_required"
    """Cannot be determined from pixels. The applicant must confirm it."""

    OPERATION_POLICY = "operation_policy"
    """Constrains what the tool may do to the photo rather than what the photo shows."""


@dataclass(frozen=True)
class Finding:
    requirement: Requirement
    outcome: Outcome
    detail: str
    score: float | None = None
    threshold: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "requirement": self.requirement.key,
            "quote": self.requirement.quote,
            "source": self.requirement.source,
            "jurisdictions": list(self.requirement.jurisdictions),
            "outcome": self.outcome.value,
            "detail": self.detail,
            "score": self.score,
            "threshold": self.threshold,
        }


@dataclass
class Preflight:
    mode: str
    jurisdiction: str | None
    findings: list[Finding]

    @property
    def warnings(self) -> list[Finding]:
        return [f for f in self.findings if f.outcome is Outcome.WARN]

    def to_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "jurisdiction": self.jurisdiction,
            "findings": [f.to_dict() for f in self.findings],
        }


def _expression_flags(scores: dict[str, float], result: MeasurementSet) -> dict[str, Flag]:
    """Advisory expression signals. Thresholds are uncalibrated - see thresholds.py."""
    flags: dict[str, Flag] = {}

    def pair(a: str, b: str) -> float | None:
        if a in scores and b in scores:
            return max(scores[a], scores[b])
        return None

    smile = pair("mouthSmileLeft", "mouthSmileRight")
    if smile is not None:
        flags["smile"] = Flag(
            name="smile", raised=smile > SMILE_SCORE, score=smile, threshold=SMILE_SCORE,
            detail=(
                f"smile score {smile:.3f} against an uncalibrated advisory threshold of "
                f"{SMILE_SCORE}"
            ),
        )

    jaw = scores.get("jawOpen")
    if jaw is not None:
        flags["mouth_open"] = Flag(
            name="mouth_open", raised=jaw > JAW_OPEN_SCORE, score=jaw,
            threshold=JAW_OPEN_SCORE,
            detail=f"jawOpen {jaw:.3f} against an uncalibrated advisory threshold of {JAW_OPEN_SCORE}",
        )

    blink = pair("eyeBlinkLeft", "eyeBlinkRight")
    if blink is not None:
        flags["eyes_closed"] = Flag(
            name="eyes_closed", raised=blink > EYE_CLOSED_SCORE, score=blink,
            threshold=EYE_CLOSED_SCORE,
            detail=(
                f"eye-closed score {blink:.3f} against an uncalibrated advisory threshold of "
                f"{EYE_CLOSED_SCORE}"
            ),
        )

    result.flags.extend(flags.values())
    return flags


def run(
    result: MeasurementSet,
    blendshapes: dict[str, float],
    jurisdiction: str | None = None,
) -> Preflight:
    flags = _expression_flags(blendshapes, result)
    ied = result.value("inter_eye_distance")

    if jurisdiction is None:
        mode, requirements, code = "generic", GENERIC_ADVISORIES, None
    else:
        code = jurisdiction.upper()
        requirements = for_jurisdiction(code)
        mode = "jurisdiction" if requirements else "unseeded"

    findings: list[Finding] = []
    for requirement in requirements:
        findings.append(_assess(requirement, flags, result))
    return Preflight(mode=mode, jurisdiction=code, findings=findings)


def _assess(
    requirement: Requirement, flags: dict[str, Flag], result: MeasurementSet
) -> Finding:
    if requirement.check is Check.USER_ATTESTATION:
        return Finding(requirement, Outcome.ATTESTATION_REQUIRED,
                       "cannot be determined from the image; the applicant must confirm it")
    if requirement.check is Check.OPERATION_POLICY:
        return Finding(requirement, Outcome.OPERATION_POLICY, requirement.note or
                       "constrains what this tool may do to the photo")
    if requirement.check is Check.NOT_ASSESSABLE:
        return Finding(requirement, Outcome.NOT_EVALUATED,
                       requirement.note or "no signal available in this build")

    if "pose" in requirement.signals:
        return _assess_pose(requirement, result)

    if "ied" in requirement.signals:
        ied = result.value("inter_eye_distance")
        if ied is None:
            return Finding(requirement, Outcome.NOT_EVALUATED,
                           "inter-eye distance could not be measured")
        detail = f"inter-eye distance {ied:.0f} px against an ICAO minimum of {MIN_IED_PIXELS:.0f}"
        if ied < MIN_IED_PIXELS:
            return Finding(requirement, Outcome.WARN,
                           detail + " - the source is too small for a compliant output at any crop",
                           score=ied, threshold=MIN_IED_PIXELS)
        return Finding(requirement, Outcome.LIKELY_OK, detail, score=ied,
                       threshold=MIN_IED_PIXELS)

    relevant = [flags[name] for name in requirement.signals if name in flags]
    if not relevant:
        return Finding(requirement, Outcome.NOT_EVALUATED,
                       "the model returned no scores for the signals this requirement needs")
    fired = [f for f in relevant if f.raised]
    if fired:
        return Finding(requirement, Outcome.WARN, "; ".join(f.detail for f in fired),
                       score=fired[0].score, threshold=fired[0].threshold)
    return Finding(requirement, Outcome.LIKELY_OK,
                   "; ".join(f.detail for f in relevant))


def _assess_pose(requirement: Requirement, result: MeasurementSet) -> Finding:
    """Check measured head angles against limits the source itself publishes.

    Both halves matter and are reported separately: the LIMIT is the destination's law, the
    MEASUREMENT is our uncalibrated estimate. A photo near a limit is not settled by this.
    """
    limits = requirement.numeric_limits or {}
    measured = {
        axis: result.value(f"pose_{axis}") for axis in ("pitch", "yaw", "roll")
    }
    if all(v is None for v in measured.values()):
        return Finding(requirement, Outcome.NOT_EVALUATED, "head pose could not be measured")

    exceeded, described = [], []
    for axis, value in measured.items():
        limit = limits.get(axis)
        if value is None or limit is None:
            continue
        described.append(f"{axis} {value:+.1f} deg (limit +/-{limit:.0f})")
        if abs(value) > limit:
            exceeded.append((axis, value, limit))

    detail = "; ".join(described) or "no comparable axes"
    if exceeded:
        axis, value, limit = exceeded[0]
        return Finding(
            requirement, Outcome.WARN,
            detail + f" - {axis} exceeds the published limit; our angle estimate is itself "
            "uncalibrated, so confirm by eye",
            score=abs(value), threshold=limit,
        )
    return Finding(requirement, Outcome.LIKELY_OK, detail)

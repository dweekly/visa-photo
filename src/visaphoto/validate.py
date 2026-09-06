"""Validation: verdicts on a file, from the file.

The solver's plan predicted that a crop would satisfy a destination's rules, from measurements
of the source. The written file is a different image - colour-converted, resampled, encoded -
and this module measures it again and takes each verdict from the written file's own
measurements. The same code checks a file the applicant already has. See docs/STAGE4-VALIDATE.md.

Only implemented checks - the profile's geometric rules and its encoding rules - take part in
the aggregate. What this build cannot assess, and what only the applicant can attest, is listed
beside the aggregate, never folded into it.
"""

from __future__ import annotations

import enum
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .geometry import EPS
from .measurements import MeasurementSet, Status
from .profiles import OutputSize, Profile, ProfileError, build_constraints
from .requirements import Check, for_jurisdiction

REPORT_VERSION = 1


class Verdict(enum.Enum):
    PASS = "pass"
    FAIL = "fail"
    INDETERMINATE = "indeterminate"
    """The observed value, with its uncertainty interval, straddles a bound - or the rule's
    two readings disagree."""
    NOT_EVALUATED = "not_evaluated"
    """The check could not run: its measurement is unavailable, or the rule is not stated at
    this file's size."""


@dataclass(frozen=True)
class Criterion:
    key: str
    kind: str
    """`rule` (a geometric rule of the profile) or `encoding` (a property of the file)."""
    verdict: Verdict
    detail: str
    observed: float | None = None
    predicted: float | None = None
    """The plan's prediction for this quantity, when a render preceded validation."""
    delta: float | None = None
    """observed - predicted. One model's disagreement with itself at two scales, not accuracy."""
    lo: float | None = None
    hi: float | None = None
    lo_strict: bool = False
    hi_strict: bool = False
    unit: str = ""
    expected: Any = None
    """Structured expectation for a non-numeric criterion (permitted sizes, format, mode)."""
    quote: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key, "kind": self.kind, "verdict": self.verdict.value,
            "observed": self.observed, "predicted": self.predicted, "delta": self.delta,
            "lo": self.lo, "hi": self.hi, "lo_strict": self.lo_strict, "hi_strict": self.hi_strict,
            "unit": self.unit, "expected": self.expected, "detail": self.detail, "quote": self.quote,
        }


@dataclass(frozen=True)
class FileFacts:
    """What the file says about itself, read before any conversion or orientation."""

    path: str
    format: str | None
    mode: str | None
    bits: int | None
    stored_width: int
    stored_height: int
    measured_width: int
    """Width after EXIF orientation - the frame measurements are taken in."""
    measured_height: int
    bytes: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path, "format": self.format, "mode": self.mode, "bits": self.bits,
            "stored": {"width": self.stored_width, "height": self.stored_height},
            "measured": {"width": self.measured_width, "height": self.measured_height},
            "bytes": self.bytes,
        }


# Bits per channel by Pillow mode, for the modes a photograph can arrive in.
_BITS = {"1": 1, "L": 8, "P": 8, "RGB": 8, "RGBA": 8, "CMYK": 8, "YCbCr": 8, "I;16": 16, "I": 32, "F": 32}


def file_facts(path: Path, measured_size: tuple[int, int]) -> FileFacts:
    """Format, mode, bit depth and stored dimensions from the file's own header."""
    from PIL import Image

    path = Path(path)
    with Image.open(path) as im:
        fmt, mode, size = im.format, im.mode, im.size
    return FileFacts(
        path=str(path), format=fmt, mode=mode, bits=_BITS.get(mode),
        stored_width=size[0], stored_height=size[1],
        measured_width=measured_size[0], measured_height=measured_size[1],
        bytes=os.path.getsize(path),
    )


def interval_verdict(
    x: float, half_width: float, lo: float | None, hi: float | None,
    lo_strict: bool = False, hi_strict: bool = False,
) -> Verdict:
    """The verdict for the interval [x - h, x + h] against the band.

    Inside ⇒ pass; disjoint ⇒ fail; anything else ⇒ indeterminate. A strict bound excludes
    its endpoint, so an interval touching it is not inside and a value equal to it, with no
    interval, is outside. Comparisons use the solver's numerical tolerance (`geometry.EPS`,
    1e-9): a value within it of a strict bound is on the bound, not past it. That is float
    noise, not a pixel tolerance.
    """
    a, b = x - half_width, x + half_width

    def above_lo(v: float) -> bool:
        return True if lo is None else (v > lo + EPS if lo_strict else v >= lo - EPS)

    def below_hi(v: float) -> bool:
        return True if hi is None else (v < hi - EPS if hi_strict else v <= hi + EPS)

    if above_lo(a) and below_hi(b):
        return Verdict.PASS
    if not above_lo(b) or not below_hi(a):
        return Verdict.FAIL
    return Verdict.INDETERMINATE


def _rule_constraints(profile: Profile, size: OutputSize, measurements: MeasurementSet):
    """The profile's rule constraints only - never source containment or a preference."""
    constraints, _ = build_constraints(profile, size, measurements)
    rules = {r.key for r in profile.rules}
    return {c.rule: c for c in constraints if c.rule in rules}


def observe(profile: Profile, measured_size: tuple[int, int], measurements: MeasurementSet):
    """Each rule's observed quantity at the identity transform, or the reason none could be.

    The quantity is the same `Constraint` the solver optimizes, evaluated at (s=1, u=0, v=0)
    on the file's own measurements, so a rule has one definition.
    """
    try:
        found = _rule_constraints(profile, OutputSize(*measured_size), measurements)
    except ProfileError as exc:
        return {}, str(exc)
    return {key: c.value(1.0, 0.0, 0.0) for key, c in found.items()}, None


def predict(profile: Profile, plan, source_measurements: MeasurementSet) -> dict[str, float]:
    """Each rule's quantity as the plan predicted it: the same constraint at the plan's
    transform on the source's measurements."""
    if not plan.feasible:
        return {}
    o = plan.chosen.outcome
    s, u, v = o.scale, o.crop_y * o.scale, o.crop_x * o.scale
    found = _rule_constraints(profile, plan.chosen.size, source_measurements)
    return {key: c.value(s, u, v) for key, c in found.items()}


@dataclass
class Validation:
    profile: str
    facts: FileFacts
    criteria: list[Criterion]
    aggregate: str
    """`fails`, `incomplete`, or `passes_implemented_checks` - over implemented checks only."""
    attestations: list[dict[str, str]]
    not_assessable: list[dict[str, str]]
    policies: dict[str, str]
    uncertainty: str
    """`delta` when a render's prediction supplied an interval, `none` for a point comparison."""
    measurements: MeasurementSet
    preflight: Any
    warnings: list[str] = field(default_factory=list)
    """Keys of the advisory requirements that warned on this file."""

    @property
    def fails(self) -> bool:
        return self.aggregate == "fails"

    def to_dict(self) -> dict[str, Any]:
        return {
            "profile": self.profile, "file": self.facts.to_dict(), "uncertainty": self.uncertainty,
            "criteria": [c.to_dict() for c in self.criteria], "aggregate": self.aggregate,
            "attestations": self.attestations, "not_assessable": self.not_assessable,
            "policies": self.policies,
            "measurements": self.measurements.to_dict(),
            "preflight": self.preflight.to_dict() if self.preflight else None,
        }


def _encoding_criteria(profile: Profile, facts: FileFacts) -> list[Criterion]:
    enc = profile.encoding
    assert enc is not None
    out: list[Criterion] = []
    sizes = [{"width": s.width, "height": s.height} for s in profile.sizes]
    stored = (facts.stored_width, facts.stored_height)
    measured = (facts.measured_width, facts.measured_height)
    listed = {(s.width, s.height) for s in profile.sizes}
    if stored == measured:
        verdict = Verdict.PASS if stored in listed else Verdict.FAIL
        why = f"{stored[0]}x{stored[1]} is {'a' if stored in listed else 'not a'} listed size"
    elif (stored in listed) == (measured in listed):
        # Both frames agree, so which one the portal checks does not matter.
        verdict = Verdict.PASS if stored in listed else Verdict.FAIL
        why = (f"stored {stored[0]}x{stored[1]}, {measured[0]}x{measured[1]} after EXIF orientation: "
               f"{'both' if verdict is Verdict.PASS else 'neither'} listed")
    else:
        verdict, why = Verdict.INDETERMINATE, (
            f"stored {stored[0]}x{stored[1]}, {measured[0]}x{measured[1]} after EXIF orientation; "
            "only one is a listed size and which the portal checks is not established")
    out.append(Criterion("dimensions", "encoding", verdict, why, expected={"sizes": sizes},
                         quote=profile.sizes_quote))

    fmt_ok = (facts.format or "").lower() == enc.format
    out.append(Criterion(
        "format", "encoding", Verdict.PASS if fmt_ok else Verdict.FAIL,
        f"file format {facts.format}", expected={"format": enc.format.upper()}, quote=enc.quote))

    colour_ok = facts.mode == "RGB" and facts.bits == 8
    out.append(Criterion(
        "colour", "encoding", Verdict.PASS if colour_ok else Verdict.FAIL,
        f"mode {facts.mode}, {facts.bits} bits per channel",
        expected={"mode": "RGB", "bits": 8}, quote=enc.quote))

    fits = {r.name: r.contains(facts.bytes) for r in enc.size_readings}
    if all(fits.values()):
        verdict, why = Verdict.PASS, f"{facts.bytes} bytes satisfies every reading"
    elif any(fits.values()):
        verdict, why = Verdict.INDETERMINATE, (
            f"{facts.bytes} bytes satisfies "
            + " but not ".join(", ".join(n for n, ok in fits.items() if ok == v) for v in (True, False)))
    else:
        verdict, why = Verdict.FAIL, f"{facts.bytes} bytes satisfies no reading"
    out.append(Criterion(
        "size_bytes", "encoding", verdict, why, observed=float(facts.bytes), unit="bytes",
        expected={"readings": [r.to_dict() for r in enc.size_readings]}, quote=enc.quote))
    return out


def _rule_criteria(profile: Profile, facts: FileFacts, measurements: MeasurementSet,
                   predicted: dict[str, float] | None) -> list[Criterion]:
    observed, refusal = observe(profile, (facts.measured_width, facts.measured_height), measurements)
    out: list[Criterion] = []
    for rule in profile.rules:
        base = dict(key=rule.key, kind="rule", lo=rule.lo, hi=rule.hi, lo_strict=rule.lo_strict,
                    hi_strict=rule.hi_strict, unit=rule.unit, quote=rule.quote)
        if refusal:
            out.append(Criterion(verdict=Verdict.NOT_EVALUATED, detail=refusal, **base))
            continue
        if rule.key not in observed:
            m = measurements.get(rule.measurement)
            status = m.status.value if m else "absent"
            reason = m.reason if m else "no such measurement"
            out.append(Criterion(verdict=Verdict.NOT_EVALUATED,
                                 detail=f"{rule.measurement} is {status}: {reason}", **base))
            continue
        x = observed[rule.key]
        pred = predicted.get(rule.key) if predicted is not None else None
        delta = (x - pred) if pred is not None else None
        half = abs(delta) if delta is not None else 0.0
        verdict = interval_verdict(x, half, rule.lo, rule.hi, rule.lo_strict, rule.hi_strict)
        band = f"{'(' if rule.lo_strict else '['}{rule.lo if rule.lo is not None else '-inf'}, " \
               f"{rule.hi if rule.hi is not None else 'inf'}{')' if rule.hi_strict else ']'}"
        detail = f"observed {x:.2f} {rule.unit} against {band}"
        if pred is not None:
            detail += f"; predicted {pred:.2f}, delta {delta:+.2f} (interval ±{half:.2f})"
        out.append(Criterion(verdict=verdict, detail=detail, observed=x, predicted=pred,
                             delta=delta, **base))
    return out


def validate(profile: Profile, facts: FileFacts, measurements: MeasurementSet, preflight,
             predicted: dict[str, float] | None = None) -> Validation:
    """Verdicts for a file against a profile, from the file's own facts and measurements."""
    if profile.encoding is None:
        raise ProfileError(f"{profile.key} states no digital encoding rules; validation of a "
                           "print profile is not supported")
    criteria = _encoding_criteria(profile, facts) + _rule_criteria(profile, facts, measurements, predicted)

    verdicts = {c.verdict for c in criteria}
    if Verdict.FAIL in verdicts:
        aggregate = "fails"
    elif Verdict.INDETERMINATE in verdicts or Verdict.NOT_EVALUATED in verdicts:
        aggregate = "incomplete"
    else:
        aggregate = "passes_implemented_checks"

    applicable = for_jurisdiction(profile.jurisdiction)
    attestations = [{"key": r.key, "quote": r.quote} for r in applicable
                    if r.check is Check.USER_ATTESTATION]
    not_assessable = [{"key": r.key, "quote": r.quote, "reason": r.note or "no check in this build"}
                      for r in applicable if r.check is Check.NOT_ASSESSABLE]
    return Validation(
        profile=profile.key, facts=facts, criteria=criteria, aggregate=aggregate,
        attestations=attestations, not_assessable=not_assessable,
        policies=dict(profile.operations),
        uncertainty="delta" if predicted is not None else "none",
        measurements=measurements, preflight=preflight,
        warnings=[f.requirement.key for f in preflight.warnings] if preflight else [],
    )

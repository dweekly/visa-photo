"""The measurement contract.

Every quantity this project measures carries its definition, its provenance, and the gates it
required. A measurement is AVAILABLE only when every one of those gates was affirmatively
satisfied; that is enforced here, at construction, and the container refuses to let a second
write replace a first. See PLAN.md -> Measurement for why the rule is inverted this way, and
registry.py for the only path that builds one.

Why this is strict: Stage 1 shipped the same defect six times - a number reported as measured
when something that had to be true for it was not. Guards added one at a time never closed it.
Structure does.
"""

from __future__ import annotations

import enum
import math
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Mapping


class Status(enum.Enum):
    """Outcome of one measurement."""

    AVAILABLE = "available"
    """Every required gate was True and a finite value was produced."""

    UNAVAILABLE = "unavailable"
    """Attempted; at least one required gate was False or not evaluated. `blockers` say which."""

    NOT_ATTEMPTED = "not_attempted"
    """This run chose not to look (e.g. segmentation disabled). Distinct from could-not."""


class Confidence(enum.Enum):
    """How much weight a consumer may place on an available value."""

    MEASURED = "measured"
    """Read from the model's output. Uncertainty is not characterised (see ROADMAP)."""

    ADVISORY = "advisory"
    """Indicative only. Must not be used as the basis of a compliance verdict."""


def _is_tristate(x: Any) -> bool:
    return x is True or x is False or x is None


@dataclass(frozen=True)
class Precondition:
    """One gate as it stood when a measurement was built. Tri-state by identity."""

    id: str
    satisfied: bool | None
    detail: str

    def __post_init__(self) -> None:
        if not _is_tristate(self.satisfied):
            raise TypeError(f"{self.id}: satisfied must be True, False or None, got {self.satisfied!r}")


@dataclass(frozen=True)
class Measurement:
    """One measured quantity, with everything needed to interpret it correctly.

    Construct through `registry.build` or `registry.not_attempted`. The invariants below are
    checked regardless of who calls, so a hand-built instance cannot be more available than
    its preconditions permit.
    """

    name: str
    definition: str
    status: Status
    preconditions: tuple[Precondition, ...]
    unit: str | None = None
    value: float | None = None
    backend: str | None = None
    confidence: Confidence | None = None
    not_attempted_reason: str | None = None

    uncertainty: float | None = None
    """Half-width of a calibrated interval, when one exists. Currently always None: no
    calibration has been performed. A model's detection confidence is NOT an uncertainty in
    pixels or degrees and must never be substituted here."""

    def __post_init__(self) -> None:
        if self.status is Status.AVAILABLE:
            if not self.preconditions:
                raise ValueError(f"{self.name}: AVAILABLE requires at least one precondition")
            bad = [p.id for p in self.preconditions if p.satisfied is not True]
            if bad:
                raise ValueError(f"{self.name}: AVAILABLE with unsatisfied preconditions {bad}")
            if self.value is None or not math.isfinite(self.value):
                raise ValueError(f"{self.name}: AVAILABLE requires a finite value, got {self.value!r}")
            if self.confidence is None:
                raise ValueError(f"{self.name}: AVAILABLE requires a confidence")
        elif self.status is Status.UNAVAILABLE:
            if self.value is not None:
                raise ValueError(f"{self.name}: UNAVAILABLE must not carry a value")
            if not self.blockers_false and not self.blockers_unknown:
                raise ValueError(f"{self.name}: UNAVAILABLE requires at least one failing gate")
        elif self.status is Status.NOT_ATTEMPTED:
            if self.value is not None or self.preconditions:
                raise ValueError(f"{self.name}: NOT_ATTEMPTED carries no value and no preconditions")
            if not self.not_attempted_reason:
                raise ValueError(f"{self.name}: NOT_ATTEMPTED requires a reason")

    @property
    def available(self) -> bool:
        return self.status is Status.AVAILABLE

    @property
    def blockers_false(self) -> tuple[Precondition, ...]:
        return tuple(p for p in self.preconditions if p.satisfied is False)

    @property
    def blockers_unknown(self) -> tuple[Precondition, ...]:
        return tuple(p for p in self.preconditions if p.satisfied is None)

    @property
    def reason(self) -> str | None:
        """Prose rendered from the structured blockers. Never hand-written."""
        if self.status is Status.AVAILABLE:
            return None
        if self.status is Status.NOT_ATTEMPTED:
            return self.not_attempted_reason
        parts = []
        if self.blockers_false:
            parts.append("failed: " + "; ".join(f"{p.id} ({p.detail})" for p in self.blockers_false))
        if self.blockers_unknown:
            parts.append("not evaluated: " + "; ".join(
                f"{p.id} ({p.detail})" for p in self.blockers_unknown))
        return " | ".join(parts)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "definition": self.definition,
            "status": self.status.value,
            "value": self.value,
            "unit": self.unit,
            "backend": self.backend,
            "confidence": self.confidence.value if self.confidence else None,
            "uncertainty": self.uncertainty,
            "reason": self.reason,
            "preconditions": [
                {"id": p.id, "satisfied": p.satisfied, "detail": p.detail}
                for p in self.preconditions
            ],
        }


@dataclass(frozen=True)
class Flag:
    """An advisory observation about the subject, not a compliance verdict.

    Flags exist to catch a photo that should be retaken *before* effort is spent cropping it -
    a smile, closed eyes, an open mouth. They are raised against uncalibrated thresholds (see
    `thresholds.py`) and say so.
    """

    name: str
    raised: bool
    detail: str
    score: float | None = None
    threshold: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "raised": self.raised,
            "detail": self.detail,
            "score": self.score,
            "threshold": self.threshold,
        }


class DuplicateMeasurement(ValueError):
    """A second write to a name already recorded. The truncated-crown bug was exactly this."""


@dataclass
class MeasurementSet:
    """Everything measured from one source image.

    Storage is private and exposed read-only, so the only way in is `add`, and `add` refuses a
    second write to the same name.
    """

    source: str
    image_width: int
    image_height: int
    flags: list[Flag] = field(default_factory=list)
    backends: dict[str, str] = field(default_factory=dict)
    """Backend name -> version, recorded so a report is reproducible."""
    gate_record: Any = None
    """The frozen `gates.GateRecord` this set was built from, for the report."""
    _measurements: dict[str, Measurement] = field(default_factory=dict, repr=False)

    def add(self, measurement: Measurement) -> None:
        if measurement.name in self._measurements:
            raise DuplicateMeasurement(
                f"{measurement.name} is already recorded as "
                f"{self._measurements[measurement.name].status.value}"
            )
        self._measurements[measurement.name] = measurement

    @property
    def measurements(self) -> Mapping[str, Measurement]:
        return MappingProxyType(self._measurements)

    def get(self, name: str) -> Measurement | None:
        return self._measurements.get(name)

    def value(self, name: str) -> float | None:
        """Value if available, else None. Callers must handle None rather than defaulting."""
        m = self._measurements.get(name)
        return m.value if m and m.available else None

    def status(self, name: str) -> Status | None:
        m = self._measurements.get(name)
        return m.status if m else None

    @property
    def raised_flags(self) -> list[Flag]:
        return [f for f in self.flags if f.raised]

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "image": {"width": self.image_width, "height": self.image_height},
            "backends": self.backends,
            "measurements": {k: v.to_dict() for k, v in self._measurements.items()},
            "flags": [f.to_dict() for f in self.flags],
            "gates": self.gate_record.to_dict() if self.gate_record is not None else None,
        }

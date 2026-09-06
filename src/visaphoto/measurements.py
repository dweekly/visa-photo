"""The measurement contract.

Every quantity this project measures carries its definition, its provenance, and — when it
could not be measured — the reason. "Unavailable" is a first-class result, not an error, and
it must never be silently replaced by a plausible number.

Why this is strict: the failure that motivated this project was a measurement applied under a
definition that did not govern it. A bare float named `head_width` invites exactly that. A
`Measurement` carrying `definition="silhouette including hair"` does not.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import Any


class Status(enum.Enum):
    """Outcome of attempting one measurement."""

    AVAILABLE = "available"
    """Measured. `value` is set."""

    UNAVAILABLE = "unavailable"
    """Could not be measured on this image with this backend. `reason` says why."""

    UNSUPPORTED = "unsupported"
    """No backend in this build can produce this measurement under this definition."""


class Confidence(enum.Enum):
    """How much weight a consumer may place on an available value."""

    MEASURED = "measured"
    """Read from the model's output. Uncertainty is not characterised (see ROADMAP)."""

    ADVISORY = "advisory"
    """Indicative only. Must not be used as the basis of a compliance verdict."""


@dataclass(frozen=True)
class Measurement:
    """One measured quantity, with everything needed to interpret it correctly."""

    name: str
    definition: str
    """Exactly what was measured, in words. Two measurements may share a name across specs
    and mean different things; this field is what distinguishes them."""

    status: Status
    unit: str | None = None
    value: float | None = None
    backend: str | None = None
    confidence: Confidence | None = None
    reason: str | None = None
    """Required when status is not AVAILABLE. Why no value exists."""

    uncertainty: float | None = None
    """Half-width of a calibrated interval, when one exists. Currently always None: no
    calibration has been performed. A model's detection confidence is NOT an uncertainty in
    pixels or degrees and must never be substituted here."""

    def __post_init__(self) -> None:
        if self.status is Status.AVAILABLE:
            if self.value is None:
                raise ValueError(f"{self.name}: AVAILABLE requires a value")
            if self.confidence is None:
                raise ValueError(f"{self.name}: AVAILABLE requires a confidence")
        elif self.reason is None:
            raise ValueError(f"{self.name}: {self.status.value} requires a reason")

    @property
    def available(self) -> bool:
        return self.status is Status.AVAILABLE

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
        }


@dataclass(frozen=True)
class Flag:
    """An advisory observation about the subject, not a compliance verdict.

    Flags exist to catch a photo that should be retaken *before* effort is spent cropping it —
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


@dataclass
class MeasurementSet:
    """Everything measured from one source image."""

    source: str
    image_width: int
    image_height: int
    measurements: dict[str, Measurement] = field(default_factory=dict)
    flags: list[Flag] = field(default_factory=list)
    backends: dict[str, str] = field(default_factory=dict)
    """Backend name -> version, recorded so a report is reproducible."""

    def add(self, measurement: Measurement) -> None:
        self.measurements[measurement.name] = measurement

    def get(self, name: str) -> Measurement | None:
        return self.measurements.get(name)

    def value(self, name: str) -> float | None:
        """Value if available, else None. Callers must handle None rather than defaulting."""
        m = self.measurements.get(name)
        return m.value if m and m.available else None

    @property
    def raised_flags(self) -> list[Flag]:
        return [f for f in self.flags if f.raised]

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "image": {"width": self.image_width, "height": self.image_height},
            "backends": self.backends,
            "measurements": {k: v.to_dict() for k, v in self.measurements.items()},
            "flags": [f.to_dict() for f in self.flags],
        }

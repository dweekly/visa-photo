"""Turn measurements plus a destination profile into a crop plan, or an explained refusal.

This layer owns the outer loop over permitted output sizes. A profile may allow several, and
failure at one must never be reported as failure at all of them.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .geometry import Infeasible, Solution, solve
from .measurements import MeasurementSet
from .profiles import OutputSize, Profile, ProfileError, build_constraints


@dataclass
class SizeAttempt:
    size: OutputSize
    outcome: Solution | Infeasible | None
    skipped: str | None = None
    """This size was not attempted, by policy (e.g. pixel rules stated at another size)."""
    blocked: str | None = None
    """This size could not be attempted because a rule's measurement is unavailable. Distinct
    from skipped (policy) and from Infeasible (the rules conflict for this face): the remedy
    here is a photo the measurement can be made on, and the rule is named."""
    unapplied: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "size": {"width": self.size.width, "height": self.size.height},
            "skipped": self.skipped,
            "blocked": self.blocked,
            "unapplied_rules": self.unapplied,
            "outcome": self.outcome.to_dict() if self.outcome else None,
        }


@dataclass
class Plan:
    profile: Profile
    chosen: SizeAttempt | None
    attempts: list[SizeAttempt]

    @property
    def feasible(self) -> bool:
        return self.chosen is not None

    def to_dict(self) -> dict[str, Any]:
        return {
            "profile": self.profile.key,
            "destination": self.profile.destination,
            "channel": self.profile.channel,
            "feasible": self.feasible,
            "chosen": self.chosen.to_dict() if self.chosen else None,
            "attempts": [a.to_dict() for a in self.attempts],
            "notes": list(self.profile.notes),
        }


def make_plan(profile: Profile, measurements: MeasurementSet) -> Plan:
    """Try every permitted output size; keep the feasible one with the most slack."""
    attempts: list[SizeAttempt] = []

    for size in profile.sizes:
        try:
            constraints, unapplied = build_constraints(profile, size, measurements)
        except ProfileError as exc:
            attempts.append(SizeAttempt(size=size, outcome=None, skipped=str(exc)))
            continue
        if unapplied:
            # Never solve with a rule silently dropped. A crop that satisfies every rule we
            # could apply is not a crop that satisfies the profile, and the report must not
            # suggest otherwise - nor call this a conflict between rules.
            attempts.append(SizeAttempt(
                size=size, outcome=None, unapplied=unapplied,
                blocked="cannot solve with the available measurements: " + "; ".join(unapplied),
            ))
            continue
        outcome = solve(constraints, size.width, size.height)
        attempts.append(SizeAttempt(size=size, outcome=outcome, unapplied=unapplied))

    feasible = [
        a for a in attempts if isinstance(a.outcome, Solution)
    ]
    # Most slack wins; ties break on the larger output, then on width, so the result is
    # deterministic rather than dependent on dict or list ordering.
    chosen = max(
        feasible,
        key=lambda a: (
            a.outcome.min_slack,  # type: ignore[union-attr]
            a.size.width * a.size.height,
            a.size.width,
        ),
        default=None,
    )
    return Plan(profile=profile, chosen=chosen, attempts=attempts)

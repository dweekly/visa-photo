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

    @property
    def feasible_attempts(self) -> list[SizeAttempt]:
        """Every solvable size, in the profile's order: the first is `chosen`, the rest are
        what rendering falls back to when the first cannot be encoded within the rules."""
        return [a for a in self.attempts if isinstance(a.outcome, Solution)]

    def applied_rules(self) -> list[dict[str, Any]]:
        """Every rule of the profile with its provenance and reading, and whether the plan
        applied it - so a report shows the words behind each bound and the reading chosen
        where the words define nothing."""
        attempt = self.chosen or (self.attempts[0] if self.attempts else None)
        out = []
        for rule in self.profile.rules:
            reason = next((u for u in (attempt.unapplied if attempt else []) if u.startswith(rule.key + ":")), None)
            source, retrieved = self.profile.provenance(rule)
            entry = rule.to_dict()
            entry.update({"source": source, "retrieved": retrieved,
                          "applied": attempt is not None and attempt.outcome is not None and reason is None,
                          "reason": reason if reason else (attempt.skipped if attempt and attempt.skipped else None)})
            out.append(entry)
        return out

    def to_dict(self) -> dict[str, Any]:
        return {
            "profile": self.profile.key,
            "destination": self.profile.destination,
            "channel": self.profile.channel,
            "feasible": self.feasible,
            "chosen": self.chosen.to_dict() if self.chosen else None,
            "attempts": [a.to_dict() for a in self.attempts],
            "applied_rules": self.applied_rules(),
            "notes": list(self.profile.notes),
        }


def make_plan(profile: Profile, measurements: MeasurementSet) -> Plan:
    """Try every permitted output size in the profile's order; the first feasible is chosen.

    The order is the profile's statement of preference - the size a destination's own tool
    produces first, or the largest first where a byte floor is easier to reach with more
    pixels - and rendering falls back along it when a size cannot be encoded."""
    attempts: list[SizeAttempt] = []

    for size in profile.sizes:
        if profile.composition_unresolved:
            attempts.append(SizeAttempt(size=size, outcome=None, skipped=profile.composition_unresolved))
            continue
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

    feasible = [a for a in attempts if isinstance(a.outcome, Solution)]
    return Plan(profile=profile, chosen=feasible[0] if feasible else None, attempts=attempts)

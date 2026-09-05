"""Exact geometry solving for a crop that satisfies a destination's published rules.

The whole stage rests on one substitution. The unknowns are a scale ``s`` and a crop origin
``(cx0, cy0)``; writing ``u = cy0 * s`` and ``v = cx0 * s`` makes every rule **linear** in
``(s, u, v)``. No rule couples ``u`` and ``v``, so for a fixed scale the vertical and
horizontal problems are independent one-dimensional interval intersections.

That matters because it lets feasibility be **decided**, not searched. A sampled search over
scales can step over an arbitrarily narrow feasible window and report a conflict that does not
exist - the worst failure available to a tool whose headline feature is telling you honestly
when rules conflict.

See docs/STAGE2-SOLVER.md for the derivation.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Iterable

# Numerical tolerance. Bounds are in pixels and scales are order 0.1-10, so 1e-9 is far below
# any meaningful quantity while still absorbing floating-point noise in the pairwise
# elimination.
EPS = 1e-9


@dataclass(frozen=True)
class Interval:
    """A closed interval on the real line. Empty when ``lo > hi``."""

    lo: float = -math.inf
    hi: float = math.inf

    @property
    def empty(self) -> bool:
        return self.lo > self.hi + EPS

    @property
    def width(self) -> float:
        return max(0.0, self.hi - self.lo)

    def intersect(self, other: "Interval") -> "Interval":
        return Interval(max(self.lo, other.lo), min(self.hi, other.hi))

    def clamp(self, value: float) -> float:
        return min(max(value, self.lo), self.hi)

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"[{self.lo:.6g}, {self.hi:.6g}]"


@dataclass(frozen=True)
class Constraint:
    """One published rule, as ``lo <= a*s + b*u + c*v + k <= hi``.

    ``rule`` identifies the source rule so an infeasibility can name it rather than saying
    "infeasible". ``normalize`` is the positive scale used when comparing slack across
    constraints measured in different units; it defaults to the band width so that slack is
    expressed as a fraction of the room the rule allows.
    """

    rule: str
    a: float = 0.0
    b: float = 0.0
    c: float = 0.0
    k: float = 0.0
    lo: float | None = None
    hi: float | None = None
    hard: bool = False
    """Hard constraints must hold but earn no slack reward - source containment, for instance.
    Without this a crop drifts toward the middle of the photograph for no reason."""

    def __post_init__(self) -> None:
        if self.lo is None and self.hi is None:
            raise ValueError(f"{self.rule}: a constraint with no bounds constrains nothing")
        if self.lo is not None and self.hi is not None and self.lo > self.hi:
            raise ValueError(f"{self.rule}: lo {self.lo} exceeds hi {self.hi}")

    def value(self, s: float, u: float, v: float) -> float:
        return self.a * s + self.b * u + self.c * v + self.k

    @property
    def normalize(self) -> float:
        if self.lo is not None and self.hi is not None:
            return max(self.hi - self.lo, EPS)
        return 1.0

    def slack(self, s: float, u: float, v: float) -> float:
        """Normalized distance to the nearer bound. Negative means violated."""
        x = self.value(s, u, v)
        margins = []
        if self.lo is not None:
            margins.append(x - self.lo)
        if self.hi is not None:
            margins.append(self.hi - x)
        return min(margins) / self.normalize


@dataclass(frozen=True)
class _Bound:
    """``coefficient * s + offset`` as a bound on u or v, tagged with its originating rule."""

    offset: float
    coefficient: float
    rule: str

    def at(self, s: float) -> float:
        return self.offset + self.coefficient * s


def _split(constraints: Iterable[Constraint], axis: str):
    """Rearrange constraints into (s-only band, lower bounds, upper bounds) for one axis."""
    s_only = Interval()
    lowers: list[_Bound] = []
    uppers: list[_Bound] = []
    other = "c" if axis == "b" else "b"

    for con in constraints:
        coeff = getattr(con, axis)
        if getattr(con, other) != 0.0:
            continue  # belongs to the other axis
        if coeff == 0.0:
            if con.a == 0.0:
                continue  # constant; validated at construction
            # lo <= a*s + k <= hi
            lo = (con.lo - con.k) / con.a if con.lo is not None else -math.inf
            hi = (con.hi - con.k) / con.a if con.hi is not None else math.inf
            if con.a < 0:
                lo, hi = hi, lo
            s_only = s_only.intersect(Interval(lo, hi))
            continue
        # lo <= a*s + coeff*x + k <= hi  ->  bounds on x, linear in s
        if con.lo is not None:
            bound = _Bound((con.lo - con.k) / coeff, -con.a / coeff, con.rule)
            (lowers if coeff > 0 else uppers).append(bound)
        if con.hi is not None:
            bound = _Bound((con.hi - con.k) / coeff, -con.a / coeff, con.rule)
            (uppers if coeff > 0 else lowers).append(bound)
    return s_only, lowers, uppers


def _pairwise_feasible_scales(
    lowers: list[_Bound], uppers: list[_Bound]
) -> tuple[Interval, list[tuple[str, str]]]:
    """Scales for which some x satisfies every bound: ``L_i(s) <= U_j(s)`` for all pairs.

    Each pair is linear in s, so it contributes an interval. This is the step that makes
    feasibility exact - no scale is ever guessed at.
    """
    feasible = Interval()
    blame: list[tuple[str, str]] = []
    for lower in lowers:
        for upper in uppers:
            # (lower.offset - upper.offset) + (lower.coefficient - upper.coefficient)*s <= 0
            alpha = lower.offset - upper.offset
            beta = lower.coefficient - upper.coefficient
            if abs(beta) <= EPS:
                if alpha > EPS:
                    return Interval(1.0, -1.0), [(lower.rule, upper.rule)]
                continue
            limit = -alpha / beta
            pair = Interval(-math.inf, limit) if beta > 0 else Interval(limit, math.inf)
            merged = feasible.intersect(pair)
            if merged.empty and not feasible.empty:
                blame.append((lower.rule, upper.rule))
            feasible = merged
    return feasible, blame


def _best_x(bounds_lo: list[_Bound], bounds_hi: list[_Bound], s: float) -> tuple[float, float]:
    """Midpoint of the feasible interval for one axis at scale ``s``, and its width."""
    lo = max((b.at(s) for b in bounds_lo), default=-math.inf)
    hi = min((b.at(s) for b in bounds_hi), default=math.inf)
    if lo == -math.inf and hi == math.inf:
        return 0.0, math.inf
    if lo == -math.inf:
        return hi, math.inf
    if hi == math.inf:
        return lo, math.inf
    return (lo + hi) / 2.0, hi - lo


@dataclass
class Solution:
    scale: float
    crop_x: float
    crop_y: float
    output_width: int
    output_height: int
    min_slack: float
    slacks: dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "scale": self.scale,
            "crop": {"x": self.crop_x, "y": self.crop_y},
            "output": {"width": self.output_width, "height": self.output_height},
            "min_slack": self.min_slack,
            "slacks": self.slacks,
        }


@dataclass
class Infeasible:
    reason: str
    detail: str
    conflicting_rules: list[tuple[str, str]] = field(default_factory=list)
    scale_bands: dict[str, tuple[float, float]] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "reason": self.reason,
            "detail": self.detail,
            "conflicting_rules": [list(p) for p in self.conflicting_rules],
            "scale_bands": {k: list(v) for k, v in self.scale_bands.items()},
        }


def solve(
    constraints: list[Constraint], output_width: int, output_height: int
) -> Solution | Infeasible:
    """Find the crop maximizing the minimum normalized slack, or explain why none exists.

    Pure: no image decoding, no model calls, no file access. Same input, same output.
    """
    vertical_band, v_lo, v_hi = _split(constraints, "b")
    horizontal_band, h_lo, h_hi = _split(constraints, "c")

    scale_band = vertical_band.intersect(horizontal_band)
    scale_band = scale_band.intersect(Interval(EPS, math.inf))

    per_rule: dict[str, tuple[float, float]] = {}
    for con in constraints:
        if con.b == 0.0 and con.c == 0.0 and con.a != 0.0:
            lo = (con.lo - con.k) / con.a if con.lo is not None else -math.inf
            hi = (con.hi - con.k) / con.a if con.hi is not None else math.inf
            if con.a < 0:
                lo, hi = hi, lo
            per_rule[con.rule] = (lo, hi)

    if scale_band.empty:
        names = list(per_rule)
        return Infeasible(
            reason="conflicting_requirements",
            detail=(
                "no single scale satisfies every size rule at "
                f"{output_width}x{output_height}"
            ),
            conflicting_rules=[(names[i], names[j])
                               for i in range(len(names)) for j in range(i + 1, len(names))],
            scale_bands=per_rule,
        )

    vertical_scales, v_blame = _pairwise_feasible_scales(v_lo, v_hi)
    horizontal_scales, h_blame = _pairwise_feasible_scales(h_lo, h_hi)
    feasible = scale_band.intersect(vertical_scales).intersect(horizontal_scales)

    if feasible.empty:
        blame = v_blame + h_blame
        return Infeasible(
            reason="conflicting_requirements" if blame else "source_too_small",
            detail=(
                f"no crop at {output_width}x{output_height} satisfies every rule; "
                "the scale bands do not overlap once placement is accounted for"
            ),
            conflicting_rules=blame,
            scale_bands=per_rule,
        )

    def objective(s: float) -> float:
        u, _ = _best_x(v_lo, v_hi, s)
        v, _ = _best_x(h_lo, h_hi, s)
        soft = [c.slack(s, u, v) for c in constraints if not c.hard]
        return min(soft) if soft else 0.0

    lo, hi = feasible.lo, feasible.hi
    if not math.isfinite(lo) or not math.isfinite(hi):
        return Infeasible(
            reason="insufficient_resolution",
            detail="the feasible scale range is unbounded; the profile under-constrains size",
            scale_bands=per_rule,
        )

    # Ternary search. Sound here where sampling was not for feasibility: with feasibility
    # already decided exactly, the objective is a max of a min of linear functions and is
    # therefore concave in s, so this converges on the true optimum.
    for _ in range(200):
        if hi - lo < 1e-12:
            break
        a = lo + (hi - lo) / 3.0
        b = hi - (hi - lo) / 3.0
        if objective(a) < objective(b):
            lo = a
        else:
            hi = b
    s = (lo + hi) / 2.0
    u, _ = _best_x(v_lo, v_hi, s)
    v, _ = _best_x(h_lo, h_hi, s)

    slacks = {c.rule: c.slack(s, u, v) for c in constraints}
    soft = [value for rule, value in slacks.items()
            if not any(c.rule == rule and c.hard for c in constraints)]
    return Solution(
        scale=s,
        crop_x=v / s,
        crop_y=u / s,
        output_width=output_width,
        output_height=output_height,
        min_slack=min(soft) if soft else 0.0,
        slacks=slacks,
    )

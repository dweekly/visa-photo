"""Exact geometry solving for a crop that satisfies a destination's published rules.

The whole stage rests on one substitution. The unknowns are a scale ``s`` and a crop origin
``(cx0, cy0)``; writing ``u = cy0 * s`` and ``v = cx0 * s`` makes every rule **linear** in
``(s, u, v)``. No rule couples ``u`` and ``v``, so for a fixed scale the vertical and
horizontal problems are independent one-dimensional interval intersections.

That matters because it lets feasibility be **decided**, not searched. A sampled search over
scales can step over an arbitrarily narrow feasible window and report a conflict that does not
exist - the worst failure available to a tool whose headline feature is telling you honestly
when rules conflict.

Every interval endpoint carries the rule that set it, so an infeasibility names the two rules
that actually disagree rather than blaming the photograph's size by default.

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

# Ternary-search iterations. Each shrinks the bracket by 2/3; 200 takes any pixel-scale
# bracket far below EPS. Sound because both objectives searched are concave (see solve).
_SEARCH_ITERATIONS = 200


@dataclass(frozen=True)
class Interval:
    """A closed interval on the real line. Empty when ``lo > hi``."""

    lo: float = -math.inf
    hi: float = math.inf

    @property
    def empty(self) -> bool:
        return self.lo > self.hi + EPS

    def intersect(self, other: "Interval") -> "Interval":
        return Interval(max(self.lo, other.lo), min(self.hi, other.hi))

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"[{self.lo:.6g}, {self.hi:.6g}]"


@dataclass(frozen=True)
class _Tagged:
    """An interval on ``s`` whose endpoints remember which rule set them."""

    interval: Interval
    lo_rule: str | None = None
    hi_rule: str | None = None

    def intersect(self, other: "_Tagged") -> "_Tagged":
        if other.interval.lo > self.interval.lo:
            lo, lo_rule = other.interval.lo, other.lo_rule
        else:
            lo, lo_rule = self.interval.lo, self.lo_rule
        if other.interval.hi < self.interval.hi:
            hi, hi_rule = other.interval.hi, other.hi_rule
        else:
            hi, hi_rule = self.interval.hi, self.hi_rule
        return _Tagged(Interval(lo, hi), lo_rule, hi_rule)

    @property
    def empty(self) -> bool:
        return self.interval.empty


@dataclass(frozen=True)
class Constraint:
    """One published rule, as ``lo <= a*s + b*u + c*v + k <= hi``.

    ``rule`` identifies the source rule so an infeasibility can name it rather than saying
    "infeasible". Slack is normalized by the band width so it is a fraction of the room the
    rule allows; one-sided rules normalize to 1.
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


def _scale_band(con: Constraint) -> _Tagged:
    """The interval on ``s`` imposed by an s-only constraint."""
    lo = (con.lo - con.k) / con.a if con.lo is not None else -math.inf
    hi = (con.hi - con.k) / con.a if con.hi is not None else math.inf
    if con.a < 0:
        lo, hi = hi, lo
    return _Tagged(Interval(lo, hi), con.rule, con.rule)


def _split(constraints: Iterable[Constraint], axis: str):
    """Rearrange constraints into (tagged s-only band, lower bounds, upper bounds) for one axis."""
    band = _Tagged(Interval())
    lowers: list[_Bound] = []
    uppers: list[_Bound] = []
    other = "c" if axis == "b" else "b"

    for con in constraints:
        coeff = getattr(con, axis)
        if getattr(con, other) != 0.0:
            continue  # belongs to the other axis
        if coeff == 0.0:
            if con.a != 0.0:
                band = band.intersect(_scale_band(con))
            continue
        # lo <= a*s + coeff*x + k <= hi  ->  bounds on x, linear in s
        if con.lo is not None:
            bound = _Bound((con.lo - con.k) / coeff, -con.a / coeff, con.rule)
            (lowers if coeff > 0 else uppers).append(bound)
        if con.hi is not None:
            bound = _Bound((con.hi - con.k) / coeff, -con.a / coeff, con.rule)
            (uppers if coeff > 0 else lowers).append(bound)
    return band, lowers, uppers


def _pairwise_feasible_scales(lowers: list[_Bound], uppers: list[_Bound]) -> _Tagged:
    """Scales for which some x satisfies every bound: ``L_i(s) <= U_j(s)`` for all pairs.

    Each pair is linear in s, so it contributes an interval tagged with the pair of rules that
    produced it. This is the step that makes feasibility exact - no scale is ever guessed at -
    and tagging is what lets the final intersection say *which* pair lost.
    """
    feasible = _Tagged(Interval())
    for lower in lowers:
        for upper in uppers:
            tag = f"{lower.rule} & {upper.rule}"
            # (lower.offset - upper.offset) + (lower.coefficient - upper.coefficient)*s <= 0
            alpha = lower.offset - upper.offset
            beta = lower.coefficient - upper.coefficient
            if abs(beta) <= EPS:
                if alpha > EPS:  # impossible at every scale
                    return _Tagged(Interval(1.0, -1.0), tag, tag)
                continue
            limit = -alpha / beta
            pair = (_Tagged(Interval(-math.inf, limit), None, tag) if beta > 0
                    else _Tagged(Interval(limit, math.inf), tag, None))
            feasible = feasible.intersect(pair)
    return feasible


def _placement_interval(lo_bounds: list[_Bound], hi_bounds: list[_Bound], s: float) -> Interval:
    return Interval(
        max((b.at(s) for b in lo_bounds), default=-math.inf),
        min((b.at(s) for b in hi_bounds), default=math.inf),
    )


def _best_placement(
    lo_bounds: list[_Bound], hi_bounds: list[_Bound], s: float,
    softs: list[Constraint], axis: str,
) -> float:
    """The placement on one axis that maximizes the minimum normalized slack at scale ``s``.

    Within the feasible interval every constraint holds; among those placements this picks the
    one that sits furthest from its nearest soft limit. That is a max of a min of functions
    linear in the placement - concave - so ternary search finds the true optimum. A midpoint
    rule is not this: hard containment and differently normalized rules move the midpoint away
    from the optimum, and the reference photograph lost 0.07 of slack to it.
    """
    span = _placement_interval(lo_bounds, hi_bounds, s)
    lo, hi = span.lo, span.hi
    if lo == -math.inf and hi == math.inf:
        return 0.0
    if lo == -math.inf:
        return hi
    if hi == math.inf:
        return lo
    relevant = [c for c in softs if getattr(c, axis) != 0.0]
    if not relevant:
        return (lo + hi) / 2.0

    def objective(x: float) -> float:
        u, v = (x, 0.0) if axis == "b" else (0.0, x)
        return min(c.slack(s, u, v) for c in relevant)

    for _ in range(_SEARCH_ITERATIONS):
        if hi - lo < 1e-12:
            break
        a = lo + (hi - lo) / 3.0
        b = hi - (hi - lo) / 3.0
        if objective(a) < objective(b):
            lo = a
        else:
            hi = b
    return (lo + hi) / 2.0


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


_SOURCE_PREFIX = "source_"


def _is_source(tag: str | None) -> bool:
    return tag is not None and all(
        part.strip().startswith(_SOURCE_PREFIX) for part in tag.split("&")
    )


def _classify(feasible: _Tagged, output_width: int, output_height: int,
              per_rule: dict[str, tuple[float, float]]) -> Infeasible:
    """Name the two rules whose endpoints collided, and say what kind of failure that is.

    A rule-versus-rule collision is a conflict in the destination's requirements for this
    face; a collision involving the source image's edges means the photograph is framed too
    tightly. They call for different remedies, so they must not be confused.
    """
    lo_rule, hi_rule = feasible.lo_rule or "?", feasible.hi_rule or "?"
    lo, hi = feasible.interval.lo, feasible.interval.hi
    if _is_source(lo_rule) and _is_source(hi_rule):
        return Infeasible(
            reason="source_too_small",
            detail=(f"the {output_width}x{output_height} crop cannot fit inside the source "
                    "image at any scale"),
            conflicting_rules=[(lo_rule, hi_rule)], scale_bands=per_rule,
        )
    if _is_source(lo_rule) or _is_source(hi_rule):
        return Infeasible(
            reason="source_too_small",
            detail=(f"a published rule and the source image's edges cannot both be satisfied "
                    f"at {output_width}x{output_height}: {lo_rule} needs scale >= {lo:.5f}, "
                    f"{hi_rule} needs scale <= {hi:.5f}"),
            conflicting_rules=[(lo_rule, hi_rule)], scale_bands=per_rule,
        )
    return Infeasible(
        reason="conflicting_requirements",
        detail=(f"two published rules disagree at {output_width}x{output_height}: {lo_rule} "
                f"needs scale >= {lo:.5f}, {hi_rule} needs scale <= {hi:.5f}"),
        conflicting_rules=[(lo_rule, hi_rule)], scale_bands=per_rule,
    )


def solve(
    constraints: list[Constraint], output_width: int, output_height: int
) -> Solution | Infeasible:
    """Find the crop maximizing the minimum normalized slack, or explain why none exists.

    Pure: no image decoding, no model calls, no file access. Same input, same output.
    """
    vertical_band, v_lo, v_hi = _split(constraints, "b")
    horizontal_band, h_lo, h_hi = _split(constraints, "c")

    per_rule = {
        con.rule: (_scale_band(con).interval.lo, _scale_band(con).interval.hi)
        for con in constraints if con.b == 0.0 and con.c == 0.0 and con.a != 0.0
    }

    feasible = (
        _Tagged(Interval(EPS, math.inf), "scale must be positive", None)
        .intersect(vertical_band)
        .intersect(horizontal_band)
        .intersect(_pairwise_feasible_scales(v_lo, v_hi))
        .intersect(_pairwise_feasible_scales(h_lo, h_hi))
    )
    if feasible.empty:
        return _classify(feasible, output_width, output_height, per_rule)

    lo, hi = feasible.interval.lo, feasible.interval.hi
    if not math.isfinite(lo) or not math.isfinite(hi):
        return Infeasible(
            reason="insufficient_resolution",
            detail="the feasible scale range is unbounded; the profile under-constrains size",
            scale_bands=per_rule,
        )

    softs = [c for c in constraints if not c.hard]

    def placed(s: float) -> tuple[float, float]:
        return (_best_placement(v_lo, v_hi, s, softs, "b"),
                _best_placement(h_lo, h_hi, s, softs, "c"))

    def objective(s: float) -> float:
        u, v = placed(s)
        return min((c.slack(s, u, v) for c in softs), default=0.0)

    # Ternary search over scale. Sound here where sampling was not for feasibility: with the
    # feasible interval already decided exactly, the objective - a max over placement of a min
    # of linear functions - is concave in s, so this converges on the true optimum.
    for _ in range(_SEARCH_ITERATIONS):
        if hi - lo < 1e-12:
            break
        a = lo + (hi - lo) / 3.0
        b = hi - (hi - lo) / 3.0
        if objective(a) < objective(b):
            lo = a
        else:
            hi = b
    s = (lo + hi) / 2.0
    u, v = placed(s)

    slacks = {c.rule: c.slack(s, u, v) for c in constraints}
    return Solution(
        scale=s, crop_x=v / s, crop_y=u / s,
        output_width=output_width, output_height=output_height,
        min_slack=min((slacks[c.rule] for c in softs), default=0.0),
        slacks=slacks,
    )

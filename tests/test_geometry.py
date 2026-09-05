"""Solver correctness, including the cases independent review said sampling would get wrong."""

from __future__ import annotations

import math

import pytest

from visaphoto.geometry import Constraint, Infeasible, Solution, solve


def size_rules(head_height: float, lo: float, hi: float) -> Constraint:
    return Constraint(rule="head_height", a=head_height, lo=lo, hi=hi)


def containment(width: int, height: int, ow: int, oh: int) -> list[Constraint]:
    """The crop must lie inside the source. Hard: it must hold, but earns no reward."""
    return [
        Constraint(rule="source_left", c=1.0, lo=0.0, hard=True),
        Constraint(rule="source_top", b=1.0, lo=0.0, hard=True),
        Constraint(rule="source_right", a=float(width), c=-1.0, lo=float(ow), hard=True),
        Constraint(rule="source_bottom", a=float(height), b=-1.0, lo=float(oh), hard=True),
    ]


class TestExactFeasibility:
    def test_a_singleton_feasible_scale_is_found(self):
        """The case that motivates exact interval algebra. Two head-size rules leave exactly
        one admissible scale; a sampled search would step over it and report a conflict."""
        constraints = [
            Constraint(rule="head_height", a=1000.0, lo=500.0, hi=500.0),
            Constraint(rule="head_width", a=600.0, lo=300.0, hi=300.0),
            *containment(2000, 3000, 400, 500),
        ]
        result = solve(constraints, 400, 500)
        assert isinstance(result, Solution)
        assert result.scale == pytest.approx(0.5, abs=1e-9)

    def test_a_very_narrow_feasible_window_is_found(self):
        constraints = [
            Constraint(rule="head_height", a=1000.0, lo=500.0, hi=500.0001),
            *containment(2000, 3000, 400, 500),
        ]
        result = solve(constraints, 400, 500)
        assert isinstance(result, Solution)
        assert 0.5 <= result.scale <= 0.5000001

    def test_incompatible_size_rules_are_reported_with_their_bands(self):
        """The 2026-09-04 China case in miniature: head height and head width cannot both be
        satisfied for this face."""
        constraints = [
            Constraint(rule="head_height", a=1000.0, lo=900.0, hi=950.0),
            Constraint(rule="head_width", a=1000.0, lo=100.0, hi=200.0),
            *containment(4000, 6000, 400, 500),
        ]
        result = solve(constraints, 400, 500)
        assert isinstance(result, Infeasible)
        assert result.reason == "conflicting_requirements"
        assert ("head_height", "head_width") in result.conflicting_rules
        assert set(result.scale_bands) == {"head_height", "head_width"}

    def test_placement_conflict_names_the_rules(self):
        """Crown gap and eye line can each be satisfiable alone yet not together.

        Substituting u = 500s - g with g in [10,20] gives eye_line's expression as -300s - g,
        which is negative for any positive scale - so demanding it lie in [200,300] is
        impossible, and the solver must say which two rules disagree.

        An earlier version of this test asserted infeasibility for a pair that was in fact
        compatible (300s + g in [50,100] admits s in [0.1,0.3]). The solver found s=0.2 and
        was right; the test was wrong."""
        constraints = [
            Constraint(rule="crown_gap", a=500.0, b=-1.0, lo=10.0, hi=20.0),
            Constraint(rule="eye_line", a=-800.0, b=1.0, k=500.0, lo=700.0, hi=800.0),
            *containment(2000, 3000, 400, 500),
        ]
        result = solve(constraints, 400, 500)
        assert isinstance(result, Infeasible)
        assert result.conflicting_rules


class TestHorizontalPlacement:
    def test_review_counterexample_is_feasible(self):
        """From the plan review: source 1000 wide, output 600, scale 1, eye midpoint at 280.

        Exact centring demands a crop origin of -20, outside the image. A band permits origin
        0, putting the eye midpoint at 46.7% - inside ICAO's 45-55%. Treating centring as an
        equality would falsely reject this."""
        constraints = [
            Constraint(rule="scale_fixed", a=1.0, lo=1.0, hi=1.0),
            Constraint(rule="eye_x_band", a=280.0, c=-1.0, lo=0.45 * 600, hi=0.55 * 600),
            *containment(1000, 1000, 600, 600),
        ]
        result = solve(constraints, 600, 600)
        assert isinstance(result, Solution)
        assert result.crop_x >= -1e-6
        eye_in_output = 280.0 * result.scale - result.crop_x * result.scale
        assert 0.45 * 600 <= eye_in_output <= 0.55 * 600

    def test_exact_centring_outside_the_source_is_infeasible(self):
        """The same geometry with centring as an equality must fail, confirming the previous
        test passes because of the band and not by accident."""
        constraints = [
            Constraint(rule="scale_fixed", a=1.0, lo=1.0, hi=1.0),
            Constraint(rule="eye_x_exact", a=280.0, c=-1.0, lo=300.0, hi=300.0),
            *containment(1000, 1000, 600, 600),
        ]
        assert isinstance(solve(constraints, 600, 600), Infeasible)


class TestAbsentBounds:
    def test_a_missing_rule_contributes_nothing(self):
        """China's digital channel states no head-height rule. Its absence must not become a
        bound, and must not make the problem unsolvable."""
        constraints = [
            Constraint(rule="head_width", a=1000.0, lo=190.0, hi=220.0),
            Constraint(rule="crown_gap", a=400.0, b=-1.0, lo=10.0, hi=70.0),
            *containment(2000, 3000, 354, 472),
        ]
        result = solve(constraints, 354, 472)
        assert isinstance(result, Solution)
        assert "head_height" not in result.slacks

    def test_one_sided_bounds_are_accepted(self):
        constraints = [
            Constraint(rule="eye_from_bottom", a=-800.0, b=1.0, k=472.0, lo=256.0),
            Constraint(rule="head_width", a=1000.0, lo=190.0, hi=220.0),
            *containment(2000, 3000, 354, 472),
        ]
        assert isinstance(solve(constraints, 354, 472), Solution)

    def test_a_constraint_with_no_bounds_is_rejected_at_construction(self):
        with pytest.raises(ValueError, match="constrains nothing"):
            Constraint(rule="nothing", a=1.0)


class TestObjective:
    def test_the_chosen_scale_sits_mid_band(self):
        """Maximizing minimum slack should not park a result against a limit."""
        constraints = [
            Constraint(rule="head_height", a=1000.0, lo=400.0, hi=600.0),
            *containment(4000, 6000, 400, 500),
        ]
        result = solve(constraints, 400, 500)
        assert isinstance(result, Solution)
        assert result.scale == pytest.approx(0.5, abs=1e-3)
        assert result.min_slack > 0.4

    def test_containment_earns_no_reward(self):
        """A hard constraint must not pull the crop toward the middle of the photograph."""
        constraints = [
            Constraint(rule="head_height", a=1000.0, lo=500.0, hi=500.0),
            Constraint(rule="crown_gap", a=400.0, b=-1.0, lo=40.0, hi=60.0),
            *containment(4000, 6000, 400, 500),
        ]
        result = solve(constraints, 400, 500)
        assert isinstance(result, Solution)
        crown_in_output = 400.0 * result.scale - result.crop_y * result.scale
        assert crown_in_output == pytest.approx(50.0, abs=1.0)

    def test_solving_is_deterministic(self):
        constraints = [
            Constraint(rule="head_height", a=1000.0, lo=400.0, hi=600.0),
            Constraint(rule="crown_gap", a=400.0, b=-1.0, lo=10.0, hi=70.0),
            *containment(2000, 3000, 400, 500),
        ]
        first = solve(constraints, 400, 500)
        for _ in range(5):
            again = solve(constraints, 400, 500)
            assert isinstance(first, Solution) and isinstance(again, Solution)
            assert again.scale == first.scale
            assert again.crop_x == first.crop_x and again.crop_y == first.crop_y


class TestSourceLimits:
    def test_a_crop_that_would_leave_the_source_is_rejected(self):
        constraints = [
            Constraint(rule="head_height", a=1000.0, lo=990.0, hi=1000.0),
            *containment(200, 300, 400, 500),
        ]
        assert isinstance(solve(constraints, 400, 500), Infeasible)

    def test_unbounded_scale_is_reported_rather_than_guessed(self):
        constraints = [Constraint(rule="crown_gap", a=400.0, b=-1.0, lo=10.0, hi=70.0)]
        result = solve(constraints, 400, 500)
        assert isinstance(result, Infeasible)
        assert result.reason == "insufficient_resolution"

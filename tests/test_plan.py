"""Planning against real profiles, using the measurements taken from the reference photo.

The measurements below were produced by Stage 1 on IMG_8822 (2026-09-04). Checking the
numbers in rather than the photograph keeps a real face out of a public repository while
still exercising the profiles against something real.
"""

from __future__ import annotations

import pytest

from visaphoto.geometry import Infeasible, Solution
from visaphoto.measurements import Confidence, Measurement, MeasurementSet, Status
from visaphoto.plan import make_plan
from visaphoto.profiles import CN_VISA_DIGITAL, CN_VISA_PAPER, OutputSize, build_constraints

# As measured on the reference portrait, 2316x3088.
REFERENCE = {
    "crown_y": 493.0,
    "chin_y_landmark": 2278.2,
    "eye_line_y": 1319.7,
    "eye_mid_x": 1223.6,
    "inter_eye_distance": 494.6,
    "head_width_silhouette": 1086.0,
}


def reference_measurements(**overrides) -> MeasurementSet:
    values = {**REFERENCE, **overrides}
    result = MeasurementSet(source="IMG_8822", image_width=2316, image_height=3088)
    for name, value in values.items():
        if value is None:
            result.add(Measurement(
                name=name, definition="d", status=Status.UNAVAILABLE, reason="withheld"
            ))
            continue
        result.add(Measurement(
            name=name, definition="d", status=Status.AVAILABLE, value=value,
            unit="px", backend="stage1", confidence=Confidence.MEASURED,
        ))
    return result


class TestChinaDigital:
    def test_the_reference_photo_has_a_feasible_crop(self):
        plan = make_plan(CN_VISA_DIGITAL, reference_measurements())
        assert plan.feasible, plan.to_dict()
        assert isinstance(plan.chosen.outcome, Solution)

    def test_it_lands_at_the_reference_size(self):
        """420x560 is skipped, not failed: China states its pixel rules at 354x472 "as an
        example" and never says whether they scale."""
        plan = make_plan(CN_VISA_DIGITAL, reference_measurements())
        assert (plan.chosen.size.width, plan.chosen.size.height) == (354, 472)
        skipped = [a for a in plan.attempts if a.skipped]
        assert any(a.size.width == 420 for a in skipped)
        assert "never says whether they scale" in skipped[0].skipped

    def test_the_crop_satisfies_every_applied_rule(self):
        plan = make_plan(CN_VISA_DIGITAL, reference_measurements())
        solution = plan.chosen.outcome
        s, u, v = solution.scale, solution.crop_y * solution.scale, solution.crop_x * solution.scale
        constraints, _ = build_constraints(
            CN_VISA_DIGITAL, OutputSize(354, 472), reference_measurements()
        )
        for constraint in constraints:
            assert constraint.slack(s, u, v) >= -1e-6, constraint.rule

    def test_the_result_resembles_the_hand_built_crop(self):
        """Sanity, not equality. The hand-built 354x472 crop used scale 0.1872 with face
        width 204 px. The solver optimises slack rather than reproducing a human's choice, so
        it need not agree exactly - but a wildly different scale would mean something is
        wrong."""
        plan = make_plan(CN_VISA_DIGITAL, reference_measurements())
        assert 0.16 <= plan.chosen.outcome.scale <= 0.21

    def test_no_head_height_rule_is_applied(self):
        """The absence that started this project. China's digital channel states no
        head-height bound and the solver must not acquire one from anywhere."""
        plan = make_plan(CN_VISA_DIGITAL, reference_measurements())
        assert "head_height" not in plan.chosen.outcome.slacks
        assert not any(r.key == "head_height" for r in CN_VISA_DIGITAL.rules)


class TestUnavailableMeasurements:
    def test_a_missing_crown_disables_only_its_rule(self):
        plan = make_plan(CN_VISA_DIGITAL, reference_measurements(crown_y=None))
        assert plan.feasible
        assert any("crown_gap" in u for u in plan.chosen.unapplied)
        assert "crown_gap" not in plan.chosen.outcome.slacks

    def test_unapplied_rules_are_reported_not_dropped(self):
        plan = make_plan(CN_VISA_DIGITAL, reference_measurements(head_width_silhouette=None))
        assert plan.chosen.unapplied
        assert any("face_width" in u for u in plan.chosen.unapplied)


class TestInfeasibility:
    def test_a_tiny_source_is_refused_with_a_reason(self):
        small = reference_measurements()
        small.image_width, small.image_height = 200, 260
        plan = make_plan(CN_VISA_DIGITAL, small)
        assert not plan.feasible
        assert all(
            isinstance(a.outcome, Infeasible) or a.skipped for a in plan.attempts
        )

    def test_every_attempted_size_is_reported(self):
        small = reference_measurements()
        small.image_width, small.image_height = 200, 260
        plan = make_plan(CN_VISA_DIGITAL, small)
        assert len(plan.attempts) == len(CN_VISA_DIGITAL.sizes)


class TestChannelsDoNotBleed:
    def test_paper_and_digital_state_different_rules(self):
        digital = {r.key for r in CN_VISA_DIGITAL.rules}
        paper = {r.key for r in CN_VISA_PAPER.rules}
        assert "head_height" in paper and "head_height" not in digital
        assert "face_width" in digital and "face_width" not in paper

    def test_the_two_channels_have_different_aspect_ratios(self):
        """33:48 against 354:472. This is why their bands are not convertible, and why the
        millimetre rules must never be applied to the digital photo."""
        assert CN_VISA_DIGITAL.sizes[0].aspect == pytest.approx(354 / 472)
        assert CN_VISA_PAPER.sizes[0].aspect == pytest.approx(390 / 567, abs=1e-3)
        assert CN_VISA_DIGITAL.sizes[0].aspect != pytest.approx(
            CN_VISA_PAPER.sizes[0].aspect, abs=1e-3
        )

    def test_every_rule_carries_its_source_text(self):
        for profile in (CN_VISA_DIGITAL, CN_VISA_PAPER):
            for rule in profile.rules:
                assert rule.quote.strip(), f"{profile.key}/{rule.key}"
            assert profile.source.startswith("http")
            assert profile.retrieved


class TestPaperProfileUnits:
    """Review pass one: millimetre bounds were compared against pixel measurements, so the paper
    profile rejected the reference photograph as source_too_small."""

    def test_paper_profile_admits_the_reference_photo(self):
        plan = make_plan(CN_VISA_PAPER, reference_measurements())
        assert plan.feasible, plan.to_dict()
        assert 0.18 <= plan.chosen.outcome.scale <= 0.23

    def test_paper_bounds_are_in_output_pixels(self):
        constraints, _ = build_constraints(
            CN_VISA_PAPER, OutputSize(390, 567), reference_measurements()
        )
        head_height = next(c for c in constraints if c.rule == "head_height")
        px_per_mm = 567 / 48.0
        assert head_height.lo == pytest.approx(28.0 * px_per_mm)
        assert head_height.hi == pytest.approx(33.0 * px_per_mm)

    def test_a_mismatched_output_aspect_is_a_profile_error(self):
        from dataclasses import replace

        from visaphoto.profiles import ProfileError

        squashed = replace(CN_VISA_PAPER, sizes=(OutputSize(390, 400),))
        with pytest.raises(ProfileError, match="does not honour the printed aspect"):
            build_constraints(squashed, OutputSize(390, 400), reference_measurements())

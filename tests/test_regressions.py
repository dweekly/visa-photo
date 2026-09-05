"""Regressions for defects found by independent review of the Stage 1 diff.

Each test reproduces the reviewer's scenario. Both defects shared a shape worth naming: the
code produced a confident, wrong answer where it should have produced either a warning or an
explicit "unavailable".
"""

from __future__ import annotations

import numpy as np

from visaphoto.backends.segmentation import head_width_between
from visaphoto.preflight import Outcome, run
from visaphoto.requirements import for_jurisdiction
from tests.test_preflight import EYES_SHUT, NEUTRAL, make_set, outcome_for


class TestClosedEyesAreNotSilentlyAccepted:
    """China's rule is 'neutral with eyes open, mouth closed'. Inferring which signals a
    requirement covers from substrings in its key dropped the eyes-open half, so a photo with
    closed eyes passed and the CLI exited 0."""

    def test_closed_eyes_warn_for_china(self):
        report = run(make_set(), EYES_SHUT, jurisdiction="CN")
        assert outcome_for(report, "expression_neutral") is Outcome.WARN
        assert report.warnings, "closed eyes must not exit cleanly for CN"

    def test_neutral_still_passes(self):
        report = run(make_set(), NEUTRAL, jurisdiction="CN")
        assert outcome_for(report, "expression_neutral") is Outcome.LIKELY_OK

    def test_every_advisory_requirement_declares_its_signals(self):
        """The root cause, guarded directly: an advisory requirement with no declared signals
        silently evaluates nothing."""
        from visaphoto.requirements import GENERIC_ADVISORIES, REQUIREMENTS, Check

        for requirement in (*REQUIREMENTS, *GENERIC_ADVISORIES):
            if requirement.check is Check.ADVISORY_SIGNAL:
                assert requirement.signals, f"{requirement.key} assesses nothing"

    def test_chinas_requirement_covers_every_clause_it_quotes(self):
        """The quote names three things. All three must be checked."""
        (requirement,) = [
            r for r in for_jurisdiction("CN") if r.key == "expression_neutral"
        ]
        assert "eyes open" in requirement.quote
        assert "mouth closed" in requirement.quote
        assert set(requirement.signals) >= {"smile", "mouth_open", "eyes_closed"}


class TestHeadWidthIsBoundedByTheHead:
    """Sampling the upper quarter of the whole subject made the identical head measure 192px
    in a head-and-shoulders frame and 300px in a full-length one - reporting shoulder width as
    a measured head width."""

    @staticmethod
    def matte() -> np.ndarray:
        solid = np.zeros((1220, 600), dtype=bool)
        solid[20:220, 200:400] = True   # head, 200 px wide
        solid[220:1220, 150:450] = True  # torso, 300 px wide
        return solid

    def test_same_head_measures_the_same_in_any_frame(self):
        solid = self.matte()
        short, _ = head_width_between(solid[:320], 20, 120.0, 219.0)
        tall, _ = head_width_between(solid, 20, 120.0, 219.0)
        assert short == tall == 200

    def test_torso_width_never_reported_as_head_width(self):
        width, _ = head_width_between(self.matte(), 20, 120.0, 219.0)
        assert width != 300

    def test_missing_chin_yields_unavailable_not_a_guess(self):
        width, reason = head_width_between(self.matte(), 20, 120.0, None)
        assert width is None
        assert "chin or eye-line position is unavailable" in reason

    def test_chin_above_crown_is_rejected(self):
        width, reason = head_width_between(self.matte(), 500, 450.0, 219.0)
        assert width is None
        assert "not below the crown" in reason

    def test_empty_band_yields_unavailable(self):
        width, reason = head_width_between(np.zeros((100, 100), dtype=bool), 0, 25.0, 50.0)
        assert width is None
        assert "no solid rows" in reason


class TestMatteNoiseAndClipping:
    """Second review pass. Both defects reported a confident number where the honest answer
    was 'unavailable' or 'that pixel is not part of the head'."""

    @staticmethod
    def head_matte() -> np.ndarray:
        solid = np.zeros((300, 400), dtype=bool)
        solid[20:220, 100:300] = True  # 200 px wide head
        return solid

    def _result(self, eye_x=200.0, eye_y=120.0, chin=219.0):
        from visaphoto.measurements import Confidence, Measurement, MeasurementSet, Status

        r = MeasurementSet(source="synthetic", image_width=400, image_height=300)
        for name, value in (("eye_mid_x", eye_x), ("eye_line_y", eye_y),
                            ("chin_y_landmark", chin)):
            r.add(Measurement(
                name=name, definition="d", status=Status.AVAILABLE, value=value,
                unit="px", backend="synthetic", confidence=Confidence.MEASURED,
            ))
        return r

    def test_one_stray_pixel_does_not_inflate_head_width(self):
        """A single detached foreground pixel near the frame edge took 200 px to 291 px."""
        from visaphoto.backends.segmentation import _face_component

        solid = self.head_matte()
        clean, _ = head_width_between(solid, 20, 120.0, 219.0)
        assert clean == 200

        noisy = self.head_matte()
        noisy[60, 390] = True
        isolated = _face_component(noisy, self._result())
        measured, _ = head_width_between(isolated, 20, 120.0, 219.0)
        assert measured == 200, "segmentation noise must not be measured as anatomy"

    def test_head_clipped_at_the_side_is_unavailable(self):
        """Cropping through the hair leaves both eyes visible, so landmarks cannot catch it."""
        clipped = self.head_matte()[:, 150:]
        width, reason = head_width_between(clipped, 20, 120.0, 219.0)
        assert width is None
        assert "left or right edge" in reason

    def test_uncropped_head_still_measures(self):
        width, reason = head_width_between(self.head_matte(), 20, 120.0, 219.0)
        assert width == 200 and reason is None


class TestNoDetectedProblemIsHidden:
    """US and NZ have no transcribed expression rule, so closed eyes were detected and then
    reported nowhere: zero warnings, exit 0, while the identical input warned for CN."""

    def test_closed_eyes_warn_in_every_supported_mode(self):
        for code in ("CN", "US", "EU", "NZ", None):
            report = run(make_set(), EYES_SHUT, jurisdiction=code)
            assert report.warnings, f"closed eyes produced no warning for {code}"

    def test_generic_fallbacks_are_labelled_generic(self):
        """A borrowed advisory must never look like that country's own law."""
        report = run(make_set(), EYES_SHUT, jurisdiction="US")
        borrowed = [f for f in report.findings if f.requirement.key.startswith("generic_")]
        assert borrowed
        assert all("GENERIC" in f.requirement.jurisdictions for f in borrowed)

    def test_china_is_not_given_a_duplicate_expression_advisory(self):
        """CN states its own expression rule; the generic one must not be added on top."""
        keys = [f.requirement.key for f in run(make_set(), EYES_SHUT, jurisdiction="CN").findings]
        assert "expression_neutral" in keys
        assert "generic_expression_neutral" not in keys

"""Pre-flight logic, exercised with synthetic model output.

Using synthetic blendshape scores rather than photographs is deliberate: it lets the WARN path
be tested without needing a picture of someone smiling, and it keeps personal images out of a
public repository. The scores below are shaped like real MediaPipe output - the neutral set is
the measurement actually observed on the reference photo on 2026-09-04.
"""

from __future__ import annotations

import pytest

from visaphoto.measurements import (
    Confidence,
    Measurement,
    MeasurementSet,
    Precondition,
    Status,
)
from visaphoto.preflight import Outcome, run

NEUTRAL = {
    "mouthSmileLeft": 0.0045,
    "mouthSmileRight": 0.0027,
    "jawOpen": 0.0373,
    "eyeBlinkLeft": 0.1452,
    "eyeBlinkRight": 0.0664,
}
SMILING = {**NEUTRAL, "mouthSmileLeft": 0.81, "mouthSmileRight": 0.77}
MOUTH_OPEN = {**NEUTRAL, "jawOpen": 0.66}
EYES_SHUT = {**NEUTRAL, "eyeBlinkLeft": 0.93, "eyeBlinkRight": 0.91}


def make_set(ied: float = 494.0) -> MeasurementSet:
    result = MeasurementSet(source="synthetic", image_width=2316, image_height=3088)
    result.add(Measurement(
        name="inter_eye_distance",
        definition="Euclidean distance between the two iris centres (ICAO IED).",
        status=Status.AVAILABLE, value=ied, unit="px",
        backend="synthetic", confidence=Confidence.MEASURED,
        preconditions=(Precondition("image_decoded", True, "ok"),),
    ))
    return result


def outcome_for(report, key: str) -> Outcome:
    for finding in report.findings:
        if finding.requirement.key == key:
            return finding.outcome
    raise AssertionError(f"no finding for {key}; got {[f.requirement.key for f in report.findings]}")


class TestExpressionWarnings:
    def test_neutral_face_raises_nothing(self):
        report = run(make_set(), NEUTRAL, jurisdiction="CN")
        assert report.warnings == []
        assert outcome_for(report, "expression_neutral") is Outcome.LIKELY_OK

    def test_smile_warns(self):
        report = run(make_set(), SMILING, jurisdiction="CN")
        assert outcome_for(report, "expression_neutral") is Outcome.WARN
        assert report.warnings, "a clear smile must raise a warning"

    def test_open_mouth_warns(self):
        report = run(make_set(), MOUTH_OPEN, jurisdiction="CN")
        assert outcome_for(report, "expression_neutral") is Outcome.WARN

    def test_closed_eyes_warn_in_generic_mode(self):
        report = run(make_set(), EYES_SHUT, jurisdiction=None)
        assert outcome_for(report, "generic_eyes_open") is Outcome.WARN

    def test_warning_reports_score_and_threshold(self):
        """A warning a reader cannot second-guess is not much use."""
        report = run(make_set(), SMILING, jurisdiction="CN")
        warning = report.warnings[0]
        assert warning.score is not None
        assert warning.threshold is not None
        assert "uncalibrated" in warning.detail

    def test_missing_blendshapes_is_not_a_pass(self):
        report = run(make_set(), {}, jurisdiction="CN")
        assert outcome_for(report, "expression_neutral") is Outcome.NOT_EVALUATED


class TestResolution:
    def test_adequate_ied_passes(self):
        report = run(make_set(ied=494.0), NEUTRAL, jurisdiction=None)
        assert outcome_for(report, "generic_resolution") is Outcome.LIKELY_OK

    def test_ied_below_icao_minimum_warns(self):
        report = run(make_set(ied=61.0), NEUTRAL, jurisdiction=None)
        assert outcome_for(report, "generic_resolution") is Outcome.WARN

    def test_unmeasurable_ied_is_not_evaluated(self):
        result = MeasurementSet(source="synthetic", image_width=100, image_height=100)
        result.add(Measurement(
            name="inter_eye_distance", definition="IED.",
            status=Status.UNAVAILABLE,
            preconditions=(Precondition("face_detected_one", False, "no face"),),
        ))
        report = run(result, NEUTRAL, jurisdiction=None)
        assert outcome_for(report, "generic_resolution") is Outcome.NOT_EVALUATED


class TestModes:
    def test_known_jurisdiction(self):
        report = run(make_set(), NEUTRAL, jurisdiction="CN")
        assert report.mode == "jurisdiction"
        assert report.jurisdiction == "CN"

    def test_no_jurisdiction_is_generic(self):
        report = run(make_set(), NEUTRAL, jurisdiction=None)
        assert report.mode == "generic"
        assert all(f.requirement.key.startswith("generic_") for f in report.findings)

    def test_unseeded_jurisdiction_invents_nothing(self):
        """The failure mode this guards is an agent synthesising a spec from a web page."""
        report = run(make_set(), NEUTRAL, jurisdiction="JP")
        assert report.mode == "unseeded"
        assert report.findings == []

    def test_lowercase_jurisdiction_accepted(self):
        assert run(make_set(), NEUTRAL, jurisdiction="cn").mode == "jurisdiction"


class TestNonAssessableRequirementsAreHonest:
    @pytest.mark.parametrize(
        "key,expected",
        [
            ("recency_cn", Outcome.ATTESTATION_REQUIRED),
            ("head_covering_cn", Outcome.ATTESTATION_REQUIRED),
            ("glasses_cn", Outcome.NOT_EVALUATED),
            ("background_cn", Outcome.NOT_EVALUATED),
        ],
    )
    def test_never_reported_as_passing(self, key, expected):
        report = run(make_set(), NEUTRAL, jurisdiction="CN")
        assert outcome_for(report, key) is expected

    def test_nz_prohibits_editing(self):
        report = run(make_set(), NEUTRAL, jurisdiction="NZ")
        assert outcome_for(report, "no_digital_alteration_nz") is Outcome.OPERATION_POLICY

    def test_every_finding_carries_a_source_quote(self):
        for code in ("CN", "US", "EU", "NZ"):
            for finding in run(make_set(), NEUTRAL, jurisdiction=code).findings:
                assert finding.requirement.quote.strip()
                assert finding.requirement.source.startswith("http")

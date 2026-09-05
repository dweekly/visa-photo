"""The measurement contract's invariants.

These exist because the whole design rests on one property: a measurement can never be
"available" without a value, and can never be unavailable without a stated reason. If that
slips, silent nulls start flowing into geometry.
"""

from __future__ import annotations

import pytest

from visaphoto.measurements import (
    Confidence,
    Measurement,
    MeasurementSet,
    Status,
)
from visaphoto.requirements import REQUIREMENTS, for_jurisdiction, jurisdictions


class TestMeasurementInvariants:
    def test_available_requires_a_value(self):
        with pytest.raises(ValueError, match="requires a value"):
            Measurement(
                name="x", definition="d", status=Status.AVAILABLE,
                confidence=Confidence.MEASURED,
            )

    def test_available_requires_a_confidence(self):
        with pytest.raises(ValueError, match="requires a confidence"):
            Measurement(name="x", definition="d", status=Status.AVAILABLE, value=1.0)

    @pytest.mark.parametrize("status", [Status.UNAVAILABLE, Status.UNSUPPORTED])
    def test_non_available_requires_a_reason(self, status):
        with pytest.raises(ValueError, match="requires a reason"):
            Measurement(name="x", definition="d", status=status)

    def test_unavailable_is_not_available(self):
        m = Measurement(
            name="x", definition="d", status=Status.UNAVAILABLE, reason="because"
        )
        assert not m.available
        assert m.value is None

    def test_uncertainty_defaults_to_none(self):
        """No calibration has been done. A default of 0.0 would claim perfect precision."""
        m = Measurement(
            name="x", definition="d", status=Status.AVAILABLE, value=1.0,
            confidence=Confidence.MEASURED,
        )
        assert m.uncertainty is None


class TestMeasurementSet:
    def test_value_returns_none_for_unavailable(self):
        s = MeasurementSet(source="s", image_width=10, image_height=10)
        s.add(Measurement(
            name="crown_y", definition="d", status=Status.UNAVAILABLE, reason="truncated"
        ))
        assert s.value("crown_y") is None

    def test_value_returns_none_for_missing(self):
        s = MeasurementSet(source="s", image_width=10, image_height=10)
        assert s.value("never_measured") is None

    def test_round_trips_to_json_shape(self):
        s = MeasurementSet(source="s", image_width=10, image_height=20)
        s.add(Measurement(
            name="eye_line_y", definition="d", status=Status.AVAILABLE, value=5.0,
            unit="px", backend="b", confidence=Confidence.MEASURED,
        ))
        d = s.to_dict()
        assert d["image"] == {"width": 10, "height": 20}
        assert d["measurements"]["eye_line_y"]["status"] == "available"
        assert d["measurements"]["eye_line_y"]["definition"]


class TestRequirementsData:
    def test_every_requirement_is_quoted_and_sourced(self):
        for r in REQUIREMENTS:
            assert r.quote.strip(), f"{r.key} has no quote"
            assert r.source.startswith("http"), f"{r.key} has no source URL"
            assert r.jurisdictions, f"{r.key} names no jurisdiction"

    def test_keys_are_unique(self):
        keys = [r.key for r in REQUIREMENTS]
        assert len(keys) == len(set(keys))

    def test_unknown_jurisdiction_yields_nothing(self):
        assert for_jurisdiction("JP") == ()

    def test_the_four_transcribed_jurisdictions_are_present(self):
        assert set(jurisdictions()) >= {"CN", "US", "EU", "NZ"}

    def test_no_jurisdiction_borrows_another_rule(self):
        """China's white-background rule must not appear under NZ, which requires the
        opposite. Cross-contamination here is the schema-level version of the wrong-channel
        error this project exists to prevent."""
        nz_keys = {r.key for r in for_jurisdiction("NZ")}
        assert "background_cn" not in nz_keys
        cn_keys = {r.key for r in for_jurisdiction("CN")}
        assert "background_nz" not in cn_keys

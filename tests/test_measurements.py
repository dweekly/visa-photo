"""The measurement contract, the gate graph, and the registry.

These are the invariants the whole design rests on: a measurement cannot be available unless
every declared gate is True; a gate's truth is tri-state by identity; the registry is the only
construction path; the container refuses a second write. If any of these slips, silent wrong
numbers start flowing into geometry again.
"""

from __future__ import annotations

import math

import pytest

from visaphoto import gates as G
from visaphoto import registry
from visaphoto.measurements import (
    Confidence,
    DuplicateMeasurement,
    Measurement,
    MeasurementSet,
    Precondition,
    Status,
)


def all_true_record(image_id: str = "t") -> G.GateRecord:
    """A record where every evaluable gate passed. always_none gates stay None."""
    evaluators = {
        spec.id: (lambda g, sid=spec.id: (True, f"{sid} ok"))
        for spec in G.GATE_SPECS if not spec.always_none
    }
    return G.evaluate(image_id, evaluators)


def record_with(**overrides) -> G.GateRecord:
    """All gates True except those named; each override is (satisfied, detail)."""
    evaluators = {
        spec.id: (lambda g, sid=spec.id: overrides.get(sid, (True, f"{sid} ok")))
        for spec in G.GATE_SPECS if not spec.always_none
    }
    return G.evaluate("t", evaluators)


class TestPreconditionAndGateAreTriState:
    @pytest.mark.parametrize("bad", [1, 0, "", "yes", 1.0])
    def test_truthy_values_are_rejected(self, bad):
        with pytest.raises(TypeError):
            Precondition(id="image_decoded", satisfied=bad, detail="d")
        with pytest.raises(TypeError):
            G.Gate(id="image_decoded", satisfied=bad, detail="d")

    def test_unknown_gate_id_is_rejected(self):
        with pytest.raises(ValueError, match="unknown gate id"):
            G.Gate(id="not_a_gate", satisfied=True, detail="d")


class TestGateGraph:
    def test_is_acyclic_and_topologically_ordered(self):
        G.check_acyclic()  # raises on violation; also runs at import

    def test_a_none_prerequisite_makes_the_dependent_none_with_cause(self):
        rec = record_with(landmarks_478=(None, "model did not run"))
        for name in G.FRAME_LANDMARKS:
            gate = rec[f"landmark_in_frame:{name}"]
            assert gate.satisfied is None
            assert "landmarks_478 is None" in gate.detail

    def test_a_false_prerequisite_makes_the_dependent_none_not_false(self):
        """Dependents were not evaluated; saying they failed would be a claim without evidence."""
        rec = record_with(face_detected_one=(False, "2 faces"))
        assert rec["landmarks_478"].satisfied is None
        assert "face_detected_one is False" in rec["landmarks_478"].detail

    def test_always_none_gates_are_never_evaluated(self):
        called = []
        evaluators = {
            spec.id: (lambda g, sid=spec.id: (called.append(sid) or True, "ok"))
            for spec in G.GATE_SPECS
        }
        rec = G.evaluate("t", evaluators)
        for spec in G.GATE_SPECS:
            if spec.always_none:
                assert spec.id not in called
                assert rec[spec.id].satisfied is None

    def test_a_gate_with_no_evaluator_is_none(self):
        rec = G.evaluate("t", {})
        assert rec["image_decoded"].satisfied is None
        assert "no evaluator" in rec["image_decoded"].detail

    def test_record_is_complete_and_read_only(self):
        rec = all_true_record()
        assert set(rec.gates) == {s.id for s in G.GATE_SPECS}
        with pytest.raises(TypeError):
            rec.gates["image_decoded"] = None  # type: ignore[index]

    def test_incomplete_record_is_rejected(self):
        with pytest.raises(ValueError, match="incomplete"):
            G.GateRecord("t", {"image_decoded": G.Gate("image_decoded", True, "ok")})


class TestRegistry:
    def test_every_measurement_declares_at_least_one_known_gate(self):
        for spec in registry.REGISTRY.values():
            assert spec.gates, spec.name
            for gid in spec.gates:
                assert gid in G.GATE_BY_ID, f"{spec.name} -> {gid}"

    def test_anatomy_dependencies_stated_by_hand(self):
        """Independent of the registry's own data, so a registry omission is not reproduced."""
        r = registry.REGISTRY
        for name in ("eye_line_y", "eye_mid_x", "inter_eye_distance"):
            assert "eyes_unobscured_both" in r[name].gates, name
            assert "eyes_open_both" in r[name].gates, name
        for name in ("inter_eye_distance", "head_width_face_oval", "head_width_silhouette"):
            assert "yaw_within_measurement_limit" in r[name].gates, name
        assert "matte_clear_of_top_edge" in r["matte_top_row"].gates
        assert "landmark_in_frame:chin_152" in r["chin_landmark_y"].gates
        assert "no_headwear" in r["anatomical_crown_y"].gates
        assert "chin_landmark_is_anatomical" in r["anatomical_chin_y"].gates

    def test_diagnostic_eye_separation_does_not_require_occlusion_gates(self):
        """This is what breaks the cycle: the raw separation sizes the patches that decide
        occlusion, so it must not itself depend on occlusion."""
        assert "eyes_unobscured_both" not in registry.REGISTRY["raw_eye_separation"].gates

    def test_unknown_name_is_rejected(self):
        with pytest.raises(KeyError):
            registry.build("nothing", 1.0, all_true_record())

    def test_all_gates_true_yields_available(self):
        m = registry.build("eye_line_y", 1320.0, all_true_record())
        assert m.status is Status.AVAILABLE and m.value == 1320.0
        assert {p.id for p in m.preconditions} == set(registry.REGISTRY["eye_line_y"].gates)

    def test_all_gates_true_but_no_candidate_is_an_emitter_bug(self):
        with pytest.raises(ValueError, match="candidate value"):
            registry.build("eye_line_y", None, all_true_record())

    def test_nan_is_never_available(self):
        with pytest.raises(ValueError):
            registry.build("eye_line_y", math.nan, all_true_record())

    def test_one_false_gate_yields_unavailable_with_that_blocker(self):
        rec = record_with(**{"eye_unobscured:left": (False, "ratio 0.30")})
        m = registry.build("inter_eye_distance", 494.0, rec)
        assert m.status is Status.UNAVAILABLE and m.value is None
        assert [p.id for p in m.blockers_unknown] == ["eyes_unobscured_both"]
        assert "eye_unobscured:left is False" in m.reason

    def test_one_none_gate_yields_unavailable_not_evaluated(self):
        rec = record_with(pose_decomposition_valid=(None, "no matrix"))
        m = registry.build("inter_eye_distance", 494.0, rec)
        assert m.status is Status.UNAVAILABLE
        assert "not evaluated" in m.reason
        assert "yaw_within_measurement_limit" in m.reason

    def test_anatomical_tier_is_unavailable_on_a_perfect_record(self):
        rec = all_true_record()
        for name in ("anatomical_crown_y", "anatomical_chin_y"):
            m = registry.build(name, 100.0, rec)
            assert m.status is Status.UNAVAILABLE
            assert m.blockers_unknown and not m.blockers_false

    def test_capabilities_needs_no_weights_and_marks_permanent_gaps(self):
        rows = {r["measurement"]: r for r in registry.capabilities()}
        assert set(rows) == set(registry.REGISTRY)
        assert rows["anatomical_crown_y"]["available_in_this_build"] is False
        assert rows["matte_top_row"]["available_in_this_build"] is True
        assert "no_headwear" in rows["anatomical_crown_y"]["always_unknown_gates"]


class TestMeasurementInvariants:
    def pre(self, satisfied):
        return (Precondition("image_decoded", satisfied, "d"),)

    def test_available_requires_every_precondition_true(self):
        for bad in (False, None):
            with pytest.raises(ValueError, match="unsatisfied"):
                Measurement(name="x", definition="d", status=Status.AVAILABLE,
                            preconditions=self.pre(bad), value=1.0,
                            confidence=Confidence.MEASURED)

    def test_available_requires_a_precondition_at_all(self):
        with pytest.raises(ValueError, match="at least one precondition"):
            Measurement(name="x", definition="d", status=Status.AVAILABLE, preconditions=(),
                        value=1.0, confidence=Confidence.MEASURED)

    @pytest.mark.parametrize("value", [None, math.nan, math.inf])
    def test_available_requires_a_finite_value(self, value):
        with pytest.raises(ValueError, match="finite"):
            Measurement(name="x", definition="d", status=Status.AVAILABLE,
                        preconditions=self.pre(True), value=value, confidence=Confidence.MEASURED)

    def test_unavailable_carries_no_value_and_needs_a_blocker(self):
        with pytest.raises(ValueError, match="must not carry a value"):
            Measurement(name="x", definition="d", status=Status.UNAVAILABLE,
                        preconditions=self.pre(False), value=1.0)
        with pytest.raises(ValueError, match="failing gate"):
            Measurement(name="x", definition="d", status=Status.UNAVAILABLE,
                        preconditions=self.pre(True))

    def test_not_attempted_needs_a_reason_and_nothing_else(self):
        m = Measurement(name="x", definition="d", status=Status.NOT_ATTEMPTED,
                        preconditions=(), not_attempted_reason="disabled")
        assert m.reason == "disabled"
        with pytest.raises(ValueError):
            Measurement(name="x", definition="d", status=Status.NOT_ATTEMPTED, preconditions=())

    def test_measurement_is_immutable(self):
        m = Measurement(name="x", definition="d", status=Status.AVAILABLE,
                        preconditions=self.pre(True), value=1.0, confidence=Confidence.MEASURED)
        with pytest.raises(Exception):
            m.status = Status.UNAVAILABLE  # type: ignore[misc]


class TestMeasurementSet:
    def test_second_write_to_a_name_is_refused(self):
        s = MeasurementSet(source="s", image_width=10, image_height=10)
        first = Measurement(name="x", definition="d", status=Status.UNAVAILABLE,
                            preconditions=(Precondition("image_decoded", False, "d"),))
        s.add(first)
        later = Measurement(name="x", definition="d", status=Status.AVAILABLE,
                            preconditions=(Precondition("image_decoded", True, "d"),),
                            value=1.0, confidence=Confidence.MEASURED)
        with pytest.raises(DuplicateMeasurement):
            s.add(later)
        assert s.status("x") is Status.UNAVAILABLE

    def test_storage_is_not_writable_from_outside(self):
        s = MeasurementSet(source="s", image_width=10, image_height=10)
        with pytest.raises(TypeError):
            s.measurements["x"] = None  # type: ignore[index]

    def test_value_is_none_unless_available(self):
        s = MeasurementSet(source="s", image_width=10, image_height=10)
        s.add(Measurement(name="x", definition="d", status=Status.NOT_ATTEMPTED,
                          preconditions=(), not_attempted_reason="off"))
        assert s.value("x") is None and s.value("missing") is None

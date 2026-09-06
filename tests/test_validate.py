"""Verdicts on a file, from the file: the interval rule, file facts, the validator on synthetic
measurement sets, and the command end to end from photographs on disk."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from tests.test_regressions import H, W, landmarks, matte, run
from visaphoto.backends.landmarks import IDX_CHIN, IDX_IRIS_LEFT, IDX_IRIS_RIGHT


def lm_index(name):
    return {"left": IDX_IRIS_LEFT, "right": IDX_IRIS_RIGHT, "chin": IDX_CHIN}[name]
from tests.test_render import (
    FAITHFUL, feasible_plan, flat, output_fits, stub_fits, textured, write_photo,
)
from visaphoto import cli
from visaphoto.evaluate import measure_all
from visaphoto.geometry import Infeasible
from visaphoto.plan import make_plan
from visaphoto.profiles import CN_VISA_DIGITAL, OutputSize, build_constraints
from visaphoto.validate import (
    REPORT_VERSION, Verdict, file_facts, interval_verdict, observe, predict, validate,
)


# --- the interval rule ------------------------------------------------------------------------
class TestIntervalVerdict:
    def test_inside_disjoint_straddling(self):
        assert interval_verdict(50, 0, 10, 70) is Verdict.PASS
        assert interval_verdict(80, 0, 10, 70) is Verdict.FAIL
        assert interval_verdict(5, 0, 10, 70) is Verdict.FAIL
        assert interval_verdict(69.5, 1.0, 10, 70) is Verdict.INDETERMINATE   # prediction 68.5
        assert interval_verdict(69.5, 0.1, 10, 70) is Verdict.PASS            # prediction 69.4
        assert interval_verdict(69.5, 0.0, 10, 70) is Verdict.PASS            # no prediction

    def test_a_feasible_prediction_makes_any_disagreement_indeterminate_not_fail(self):
        """The interval around the observation contains the prediction, which satisfied the
        band, so it cannot be disjoint from the band."""
        assert interval_verdict(120, abs(120 - 40), 10, 70) is Verdict.INDETERMINATE

    def test_inclusive_endpoints_pass_on_equality(self):
        assert interval_verdict(70, 0, 10, 70) is Verdict.PASS
        assert interval_verdict(69.5, 0.5, 10, 70) is Verdict.PASS  # touches an inclusive bound

    def test_strict_bounds_exclude_their_endpoint(self):
        assert interval_verdict(60, 0, 60, None, lo_strict=True) is Verdict.FAIL
        assert interval_verdict(60.01, 0, 60, None, lo_strict=True) is Verdict.PASS
        assert interval_verdict(59.99, 0, 60, None, lo_strict=True) is Verdict.FAIL
        assert interval_verdict(60.5, 0.5, 60, None, lo_strict=True) is Verdict.INDETERMINATE
        assert interval_verdict(256, 0, 256, None, lo_strict=True) is Verdict.FAIL

    def test_one_sided_bands(self):
        assert interval_verdict(1e9, 0, 256, None) is Verdict.PASS
        assert interval_verdict(-5, 0, None, 70) is Verdict.PASS


class TestStrictBoundsInTheSchema:
    def test_chinas_two_greater_than_rules_are_strict(self):
        rules = {r.key: r for r in CN_VISA_DIGITAL.rules}
        assert rules["inter_eye_distance"].lo_strict and rules["eye_line_from_bottom"].lo_strict
        assert not rules["face_width"].lo_strict and not rules["crown_gap"].hi_strict

    def test_strictness_reaches_the_constraints(self):
        constraints, _ = build_constraints(CN_VISA_DIGITAL, OutputSize(354, 472), run())
        by_rule = {c.rule: c for c in constraints}
        assert by_rule["inter_eye_distance"].lo_strict and by_rule["eye_line_from_bottom"].lo_strict

    def test_solver_refuses_a_point_on_a_strict_bound(self):
        """Through the real profile: a head width of 300 px allows scales up to 219/300, and an
        inter-eye distance of exactly 60/(219/300) needs at least that scale to reach 60 px. The
        feasible set is one point, and at it the IED is exactly 60 - on the strict bound."""
        from tests.test_plan import reference_measurements

        s_max = 219.0 / 300.0
        m = reference_measurements(head_width_silhouette=300.0, inter_eye_distance=60.0 / s_max,
                                   eye_line_y=1200.0, matte_top_row=1000.0,
                                   chin_landmark_y=1800.0, eye_mid_x=1158.0)
        plan = make_plan(CN_VISA_DIGITAL, m)
        assert not plan.feasible
        out = plan.attempts[0].outcome
        assert isinstance(out, Infeasible) and out.reason == "strict_bound", out
        assert "inter_eye_distance" in out.detail and "> 60" in out.detail

    def test_the_same_point_just_above_the_bound_solves(self):
        from tests.test_plan import reference_measurements

        s_max = 219.0 / 300.0
        m = reference_measurements(head_width_silhouette=300.0, inter_eye_distance=60.5 / s_max,
                                   eye_line_y=1200.0, matte_top_row=1000.0,
                                   chin_landmark_y=1800.0, eye_mid_x=1158.0)
        assert make_plan(CN_VISA_DIGITAL, m).feasible


# --- file facts ---------------------------------------------------------------------------------
class TestFileFacts:
    def test_facts_come_from_the_file_not_the_view(self, tmp_path):
        grey = tmp_path / "g.jpg"
        Image.new("L", (354, 472), 128).save(grey, quality=95)
        f = file_facts(grey, (354, 472))
        assert (f.format, f.mode, f.bits) == ("JPEG", "L", 8)
        assert f.bytes == grey.stat().st_size
        png = tmp_path / "p.png"
        Image.new("RGB", (354, 472), (1, 2, 3)).save(png)
        assert file_facts(png, (354, 472)).format == "PNG"

    def test_stored_and_measured_dimensions_are_both_kept(self, tmp_path):
        photo = write_photo(tmp_path / "r.jpg", flat(354, 472), orientation=6)
        f = file_facts(photo, (354, 472))
        assert (f.stored_width, f.stored_height) == (472, 354)
        assert (f.measured_width, f.measured_height) == (354, 472)


# --- the validator on synthetic measurement sets --------------------------------------------------
def output_measurements(plan, dx=0.0, dy=0.0):
    """A measurement set for a 354x472 output whose fits are the plan-transformed fixture."""
    lm, m = output_fits(plan, dx, dy)
    px = np.full((472, 354, 3), 128, dtype=np.uint8)
    return measure_all(px, lm, m, source="out", segmentation_attempted=True)


def facts_like(path="out.jpg", fmt="JPEG", mode="RGB", size=(354, 472), nbytes=100_000, stored=None):
    from visaphoto.validate import FileFacts
    stored = stored or size
    return FileFacts(path, fmt, mode, 8 if mode in ("RGB", "L") else None,
                     stored[0], stored[1], size[0], size[1], nbytes)


class TestObserveAndPredict:
    def test_only_rules_get_quantities(self):
        plan = feasible_plan()
        observed, refusal = observe(CN_VISA_DIGITAL, (354, 472), output_measurements(plan))
        assert refusal is None
        assert set(observed) == {r.key for r in CN_VISA_DIGITAL.rules}
        predicted = predict(CN_VISA_DIGITAL, plan, run())
        assert set(predicted) == set(observed)

    def test_observed_equals_the_constraint_at_identity(self):
        plan = feasible_plan()
        m = output_measurements(plan)
        observed, _ = observe(CN_VISA_DIGITAL, (354, 472), m)
        constraints, _ = build_constraints(CN_VISA_DIGITAL, OutputSize(354, 472), m)
        for c in constraints:
            if c.rule in observed:
                assert observed[c.rule] == c.value(1.0, 0.0, 0.0)

    def test_prediction_matches_a_faithful_output_within_rounding(self):
        plan = feasible_plan()
        observed, _ = observe(CN_VISA_DIGITAL, (354, 472), output_measurements(plan))
        predicted = predict(CN_VISA_DIGITAL, plan, run())
        for key in predicted:
            assert abs(observed[key] - predicted[key]) < 1.0, (key, observed[key], predicted[key])

    def test_a_non_reference_size_refuses_the_pixel_rules_with_the_reason(self):
        observed, refusal = observe(CN_VISA_DIGITAL, (420, 560), output_measurements(feasible_plan()))
        assert observed == {} and "as an example" in refusal


class TestValidate:
    def test_a_faithful_output_passes_implemented_checks(self):
        plan = feasible_plan()
        v = validate(CN_VISA_DIGITAL, facts_like(), output_measurements(plan), None,
                     predict(CN_VISA_DIGITAL, plan, run()))
        assert v.aggregate == "passes_implemented_checks", [(c.key, c.verdict, c.detail) for c in v.criteria]
        assert v.uncertainty == "delta"
        assert {c.key for c in v.criteria if c.kind == "rule"} == {r.key for r in CN_VISA_DIGITAL.rules}
        assert {c.key for c in v.criteria if c.kind == "encoding"} == {"dimensions", "format", "colour", "size_bytes"}
        assert [a["key"] for a in v.attestations] == ["head_covering_cn", "recency_cn"]
        assert {n["key"] for n in v.not_assessable} >= {"background_cn", "photo_quality_cn"}
        assert v.policies["replace_background"] == "unresolved"

    def test_a_large_disagreement_is_indeterminate_with_both_numbers(self):
        plan = feasible_plan()
        v = validate(CN_VISA_DIGITAL, facts_like(), output_measurements(plan, dy=+30.0), None,
                     predict(CN_VISA_DIGITAL, plan, run()))
        eye = next(c for c in v.criteria if c.key == "eye_line_from_bottom")
        assert eye.verdict is Verdict.INDETERMINATE
        assert eye.predicted is not None and abs(eye.delta - (-30.0)) < 1.0
        assert "predicted" in eye.detail and v.aggregate == "incomplete"

    def test_standalone_has_no_interval(self):
        v = validate(CN_VISA_DIGITAL, facts_like(), output_measurements(feasible_plan()), None)
        assert v.uncertainty == "none"
        assert all(c.predicted is None and c.delta is None for c in v.criteria if c.kind == "rule")

    def test_unavailable_measurement_names_the_outputs_blocker(self):
        plan = feasible_plan()
        lm, _ = output_fits(plan)
        from visaphoto.backends.segmentation import MatteFit
        alpha = np.zeros((472, 354), dtype=np.uint8); alpha[0:400, 100:250] = 255  # touches the top edge
        m = measure_all(np.full((472, 354, 3), 128, dtype=np.uint8), lm, MatteFit(True, True, alpha, "t"),
                        source="out", segmentation_attempted=True)
        v = validate(CN_VISA_DIGITAL, facts_like(), m, None, predict(CN_VISA_DIGITAL, plan, run()))
        crown = next(c for c in v.criteria if c.key == "crown_gap")
        assert crown.verdict is Verdict.NOT_EVALUATED and crown.observed is None
        assert "matte_top_row is unavailable" in crown.detail and "matte_clear_of_top_edge" in crown.detail

    @pytest.mark.parametrize("nbytes,expected", [
        (39_000, Verdict.FAIL), (40_000, Verdict.INDETERMINATE), (40_500, Verdict.INDETERMINATE),
        (40_960, Verdict.PASS), (41_000, Verdict.PASS), (120_000, Verdict.PASS),
        (121_000, Verdict.INDETERMINATE), (122_880, Verdict.INDETERMINATE), (123_000, Verdict.FAIL),
    ])
    def test_both_readings_of_kb(self, nbytes, expected):
        v = validate(CN_VISA_DIGITAL, facts_like(nbytes=nbytes), output_measurements(feasible_plan()), None)
        c = next(c for c in v.criteria if c.key == "size_bytes")
        assert c.verdict is expected, c.detail
        if expected is Verdict.INDETERMINATE:
            assert "KB = 1,000" in c.detail and "KB = 1,024" in c.detail

    def test_format_and_colour_from_the_file(self):
        m = output_measurements(feasible_plan())
        v = validate(CN_VISA_DIGITAL, facts_like(fmt="PNG"), m, None)
        assert next(c for c in v.criteria if c.key == "format").verdict is Verdict.FAIL
        v = validate(CN_VISA_DIGITAL, facts_like(mode="L"), m, None)
        assert next(c for c in v.criteria if c.key == "colour").verdict is Verdict.FAIL
        assert v.aggregate == "fails"

    def test_the_three_sizes(self):
        plan = feasible_plan()
        m354 = output_measurements(plan)
        v = validate(CN_VISA_DIGITAL, facts_like(), m354, None)
        assert next(c for c in v.criteria if c.key == "dimensions").verdict is Verdict.PASS

        v = validate(CN_VISA_DIGITAL, facts_like(size=(420, 560)), m354, None)
        assert next(c for c in v.criteria if c.key == "dimensions").verdict is Verdict.PASS
        assert all(c.verdict is Verdict.NOT_EVALUATED for c in v.criteria if c.kind == "rule")
        assert v.aggregate == "incomplete"

        v = validate(CN_VISA_DIGITAL, facts_like(size=(600, 800)), run(), None)
        assert next(c for c in v.criteria if c.key == "dimensions").verdict is Verdict.FAIL
        assert all(c.verdict is Verdict.NOT_EVALUATED for c in v.criteria if c.kind == "rule")
        assert v.aggregate == "fails"

    def test_rotated_file_dimensions_follow_the_frames_that_are_listed(self):
        m = output_measurements(feasible_plan())

        def dims(stored, measured):
            v = validate(CN_VISA_DIGITAL, facts_like(size=measured, stored=stored), m, None)
            return next(c for c in v.criteria if c.key == "dimensions"), v.aggregate

        c, _ = dims((472, 354), (354, 472))  # only the oriented frame is listed
        assert c.verdict is Verdict.INDETERMINATE and "only one" in c.detail
        c, aggregate = dims((800, 600), (600, 800))  # neither frame is listed: a definite failure
        assert c.verdict is Verdict.FAIL and "neither" in c.detail and aggregate == "fails"
        c, _ = dims((354, 472), (354, 472))
        assert c.verdict is Verdict.PASS


# --- the command ------------------------------------------------------------------------------------
def run_cli(args, capsys):
    code = cli.main(args)
    out = capsys.readouterr().out
    return code, (json.loads(out) if args and "--json" in args else out)


ENVELOPE = {"report_version", "tool", "error", "measurements", "preflight", "plan", "render", "encode", "validation"}


class TestCli:
    def test_out_then_validation_of_the_written_file(self, tmp_path, monkeypatch, capsys):
        photo = write_photo(tmp_path / "p.jpg", textured(600, 800, sigma=20))
        stub_fits(monkeypatch)
        out = tmp_path / "o.jpg"
        code, r = run_cli([str(photo), "--spec", "cn_visa_digital", "--out", str(out), "--model", str(photo), "--json"], capsys)
        assert code == cli.EXIT_OK, r["validation"]
        assert set(r) == ENVELOPE and r["report_version"] == REPORT_VERSION and r["error"] is None
        assert r["tool"]["version"] and "mediapipe" in r["tool"]["backends"]
        v = r["validation"]
        assert v["profile"] == "cn_visa_digital" and v["uncertainty"] == "delta"
        assert v["file"]["path"] == str(out) and v["file"]["bytes"] == out.stat().st_size
        assert v["aggregate"] == "passes_implemented_checks", v["criteria"]
        assert v["preflight"]["mode"] == "jurisdiction" and v["preflight"]["jurisdiction"] == "CN"
        assert r["preflight"]["jurisdiction"] == "CN"  # --spec selected China's advisories for the input too
        assert r["measurements"]["image"] == {"width": 600, "height": 800}
        assert v["measurements"]["image"] == {"width": 354, "height": 472}
        rules = {c["key"]: c for c in v["criteria"] if c["kind"] == "rule"}
        assert all(c["predicted"] is not None and c["delta"] is not None for c in rules.values())

    def test_validate_the_written_file_standalone_agrees(self, tmp_path, monkeypatch, capsys):
        photo = write_photo(tmp_path / "p.jpg", textured(600, 800, sigma=20))
        stub_fits(monkeypatch)
        out = tmp_path / "o.jpg"
        _, first = run_cli([str(photo), "--spec", "cn_visa_digital", "--out", str(out), "--model", str(photo), "--json"], capsys)
        code, second = run_cli([str(out), "--spec", "cn_visa_digital", "--validate", "--model", str(photo), "--json"], capsys)
        assert code == cli.EXIT_OK
        assert second["plan"] is None and second["render"] is None and second["encode"] is None
        a = {c["key"]: c for c in first["validation"]["criteria"]}
        b = {c["key"]: c for c in second["validation"]["criteria"]}
        assert set(a) == set(b)
        for key in a:
            assert a[key]["observed"] == b[key]["observed"], key
            assert (a[key]["lo"], a[key]["hi"]) == (b[key]["lo"], b[key]["hi"])
            if a[key]["kind"] == "encoding":
                assert a[key]["verdict"] == b[key]["verdict"], key
        assert second["validation"]["uncertainty"] == "none"
        assert all(c["predicted"] is None for c in b.values())
        # comfortably interior: the geometric verdicts agree too
        assert {k: a[k]["verdict"] for k in a} == {k: b[k]["verdict"] for k in b}

    def test_a_near_bound_output_differs_between_the_two_paths(self, tmp_path, monkeypatch, capsys):
        """The output's eye line lands a third of the way from the prediction toward the 256-px
        bound: x itself passes, but the interval [x - |x - pred|, x + |x - pred|] reaches below
        256. Post-write is indeterminate; the same file standalone passes."""
        photo = write_photo(tmp_path / "p.jpg", textured(600, 800, sigma=20))
        plan = feasible_plan()
        pred = predict(CN_VISA_DIGITAL, plan, run())["eye_line_from_bottom"]
        target = 256.0 + (pred - 256.0) / 3.0
        assert target > 256.0 and target - (pred - target) < 256.0
        stub_fits(monkeypatch, output=output_fits(plan, dy=pred - target))  # eye line moves down
        out = tmp_path / "o.jpg"
        code, r = run_cli([str(photo), "--spec", "cn_visa_digital", "--out", str(out), "--model", str(photo), "--json"], capsys)
        eye = next(c for c in r["validation"]["criteria"] if c["key"] == "eye_line_from_bottom")
        assert eye["verdict"] == "indeterminate", eye
        assert code == cli.EXIT_OK and r["validation"]["aggregate"] == "incomplete"
        code, s = run_cli([str(out), "--spec", "cn_visa_digital", "--validate", "--model", str(photo), "--json"], capsys)
        eye = next(c for c in s["validation"]["criteria"] if c["key"] == "eye_line_from_bottom")
        assert eye["verdict"] == "pass", eye

    def test_validate_a_photo_of_the_wrong_size_fails_and_exits_6(self, tmp_path, monkeypatch, capsys):
        photo = write_photo(tmp_path / "p.jpg", textured(600, 800, sigma=20))
        stub_fits(monkeypatch)
        code, r = run_cli([str(photo), "--spec", "cn_visa_digital", "--validate", "--model", str(photo), "--json"], capsys)
        assert code == cli.EXIT_FAILS
        v = r["validation"]
        assert v["aggregate"] == "fails"
        assert next(c for c in v["criteria"] if c["key"] == "dimensions")["verdict"] == "fail"
        assert all(c["verdict"] == "not_evaluated" for c in v["criteria"] if c["kind"] == "rule")

    def test_validate_text_output(self, tmp_path, monkeypatch, capsys):
        photo = write_photo(tmp_path / "p.jpg", textured(600, 800, sigma=20))
        stub_fits(monkeypatch)
        code, text = run_cli([str(photo), "--spec", "cn_visa_digital", "--validate", "--model", str(photo)], capsys)
        assert "validation of" in text and "aggregate: fails" in text
        assert "dimensions" in text and "not assessable in this build" in text and "still to attest" in text

    def test_usage_errors(self, tmp_path, capsys):
        photo = write_photo(tmp_path / "p.jpg", flat())
        assert cli.main([str(photo), "--validate"]) == cli.EXIT_USAGE
        assert cli.main([str(photo), "--spec", "cn_visa_digital", "--validate", "--out", str(tmp_path / "o.jpg")]) == cli.EXIT_USAGE
        assert cli.main([str(photo), "--spec", "cn_visa_paper", "--validate"]) == cli.EXIT_USAGE
        assert cli.main([str(photo), "--spec", "cn_visa_digital", "--for", "NZ", "--validate"]) == cli.EXIT_USAGE
        assert "conflicts" in capsys.readouterr().err

    def test_for_agreeing_with_spec_is_fine(self, tmp_path, monkeypatch, capsys):
        photo = write_photo(tmp_path / "p.jpg", textured(600, 800, sigma=20))
        stub_fits(monkeypatch)
        code, r = run_cli([str(photo), "--spec", "cn_visa_digital", "--for", "cn", "--model", str(photo), "--json"], capsys)
        assert code == cli.EXIT_OK and r["preflight"]["jurisdiction"] == "CN"

    def test_an_undecodable_input_still_emits_the_envelope(self, tmp_path, capsys):
        bad = tmp_path / "p.jpg"
        bad.write_bytes(b"not an image")
        code, r = run_cli([str(bad), "--spec", "cn_visa_digital", "--model", str(bad), "--json"], capsys)
        assert code == cli.EXIT_CANNOT_MEASURE
        assert set(r) == ENVELOPE and "could not read" in r["error"]
        assert r["measurements"] is None and r["validation"] is None

    def test_an_unmeasurable_written_file_keeps_encode_done_and_exits_2(self, tmp_path, monkeypatch, capsys):
        photo = write_photo(tmp_path / "p.jpg", textured(600, 800, sigma=20))
        stub_fits(monkeypatch)
        out = tmp_path / "o.jpg"
        from visaphoto import measure
        real = measure.load_source

        def failing(p):
            if Path(p) == out:
                raise measure.MeasurementError(f"could not read {p}: injected")
            return real(p)

        monkeypatch.setattr(cli, "load_source", failing)
        code, r = run_cli([str(photo), "--spec", "cn_visa_digital", "--out", str(out), "--model", str(photo), "--json"], capsys)
        assert code == cli.EXIT_CANNOT_MEASURE
        assert r["encode"]["status"] == "done" and out.exists()
        assert "written file could not be measured" in r["validation"]["error"] and r["error"]

    def test_an_advisory_warning_on_the_written_file_is_exit_1_in_both_output_modes(self, tmp_path, monkeypatch, capsys):
        """A smile on the output: text mode must print the warning, not crash on it."""
        from tests.test_regressions import NEUTRAL

        photo = write_photo(tmp_path / "p.jpg", textured(600, 800, sigma=20))
        plan = feasible_plan()
        lm, m = output_fits(plan)
        smiling = landmarks(left=lm.points[lm_index("left")], right=lm.points[lm_index("right")],
                            chin=lm.points[lm_index("chin")],
                            blendshapes={**NEUTRAL, "mouthSmileLeft": 0.9, "mouthSmileRight": 0.9})
        stub_fits(monkeypatch, output=(smiling, m))
        out = tmp_path / "o.jpg"
        code, text = run_cli([str(photo), "--spec", "cn_visa_digital", "--out", str(out), "--model", str(photo)], capsys)
        assert code == cli.EXIT_WARNINGS
        assert "advisory warnings on this file: expression_neutral" in text
        code, r = run_cli([str(photo), "--spec", "cn_visa_digital", "--out", str(out), "--model", str(photo), "--json"], capsys)
        assert code == cli.EXIT_WARNINGS and r["validation"]["aggregate"] == "passes_implemented_checks"

    def test_a_written_file_with_no_face_is_an_unmeasured_output_exit_2(self, tmp_path, monkeypatch, capsys):
        photo = write_photo(tmp_path / "p.jpg", textured(600, 800, sigma=20))
        stub_fits(monkeypatch, output=(landmarks(faces=0), output_fits(feasible_plan())[1]))
        out = tmp_path / "o.jpg"
        code, r = run_cli([str(photo), "--spec", "cn_visa_digital", "--out", str(out), "--model", str(photo), "--json"], capsys)
        assert code == cli.EXIT_CANNOT_MEASURE
        assert r["encode"]["status"] == "done" and out.exists()
        assert "written file could not be measured" in r["validation"]["error"] and r["error"]
        assert r["validation"]["aggregate"] == "incomplete"  # the validation that was possible is kept

    def test_capabilities_json_keeps_its_own_schema(self, capsys):
        code, r = run_cli(["--capabilities", "--json"], capsys)
        assert code == cli.EXIT_OK and "measurements" in r and "report_version" not in r

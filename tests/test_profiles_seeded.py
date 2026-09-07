"""The seeded profiles: every rule traceable to its sentence, every plan honest about what it
could and could not apply, and the report carrying the reading wherever one was chosen."""

from __future__ import annotations

import json
import re
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from tests.test_plan import reference_measurements
from tests.test_regressions import NEUTRAL, landmarks
from tests.test_render import FAITHFUL, SWAPPED_RG, feasible_plan, flat, output_fits, textured, write_photo
from tests.test_validate import facts_like, run_cli
from visaphoto import cli, measure
from visaphoto.backends.segmentation import MatteFit
from visaphoto.encode import EncodeResult
from visaphoto.evaluate import measure_all
from visaphoto.geometry import Infeasible
from visaphoto.measurements import Confidence, Measurement, MeasurementSet, Precondition, Status
from visaphoto.plan import make_plan
from visaphoto.preflight import Outcome, run as preflight_run
from visaphoto.profiles import (
    CN_VISA_DIGITAL, NZ_NZETA, PROFILES, SCHENGEN_PRINT, US_PASSPORT_PRINT, US_VISA_DIGITAL,
    OutputSize,
)
from visaphoto.render import render
from visaphoto.validate import Verdict, predict, validate

RECEIPT = json.loads(Path("docs/sources/china-reference-run-2026-09-06.json").read_text())


# --- provenance ------------------------------------------------------------------------------------
class TestProvenance:
    def test_every_rule_has_its_sentence_source_and_date(self):
        for profile in PROFILES.values():
            for rule in profile.rules:
                source, retrieved = profile.provenance(rule)
                assert rule.quote.strip(), (profile.key, rule.key)
                assert source.startswith("http"), (profile.key, rule.key)
                assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", retrieved), (profile.key, rule.key)

    def test_every_bound_is_in_the_words_or_derived_or_read(self):
        """A number applied must be in the quote, or be arithmetic the quote implies
        (derivation), or come with the reading that produced it (interpretation)."""
        for profile in PROFILES.values():
            for rule in profile.rules:
                for bound in (rule.lo, rule.hi):
                    if bound is None:
                        continue
                    literal = any(t in rule.quote for t in (f"{bound:g}", f"{int(bound)}" if bound == int(bound) else "\x00",
                                                            f"{bound * 100:g}%" if rule.unit == "fraction_height" else "\x00"))
                    assert literal or rule.derivation or rule.interpretation, (profile.key, rule.key, bound)

    def test_china_carries_derivations_and_no_reading(self):
        rules = {r.key: r for r in CN_VISA_DIGITAL.rules}
        assert rules["face_width"].derivation.startswith("205")
        assert all(r.interpretation == "" for r in CN_VISA_DIGITAL.rules)

    def test_readings_are_where_the_words_define_nothing(self):
        assert NZ_NZETA.rules[0].interpretation.startswith("'face covers")
        us = {r.key: r for r in US_PASSPORT_PRINT.rules}
        assert us["head_height"].interpretation and us["eye_line_from_bottom"].interpretation
        assert {r.key: r for r in US_VISA_DIGITAL.rules}["head_height"].interpretation == ""

    def test_graphic_labels_say_so(self):
        for profile in (US_VISA_DIGITAL, US_PASSPORT_PRINT):
            eye = next(r for r in profile.rules if r.key == "eye_line_from_bottom")
            assert "graphic label" in eye.note.lower() and "template" in eye.source

    def test_the_us_22mm_conflict_is_recorded_not_applied(self):
        assert any("22 mm" in n and "25.4" in n for n in US_VISA_DIGITAL.notes)
        head = next(r for r in US_VISA_DIGITAL.rules if r.key == "head_height")
        assert (head.lo, head.hi, head.unit) == (0.50, 0.69, "fraction_height")


# --- fixtures ------------------------------------------------------------------------------------------
def wide_measurements(w=1600, h=1600, top=300.0, chin=800.0, eye_y=480.0, eyes=(700.0, 900.0), width=400.0):
    """A face with room around it: the US square needs a head no taller than 69% of the crop."""
    m = MeasurementSet(source="wide", image_width=w, image_height=h)
    for name, value in {"matte_top_row": top, "chin_landmark_y": chin, "eye_line_y": eye_y,
                        "eye_mid_x": sum(eyes) / 2, "inter_eye_distance": eyes[1] - eyes[0],
                        "head_width_silhouette": width}.items():
        m.add(Measurement(name=name, definition="d", status=Status.AVAILABLE, value=value, unit="px",
                          backend="t", confidence=Confidence.MEASURED,
                          preconditions=(Precondition("image_decoded", True, "ok"),)))
    return m


def wide_fits(w=1600, h=1600):
    """Landmarks and matte for the wide face, in a w x h frame."""
    lm = landmarks(left=(700.0, 480.0), right=(900.0, 480.0), chin=(800.0, 800.0),
                   oval_left=(600.0, 560.0), oval_right=(1000.0, 560.0))
    alpha = np.zeros((h, w), dtype=np.uint8)
    alpha[300:1300, 600:1000] = 255
    return lm, MatteFit(True, True, alpha, "test")


def transformed_fits(attempt, dx=0.0, dy=0.0):
    """The wide face as the chosen crop shows it in the output frame."""
    o = attempt.outcome
    s, ox, oy = o.scale, o.crop_x, o.crop_y
    W, H = attempt.size.width, attempt.size.height
    t = lambda p: ((p[0] - ox) * s + dx, (p[1] - oy) * s + dy)  # noqa: E731
    lm = landmarks(left=t((700.0, 480.0)), right=t((900.0, 480.0)), chin=t((800.0, 800.0)),
                   oval_left=t((600.0, 560.0)), oval_right=t((1000.0, 560.0)))
    alpha = np.zeros((H, W), dtype=np.uint8)
    top, bottom = int(round((300 - oy) * s)), int(round((1300 - oy) * s))
    left, right = int(round((600 - ox) * s)), int(round((1000 - ox) * s))
    alpha[max(top, 0):min(bottom, H), max(left, 0):min(right, W)] = 255
    return lm, MatteFit(True, True, alpha, "test")


def stub_wide(monkeypatch, plan, source_size=(1600, 1600)):
    src_lm, src_m = wide_fits(*source_size)
    by_size = {}

    def fits_for(image):
        if image.size == source_size:
            return src_lm, src_m
        if image.size not in by_size:
            attempt = next(a for a in plan.feasible_attempts if (a.size.width, a.size.height) == image.size)
            by_size[image.size] = transformed_fits(attempt)
        return by_size[image.size]

    monkeypatch.setattr(measure.landmarks, "fit", lambda image, model_path: fits_for(image)[0])
    monkeypatch.setattr(measure.segmentation, "fit", lambda image: fits_for(image)[1])


# --- plans -----------------------------------------------------------------------------------------------
class TestPlans:
    def test_us_visa_refuses_the_reference_photograph_with_the_arithmetic(self):
        """Head 1785 px tall in a 2316-px-wide source: the 69% ceiling needs a 2587-px square."""
        plan = make_plan(US_VISA_DIGITAL, reference_measurements())
        assert not plan.feasible
        for attempt in plan.attempts:
            assert isinstance(attempt.outcome, Infeasible), attempt
            assert attempt.outcome.reason == "source_too_small"
            assert "head_height" in attempt.outcome.scale_bands

    def test_us_visa_plans_the_wide_face_at_600_first(self):
        plan = make_plan(US_VISA_DIGITAL, wide_measurements())
        assert plan.feasible and (plan.chosen.size.width, plan.chosen.size.height) == (600, 600)
        assert [(a.size.width, a.size.height) for a in plan.feasible_attempts] == [(600, 600), (1200, 1200)]
        p = predict(US_VISA_DIGITAL, plan, wide_measurements())
        assert 300.0 <= p["head_height"] <= 414.0 and 336.0 <= p["eye_line_from_bottom"] <= 414.0

    def test_us_passport_refuses_the_reference_and_plans_the_wide_face(self):
        assert not make_plan(US_PASSPORT_PRINT, reference_measurements()).feasible
        plan = make_plan(US_PASSPORT_PRINT, wide_measurements())
        assert plan.feasible
        rules = {r["key"]: r for r in plan.applied_rules()}
        assert rules["head_height"]["interpretation"] and rules["eye_line_from_bottom"]["interpretation"]
        assert rules["eye_line_from_bottom"]["derivation"].startswith("1 1/8 in")

    def test_nz_plans_the_reference_largest_first_and_prints_its_reading(self):
        plan = make_plan(NZ_NZETA, reference_measurements())
        assert plan.feasible
        assert [(a.size.width, a.size.height) for a in plan.feasible_attempts] == [(2250, 3000), (1500, 2000), (900, 1200)]
        rule = plan.to_dict()["applied_rules"][0]
        assert rule["applied"] and rule["interpretation"].startswith("'face covers")
        p = predict(NZ_NZETA, plan, reference_measurements())
        assert 0.70 * 3000 <= p["head_height"] <= 0.80 * 3000

    def test_schengen_applies_nothing_and_says_why(self):
        plan = make_plan(SCHENGEN_PRINT, reference_measurements())
        assert not plan.feasible and plan.applied_rules() == []
        assert all(a.skipped and "Part 1, 6th edition" in a.skipped and "Zone V" in a.skipped for a in plan.attempts)

    def test_china_reproduces_its_receipt(self):
        """The receipt is the live run on the photograph; the fixture is Stage 1's checked-in
        numbers for it, which differ from today's measurement by a tenth of a pixel. The scale
        is identical; the crop origin agrees to that measurement difference."""
        plan = make_plan(CN_VISA_DIGITAL, reference_measurements())
        o = plan.chosen.outcome
        assert o.scale == pytest.approx(RECEIPT["plan"]["scale"], abs=1e-9)
        assert o.crop_x == pytest.approx(RECEIPT["plan"]["crop"]["x"], abs=0.05)
        assert o.crop_y == pytest.approx(RECEIPT["plan"]["crop"]["y"], abs=0.05)
        assert (plan.chosen.size.width, plan.chosen.size.height) == (354, 472)
        assert RECEIPT["encode"] == {"quality": 98, "bytes": 101482}


# --- validation of the new rules ---------------------------------------------------------------------------
def output_measurements_for(profile, plan, attempt=None):
    attempt = attempt or plan.chosen
    lm, m = transformed_fits(attempt)
    px = np.full((attempt.size.height, attempt.size.width, 3), 128, dtype=np.uint8)
    return measure_all(px, lm, m, source="out", segmentation_attempted=True)


class TestValidateNewRules:
    def test_fraction_rules_compare_in_pixels_and_show_the_stated_fraction(self):
        plan = make_plan(US_VISA_DIGITAL, wide_measurements())
        m = output_measurements_for(US_VISA_DIGITAL, plan)
        facts = facts_like(size=(600, 600), nbytes=100_000)
        v = validate(US_VISA_DIGITAL, facts, m, None, predict(US_VISA_DIGITAL, plan, wide_measurements()))
        head = next(c for c in v.criteria if c.key == "head_height")
        assert (head.lo, head.hi) == (pytest.approx(300.0), pytest.approx(414.0)) and head.unit == "px"
        assert head.stated == {"lo": 0.50, "hi": 0.69, "unit": "fraction_height"}
        assert head.verdict is Verdict.PASS and "stated 0.5-0.69 fraction_height at 600 px" in head.detail

    def test_fraction_bounds_scale_with_the_files_height(self):
        plan = make_plan(US_VISA_DIGITAL, wide_measurements())
        big = next(a for a in plan.feasible_attempts if a.size.width == 1200)
        m = output_measurements_for(US_VISA_DIGITAL, plan, big)
        v = validate(US_VISA_DIGITAL, facts_like(size=(1200, 1200), nbytes=230_000), m, None)
        head = next(c for c in v.criteria if c.key == "head_height")
        assert (head.lo, head.hi) == (pytest.approx(600.0), pytest.approx(828.0)) and head.verdict is Verdict.PASS

    @pytest.mark.parametrize("size,nbytes,expected", [
        ((600, 600), 53_999, Verdict.FAIL), ((600, 600), 54_000, Verdict.PASS),
        ((1200, 1200), 215_999, Verdict.FAIL), ((1200, 1200), 216_000, Verdict.PASS),
    ])
    def test_us_compression_floor(self, size, nbytes, expected):
        plan = make_plan(US_VISA_DIGITAL, wide_measurements())
        attempt = next(a for a in plan.feasible_attempts if a.size.width == size[0])
        v = validate(US_VISA_DIGITAL, facts_like(size=size, nbytes=nbytes), output_measurements_for(US_VISA_DIGITAL, plan, attempt), None)
        c = next(c for c in v.criteria if c.key == "compression_ratio")
        assert c.verdict is expected, c.detail
        assert c.interpretation.startswith("uncompressed bytes")

    @pytest.mark.parametrize("nbytes,expected,fails_one", [
        (524_287, Verdict.INDETERMINATE, "KB = 1,024"), (524_288, Verdict.PASS, None),
        (3_000_000, Verdict.PASS, None), (3_000_001, Verdict.INDETERMINATE, "upload-error page, KB = 1,000"),
        (400_000, Verdict.FAIL, None), (4_000_000, Verdict.FAIL, None),
    ])
    def test_nz_readings_each_report(self, nbytes, expected, fails_one):
        plan = make_plan(NZ_NZETA, reference_measurements())
        m = output_measurements_for(NZ_NZETA, plan) if False else None
        # the size criterion needs no measurements; use the wide set at NZ's first size
        facts = facts_like(size=(2250, 3000), nbytes=nbytes)
        v = validate(NZ_NZETA, facts, wide_measurements(2250, 3000), None)
        c = next(c for c in v.criteria if c.key == "size_bytes")
        assert c.verdict is expected, c.detail
        if fails_one:
            assert fails_one in c.detail

    def test_nz_has_no_colour_criterion_and_china_checks_mode_only(self):
        v = validate(NZ_NZETA, facts_like(size=(2250, 3000), nbytes=1_000_000), wide_measurements(2250, 3000), None)
        assert not any(c.key == "colour" for c in v.criteria)
        v = validate(CN_VISA_DIGITAL, facts_like(), output_measurements_for(CN_VISA_DIGITAL, feasible_plan()) if False else wide_measurements(354, 472), None)
        colour = next(c for c in v.criteria if c.key == "colour")
        assert colour.verdict is Verdict.PASS and "profile" not in colour.detail

    @pytest.mark.parametrize("icc_state,icc_name,expected", [
        ("absent", None, Verdict.PASS), ("readable", "sRGB IEC61966-2.1", Verdict.PASS),
        ("readable", "Display P3", Verdict.FAIL), ("unreadable", None, Verdict.INDETERMINATE),
    ])
    def test_us_srgb_from_file_evidence(self, icc_state, icc_name, expected):
        from visaphoto.validate import FileFacts

        facts = FileFacts("o.jpg", "JPEG", "RGB", 8, 600, 600, 600, 600, 100_000, icc_state, icc_name)
        v = validate(US_VISA_DIGITAL, facts, wide_measurements(600, 600), None)
        c = next(c for c in v.criteria if c.key == "colour")
        assert c.verdict is expected, c.detail

    @pytest.mark.parametrize("profile,size,expected", [
        (US_VISA_DIGITAL, (800, 800), Verdict.PASS), (US_VISA_DIGITAL, (500, 500), Verdict.FAIL),
        (US_VISA_DIGITAL, (600, 800), Verdict.FAIL), (NZ_NZETA, (1200, 1600), Verdict.PASS),
        (NZ_NZETA, (900, 1201), Verdict.FAIL), (NZ_NZETA, (2251, 3000), Verdict.FAIL),
    ])
    def test_dimension_ranges(self, profile, size, expected):
        v = validate(profile, facts_like(size=size, nbytes=600_000), wide_measurements(*size), None)
        c = next(c for c in v.criteria if c.key == "dimensions")
        assert c.verdict is expected, c.detail


# --- operations, advisories, retry -----------------------------------------------------------------------
class TestPolicyAndAdvisories:
    def test_a_prohibited_resize_makes_the_renderer_refuse(self):
        from tests.test_render import source_of

        forbidding = replace(CN_VISA_DIGITAL, key="test_forbids",
                             operations={**CN_VISA_DIGITAL.operations, "resize": "prohibited"},
                             operations_quotes={"resize": "Do not stretch or compress your image to resize it."})
        out = render(source_of(flat()), feasible_plan(), forbidding)
        assert not out.rendered
        assert "prohibits resize" in out.history[-1].detail and "stretch" in out.history[-1].detail

    def test_nz_policies_are_quoted(self):
        assert NZ_NZETA.operations["replace_background"] == "prohibited"
        assert "place it on a plain background" in NZ_NZETA.operations_quotes["replace_background"]
        assert NZ_NZETA.operations["adjust_colour"] == "prohibited"

    def test_the_passport_permits_a_smile_and_the_visa_does_not(self):
        smiling = {**NEUTRAL, "mouthSmileLeft": 0.9, "mouthSmileRight": 0.9}
        m = wide_measurements()
        visa = preflight_run(m, smiling, jurisdiction="US", profile="us_visa_digital")
        assert any(f.requirement.key == "expression_neutral_us_visa" and f.outcome is Outcome.WARN for f in visa.findings)
        passport = preflight_run(m, smiling, jurisdiction="US", profile="us_passport_print")
        assert passport.warnings == []
        assert not any(f.requirement.key.startswith("generic_expression") for f in passport.findings)

    def test_a_bare_for_us_keeps_the_generic_set(self):
        report = preflight_run(wide_measurements(), dict(NEUTRAL), jurisdiction="US")
        assert report.mode == "jurisdiction"
        assert any(f.requirement.key.startswith("generic_") for f in report.findings)

    def test_encoding_failure_at_the_first_size_falls_back_to_the_next(self, tmp_path, monkeypatch, capsys):
        """The mechanism, on a variant of the US profile without its compression floor (so the
        second size has a band a synthetic texture can land in): the first size's encode is
        made to fail, the second must be tried, written and validated."""
        variant = replace(US_VISA_DIGITAL, key="test_us_retry",
                          encoding=replace(US_VISA_DIGITAL.encoding, max_compression_ratio=None))
        monkeypatch.setitem(cli.PROFILES, "test_us_retry", variant)
        plan = make_plan(variant, wide_measurements())
        # A smooth texture: at 1200x1200 a noisy one stays above 240,000 bytes at every quality.
        photo = write_photo(tmp_path / "p.jpg", textured(1600, 1600, sigma=4))
        stub_wide(monkeypatch, plan)
        real_encode = cli.encode

        def encode_600_fails(image, encoding, out):
            if image.size == (600, 600):
                return EncodeResult("no_encoding_satisfies", None, None, None,
                                    [{"quality": 98, "bytes": 1, "fits": False}], "injected: nothing fits at 600")
            return real_encode(image, encoding, out)

        monkeypatch.setattr(cli, "encode", encode_600_fails)
        out = tmp_path / "o.jpg"
        code, r = run_cli([str(photo), "--spec", "test_us_retry", "--out", str(out), "--model", str(photo), "--json"], capsys)
        assert code == cli.EXIT_OK, (r["encode"], r["validation"] and r["validation"].get("aggregate"))
        assert r["encode"]["size"] == {"width": 1200, "height": 1200}
        assert [e["size"]["width"] for e in r["encode"]["earlier_sizes"]] == [600]
        with Image.open(out) as im:
            assert im.size == (1200, 1200)
        assert r["validation"]["aggregate"] == "passes_implemented_checks", r["validation"]["criteria"]


# --- the command with the new profiles -----------------------------------------------------------------------
class TestCliProfiles:
    def test_us_visa_end_to_end_on_the_wide_face(self, tmp_path, monkeypatch, capsys):
        plan = make_plan(US_VISA_DIGITAL, wide_measurements())
        photo = write_photo(tmp_path / "p.jpg", textured(1600, 1600, sigma=20), profile=FAITHFUL)
        stub_wide(monkeypatch, plan)
        out = tmp_path / "o.jpg"
        code, r = run_cli([str(photo), "--spec", "us_visa_digital", "--out", str(out), "--model", str(photo), "--json"], capsys)
        assert code == cli.EXIT_OK, (r["encode"], r["validation"])
        v = r["validation"]
        assert v["aggregate"] == "passes_implemented_checks", v["criteria"]
        keys = {c["key"] for c in v["criteria"]}
        assert {"dimensions", "format", "colour", "size_bytes", "compression_ratio", "head_height", "eye_line_from_bottom"} <= keys
        eye = next(c for c in v["criteria"] if c["key"] == "eye_line_from_bottom")
        assert "graphic label" in eye["quote"].lower() or "56-69%" in eye["quote"]
        assert r["preflight"]["jurisdiction"] == "US"
        assert any(f["requirement"] == "glasses_us_visa" for f in r["preflight"]["findings"])
        with Image.open(out) as im:
            assert im.size == (600, 600) and out.stat().st_size >= 54_000

    def test_schengen_run_advises_and_prints_its_notes(self, tmp_path, monkeypatch, capsys):
        photo = write_photo(tmp_path / "p.jpg", textured(1600, 1600, sigma=20))
        stub_wide(monkeypatch, make_plan(US_VISA_DIGITAL, wide_measurements()))
        code, text = run_cli([str(photo), "--spec", "schengen_print", "--model", str(photo)], capsys)
        assert code == cli.EXIT_NO_CROP
        assert "Part 1, 6th edition" in text and "Zone V" in text
        assert "note  " in text and "recency_eu" in text
        assert cli.main([str(photo), "--spec", "schengen_print", "--validate"]) == cli.EXIT_USAGE

    def test_list_specs_shows_ranges_and_print_profiles(self, capsys):
        code, text = run_cli(["--list-specs"], capsys)
        assert code == cli.EXIT_OK
        assert "permitted: 1:1, 600x600 to 1200x1200" in text
        assert "permitted: 3:4, 900x1200 to 2250x3000" in text
        assert text.count("print profile: plans only") == 3

"""Rendering and encoding, driven through the production path with synthetic fits."""

from __future__ import annotations

import json
from dataclasses import replace

import numpy as np
from PIL import Image, JpegImagePlugin

from tests.test_regressions import landmarks, matte, pixels, run
from visaphoto.encode import JPEG_QUALITIES, encode
from visaphoto.plan import make_plan
from visaphoto.profiles import CN_VISA_DIGITAL, CN_VISA_PAPER, Encoding
from visaphoto.render import render

PROHIBITING = replace(CN_VISA_DIGITAL, key="test_prohibits",
                      operations={**CN_VISA_DIGITAL.operations, "replace_background": "prohibited"})
ALLOWING = replace(CN_VISA_DIGITAL, key="test_allows",
                   operations={**CN_VISA_DIGITAL.operations, "replace_background": "allowed"})


def measured(**kw):
    """A synthetic photo the China digital profile can crop: grey 600x800, head at rows
    100-700, eyes at y=300 with 200 px separation."""
    return run(**kw)


def image_for(m):
    return Image.fromarray(pixels(), "RGB")


def noise(w, h, seed=7):
    """Uniform random RGB: the highest-entropy input a JPEG encoder can be handed."""
    return Image.fromarray(np.random.default_rng(seed).integers(0, 255, (h, w, 3), dtype=np.uint8), "RGB")


def textured(w, h, sigma=12, seed=1):
    """A smooth pattern with independent per-channel noise. At 354x472, sigma 12 encodes to
    ~254 KB at quality 98 and first fits China's 40-120 KB band at quality 90, so the search
    has to descend to find its answer (measured on Pillow 12.3.0)."""
    y, x = np.mgrid[0:h, 0:w]
    base = 128 + 60 * np.sin(x / 9.0) * np.cos(y / 7.0)
    rng = np.random.default_rng(seed)
    chans = [(base + rng.normal(0, sigma, (h, w))).clip(0, 255).astype(np.uint8) for _ in range(3)]
    return Image.fromarray(np.stack(chans, -1), "RGB")


def op(result, name):
    return next(h for h in result.history if h.name == name)


class TestCropResize:
    def test_a_feasible_plan_renders_at_the_chosen_size(self):
        m = measured()
        plan = make_plan(CN_VISA_DIGITAL, m)
        assert plan.feasible
        out = render(image_for(m), m, plan, CN_VISA_DIGITAL)
        assert out.rendered
        assert out.image.size == (354, 472)
        assert op(out, "crop_resize").status == "done"

    def test_no_feasible_plan_renders_nothing(self):
        m = measured(lm=landmarks(faces=0))
        plan = make_plan(CN_VISA_DIGITAL, m)
        out = render(image_for(m), m, plan, CN_VISA_DIGITAL)
        assert not out.rendered
        assert op(out, "crop_resize").status == "refused"

    def test_crop_is_one_uniform_resample_not_round_then_resize(self):
        """A float crop box resampled once differs, measurably, from rounding the box to
        integers and resizing the integer crop. The shortcut introduces a non-uniform scale
        the plan forbids; this keeps it out."""
        m = measured()
        plan = make_plan(CN_VISA_DIGITAL, m)
        source = noise(600, 800, seed=1)
        out = render(source, m, plan, CN_VISA_DIGITAL)
        box = op(out, "crop_resize").params["box"]
        shortcut = source.crop(tuple(int(round(v)) for v in box)).resize((354, 472), Image.Resampling.LANCZOS)
        diff = np.abs(np.asarray(out.image, dtype=int) - np.asarray(shortcut, dtype=int))
        assert diff.max() > 0

    def test_history_records_the_colour_assumption(self):
        m = measured()
        out = render(image_for(m), m, make_plan(CN_VISA_DIGITAL, m), CN_VISA_DIGITAL)
        assert op(out, "colour_convert").status == "skipped"
        assert "sRGB is assumed" in op(out, "colour_convert").detail


class TestReplaceBackground:
    def test_unresolved_is_skipped_without_the_flag(self):
        m = measured()
        out = render(image_for(m), m, make_plan(CN_VISA_DIGITAL, m), CN_VISA_DIGITAL)
        rec = op(out, "replace_background")
        assert rec.status == "skipped" and "does not address" in rec.detail
        assert np.asarray(out.image)[0, 0].tolist() == [128, 128, 128]  # untouched grey

    def test_unresolved_is_performed_with_the_flag_and_recorded_as_opt_in(self):
        m = measured()
        out = render(image_for(m), m, make_plan(CN_VISA_DIGITAL, m), CN_VISA_DIGITAL,
                     allow_unresolved=True)
        rec = op(out, "replace_background")
        assert rec.status == "done" and rec.opt_in is True
        assert np.asarray(out.image)[0, 0].tolist() == [255, 255, 255]  # background now white

    def test_prohibited_is_skipped_even_with_the_flag(self):
        m = measured()
        out = render(image_for(m), m, make_plan(PROHIBITING, m), PROHIBITING,
                     allow_unresolved=True)
        rec = op(out, "replace_background")
        assert rec.status == "skipped" and "prohibits" in rec.detail
        assert np.asarray(out.image)[0, 0].tolist() == [128, 128, 128]

    def test_allowed_is_performed_without_opt_in(self):
        m = measured()
        out = render(image_for(m), m, make_plan(ALLOWING, m), ALLOWING)
        rec = op(out, "replace_background")
        assert rec.status == "done" and rec.opt_in is False

    def test_refused_when_the_matte_did_not_isolate_the_face(self):
        """Gate False: the eye pixel is matte background. Even an allowing channel refuses -
        a background cannot be replaced from a matte that never found the face."""
        m = measured(m=matte(top=600))
        # The plan is blocked (matte_top_row unavailable), so drive render with a plan from a
        # good measurement set but this set's gate record and alpha.
        good = measured()
        plan = make_plan(ALLOWING, good)
        out = render(image_for(m), m, plan, ALLOWING)
        rec = op(out, "replace_background")
        assert rec.status == "refused"
        assert any(g == "face_component_isolated" and s is False for g, s, _ in rec.gates)

    def test_refused_when_the_subject_crosses_the_crop_top(self):
        """The head runs to the crop's top edge: compositing would leave a hard edge across it.
        The crop still renders; only the replacement is refused."""
        good = measured()
        plan = make_plan(ALLOWING, good)
        # Same photo, but the matte now starts at row 0 - above the crop's top.
        m = measured(m=matte(top=0))
        m_gates_ok = m.gate_record["face_component_isolated"].satisfied
        assert m_gates_ok is True
        out = render(image_for(m), m, plan, ALLOWING)
        rec = op(out, "replace_background")
        assert rec.status == "refused" and "top" in rec.detail
        assert out.rendered


class TestEncode:
    def test_highest_quality_inside_the_band_wins(self, tmp_path):
        result = encode(textured(354, 472), CN_VISA_DIGITAL.encoding, tmp_path / "out.jpg")
        assert result.done
        assert 40 * 1024 <= result.bytes <= 120 * 1024
        assert result.bytes == (tmp_path / "out.jpg").stat().st_size
        chosen_index = JPEG_QUALITIES.index(result.quality)
        assert chosen_index > 0  # the search descended; it did not pass on the first try
        assert all(t["bytes"] > 120 * 1024 and not t["fits"] for t in result.trace[:chosen_index])
        assert len(result.trace) == chosen_index + 1  # and stopped at the first fit

    def test_maximum_entropy_content_does_not_break_the_encoder(self, tmp_path):
        """Random noise at quality 98, 4:4:4, optimized overruns Pillow's default output buffer
        and the save raises. The encoder buffer is sized for it; the outcome here is whatever
        the band says, never an exception."""
        result = encode(noise(354, 472), CN_VISA_DIGITAL.encoding, tmp_path / "out.jpg")
        assert result.trace[0]["quality"] == 98 and result.trace[0]["bytes"] > 0
        assert result.status in ("done", "no_encoding_satisfies")

    def test_nothing_fits_is_reported_and_no_file_is_left(self, tmp_path):
        flat = Image.new("RGB", (354, 472), (128, 128, 128))  # compresses far below 40 KB
        result = encode(flat, CN_VISA_DIGITAL.encoding, tmp_path / "out.jpg")
        assert result.status == "no_encoding_satisfies"
        assert not (tmp_path / "out.jpg").exists()
        assert "not written" in result.detail
        assert result.trace  # the search is shown, not hidden

    def test_search_stops_once_files_are_below_the_floor(self, tmp_path):
        flat = Image.new("RGB", (354, 472), (128, 128, 128))
        result = encode(flat, CN_VISA_DIGITAL.encoding, tmp_path / "out.jpg")
        assert len(result.trace) == 1  # lower quality can only be smaller

    def test_output_is_444_with_no_exif(self, tmp_path):
        result = encode(textured(354, 472), CN_VISA_DIGITAL.encoding, tmp_path / "out.jpg")
        with Image.open(result.path) as im:
            assert im.mode == "RGB" and im.size == (354, 472)
            assert not im.getexif()
            assert JpegImagePlugin.get_sampling(im) == 0  # Pillow's code for 4:4:4

    def test_a_print_profile_has_no_encoding(self):
        assert CN_VISA_PAPER.encoding is None

    def test_unsupported_format_is_refused_not_guessed(self, tmp_path):
        enc = Encoding(format="png", colour="srgb_24bit", min_bytes=None, max_bytes=None, quote="q")
        result = encode(Image.new("RGB", (10, 10)), enc, tmp_path / "x.png")
        assert result.status == "no_encoding_satisfies"


class TestCli:
    def test_out_writes_the_file_and_reports_the_history(self, monkeypatch, tmp_path, capsys):
        from visaphoto import cli
        from visaphoto.preflight import run as preflight_run

        photo = tmp_path / "p.jpg"
        photo.write_bytes(b"x")
        m = measured()
        source = textured(600, 800, sigma=28)  # downscaling smooths it; sigma 28 still needs the search
        monkeypatch.setattr(cli, "measure_photo", lambda *a, **k: (m, preflight_run(m, {}, jurisdiction="CN")))
        monkeypatch.setattr(cli, "load_rgb", lambda p: source)
        out = tmp_path / "out.jpg"
        code = cli.main([str(photo), "--spec", "cn_visa_digital", "--out", str(out), "--json"])
        report = json.loads(capsys.readouterr().out)
        assert code == cli.EXIT_OK, report.get("encode")
        assert out.exists()
        assert report["render"]["rendered"] is True
        assert report["encode"]["status"] == "done"
        assert [h["operation"] for h in report["render"]["history"]][0] == "replace_background"
        with Image.open(out) as im:
            assert im.size == (354, 472)

    def test_out_without_spec_is_a_usage_error(self, tmp_path):
        from visaphoto import cli

        photo = tmp_path / "p.jpg"
        photo.write_bytes(b"x")
        assert cli.main([str(photo), "--out", str(tmp_path / "o.jpg")]) == cli.EXIT_USAGE

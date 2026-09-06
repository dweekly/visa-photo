"""Rendering, encoding and --out, driven from photographs written to disk with only the two
model fits stubbed - so the loader, orientation, colour, crop, encoder and CLI are the real ones.

Colour tests use a synthetic ICC profile built here (an ICC v2 matrix/TRC profile, ~500 bytes)
rather than a vendor's binary; swapping its red and green colorants gives a profile under which
a red pixel is, in truth, green, so a correct conversion must change the colour.
"""

from __future__ import annotations

import errno
import json
import struct
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest
from PIL import Image, JpegImagePlugin

from tests.test_regressions import landmarks, matte, run
from visaphoto import cli, measure
from visaphoto.encode import JPEG_QUALITIES, encode
from visaphoto.measure import MeasurementError, Source, load_source
from visaphoto.plan import make_plan
from visaphoto.profiles import CN_VISA_DIGITAL, CN_VISA_PAPER, Encoding
from visaphoto.render import render

# --- synthetic ICC profiles ------------------------------------------------------------------
# Layout per ICC.1:2001-04 (v2): 128-byte header, tag table, tag data. Accepted by LittleCMS
# (checked on Pillow 12.3.0). The colorants are the D50-adapted values every sRGB profile carries.
_D50 = (0.9642, 1.0, 0.8249)
SRGB_R, SRGB_G, SRGB_B = (0.4361, 0.2225, 0.0139), (0.3851, 0.7169, 0.0971), (0.1431, 0.0606, 0.7141)


def _s15f16(v):
    return struct.pack(">i", int(round(v * 65536)))


def _xyz(x, y, z):
    return b"XYZ " + b"\0" * 4 + _s15f16(x) + _s15f16(y) + _s15f16(z)


def _curv(gamma):
    return b"curv" + b"\0" * 4 + struct.pack(">I", 1) + struct.pack(">H", int(round(gamma * 256)))


def _desc(text):
    a = text.encode("ascii") + b"\0"
    return (b"desc" + b"\0" * 4 + struct.pack(">I", len(a)) + a + struct.pack(">II", 0, 0)
            + struct.pack(">HB", 0, 0) + b"\0" * 67)


def _profile(space: bytes, tags) -> bytes:
    table, body = b"", b""
    first = 128 + 4 + 12 * len(tags)
    for sig, data in tags:
        table += sig + struct.pack(">II", first + len(body), len(data))
        body += data + b"\0" * ((-len(data)) % 4)
    header = (struct.pack(">I", first + len(body)) + b"\0" * 4 + struct.pack(">I", 0x02100000)
              + b"mntr" + space + b"XYZ " + b"\0" * 12 + b"acsp" + b"\0" * 28
              + _s15f16(_D50[0]) + _s15f16(_D50[1]) + _s15f16(_D50[2]) + b"\0" * 48)
    assert len(header) == 128
    return header + struct.pack(">I", len(tags)) + table + body


def icc_rgb(description, r=SRGB_R, g=SRGB_G, b=SRGB_B, gamma=2.2) -> bytes:
    return _profile(b"RGB ", [
        (b"desc", _desc(description)), (b"cprt", b"text" + b"\0" * 4 + b"synthetic\0"),
        (b"wtpt", _xyz(*_D50)), (b"rXYZ", _xyz(*r)), (b"gXYZ", _xyz(*g)), (b"bXYZ", _xyz(*b)),
        (b"rTRC", _curv(gamma)), (b"gTRC", _curv(gamma)), (b"bTRC", _curv(gamma))])


def icc_gray(description, gamma=2.2) -> bytes:
    """A greyscale profile: parses fine, and cannot be applied to an RGB image."""
    return _profile(b"GRAY", [
        (b"desc", _desc(description)), (b"cprt", b"text" + b"\0" * 4 + b"synthetic\0"),
        (b"wtpt", _xyz(*_D50)), (b"kTRC", _curv(gamma))])


SWAPPED_RG = icc_rgb("synthetic red/green swapped", r=SRGB_G, g=SRGB_R)
FAITHFUL = icc_rgb("synthetic sRGB")

# --- fixtures ----------------------------------------------------------------------------------
RED = (200, 50, 50)


def flat(w=600, h=800, rgb=RED, profile=None):
    im = Image.new("RGB", (w, h), rgb)
    if profile is not None:
        im.info["icc_profile"] = profile
    return im


def textured(w, h, sigma=12, seed=1, rgb=(128, 128, 128), profile=None):
    """A smooth pattern with independent per-channel noise around a base colour. At 354x472,
    grey base, sigma 12 encodes to ~250 KB at quality 98 and first fits China's band at quality
    90 (Pillow 12.3.0), so the search has to descend to find its answer. A flat image, by
    contrast, falls under the band's floor at every quality."""
    y, x = np.mgrid[0:h, 0:w]
    wave = 40 * np.sin(x / 9.0) * np.cos(y / 7.0)
    rng = np.random.default_rng(seed)
    chans = [(c + wave + rng.normal(0, sigma, (h, w))).clip(0, 255).astype(np.uint8) for c in rgb]
    im = Image.fromarray(np.stack(chans, -1), "RGB")
    if profile is not None:
        im.info["icc_profile"] = profile
    return im


def write_photo(path: Path, image, *, profile=None, comment=None, orientation=None) -> Path:
    """A JPEG on disk. `orientation` 6 stores the image rotated so that EXIF says 'rotate to
    view'; the loader must undo it."""
    kw = {"quality": 95}
    if profile is not None:
        kw["icc_profile"] = profile
    if comment is not None:
        kw["comment"] = comment
    if orientation is not None:
        image = image.transpose(Image.Transpose.ROTATE_90)  # stored sideways
        exif = Image.Exif()
        exif[0x0112] = orientation
        kw["exif"] = exif.tobytes()
    image.save(path, format="JPEG", **kw)
    return path


def source_of(image) -> Source:
    return Source(native=image, rgb=image if image.mode == "RGB" else image.convert("RGB"))


def feasible_plan(m=None):
    m = m if m is not None else run()
    plan = make_plan(CN_VISA_DIGITAL, m)
    assert plan.feasible
    return plan


def op(result, name):
    return next(h for h in result.history if h.name == name)


def output_fits(plan, dx=0.0, dy=0.0):
    """The source fixture's landmarks and matte as the plan's crop would show them in the
    output: every point moved by (p - origin) * scale. `dx`, `dy` shift the landmarks so the
    output disagrees with the plan's prediction by a known amount."""
    from visaphoto.backends.segmentation import MatteFit

    o = plan.chosen.outcome
    s, ox, oy = o.scale, o.crop_x, o.crop_y
    w, h = plan.chosen.size.width, plan.chosen.size.height
    t = lambda p: ((p[0] - ox) * s + dx, (p[1] - oy) * s + dy)  # noqa: E731
    lm = landmarks(left=t((200.0, 300.0)), right=t((400.0, 300.0)), chin=t((300.0, 520.0)),
                   oval_left=t((150.0, 350.0)), oval_right=t((450.0, 350.0)))
    alpha = np.zeros((h, w), dtype=np.uint8)
    top, bottom = int(round((100 - oy) * s)), int(round((700 - oy) * s))
    left, right = int(round((150 - ox) * s)), int(round((450 - ox) * s))
    alpha[max(top, 0):min(bottom, h), max(left, 0):min(right, w)] = 255
    return lm, MatteFit(True, True, alpha, "test")


def stub_fits(monkeypatch, lm=None, m=None, output=None):
    """Serve the 600x800 source fixture's fits to the source image and, to any other size, the
    plan-transformed fits (or `output`, a (landmarks, matte) pair) - so a written file gets
    fits that belong to it, not the source's."""
    src_lm, src_m = lm or landmarks(), m or matte()
    out_lm = out_m = None

    def fits_for(image):
        nonlocal out_lm, out_m
        if image.size == (600, 800):
            return src_lm, src_m
        if out_lm is None:
            out_lm, out_m = output if output is not None else output_fits(feasible_plan())
        return out_lm, out_m

    monkeypatch.setattr(measure.landmarks, "fit", lambda image, model_path: fits_for(image)[0])
    monkeypatch.setattr(measure.segmentation, "fit", lambda image: fits_for(image)[1])


# --- the loader ----------------------------------------------------------------------------------
class TestLoadSource:
    def test_orientation_is_normalized_and_the_profile_kept(self, tmp_path):
        photo = write_photo(tmp_path / "p.jpg", flat(), profile=FAITHFUL, orientation=6)
        with Image.open(photo) as stored:
            assert stored.size == (800, 600)  # sideways on disk
        src = load_source(photo)
        assert src.native.size == (600, 800) and src.rgb.size == (600, 800)
        assert src.native.info["icc_profile"] == FAITHFUL
        assert src.rgb.mode == "RGB"

    def test_an_undecodable_file_is_a_measurement_error(self, tmp_path):
        bad = tmp_path / "p.jpg"
        bad.write_bytes(b"not an image")
        with pytest.raises(MeasurementError, match="could not read"):
            load_source(bad)


# --- colour --------------------------------------------------------------------------------------
class TestColourConvert:
    def test_no_profile_is_the_recorded_assumption(self):
        out = render(source_of(flat()), feasible_plan())
        rec = op(out, "colour_convert")
        assert rec.status == "skipped" and rec.detail == "assumed sRGB: no embedded profile"
        assert out.image.getpixel((100, 100)) == RED

    def test_an_embedded_profile_is_converted_not_relabelled(self):
        out = render(source_of(flat(profile=SWAPPED_RG)), feasible_plan())
        rec = op(out, "colour_convert")
        assert rec.status == "done" and rec.params["from"] == "synthetic red/green swapped"
        r, g, b = out.image.getpixel((100, 100))
        assert g > 150 and r < 100, (r, g, b)

    def test_a_faithful_profile_leaves_colours_alone(self):
        out = render(source_of(flat(profile=FAITHFUL)), feasible_plan())
        assert op(out, "colour_convert").status == "done"
        r, g, b = out.image.getpixel((100, 100))
        assert abs(r - 200) <= 3 and abs(g - 50) <= 5 and abs(b - 50) <= 5, (r, g, b)

    def test_an_unparseable_profile_is_named_as_such(self):
        out = render(source_of(flat(profile=b"not an icc profile")), feasible_plan())
        rec = op(out, "colour_convert")
        assert rec.status == "skipped" and rec.detail.startswith("assumed sRGB: profile unreadable")
        assert out.image.getpixel((100, 100)) == RED

    def test_a_profile_that_parses_but_cannot_apply_keeps_its_name(self):
        out = render(source_of(flat(profile=icc_gray("synthetic gray"))), feasible_plan())
        rec = op(out, "colour_convert")
        assert rec.status == "skipped"
        assert rec.detail.startswith("assumed sRGB: conversion from 'synthetic gray' failed")
        assert out.image.getpixel((100, 100)) == RED


# --- crop + resize -------------------------------------------------------------------------------
class TestCropResize:
    def test_renders_at_the_chosen_size_with_the_plans_box(self):
        plan = feasible_plan()
        out = render(source_of(flat()), plan)
        assert out.rendered and out.image.size == (354, 472)
        o = plan.chosen.outcome
        assert op(out, "crop_resize").params["box"] == [
            o.crop_x, o.crop_y, o.crop_x + 354 / o.scale, o.crop_y + 472 / o.scale]
        assert [h.name for h in out.history] == ["colour_convert", "crop_resize"]

    def test_no_feasible_plan_renders_nothing(self):
        plan = make_plan(CN_VISA_DIGITAL, run(lm=landmarks(faces=0)))
        out = render(source_of(flat()), plan)
        assert not out.rendered and op(out, "crop_resize").status == "refused"

    def test_one_resample_differs_from_round_then_resize(self):
        plan = feasible_plan()
        src = Image.fromarray(np.random.default_rng(1).integers(0, 255, (800, 600, 3), dtype=np.uint8), "RGB")
        out = render(source_of(src), plan)
        box = op(out, "crop_resize").params["box"]
        shortcut = src.crop(tuple(int(round(v)) for v in box)).resize((354, 472), Image.Resampling.LANCZOS)
        assert np.abs(np.asarray(out.image, dtype=int) - np.asarray(shortcut, dtype=int)).max() > 0

    def test_solver_roundoff_outside_the_source_is_clamped(self):
        """The solver produced a crop origin of -3.163e-14 for a crop touching the left edge;
        Pillow rejects a negative box offset. Noise inside the solver's tolerance is clamped to
        the edge and the box supplied is the one recorded."""
        plan = feasible_plan()
        noisy = replace(plan.chosen.outcome, crop_x=-3.163320202141011e-14)
        plan.chosen.outcome = noisy
        out = render(source_of(flat()), plan)
        assert out.rendered
        assert op(out, "crop_resize").params["box"][0] == 0.0

    def test_a_crop_genuinely_outside_the_source_is_a_solver_bug_not_a_move(self):
        plan = feasible_plan()
        plan.chosen.outcome = replace(plan.chosen.outcome, crop_x=-1.0)
        with pytest.raises(ValueError, match="outside"):
            render(source_of(flat()), plan)


# --- encode --------------------------------------------------------------------------------------
class TestEncode:
    def test_highest_quality_inside_the_band_wins_after_descending(self, tmp_path):
        result = encode(textured(354, 472), CN_VISA_DIGITAL.encoding, tmp_path / "out.jpg")
        assert result.done
        assert 40 * 1024 <= result.bytes <= 120 * 1000
        assert result.bytes == (tmp_path / "out.jpg").stat().st_size
        chosen = JPEG_QUALITIES.index(result.quality)
        assert chosen > 0
        assert all(t["bytes"] > 120 * 1000 and not t["fits"] for t in result.trace[:chosen])
        assert len(result.trace) == chosen + 1

    def test_nothing_fits_tries_every_quality_and_touches_nothing(self, tmp_path):
        out = tmp_path / "out.jpg"
        out.write_bytes(b"the applicant's original")
        result = encode(Image.new("RGB", (354, 472), (128, 128, 128)), CN_VISA_DIGITAL.encoding, out)
        assert result.status == "no_encoding_satisfies"
        assert len(result.trace) == len(JPEG_QUALITIES)
        assert out.read_bytes() == b"the applicant's original"
        assert not list(tmp_path.glob("*.part"))

    def test_a_fit_replaces_what_was_there(self, tmp_path):
        out = tmp_path / "out.jpg"
        out.write_bytes(b"stale")
        result = encode(textured(354, 472), CN_VISA_DIGITAL.encoding, out)
        assert result.done and out.stat().st_size == result.bytes
        assert not list(tmp_path.glob("*.part"))

    def test_an_unwritable_destination_is_a_result_not_an_exception(self, tmp_path):
        result = encode(textured(354, 472), CN_VISA_DIGITAL.encoding, tmp_path)  # a directory
        assert result.status == "write_failed" and str(tmp_path) in result.detail
        assert not list(tmp_path.glob("*.part"))

    def test_a_failed_write_keeps_the_existing_file_and_reports_a_failed_cleanup(self, tmp_path, monkeypatch):
        out = tmp_path / "out.jpg"
        out.write_bytes(b"the previous output")

        def dies(self, fp, *a, **k):
            Path(fp).write_bytes(b"\xff\xd8")
            raise OSError(errno.ENOSPC, "No space left on device")

        def cannot_unlink(self, missing_ok=False):
            raise OSError(errno.EPERM, "Operation not permitted")

        monkeypatch.setattr(Image.Image, "save", dies)
        monkeypatch.setattr(Path, "unlink", cannot_unlink)
        result = encode(textured(354, 472), CN_VISA_DIGITAL.encoding, out)
        assert result.status == "write_failed"
        assert "No space left" in result.detail and "cleanup failed" in result.detail
        assert ".part" in result.detail  # the path left behind is named
        assert out.read_bytes() == b"the previous output"

    def test_source_metadata_never_reaches_the_output(self, tmp_path):
        src = textured(600, 800)
        src.info["comment"] = b"private source annotation"
        src.info["icc_profile"] = FAITHFUL
        exif = Image.Exif()
        exif[0x010E] = "private image description"
        src.info["exif"] = exif.tobytes()
        rendered = render(source_of(src), feasible_plan())
        result = encode(rendered.image, CN_VISA_DIGITAL.encoding, tmp_path / "out.jpg")
        assert result.done
        with Image.open(result.path) as im:
            assert "comment" not in im.info and "icc_profile" not in im.info
            assert not im.getexif()
            assert JpegImagePlugin.get_sampling(im) == 0  # 4:4:4
        assert b"private" not in (tmp_path / "out.jpg").read_bytes()

    def test_unsupported_rules_are_refused_not_guessed(self, tmp_path):
        for enc in (Encoding(format="png", colour="srgb_24bit", quote="q", interpretation="i"),
                    Encoding(format="jpeg", colour="cmyk", quote="q", interpretation="i")):
            result = encode(Image.new("RGB", (10, 10)), enc, tmp_path / "x.jpg")
            assert result.status == "no_encoding_satisfies" and "not supported" in result.detail

    def test_the_paper_profile_has_no_encoding(self):
        assert CN_VISA_PAPER.encoding is None
        assert CN_VISA_DIGITAL.encoding.min_bytes == 40_960
        assert CN_VISA_DIGITAL.encoding.max_bytes == 120_000


# --- the command -----------------------------------------------------------------------------------
class TestCli:
    def test_end_to_end_from_a_photo_on_disk(self, tmp_path, monkeypatch, capsys):
        """A sideways JPEG with a red/green-swapped profile and a private comment. One decode,
        orientation undone, colour converted, a 4:4:4 sRGB JPEG inside the band with nothing
        from the source in it, and the history says exactly what happened."""
        # Base colour and noise chosen so no channel clips: a clipped channel reads as glare to
        # the specular check, which is an advisory this test is not about.
        photo = write_photo(tmp_path / "p.jpg", textured(600, 800, sigma=12, rgb=(160, 60, 60)),
                            profile=SWAPPED_RG, comment=b"private source annotation", orientation=6)
        stub_fits(monkeypatch)
        decodes = []
        real = measure.load_source
        counting = lambda p: decodes.append(p) or real(p)  # noqa: E731
        monkeypatch.setattr(measure, "load_source", counting)
        monkeypatch.setattr(cli, "load_source", counting)

        out = tmp_path / "out.jpg"
        code = cli.main([str(photo), "--spec", "cn_visa_digital", "--out", str(out),
                         "--model", str(photo), "--json"])
        report = json.loads(capsys.readouterr().out)
        assert code == cli.EXIT_OK, (report["preflight"], report["encode"], report["validation"])
        assert decodes == [photo, out]  # one decode per snapshot: the input, then the written file
        assert report["measurements"]["image"] == {"width": 600, "height": 800}  # orientation applied
        assert [h["operation"] for h in report["render"]["history"]] == ["colour_convert", "crop_resize"]
        assert report["render"]["history"][0]["status"] == "done"
        assert report["encode"]["status"] == "done" and report["encode"]["trace"]
        assert 40_960 <= report["encode"]["bytes"] <= 120_000
        with Image.open(out) as im:
            assert im.size == (354, 472) and im.mode == "RGB"
            assert JpegImagePlugin.get_sampling(im) == 0
            assert not im.getexif() and "comment" not in im.info and "icc_profile" not in im.info
            r, g, b = np.asarray(im, dtype=float).reshape(-1, 3).mean(axis=0)
            assert g > 150 and r < 100, (r, g, b)  # red source, swapped profile: green output
        assert b"private" not in out.read_bytes()

    def test_text_output_shows_the_box_scale_and_trace(self, tmp_path, monkeypatch, capsys):
        photo = write_photo(tmp_path / "p.jpg", textured(600, 800, sigma=20))
        stub_fits(monkeypatch)
        code = cli.main([str(photo), "--spec", "cn_visa_digital", "--out", str(tmp_path / "o.jpg"),
                         "--model", str(photo)])
        text = capsys.readouterr().out
        assert code == cli.EXIT_OK
        assert "colour_convert" in text and "crop_resize" in text
        assert "box (" in text and "scale" in text and "-> 354x472" in text
        assert "<- chosen" in text and "written:" in text

    def test_out_requires_spec(self, tmp_path):
        photo = write_photo(tmp_path / "p.jpg", flat())
        assert cli.main([str(photo), "--out", str(tmp_path / "o.jpg")]) == cli.EXIT_USAGE

    def test_out_refuses_a_print_profile_by_name(self, tmp_path, capsys):
        photo = write_photo(tmp_path / "p.jpg", flat())
        code = cli.main([str(photo), "--spec", "cn_visa_paper", "--out", str(tmp_path / "o.jpg")])
        assert code == cli.EXIT_USAGE
        assert "cn_visa_paper" in capsys.readouterr().err

    def test_out_equal_to_the_input_is_refused_before_anything_runs(self, tmp_path):
        photo = write_photo(tmp_path / "p.jpg", flat())
        before = photo.read_bytes()
        code = cli.main([str(photo), "--spec", "cn_visa_digital", "--out", str(tmp_path / "p.jpg")])
        assert code == cli.EXIT_USAGE and photo.read_bytes() == before

    def test_out_that_is_the_input_by_another_name_is_refused(self, tmp_path):
        """A hard link: a different path, the same file. On macOS a case variant of the name
        does the same thing, and a resolved-path comparison misses both."""
        import os

        photo = write_photo(tmp_path / "p.jpg", flat())
        before = photo.read_bytes()
        alias = tmp_path / "alias.jpg"
        os.link(photo, alias)
        code = cli.main([str(photo), "--spec", "cn_visa_digital", "--out", str(alias)])
        assert code == cli.EXIT_USAGE and photo.read_bytes() == before

    def test_out_with_no_photo_is_a_usage_error_not_a_traceback(self, tmp_path):
        with pytest.raises(SystemExit):
            cli.main(["--spec", "cn_visa_digital", "--out", str(tmp_path / "o.jpg")])

    def test_unwritable_out_still_emits_the_report_and_exits_5(self, tmp_path, monkeypatch, capsys):
        photo = write_photo(tmp_path / "p.jpg", textured(600, 800, sigma=20))
        stub_fits(monkeypatch)
        code = cli.main([str(photo), "--spec", "cn_visa_digital", "--out", str(tmp_path),
                         "--model", str(photo), "--json"])
        report = json.loads(capsys.readouterr().out)
        assert code == cli.EXIT_NOT_WRITTEN
        assert report["render"]["rendered"] is True
        assert report["encode"]["status"] == "write_failed"

    def test_a_destination_that_cannot_be_inspected_is_reported_not_raised(self, tmp_path, monkeypatch, capsys):
        """`Path.exists()` raises when the destination's directory cannot be traversed; the
        report is still emitted and the failure is the encode result, exit 5."""
        photo = write_photo(tmp_path / "p.jpg", textured(600, 800, sigma=20))
        stub_fits(monkeypatch)
        out = tmp_path / "forbidden" / "o.jpg"
        real_exists = Path.exists

        def exists(self):
            if self == out:
                raise PermissionError(errno.EACCES, "Permission denied", str(self))
            return real_exists(self)

        monkeypatch.setattr(Path, "exists", exists)
        code = cli.main([str(photo), "--spec", "cn_visa_digital", "--out", str(out),
                         "--model", str(photo), "--json"])
        report = json.loads(capsys.readouterr().out)
        assert code == cli.EXIT_NOT_WRITTEN
        assert report["render"]["rendered"] is True
        assert report["encode"]["status"] == "write_failed"
        assert "Permission denied" in report["encode"]["detail"]
        assert not out.parent.exists()  # no write was attempted

    def test_nothing_fits_exits_5_and_writes_nothing(self, tmp_path, monkeypatch, capsys):
        photo = write_photo(tmp_path / "p.jpg", flat(rgb=(128, 128, 128)))  # under the floor at every quality
        stub_fits(monkeypatch)
        out = tmp_path / "o.jpg"
        code = cli.main([str(photo), "--spec", "cn_visa_digital", "--out", str(out),
                         "--model", str(photo), "--json"])
        report = json.loads(capsys.readouterr().out)
        assert code == cli.EXIT_NOT_WRITTEN
        assert report["encode"]["status"] == "no_encoding_satisfies"
        assert len(report["encode"]["trace"]) == len(JPEG_QUALITIES)
        assert not out.exists()

    def test_exit_codes_keep_their_precedence(self, tmp_path, monkeypatch, capsys):
        photo = write_photo(tmp_path / "p.jpg", flat())
        out = tmp_path / "o.jpg"
        stub_fits(monkeypatch, lm=landmarks(faces=0))
        assert cli.main([str(photo), "--spec", "cn_visa_digital", "--out", str(out),
                         "--model", str(photo), "--json"]) == cli.EXIT_CANNOT_MEASURE
        capsys.readouterr()
        stub_fits(monkeypatch, m=matte(top=0))  # crown unavailable: the plan is blocked
        assert cli.main([str(photo), "--spec", "cn_visa_digital", "--out", str(out),
                         "--model", str(photo), "--json"]) == cli.EXIT_NO_CROP
        assert not out.exists()

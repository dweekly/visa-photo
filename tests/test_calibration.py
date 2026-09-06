"""Threshold calibration, pinned against a real posed photo set.

On 2026-09-04 one subject was photographed 18 times: neutral, subtle and broad smiles, winks,
both eyes shut, grimaces, and deliberate head turns. The blendshape scores and pose angles
MediaPipe produced are reproduced below and asserted against.

The scores are checked in; the photographs are not. That keeps a real person's face out of a
public repository while still pinning the thresholds to real measurements, and it means these
tests run anywhere with no model download.

One subject is not a dataset. These tests say the thresholds behave correctly on the evidence
we have, not that they generalise. The three known misses at the bottom are stated as tests so
they cannot be quietly forgotten.
"""

from __future__ import annotations

import pytest

from visaphoto.measurements import Confidence, Measurement, MeasurementSet, Precondition, Status
from visaphoto.preflight import Outcome, run

# file -> (smile, jawOpen, eyeBlink, pitch, yaw, roll), as measured.
POSED = {
    "8833_neutral":            (0.000, 0.066, 0.139,   1.2,  1.9, 1.0),
    "8834_neutral":            (0.005, 0.042, 0.152,   2.0,  2.1, 1.4),
    "8835_subtle_smile":       (0.337, 0.022, 0.182,   3.0,  2.2, 1.4),
    "8836_closed_lip_grin":    (0.653, 0.005, 0.174,   0.5,  2.2, 1.7),
    "8837_broad_smile":        (0.768, 0.005, 0.034,   0.6,  2.1, 1.7),
    "8838_eyes_shut_smiling":  (0.338, 0.011, 0.793,   0.2,  2.1, 1.8),
    "8839_eyes_shut_smiling":  (0.218, 0.020, 0.526,   0.4,  2.1, 2.1),
    "8840_closed_lip_smile":   (0.179, 0.018, 0.236,   1.1,  1.5, 2.3),
    "8841_wink":               (0.036, 0.028, 0.211,   1.3,  1.0, 2.6),
    "8842_wide_stare":         (0.000, 0.088, 0.020,   1.1,  2.5, 1.5),
    "8843_grimace":            (0.088, 0.038, 0.093,  -0.0,  2.8, 1.7),
    "8844_open_grin":          (0.367, 0.089, 0.135,   1.4, -0.8, -0.4),
    "8845_big_open_smile":     (0.901, 0.245, 0.046,  -3.0,  1.2, 3.0),
    "8846_big_smile":          (0.912, 0.110, 0.275,   0.2,  2.1, 2.6),
    "8847_head_turned":        (0.004, 0.005, 0.119,  -2.3, 35.3, -1.0),
    "8848_head_up_turned":     (0.000, 0.117, 0.165,  24.2,  9.9, 4.0),
    "8849_head_back":          (0.008, 0.005, 0.344, -33.7,  1.0, 0.5),
    "8850_slight_turn":        (0.001, 0.028, 0.187,  -0.0, 12.2, 1.9),
}

SHOULD_WARN_EXPRESSION = {
    "8835_subtle_smile", "8836_closed_lip_grin", "8837_broad_smile",
    "8838_eyes_shut_smiling", "8839_eyes_shut_smiling", "8840_closed_lip_smile",
    "8844_open_grin", "8845_big_open_smile", "8846_big_smile",
}
SHOULD_WARN_POSE = {"8847_head_turned", "8849_head_back"}

# Documented misses. Asserted so they stay visible; see thresholds.py and ROADMAP.md.
KNOWN_MISSES = {"8841_wink", "8842_wide_stare", "8843_grimace"}


def build(name: str) -> MeasurementSet:
    smile, jaw, blink, pitch, yaw, roll = POSED[name]
    result = MeasurementSet(source=name, image_width=2316, image_height=3088)
    for axis, value in (("pitch", pitch), ("yaw", yaw), ("roll", roll)):
        result.add(Measurement(
            name=f"pose_{axis}", definition="Head rotation.", status=Status.AVAILABLE,
            value=value, unit="deg", backend="posed-set", confidence=Confidence.ADVISORY,
            preconditions=(Precondition("image_decoded", True, "ok"),),
        ))
    result.add(Measurement(
        name="inter_eye_distance", definition="IED.", status=Status.AVAILABLE,
        value=494.0, unit="px", backend="posed-set", confidence=Confidence.MEASURED,
        preconditions=(Precondition("image_decoded", True, "ok"),),
    ))
    return result


def scores(name: str) -> dict[str, float]:
    smile, jaw, blink, *_ = POSED[name]
    return {
        "mouthSmileLeft": smile, "mouthSmileRight": smile,
        "jawOpen": jaw,
        "eyeBlinkLeft": blink, "eyeBlinkRight": blink,
    }


def outcome(name: str, key: str) -> Outcome:
    report = run(build(name), scores(name), jurisdiction="CN")
    for finding in report.findings:
        if finding.requirement.key == key:
            return finding.outcome
    raise AssertionError(f"no finding {key}")


@pytest.mark.parametrize("name", sorted(SHOULD_WARN_EXPRESSION))
def test_non_neutral_expressions_warn(name):
    assert outcome(name, "expression_neutral") is Outcome.WARN


@pytest.mark.parametrize(
    "name", sorted(set(POSED) - SHOULD_WARN_EXPRESSION - KNOWN_MISSES)
)
def test_acceptable_expressions_do_not_warn(name):
    assert outcome(name, "expression_neutral") is Outcome.LIKELY_OK


@pytest.mark.parametrize("name", sorted(SHOULD_WARN_POSE))
def test_head_turns_beyond_chinas_limits_warn(name):
    assert outcome(name, "pose_frontal_cn") is Outcome.WARN


def test_pose_within_chinas_limits_passes():
    """24.2 deg pitch is inside China's +/-25. Passing it is correct even though the head is
    visibly tilted - the tolerance is theirs, and we do not tighten it."""
    assert outcome("8848_head_up_turned", "pose_frontal_cn") is Outcome.LIKELY_OK


def test_neutral_photos_raise_nothing_at_all():
    for name in ("8833_neutral", "8834_neutral"):
        report = run(build(name), scores(name), jurisdiction="CN")
        assert report.warnings == [], f"{name} should be clean"


class TestKnownMisses:
    """Failures we can currently detect but not flag. Kept as tests so that fixing one
    breaks the test and forces the record to be updated, rather than going unnoticed."""

    def test_wink_is_missed(self):
        """MediaPipe scores a hard wink as eyeSquint (0.451/0.736), not eyeBlink
        (0.182/0.211), and squint reads 0.43-0.47 on a neutral face so it cannot be used
        directly. Squint asymmetry would separate it; one example is not enough to calibrate."""
        assert outcome("8841_wink", "expression_neutral") is Outcome.LIKELY_OK

    def test_grimace_is_missed(self):
        """A bared-teeth grimace scores 0.088 smile. browDown and mouthPress do not help:
        both read HIGHER on the neutral photos than on the grimace."""
        assert outcome("8843_grimace", "expression_neutral") is Outcome.LIKELY_OK

    def test_wide_stare_is_missed(self):
        """eyeWide reads 0.029/0.046 on a deliberate wide stare against 0.004 neutral - too
        small a separation to threshold."""
        assert outcome("8842_wide_stare", "expression_neutral") is Outcome.LIKELY_OK


# --- Eye-region signals, per eye, Stage 1b patch definition (re-derived 2026-09-06) ---------
# file -> ((ratio_left, ratio_right), (specular_left, specular_right)), as measured.
EYE_REGION = {
    "8822_bare_reference":     ((0.780, 0.720), (0.0000, 0.0000)),
    "8833_bare_eyes":          ((0.851, 0.848), (0.0002, 0.0002)),
    "8862_bare_eyes":          ((0.774, 0.736), (0.0004, 0.0004)),
    "8864_shades_on_head":     ((0.845, 0.790), (0.0002, 0.0002)),
    "8858_shades_on_head":     ((0.826, 0.758), (0.0005, 0.0005)),
    "8855_clear_glasses":      ((0.718, 0.772), (0.0117, 0.0117)),
    "8856_clear_glasses":      ((0.683, 0.784), (0.0340, 0.0340)),
    "8857_glasses_glare":      ((0.721, 0.628), (0.0100, 0.0100)),
    "8852_cap_shadowed_eyes":  ((0.392, 0.441), (0.0000, 0.0000)),
    "8853_mirrored_shades":    ((0.383, 0.299), (0.0162, 0.0162)),
    "8863_mirrored_shades":    ((0.394, 0.428), (0.0201, 0.0201)),
}
EYES_LOOK_OBSCURED = {"8852_cap_shadowed_eyes", "8853_mirrored_shades", "8863_mirrored_shades"}
EYES_LOOK_GLARED = {
    "8855_clear_glasses", "8856_clear_glasses", "8857_glasses_glare",
    "8853_mirrored_shades", "8863_mirrored_shades",
}


def eye_region_set(name: str) -> MeasurementSet:
    (rl, rr), (sl, sr) = EYE_REGION[name]
    result = build("8833_neutral")
    result.source = name
    for field, value, unit in (
        ("patch_brightness_ratio:left", rl, "ratio"), ("patch_brightness_ratio:right", rr, "ratio"),
        ("eye_specular_fraction:left", sl, "fraction"), ("eye_specular_fraction:right", sr, "fraction"),
    ):
        result.add(Measurement(
            name=field, definition="d", status=Status.AVAILABLE, value=value,
            unit=unit, backend="posed-set", confidence=Confidence.ADVISORY,
            preconditions=(Precondition("image_decoded", True, "ok"),),
        ))
    return result


def glasses_outcome(name: str) -> Outcome:
    report = run(eye_region_set(name), scores("8833_neutral"), jurisdiction="CN")
    for finding in report.findings:
        if finding.requirement.key == "glasses_cn":
            return finding.outcome
    raise AssertionError("no glasses finding")


@pytest.mark.parametrize("name", sorted(EYES_LOOK_OBSCURED | EYES_LOOK_GLARED))
def test_obscured_or_glared_eyes_warn(name):
    assert glasses_outcome(name) is Outcome.WARN


@pytest.mark.parametrize("name", sorted(set(EYE_REGION) - EYES_LOOK_OBSCURED - EYES_LOOK_GLARED))
def test_clearly_visible_eyes_do_not_warn(name):
    assert glasses_outcome(name) is Outcome.LIKELY_OK


def test_the_separation_is_real_and_stated():
    """The gap the threshold sits in, asserted from the data rather than assumed. If a new
    photograph closes it, this fails and the threshold - not the photograph - is in question."""
    from visaphoto.thresholds import EYES_OBSCURED_RATIO

    obscured = [r for n in EYES_LOOK_OBSCURED for r in EYE_REGION[n][0]]
    clear = [r for n in set(EYE_REGION) - EYES_LOOK_OBSCURED for r in EYE_REGION[n][0]]
    assert max(obscured) < EYES_OBSCURED_RATIO < min(clear)


def test_mirrored_shades_without_a_cap_are_deep_in_the_obscured_band():
    """Under the old both-eyes patch this photo read 1.013 against 1.0 and nearly escaped."""
    rl, rr = EYE_REGION["8863_mirrored_shades"][0]
    from visaphoto.thresholds import EYES_OBSCURED_RATIO
    assert max(rl, rr) < EYES_OBSCURED_RATIO - 0.1


def test_partial_assessment_is_stated_in_the_finding():
    """A pass must not read as covering clauses we cannot check."""
    report = run(eye_region_set("8833_bare_eyes"), scores("8833_neutral"), jurisdiction="CN")
    finding = next(f for f in report.findings if f.requirement.key == "glasses_cn")
    assert "PARTIAL" in finding.detail
    assert "Frames" in finding.detail

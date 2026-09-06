"""Inventory reproductions, driven through the production pipeline.

Every test here goes through `evaluate.measure_all` with synthetic raw fits - the same path
the CLI takes after the models have run. Nothing calls a helper directly. An earlier
regression called a helper the production path never invoked, passed, and shipped the bug;
this file exists so that cannot recur.

Each defect has a paired positive case with the defect removed, so a test cannot pass merely
because every measurement was already blocked by something else.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from visaphoto.backends.landmarks import (
    IDX_CHIN, IDX_IRIS_LEFT, IDX_IRIS_RIGHT, IDX_OVAL_LEFT, IDX_OVAL_RIGHT, LandmarkFit,
)
from visaphoto.backends.segmentation import NOT_ATTEMPTED, MatteFit
from visaphoto.evaluate import measure_all
from visaphoto.measurements import Status
from visaphoto.registry import REGISTRY

W, H = 600, 800
NEUTRAL = {"eyeBlinkLeft": 0.15, "eyeBlinkRight": 0.07, "mouthSmileLeft": 0.0,
           "mouthSmileRight": 0.0, "jawOpen": 0.03}
IDENTITY = tuple(tuple(1.0 if i == j else 0.0 for j in range(4)) for i in range(4))


def yaw_matrix(degrees: float):
    t = math.radians(degrees)
    c, s = math.cos(t), math.sin(t)
    # Rotation about the vertical (y) axis, as a 4x4 with unit scale.
    return ((c, 0.0, s, 0.0), (0.0, 1.0, 0.0, 0.0), (-s, 0.0, c, 0.0), (0.0, 0.0, 0.0, 1.0))


GIMBAL = ((0.0, 0.0, 1.0, 0.0), (0.0, 1.0, 0.0, 0.0), (-1.0, 0.0, 0.0, 0.0), (0.0, 0.0, 0.0, 1.0))


def landmarks(*, left=(200.0, 300.0), right=(400.0, 300.0), chin=(300.0, 520.0),
              oval_left=(150.0, 350.0), oval_right=(450.0, 350.0), blendshapes=NEUTRAL,
              matrix=IDENTITY, faces=1, error=None, count=478) -> LandmarkFit:
    if faces != 1:
        return LandmarkFit(faces, None, None, None, "test", error)
    pts = [(300.0, 400.0)] * count
    for idx, p in ((IDX_IRIS_LEFT, left), (IDX_IRIS_RIGHT, right), (IDX_CHIN, chin),
                   (IDX_OVAL_LEFT, oval_left), (IDX_OVAL_RIGHT, oval_right)):
        if idx < count:
            pts[idx] = p
    return LandmarkFit(1, tuple(pts), blendshapes, matrix, "test")


def matte(*, top=100, bottom=700, left=150, right=450, extra=()) -> MatteFit:
    alpha = np.zeros((H, W), dtype=np.uint8)
    alpha[top:bottom, left:right] = 255
    for (r, c) in extra:
        alpha[r, c] = 255
    return MatteFit(True, True, alpha, "test")


def pixels(level: int = 128, eye_level: int | None = None):
    px = np.full((H, W, 3), level, dtype=np.uint8)
    if eye_level is not None:
        px[240:360, 120:480] = eye_level  # darken the whole eye band
    return px


def run(lm=None, m=None, px=None, segmentation=True):
    return measure_all(px if px is not None else pixels(),
                       lm if lm is not None else landmarks(),
                       m if m is not None else matte(),
                       source="synthetic", segmentation_attempted=segmentation)


def blockers(result, name):
    meas = result.get(name)
    return {p.id for p in meas.blockers_false}, {p.id for p in meas.blockers_unknown}


class TestCompleteSetEveryRun:
    """"Every emitted measurement matches the registry" passes when nothing is emitted.
    This asserts the whole set is present in every run configuration."""

    @pytest.mark.parametrize("config", ["normal", "no_face", "two_faces", "model_failed",
                                        "no_segmentation"])
    def test_every_registry_name_is_present(self, config):
        if config == "normal":
            r = run()
        elif config == "no_face":
            r = run(lm=landmarks(faces=0))
        elif config == "two_faces":
            r = run(lm=landmarks(faces=2))
        elif config == "model_failed":
            r = run(lm=landmarks(faces=-1, error="boom"))
        else:
            r = run(m=NOT_ATTEMPTED, segmentation=False)
        assert set(r.measurements) == set(REGISTRY)

    def test_a_good_synthetic_photo_measures_the_observed_tier(self):
        r = run()
        for name, spec in REGISTRY.items():
            if spec.tier.value == "observed":
                assert r.status(name) is Status.AVAILABLE, (name, r.get(name).reason)
        assert r.value("eye_line_y") == 300.0
        assert r.value("inter_eye_distance") == 200.0
        assert r.value("matte_top_row") == 100.0
        assert r.value("head_width_silhouette") == 300.0

    def test_no_face_makes_everything_unavailable_by_a_false_gate(self):
        r = run(lm=landmarks(faces=0))
        assert r.gate_record["face_detected_one"].satisfied is False
        assert all(r.status(n) is not Status.AVAILABLE for n in REGISTRY)

    def test_model_failure_is_none_not_false(self):
        r = run(lm=landmarks(faces=-1, error="landmarker failed"))
        assert r.gate_record["face_detected_one"].satisfied is None
        assert "landmarker failed" in r.gate_record["face_detected_one"].detail

    def test_no_segmentation_is_not_attempted_not_unavailable(self):
        r = run(m=NOT_ATTEMPTED, segmentation=False)
        for name in ("matte_top_row", "head_width_silhouette", "anatomical_crown_y"):
            assert r.status(name) is Status.NOT_ATTEMPTED
        assert r.status("eye_line_y") is Status.AVAILABLE


class TestInventoryReproductions:
    def test_a_tuft_touching_the_top_edge_is_not_a_crown(self):
        """Stage 1's guard required top == 0 AND a wide first row; a narrow tuft at row 0 passed
        it and reported crown_y = 0 as measured."""
        tuft = [(0, c) for c in range(290, 310)] + [(r, c) for r in range(1, 100) for c in (300,)]
        r = run(m=matte(extra=tuft))
        assert r.status("matte_top_row") is Status.UNAVAILABLE
        assert blockers(r, "matte_top_row")[0] == {"matte_clear_of_top_edge"}
        assert r.status("head_width_silhouette") is Status.UNAVAILABLE

    def test_paired_untouched_top_edge_measures(self):
        r = run(m=matte(top=5))
        assert r.value("matte_top_row") == 5.0

    def test_gimbal_lock_does_not_fabricate_roll(self):
        r = run(lm=landmarks(matrix=GIMBAL))
        assert r.status("pose_roll") is Status.UNAVAILABLE
        assert blockers(r, "pose_roll")[0] == {"pose_decomposition_valid"}
        assert "gimbal" in r.gate_record["pose_decomposition_valid"].detail

    def test_paired_identity_matrix_measures_pose(self):
        r = run()
        assert r.value("pose_roll") == pytest.approx(0.0)

    def test_nonfinite_matrix_is_invalid(self):
        bad = tuple(tuple(math.nan if i == j == 0 else v for j, v in enumerate(row))
                    for i, row in enumerate(IDENTITY))
        r = run(lm=landmarks(matrix=bad))
        assert r.gate_record["pose_decomposition_valid"].satisfied is False

    def test_tiny_eye_separation_names_the_right_gate(self):
        """Stage 1 reported this as 'falls outside the image', which was false."""
        r = run(lm=landmarks(left=(300.0, 300.0), right=(302.0, 300.0)))
        assert r.status("patch_brightness_ratio:left") is Status.UNAVAILABLE
        assert "raw_eye_separation_usable is False" in r.get("patch_brightness_ratio:left").reason

    def test_eye_patch_off_the_bottom_edge_is_unavailable(self):
        r = run(lm=landmarks(left=(200.0, 790.0), right=(400.0, 790.0), chin=(300.0, 799.0)))
        assert r.status("patch_brightness_ratio:left") is Status.UNAVAILABLE
        assert r.gate_record["eye_patch_in_frame:left"].satisfied is False

    def test_eye_pixel_on_matte_background_fails_isolation(self):
        r = run(m=matte(top=600))  # matte starts below the eyes
        assert r.gate_record["face_component_isolated"].satisfied is False
        for name in ("matte_top_row", "head_width_silhouette"):
            assert r.status(name) is Status.UNAVAILABLE
            assert "face_component_isolated" in r.get(name).reason

    def test_chin_below_the_frame_is_unavailable(self):
        r = run(lm=landmarks(chin=(300.0, 850.0)))
        assert r.status("chin_landmark_y") is Status.UNAVAILABLE
        assert blockers(r, "chin_landmark_y")[0] == {"landmark_in_frame:chin_152"}

    def test_a_stray_pixel_does_not_inflate_head_width(self):
        clean = run().value("head_width_silhouette")
        noisy = run(m=matte(extra=[(150, 590)])).value("head_width_silhouette")
        assert clean == noisy == 300.0

    def test_a_head_clipped_at_the_side_has_no_width(self):
        r = run(m=matte(left=0))
        assert r.status("head_width_silhouette") is Status.UNAVAILABLE
        assert blockers(r, "head_width_silhouette")[0] == {"matte_clear_of_left_edge"}
        assert r.value("matte_top_row") == 100.0  # the crown is still fine


class TestNewGates:
    def test_yaw_beyond_limit_blocks_horizontal_projections_only(self):
        r = run(lm=landmarks(matrix=yaw_matrix(35.0)))
        for name in ("inter_eye_distance", "head_width_face_oval", "head_width_silhouette",
                     "eye_mid_x"):
            assert r.status(name) is Status.UNAVAILABLE, name
            assert "yaw_within_measurement_limit" in blockers(r, name)[0]
        assert r.status("eye_line_y") is Status.AVAILABLE  # vertical; not gated on yaw
        assert r.value("pose_yaw") == pytest.approx(35.0, abs=0.01)

    @pytest.mark.parametrize("deg", [12.0, -12.0])
    def test_yaw_within_limit_on_both_signs_measures(self, deg):
        r = run(lm=landmarks(matrix=yaw_matrix(deg)))
        assert r.status("inter_eye_distance") is Status.AVAILABLE

    def test_obscured_eyes_block_the_iris_measurements(self):
        r = run(px=pixels(level=128, eye_level=40))  # eyes at 0.31 of cheek
        for name in ("eye_line_y", "eye_mid_x", "inter_eye_distance"):
            assert r.status(name) is Status.UNAVAILABLE, name
            assert "eyes_unobscured_both" in blockers(r, name)[1]
        assert r.gate_record["eye_unobscured:left"].satisfied is False
        assert r.status("raw_eye_separation") is Status.AVAILABLE  # diagnostic survives

    def test_one_obscured_eye_is_enough(self):
        px = pixels()
        px[240:360, 120:280] = 40  # left eye only
        r = run(px=px)
        assert r.gate_record["eye_unobscured:left"].satisfied is False
        assert r.gate_record["eye_unobscured:right"].satisfied is True
        assert r.status("inter_eye_distance") is Status.UNAVAILABLE

    def test_closed_eyes_block_the_iris_measurements(self):
        r = run(lm=landmarks(blendshapes={**NEUTRAL, "eyeBlinkLeft": 0.9, "eyeBlinkRight": 0.9}))
        assert r.status("eye_line_y") is Status.UNAVAILABLE
        assert "eyes_open_both" in blockers(r, "eye_line_y")[1]

    def test_missing_blendshapes_leave_eyes_open_unknown_not_true(self):
        """A detector that could not run is not a detector that passed."""
        r = run(lm=landmarks(blendshapes=None))
        assert r.gate_record["eye_open:left"].satisfied is None
        assert r.status("eye_line_y") is Status.UNAVAILABLE

    def test_missing_matrix_leaves_pose_gates_none(self):
        r = run(lm=landmarks(matrix=None))
        assert r.gate_record["pose_decomposition_valid"].satisfied is None
        assert r.status("inter_eye_distance") is Status.UNAVAILABLE
        assert "not evaluated" in r.get("inter_eye_distance").reason

    def test_reason_lists_every_blocker_not_the_first(self):
        r = run(lm=landmarks(matrix=None, blendshapes=None))
        reason = r.get("inter_eye_distance").reason
        assert "eyes_open_both" in reason and "yaw_within_measurement_limit" in reason


def pitch_matrix(degrees: float):
    t = math.radians(degrees)
    c, s = math.cos(t), math.sin(t)
    # Rotation about the horizontal (x) axis, as a 4x4 with unit scale.
    return ((1.0, 0.0, 0.0, 0.0), (0.0, c, -s, 0.0), (0.0, s, c, 0.0), (0.0, 0.0, 0.0, 1.0))


class TestPosedSetGates:
    """The head-turn photographs from the 2026-09-04 posed set, via their measured angles.

    Only the angles are checked in, not the photographs, so the matrix is reconstructed from
    the angle. That tests the gate; it does not re-test the decomposition on real output."""

    def test_8847_yaw_35_blocks_projected_widths(self):
        r = run(lm=landmarks(matrix=yaw_matrix(35.3)))
        for name in ("inter_eye_distance", "head_width_silhouette", "head_width_face_oval"):
            assert r.status(name) is Status.UNAVAILABLE, name
            assert "yaw_within_measurement_limit" in blockers(r, name)[0]

    def test_8850_yaw_12_measures(self):
        r = run(lm=landmarks(matrix=yaw_matrix(12.2)))
        assert r.status("inter_eye_distance") is Status.AVAILABLE

    def test_8849_pitch_minus_34_blocks_vertical_positions_not_ied(self):
        r = run(lm=landmarks(matrix=pitch_matrix(-33.7)))
        assert r.status("eye_line_y") is Status.UNAVAILABLE
        assert r.status("chin_landmark_y") is Status.UNAVAILABLE
        assert "pitch_within_measurement_limit" in blockers(r, "eye_line_y")[0]
        assert r.status("inter_eye_distance") is Status.AVAILABLE  # not gated on pitch

    def test_8848_pitch_24_is_inside_chinas_law_but_outside_our_operating_limit(self):
        """The cost stated in the plan, asserted so it stays visible: China permits +/-25 deg
        pitch, our measurement limit is 15, so this photo gets no eye line and hence no crop.
        The remedy is the tunable in thresholds.py, not a silent widening."""
        r = run(lm=landmarks(matrix=pitch_matrix(24.2)))
        assert r.status("eye_line_y") is Status.UNAVAILABLE

# Changelog

User-facing changes, newest first. Cited from [README.md](README.md).

## Unreleased

Nothing released yet. The project is at Stage 0 of 5; see [ROADMAP.md](ROADMAP.md).

### Changed (unreleased, Stage 1b)
- A measurement is now unavailable unless every gate it declares is affirmatively true. Gates
  are evaluated once into a frozen, tri-state record before anything is emitted. The report
  lists every failed and every not-evaluated gate, not the first.
- Renamed to say what was observed: `crown_y` → `matte_top_row`; `eye_brightness_ratio` →
  `patch_brightness_ratio:left` / `:right`; `eye_specular_fraction` → per side; `chin_y_landmark`
  → `chin_landmark_y`. `chin_y_visible` and `head_width_ear_to_ear` are gone; their absence is
  now expressed as the `anatomical_*` tier, unavailable on every image this build can process.
- The eye-obscured signal is redefined per eye on cheek proper and recalibrated (threshold 0.53).
  Iris-derived measurements now require both eyes open and unobscured, and head widths require
  yaw and roll within ±15°; a mirrored-sunglasses photo therefore reports IED as unavailable.
- `--no-segmentation` reports the matte measurements as `not_attempted`, distinct from
  unavailable. No face, several faces, or a failed model no longer abort; the full measurement
  set is returned with the gate that failed.
- `--capabilities` prints what this build can measure, and under which conditions, with no
  model weights installed.

### Added
- Design and staged delivery plan (`docs/PLAN.md`), peer-reviewed once before implementation.
- Stage 0 diagnostic (`tools/spikes/mediapipe_smoke.py`) proving the face-landmarking backend
  runs and returns usable geometry on a given machine.
- `NEGATIVE_RESULTS.md` recording approaches that failed, with traces and conditions.
- `THIRD_PARTY_LICENSES.md` stating code and model-weight licences separately.

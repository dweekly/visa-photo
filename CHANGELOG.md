# Changelog

User-facing changes, newest first. Cited from [README.md](README.md).

## Unreleased

Nothing released yet. Progress by stage is in [ROADMAP.md](ROADMAP.md).

### Added (unreleased, Stage 3)
- `--out FILE` renders the planned crop and writes it (requires `--spec`). Crop and resize are a
  single uniform resample; the output is 8-bit sRGB JPEG, 4:4:4, no metadata, at the highest
  listed quality whose written size falls inside the destination's byte band. A source with an
  embedded colour profile (Display P3 on iPhone photos) is converted to sRGB; one without is
  assumed sRGB and the report says so. If no listed quality fits, or the destination cannot be
  written, nothing at `--out` is touched and the report says why (exit 5). `--out` naming the
  input photo is refused.
- Background replacement is performed only where the destination's rules allow it. A destination
  whose rules do not address editing (China) gets it only with `--allow-unresolved-operations`,
  and the report records that it was an opt-in; a destination that prohibits it (NZ) never does.
  It is also refused, whatever the policy, when the matte did not isolate the face or the subject
  crosses the crop's top or sides.
- The report carries an operation history: each operation, its status, the gates it consulted,
  and the parameters used (crop box, scale, quality, bytes).

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

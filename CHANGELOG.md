# Changelog

User-facing changes, newest first. Cited from [README.md](README.md).

## Unreleased

Nothing released yet. Progress by stage is in [ROADMAP.md](ROADMAP.md).

### Added (unreleased, Stage 4)
- After `--out`, the written file is reopened, measured afresh, and checked rule by rule from
  its own measurements: `pass`, `fail`, `indeterminate` or `not_evaluated`, each with the
  observed value, the plan's prediction, their delta and the reason. Encoding is checked from
  the file: dimensions, format, 24-bit RGB, and the size in bytes under both readings of "KB".
  The aggregate covers implemented checks only; what still needs the applicant's word and what
  this build cannot assess are listed beside it. Exit 6 when the file fails.
- `--validate` checks a photo you already have against `--spec`, at its own size, with no crop.
- `--spec` now selects the destination's advisories (China's, for `cn_visa_digital`) without
  `--for`; a conflicting `--for` is refused.
- China's "> 60 pixels" and "> 256 pixels" are strict: a value exactly on the bound fails, and the
  solver refuses a crop whose only feasible point sits on one.
- `--json` emits one envelope for every photo run - `report_version`, `tool`, `error`, then each
  stage, `null` when not reached - documented under "The report" in the README.

### Added (unreleased, Stage 3)
- `--out FILE` renders the planned crop and writes it (requires `--spec` and a digital profile).
  The photo is decoded once; an embedded colour profile (Display P3 on iPhone photos) is
  converted to sRGB, and a photo without one is written as-is with the assumption stated. Crop
  and resize are one resample. The output is an 8-bit sRGB JPEG, 4:4:4, carrying nothing from
  the source - no EXIF, no profile, no comment - at the highest listed quality whose written
  size falls inside the destination's byte band (China's "40 KB - 120 KB" read as
  40,960-120,000 bytes, satisfying either reading of KB).
- When no listed quality fits, or the destination cannot be written, nothing at `--out` is
  touched and the report says why, with every quality tried (exit 5). `--out` naming the input
  photo is refused.
- The report records what was done to the pixels, in order - colour conversion, crop and
  resize (box, scale, output size), encoding (quality, bytes, trace) - and claims nothing else.

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

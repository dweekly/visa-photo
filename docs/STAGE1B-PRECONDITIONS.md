# Stage 1b — precondition-driven measurement

Working plan for the stage. The *why* and the invariant are in [PLAN.md](PLAN.md) → Measurement
and are not repeated here; this document is the concrete gate graph, the registry, and the
sequence. Fresh as of 2026-09-06.

**Where:** worktree `~/dev/visa-photo-preconditions`, branch `stage1b-preconditions`. Tracking PR
opened with this commit. Rebases onto `main` once Stage 2 (PR #2) merges.

## The gate graph

Every gate records its own prerequisites and its evidence method. A gate whose prerequisite is
`None` is `None`. A gate is `True` only when its evidence was actually obtained and passed; a
detector that could not run is not a detector that passed. Evaluated in this order (each row's
prerequisites are above it), then the record is frozen.

| Gate id | Evidence | Prerequisites | `None` when |
|---|---|---|---|
| `image_decoded` | Pillow decoded to RGB after EXIF transpose | — | never (a failure is a hard stop) |
| `face_detected_one` | landmarker run with `num_faces=4` returned exactly one face | `image_decoded` | model failed to run |
| `landmarks_478` | result carries the iris-refined point set | `face_detected_one` | — |
| `landmark_in_frame:<L>` for `chin_152`, `iris_468`, `iris_473`, `oval_234`, `oval_454` | `0 ≤ x < W` and `0 ≤ y < H` in EXIF-normalized coordinates, before any int conversion | `landmarks_478` | — |
| `raw_eye_separation_usable` | ‖iris_468 − iris_473‖ ≥ `MIN_RAW_EYE_SEPARATION_PX` | both iris `landmark_in_frame` | — |
| `pose_decomposition_valid` | matrix present, 4×4, all finite, rotation block non-singular within tolerance, Euler decomposition succeeded (`sy` above gimbal tolerance) | `face_detected_one` | matrix absent |
| `pitch_within_measurement_limit` / `yaw_…` / `roll_…` | \|angle\| ≤ `POSE_MEASUREMENT_LIMIT_DEG` | `pose_decomposition_valid` | pose invalid |
| `blendshapes_present` | result carries 52 blendshapes | `face_detected_one` | — |
| `eye_open:left` / `eye_open:right` | `eyeBlink*` ≤ `EYE_CLOSED_SCORE`, per eye | `blendshapes_present` | blendshapes absent |
| `eye_patch_in_frame:left` / `:right` | patch rectangle wholly inside the image | `raw_eye_separation_usable`, that iris in frame | — |
| `cheek_patch_in_frame:left` / `:right` | the redefined cheek patch wholly inside the image | `raw_eye_separation_usable`, that iris in frame | — |
| `cheek_denominator_valid:left` / `:right` | patch non-empty, mean luminance > `MIN_CHEEK_LUMINANCE` | `cheek_patch_in_frame:*` | patch not in frame |
| `eye_unobscured:left` / `:right` | per-eye brightness ratio ≥ `EYES_OBSCURED_RATIO` | `eye_patch_in_frame:*`, `cheek_denominator_valid:*` | either input missing |
| `eyes_open_both`, `eyes_unobscured_both` | conjunction | the two per-eye gates | either is `None` |
| `matte_present` | segmentation ran with weights on disk | `image_decoded` | segmentation not attempted or weights absent |
| `matte_has_subject` | some row has ≥ `MIN_ROW_PIXELS` solid pixels | `matte_present` | — |
| `face_component_isolated` | scipy available; eye midpoint inside frame; that pixel labelled foreground; that component selected | `matte_has_subject`, both iris in frame | scipy missing; **`False`** when the eye pixel is background |
| `matte_clear_of_top_edge` | component's top row > 0 — **`top == 0` alone**; `MIN_ROW_PIXELS` already excludes specks | `face_component_isolated` | — |
| `matte_clear_of_left_edge` / `_right_edge` | no solid pixel in column 0 / W−1 within the head band | `face_component_isolated`, chin and both iris in frame | — |
| `no_headwear` | — | — | **always** in this build |
| `cheek_patch_on_skin:*` | — | — | **always** in this build |
| `chin_landmark_is_anatomical` | — | — | **always** in this build (beard) |

The cycle the review found is broken by `raw_eye_separation_usable`: it sizes the patches, has
weaker prerequisites than anatomical IED, and never escapes as `inter_eye_distance`.

## The registry

Measurement → required gates. Construction takes a name and a candidate value, looks this up,
resolves each id against the frozen record, and decides the status. Emitters supply no evidence.

**Observed tier** — available on a good photo.

| Measurement | Required gates |
|---|---|
| `eye_line_y` | `landmarks_478`, `landmark_in_frame:iris_468`, `:iris_473`, `eyes_open_both`, `eyes_unobscured_both`, `pitch_within_measurement_limit` |
| `eye_mid_x` | as `eye_line_y`, plus `yaw_…`, `roll_…` |
| `inter_eye_distance` | `landmark_in_frame:iris_*`, `eyes_open_both`, `eyes_unobscured_both`, `yaw_…`, `roll_…` |
| `chin_landmark_y` | `landmarks_478`, `landmark_in_frame:chin_152`, `pitch_…` |
| `head_width_face_oval` | `landmark_in_frame:oval_*`, `yaw_…`, `roll_…` |
| `pose_pitch` / `pose_yaw` / `pose_roll` | `face_detected_one`, `pose_decomposition_valid` (confidence stays ADVISORY) |
| `matte_top_row` (renamed from `crown_y`) | `matte_present`, `matte_has_subject`, `face_component_isolated`, `matte_clear_of_top_edge` |
| `head_width_silhouette` | `matte_top_row`'s gates, `landmark_in_frame:chin_152`, `:iris_*`, `eyes_unobscured_both`, `matte_clear_of_left_edge`, `_right_edge`, `yaw_…`, `roll_…` |
| `head_height` (derived) | `matte_top_row` available **and** `chin_landmark_y` available |

**Diagnostic tier** — inputs to gates; recorded, never consumed by profiles.

| Measurement | Required gates |
|---|---|
| `raw_eye_separation` | `raw_eye_separation_usable` |
| `patch_brightness_ratio:left` / `:right` | `eye_patch_in_frame:*`, `cheek_denominator_valid:*` |
| `eye_specular_fraction:left` / `:right` | `eye_patch_in_frame:*` |

**Anatomical tier** — unavailable in this build unless recorded human evidence supplies the gate.

| Measurement | Required gates |
|---|---|
| `anatomical_crown_y` | `matte_top_row`'s gates + `no_headwear` |
| `anatomical_chin_y` | `chin_landmark_y`'s gates + `chin_landmark_is_anatomical` |

Profiles bind to the observed tier and say so; `cn_visa_digital`'s "crown" is `matte_top_row`,
which is what its diagram measures.

**Cost stated up front:** `pitch_within_measurement_limit` at ±15° gates `eye_line_y`, so a
photo pitched 20° — inside China's ±25° legal tolerance — gets no crop. That is the plan's stated
policy (gate toward unavailable; never correct by an uncalibrated angle), and the limit is the
tunable in `thresholds.py`. The report says which gate blocked it.

## Cheek patch, defined before it is measured

Per eye. Anchor: that eye's iris centre. Offset: `+0.35·d` horizontally *away* from the face
midline and `+0.55·d` downward, where `d` is `raw_eye_separation`. Size: `0.25·d` square.
Clipping: not permitted — a patch touching the frame makes `cheek_patch_in_frame` `False`.
Luminance: mean of `0.2126R + 0.7152G + 0.0722B` over the patch in sRGB. Denominator floor:
`MIN_CHEEK_LUMINANCE`. Eye patch: as today, per eye. The per-eye ratio is that eye's patch over
that eye's cheek. **No averaging across eyes**; `eyes_unobscured_both` is a conjunction.

This changes every calibrated ratio. The eleven photographs are re-run and the result is *reported
as whatever it is*. If the separation is gone, `eye_unobscured:*` stays `None` and the flag is
withdrawn until the calibration stage — not tuned until eleven examples separate.

## Sequence

One PR, commits in this order, each pushed when green.

- [ ] This document.
- [ ] `Gate`, `GateRecord` (frozen, topological), `Precondition`, registry; `Measurement` constructor
      invariant (identity tri-state, finite value); `MeasurementSet` private storage, `add()` once,
      `NOT_ATTEMPTED`; structured reasons; `--capabilities` from the registry with no weights.
      Tests: constructor, container, registry completeness both directions, capabilities output.
- [ ] `measure()` as fit → gates → emit. Landmark and segmentation backends become fit-only;
      gate evaluators move to `gates.py`. The inventory fixes fall out of the gates rather than
      being patched: top-edge tuft, gimbal roll, mis-attributed reason, eye-patch bottom bound,
      five isolation fallbacks, landmark-in-frame, `--no-segmentation` absence. Tests: every
      inventory reproduction through `measure()` with stubbed raw outputs, each with a paired
      positive case; both `False` and `None` per gate; complete name set per run configuration.
- [ ] Cheek patch redefinition; re-derive the eleven ratios; report; calibration tests updated to
      whatever the truth is.
- [ ] Solver consumer refusal: `build_constraints` reports *cannot solve with available
      measurements* naming the rule; planner surfaces it; one CLI test.
- [ ] Posed-set gate tests (8847 yaw, 8850, 8853 shades, 8864); reference regression (493, 1320,
      495, 1086); `NEGATIVE_RESULTS.md`, `ROADMAP.md`, `CHANGELOG.md`.

## Acceptance

PLAN.md → "Stage 1b verification", in full. Review under the two-pass rule; a repeated class at
pass two stops the branch.

# Roadmap

Stack-ranked. Cited from [README.md](README.md). Fresh as of 2026-09-04.
Full design in [docs/PLAN.md](docs/PLAN.md).

## Stages

- ~~**Stage 0 — spike: does MediaPipe run?**~~ Done 2026-09-04. Gate passed on mediapipe 0.10.21;
  1.0.x is unusable (see [NEGATIVE_RESULTS.md](NEGATIVE_RESULTS.md)). Diagnostic retained at
  `tools/spikes/mediapipe_smoke.py`.
- **Stage 1 — measurement and capability matrix.** Eye centres, chin, crown from the segmentation
  matte, pose. Each measurement declares which backend supplies it, its uncertainty, and when it
  returns *unavailable*. A minimal CLI lands here so end-to-end verification starts early rather
  than at the end.
- **Stage 2 — spec schema and geometry solver.** Typed measurements; named interpretation rule
  sets; per-channel operation policy; exact interval feasibility with named conflicting rules on
  failure.
- **Stage 3 — render and encode.** Crop, background replacement *where the channel permits it*,
  resize, and a bounded encoder search against format, colour-space and byte-band constraints.
- **Stage 4 — validator and report contract.** Per-criterion pass / fail / indeterminate /
  not-evaluated, each with a reason, measured from the written file.
- **Stage 5 — seeded profiles and docs.** `cn_visa_digital`, `cn_visa_paper`, `us_visa_digital`,
  `us_passport_print`, `schengen_icao_base`, `nz_nzeta`.

## Known work not yet scheduled

- **Pose acceptance gate.** Pose is advisory until measured against known angles near the actual
  thresholds. Two models disagreed by up to 2.6° on one image, against an ICAO tolerance of ±5°.
- **Redistributable test fixtures.** Public CI cannot use personal photographs. The ONOT synthetic
  ICAO-compliant mugshot dataset is a candidate.
- **File the MediaPipe 1.0.x abort upstream.** Reproduced on two Python versions on macOS 26.6.1 /
  M4 Max; no matching issue found on the tracker as of 2026-09-04.
- **Linux CI.** Needs `libgles2` present in the image for any mediapipe version.
- **Verify OFIQ's licence**, which is a precondition for even evaluating it as a dependency.

## Deferred past v1

Deliberately out of scope, recorded so the boundary holds:

- OFIQ integration for image-quality scoring (sharpness, illumination uniformity, background
  homogeneity, eyes-open). Right long-term answer; large C++ dependency.
- Broad demographic accuracy evaluation across age, skin tone, facial hair, head coverings and
  capture devices, beyond a small varied validation set. Until then, claimed support stays narrow.
- Advanced anatomy estimation (better skull and ear estimators) and interactive measurement
  correction. *Unavailable* is an acceptable v1 outcome.
- Guided capture / camera assistance.
- Automated monitoring of official sources for change. v1 entries are versioned and reviewed by
  hand.
- Print-production assurance — printer scaling, paper, colour management. v1 exports an intended
  physical size and states plainly that the actual print is unchecked.
- Image rotation as a correction step. v1 crops and scales only.
- GPU tuning and a broad platform matrix.

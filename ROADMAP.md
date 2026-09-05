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

## Adoption: distribution and the Claude skill

Scheduled after Stage 5, but it constrains CLI design now, so it is recorded here.

**Distribution is `uvx`.** Publish to PyPI so the entry point is
`uvx visa-photo photo.jpg --spec cn_visa_digital` with no venv and no install step. `uv` pins the
interpreter, which this project genuinely needs: mediapipe must be 0.10.x, and pip will install it
onto an unsupported Python where it aborts (see [NEGATIVE_RESULTS.md](NEGATIVE_RESULTS.md)).
`uvx --python 3.12` makes that invisible rather than a support burden. Model weights cache once
under `~/.cache/visa-photo`, pinned by checksum.

**CLI decisions this forces:**

- **Refuse to guess the submission channel.** `--country CN` alone must be an error listing
  `cn_visa_digital` and `cn_visa_paper` and stating that they have different aspect ratios and
  different rules. This is the founding mistake encoded as a hard failure rather than a doc note.
- `--json` report with a stable, versioned schema, so a caller parses rather than scrapes.
- `visa-photo specs` lists available profiles and their channels.
- Exit codes distinguish *fails a requirement* from *could not evaluate* from *crashed*.
- HEIC input support (`pillow-heif`). Phone photos are the common case.

**The Claude skill is mostly prohibitions.** Its purpose is to stop an agent doing by hand what
this tool exists to prevent. `SKILL.md` must instruct:

- Never hand-crop with ImageMagick or equivalent. Run the CLI, or report that you cannot.
- **Never invent a spec for an unlisted country.** Refuse, list what exists, point at the
  contribution workflow. An agent reading a consulate page and synthesising a spec entry is the
  worst available failure mode for this project.
- **Never collapse `indeterminate` or `not_evaluated` into "compliant".** Quote per-criterion
  outcomes verbatim. A summarising model drifts toward a clean pass, and distinguishing "passes"
  from "we could not check" is the entire value of the tool.

## Hosted service - visa.weekly.org

A web service taking a source photo plus a destination and returning either a conformant photo or
a rejection reason. Recorded 2026-09-04.

**The unresolved question is not hosting, it is the privacy promise.** This project's stated
property today is that no photo leaves your machine, and the README says so. A hosted service
inverts that: users would upload a face and, for a visa photo specifically, an ID-grade portrait.
Before building it we need a data-handling position we are willing to publish - process and
discard in memory, no retention, no image logging, no third-party analytics on the page - and the
local tool's promise must not be quietly weakened to match the service's.

Secondary: the stack cannot run on Cloudflare Workers (mediapipe and rembg are native Python).
Cloudflare Containers or GCP Cloud Run are the realistic options. Decide only after the privacy
position is settled.

## Demonstration assets

A before/after pair on a real photo, for the README and for showing what the tool does. Blocked
on a decision recorded in docs/PLAN.md: personal photographs stay out of the public repository
unless publication is explicitly authorised. Options are an authorised real portrait, or a
synthetic face from the ONOT dataset, which costs nothing in consent and is reproducible by
anyone cloning the repo.

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

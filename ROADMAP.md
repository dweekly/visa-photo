# Roadmap

Stack-ranked. Cited from [README.md](README.md). Fresh as of 2026-09-06.
Full design in [docs/PLAN.md](docs/PLAN.md).

## Stages

- ~~**Stage 0 — spike: does MediaPipe run?**~~ Done 2026-09-04. Gate passed on mediapipe 0.10.21;
  1.0.x is unusable (see [NEGATIVE_RESULTS.md](NEGATIVE_RESULTS.md)). Diagnostic retained at
  `tools/spikes/mediapipe_smoke.py`.
- ~~**Stage 1 — measurement.**~~ Merged 2026-09-06 (PR #1). Eye centres, chin, crown, pose,
  expression and eye-region signals, checked against sourced requirements. Shipped *without* the
  capability matrix the plan required, at the cost of six review passes finding one defect class;
  see Stage 1b.
- **Stage 2 — spec schema and geometry solver.** Built (PR #2): exact interval feasibility, China
  digital and paper profiles, `--spec`. Reproduced the hand-built crop to 0.14%. Awaiting review
  and merge.
- **Stage 1b — precondition-driven measurement.** In progress on PR #3. Landed on the
  branch: gate graph and registry; frozen tri-state gates evaluated once before anything is
  emitted; the registry as the only construction path; `add()` refusing double writes;
  `NOT_ATTEMPTED`; `--capabilities`; three-pass `measure()`; all seven inventory defects fixed
  by construction with reproductions driven through the production path; the cheek patch
  redefined per eye and re-derived on the eleven photographs (threshold 0.53, clean gap).
  Remaining: the solver refusing unavailable inputs by name, which waits for Stage 2 to merge.
- **Calibration beyond one subject.** MST-E, then the Chicago Face Database, then consenting
  volunteers for the matched failure conditions no dataset covers. Sources, terms and the analysis
  design are in [docs/PLAN.md](docs/PLAN.md) → Calibration. After Stage 1b.
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

## Expression detection gaps, with evidence

Calibrated 2026-09-04 against 18 posed photographs of one subject. Smiles, open mouths and
closed eyes are now caught reliably. Three failure types are not, and each has been tested
rather than assumed:

- **One-eyed wink.** MediaPipe scores it as `eyeSquint` (0.451/0.736), not `eyeBlink`
  (0.182/0.211). `eyeSquint` cannot be used directly - it reads 0.43-0.47 on a fully neutral
  face. Left-right squint *asymmetry* does separate it (0.285 wink vs 0.043 neutral), but one
  example is not enough to set a threshold on. Needs more winks, ideally from several people.
- **Grimace / bared teeth.** Scores 0.088 smile, below any usable threshold. `browDown` and
  `mouthPress` are no help: both read *higher* on the neutral photos than on the grimace.
- **Deliberate wide stare.** `eyeWide` reads 0.029/0.046 against 0.004 neutral - too small a
  separation to threshold.

All three are asserted as known misses in `tests/test_calibration.py`, so fixing one breaks a
test and forces this section to be updated.

**The set is one adult male subject.** Thresholds that separate cleanly here may not
generalise across age, skin tone, facial hair or capture device. Broadening it is the single
highest-value thing that could be done for detection quality.

## Gaze direction - measured, promising, not yet shippable

Every source surveyed requires the subject to look directly at the camera, and a photo can
have acceptable head pose while the eyes look elsewhere. MediaPipe's `eyeLook*` blendshapes
respond strongly - measured on posed photographs 2026-09-04:

    looking at camera        eyeLookInLeft 0.002  eyeLookOutRight 0.010
    gaze averted sideways    eyeLookInLeft 0.650  eyeLookOutRight 0.651
    looking down             eyeLookDownLeft 0.538 / DownRight 0.544 (neutral: 0.130 / 0.135)

Two problems stop it shipping today.

**The signal is head-relative, not camera-relative.** A subject looking straight at the lens
with the head turned shows large eye rotation, because the eyes are compensating for the head.
Separating "looking away" from "looking at the camera with a turned head" needs the gaze
combined with head yaw, which is an algorithm to validate rather than a threshold to pick.

**Mirrored sunglasses corrupt it.** Behind opaque lenses the iris landmarks are fabricated,
and the sunglasses photo reports eyeLookDown 0.47/0.45 - indistinguishable from genuinely
looking down. Any gaze check must therefore run after, and be gated on, the eyes being visible.

Also unhandled: crossed or divergent eyes. The one example measured looks identical to a
straight-ahead gaze under this signal.

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

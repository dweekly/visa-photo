# Visa photo compliance tool — plan

Reviewed once by GPT-6 Astra (high reasoning) on 2026-09-04; findings folded in below.

## Context

On 2026-09-04 we made a portrait visa-compliant for the Chinese online application by hand. The
photo itself was fine — neutral expression, plain wall, frontal. Almost none of the cost was
knowledge of the requirements. The cost was:

- **Measurement by eyeball.** Crown, chin and eye-line positions were read off cropped previews
  with drawn grid lines. The numbers moved as work progressed (crown 450 → 532, chin 2345 → 2367
  in source pixels), and those revisions changed the output geometry.
- **Hand-solved geometry**, re-derived three times after hitting the source image's bottom edge.
- **A skipped check.** Head pose was never measured, only asserted. It happened to be fine
  (pitch −3.2°, yaw 3.4°, roll −0.4°), but the claim preceded the evidence.
- **The wrong channel's constraints.** The crop was built to head height 28–33 mm and head width
  15–22 mm. Those are China's **paper** rules. The **digital** spec states no head-height bound at
  all — it constrains face width, crown gap and eye line. The width-versus-height conflict agonized
  over that day was partly self-inflicted by importing a constraint that does not apply.

That last failure is the thesis. The tool exists to stop a careful operator applying a plausible
rule that the governing document never set.

Scope: engine plus four destination families / six seeded profiles (China, US, Schengen, NZ),
**public** repo, unseeded destinations handled by a documented "fetch the official page, add a
cited entry" workflow.

## Why build rather than extend

From a survey of GitHub topics, PyPI, npm and crates on 2026-09-04: **we did not find a project
combining machine-readable per-country spec data, spec-driven cropping, background replacement,
and per-criterion validation.** Every project found does at most two of four. `dpar39/ppp` has the
only real geometry dataset (499 entries, `faceHeight`/`crownTop`/`officialLinks`) but is GPL-3.0,
last pushed 2024-03, and its `compliance-checks.json` is an empty stub. `HivisionIDPhotos`
(Apache-2.0, 21k stars, active) is an excellent matting engine with a China-centric size table and
no validation. `BlondDev-Art/passport-photo-specs` is MIT but stores requirements as freeform
English prose. `BSI-OFIQ/OFIQ-Project` is the ISO/IEC 29794-5 reference implementation but scores
generic ICAO quality — never "does this satisfy *this* destination's rules" — and does no cropping.
This is a claim about what we surveyed, not a proof that nothing exists.

## Architecture: three layers, no inheritance

**The original "ICAO base plus country overrides" design was wrong and is replaced.** Inheritance
would turn *absence* into a requirement: China's digital spec sets no head-height bound, so
inheriting ICAO's `60% ≤ L/B ≤ 90%` would enforce a rule China never wrote — institutionalizing the
exact error made by hand that day. The same trap applies to unstated pose thresholds, measurement
definitions and age exceptions.

Three separately-evaluated layers:

1. **Destination requirements** — explicit channel rules, plus standards the destination
   *explicitly incorporates* (with edition). A reference to Doc 9303 Part 1 6th ed. does **not**
   automatically pull in a later ICAO technical report. Missing fields stay missing.
2. **ICAO assessment** — an independently versioned reference profile, evaluated and reported
   separately. **ICAO preferences must never make a destination-feasible crop infeasible.**
3. **Crop preferences** — optional composition targets used only where destination rules leave
   freedom (e.g. centering when no band is stated).

Definitions and implementation are shared across layers; requirements are not.

ICAO figures, read directly from the free TR (`pdftotext -layout`), for layer 2 — not for layer 1:
`74% ≤ A/B ≤ 80%`, `45% ≤ Mh/A ≤ 55%`, `30% ≤ Mv/B ≤ 50%`, `50% ≤ W/A ≤ 75%`, `60% ≤ L/B ≤ 90%`
(Table 9); pose requirement pitch/yaw `≤ ±5°`, roll `≤ ±8°`, best practice all `≤ ±5°` (Table 8);
IED `≥ 90 px` required / `≥ 240 px` best practice, stated separately for Electronic Submission
(Table 5); children ≤11 relax L/B to 50–90% and Mv/B to 30–60% (5.5.4).

**ICAO's W and L are anatomical, not silhouette:** `W` is ear-to-ear (feature points 10.2/10.6,
10.1/10.5), *not* the hair outline; `L` runs chin base (2.1) to crown (11.4). China's own diagram
draws head width across the hair. Same word, different physical quantity.

## Spec schema

A `conflicts` list plus a few definition fields is not enough — prose attached to one active bound
still forces the program to silently pick a reading. Instead: **typed measurements referenced by
individual constraints, and alternative interpretations as complete, named rule sets.**

| Concern | Required representation |
|---|---|
| Measurement | endpoints or region; hair/beard inclusion; axis or distance convention; units; denominator |
| Bounds | inclusive/exclusive endpoints; one-sided; equality |
| Missing information | `not_specified`, qualitative-requirement, ambiguous-definition, and explicitly-unrestricted as **four distinct values** |
| Applicability | document, submission channel, portal/provider, jurisdiction, age or stated exception |
| Authority | requirement vs recommendation vs tool preference |
| Evidence | source URL, language, section/page/diagram, quotation, retrieval date, source revision/hash |
| Conflict | competing interpretations, affected constraints, scope, any selected policy |
| Evaluation | pass / fail / indeterminate / not-evaluated / not-applicable, each with a reason |

Consequences that fall out:
- **"Face covers 70–80%" (NZ, EU) must not silently become `head_height / image_height`.** Without a
  stated dimension or area it is not a computable constraint.
- **Distinguish "the source states no numerical pose threshold" from "the source requires frontal
  pose but we cannot certify it."** The second is an outstanding requirement, not an absence.
- **Silence has no quotation.** Record which sources were reviewed and that no rule was found there.
  Never invent a quote, never claim universal absence — write "the reviewed sources state no bound."
- **Never mix readings.** Taking the narrowest width from one interpretation and the resolution
  treatment from another composes a specification nobody published. Evaluate each coherent
  interpretation separately; "satisfies all recorded readings" is a distinct result from "passes",
  and an empty intersection is distinct from failing under every reading.

### Operation policy — per channel, and it can be *prohibited*

**Background replacement cannot be a universal rendering step.** Immigration New Zealand explicitly
prohibits editing that cuts out the head and shoulders and places them on a plain background, and
prohibits AI/digital alteration outright. US passport guidance broadly prohibits digital alteration.
This directly constrains the product — and it is what we did to the 2026-09-04 photo.

Each channel records, for each of `crop`, `resize`, `encode`, `rotate`, `replace_background`,
`adjust_colour`, `synthesize_pixels`: **allowed / prohibited / unresolved.**

- **NZeTA: background replacement disabled.** A bad background means a retake. Segmentation may
  still measure without altering pixels.
- **China digital: `unresolved`** — the MFA sheet says nothing about editing either way.
- Keep an **operation history** in the report. A finished JPEG cannot establish whether its
  background was replaced, whether it is recent, or whether it faithfully depicts the applicant.

## Geometry solver

Unknowns: scale `s`, crop origin `(cx0, cy0)`. Substituting `u = cy0·s` and `v = cx0·s` makes every
constraint linear in `(s, u, v)`.

| Constraint | Form |
|---|---|
| head height band | `Hmin ≤ s·HH ≤ Hmax` |
| head width band | `Wmin ≤ s·HW ≤ Wmax` |
| crown gap | `Gmin ≤ s·crown_y − u ≤ Gmax` |
| eye line from bottom | `Emin ≤ OH − s·eye_y + u ≤ Emax` |
| eye midpoint horizontal | `Xmin ≤ s·eye_x − v ≤ Xmax` |
| source containment | `0 ≤ v ≤ s·W − OW`, `0 ≤ u ≤ s·H − OH` |

**Feasibility is decided exactly, never by sampling.** Dense sampling can miss an arbitrarily narrow
feasible interval and report a conflict that does not exist — the worst failure mode for a tool
whose headline feature is honest conflict reporting. Write every lower bound as `L_i(s)` and every
upper as `U_j(s)`; feasibility is exactly `L_i(s) ≤ U_j(s)` for **every pair** `(i,j)`, each pair a
linear restriction on `s`. Intersect those with the scale bands; do the same horizontally. Attach
source constraint IDs to every derived bound so an infeasibility explanation names the actual
conflicting rules.

**Horizontal centering is a band, not an equality.** The original `cx0 = face_cx − OW/(2s)` falsely
rejects compliant crops. Counterexample: source width 1000, `OW` 600, `s` 1, eye midpoint x 280 —
exact centering demands origin −20 (outside the source), while origin 0 fits and puts the midpoint
at 46.7%, inside ICAO's 45–55%. Centering is a *preference* unless a requirement makes it mandatory.
Also define `face_cx` explicitly: eye midpoint, face-box centre and silhouette centre are three
different quantities.

**Output size is an outer decision.** China permits 354×472 *through* 420×560; failure at one size
must not report failure at all sizes. Solve per permitted size, or per a documented preferred size.
Record China's stated reference size (354×472, given "as an example") and **do not proportionally
scale its pixel figures to other sizes without an explicit, named interpretation policy.**

**Absent and one-sided bounds are first-class.** The solver must not assume two finite scale
intervals exist.

**Slack objective, precisely.** For band `a_i ≤ f_i ≤ b_i`, maximize `t` subject to
`a_i + t·d_i ≤ f_i ≤ b_i − t·d_i` with documented positive normalization `d_i`. Source containment
stays a hard constraint and earns no reward. Optimize `s, u, v` jointly. Deterministic tie-breaking.

**Distinguish failure modes** in the report: source-edge limitation, prohibited padding, insufficient
source resolution, and intrinsically conflicting requirements are four different explanations.

Uniform scaling only; do not round crop edges and resize independently. Apply EXIF orientation
before measurement. Rotation is out of scope for v1 and stated as such.

## Measurement

**The chosen stack does not automatically deliver the required anatomical quantities**, and Stage 1
must prove each one rather than assume it. A person matte merges beard, neck and clothing into one
foreground region — it gives the crown, but it does **not** give a visible beard boundary, and it
does not give ICAO's ear reference points. Deliverable: a **measurement capability matrix** — which
backend supplies each measurement definition, its uncertainty, and when it returns *unavailable*.

Unavailable is an acceptable outcome, with an optional recorded manual override. Guard against zero
or multiple faces, clipped anatomy, segmentation fragments, hair volume, head coverings and low
foreground/background contrast. **A matte touching the source border may mean truncation, not a
measured crown.**

Carry uncertainty into both crop selection and validation. For measurement interval `[m₋, m₊]` and
band `[a, b]`: entirely inside ⇒ passes within stated uncertainty; disjoint ⇒ fails; straddling a
boundary ⇒ **indeterminate**. Model detection confidence is not a calibrated error interval in
pixels or degrees and must not be used as one.

## Model selection

Landmarks: **MediaPipe Face Landmarker** — Apache-2.0 code *and* weights, the latter stated on
Google's FaceMesh V2 and BlazeFace model cards rather than inferred. Backup: **OpenSeeFace**
(BSD 2-clause explicitly covering models; 66 points with jaw contour; onnxruntime CPU; ship its
`Licenses` folder).

Segmentation: **BiRefNet via rembg** — rembg MIT, BiRefNet weights MIT on the model card. **Always
pin the model explicitly**: rembg's current default is BRIA RMBG-2.0, which requires a paid
commercial agreement. Backup MODNet (Apache-2.0 covering "code, models, and demos").

Rejected, and why, so nobody re-proposes them:
- **InsightFace `buffalo_l`** — what we validated on 2026-09-04. MIT code, but models are
  "non-commercial research purposes only" (stated three times, including for auto-downloaded
  weights). Incompatible with this project's redistribution and commercial-use requirements.
- **dlib 68-landmark** — iBUG 300-W annotations forbid commercial use and the author states the
  restriction reaches the trained model.
- **3DDFA_V2, SynergyNet, PIPNet, 6DRepNet, Hopenet, FSA-Net** — permissive code, **no weights
  license at all**; most trained on 300W-LP. Whether training-data terms propagate to weights is
  unsettled law; the practical problem is simply that there is no grant to rely on.
- **YuNet + `solvePnP` as a pose verdict** — published MAE for landmark→PnP pipelines is 7.4–15.8°
  (Ruiz et al. CVPRW 2018) against tolerances of ±20°/±25°. Advisory only. Note in
  `NEGATIVE_RESULTS.md` that those are benchmark MAEs, *not* per-image uncertainty bounds and not
  measurements of our configuration.

Empirical, 2026-09-04: `u2net` and `isnet-general-use` erased a light tweed jacket leaving a
ghost-white torso; `birefnet-general` retained it. `alpha_matting=True` degraded the matte. Avoid
`isnet-general-use` regardless — its Apache-2.0 covers "code and evaluation metric", not weights.

**Pose needs its own acceptance gate.** MediaPipe documents its transformation matrix as a
canonical-face-to-detected-face transform for applying effects; that does not establish angular
accuracy near a ±5° threshold. Specify coordinate handedness, matrix direction, scale removal and
Euler convention, then test against known angles near the actual thresholds at representative
resolution and framing. **Until that gate passes, pose is advisory or indeterminate for both primary
and backup engines.** Preserve ambiguous source wording — China's "≤20° for left or right tilt (Yaw
and Roll)" lumps two axes under one phrase; do not silently assign it.

## Validation

**A geometry-only validator cannot emit an unqualified compliance verdict.** Expression, eyes open,
shadows and sharpness are real requirements v1 defers; photo age cannot be established from pixels
at all. Report per-criterion outcomes with reasons plus an aggregate of `fails`,
`passes_implemented_checks`, or `incomplete` — distinguishing unmet requirements, unimplemented
checks, ambiguous sources, unavailable measurements, and required user attestations.

Reopening the written file is necessary but does **not** make validation independent: the same
systematic landmark error can drive both the crop and its apparent validation. Compare transformed
source measurements against fresh output measurements to detect instability, and use independently
annotated fixtures to assess accuracy.

Preserve source-resolution provenance — upscaling raises pixel IED without adding facial detail.
Only call a best-practice limitation inherent to a format after showing it cannot be met across the
feasible crop and output choices.

## Encoding

A byte band alone permits visibly poor output and may be unreachable at acceptable quality. Specify
supported encodings, colour conversion (US visa requires 24-bit sRGB and recommends ≤20:1
compression), quality limits, and a finite candidate search. Measure the final file *after* metadata
handling; normalize orientation metadata in the output. If no allowed candidate satisfies the
requirements, **report that** rather than degrading quality indefinitely or padding to reach a floor.

## Staging

- **Stage 0 — spike: does MediaPipe run?** On 2026-09-04 MediaPipe 1.0.1 aborted twice during graph
  setup (`absl` `LOG(FATAL)` in `-[DrishtiMetalHelper initWithCalculatorContext:]` from
  `TensorsToDetectionsCalculator::Open`; `Delegate.CPU` did not avoid it). That was on **Python
  3.14, which the vendor does not support** — classifiers list 3.9–3.12, and the wheel is
  `py3-none-macosx_11_0_arm64` with no `Requires-Python` gate, so pip installed it anyway. The crash
  is in the bundled dylib via ctypes, where Python version *should* be irrelevant — but that is
  reasoning, not evidence. Test on 3.12 in a clean venv and on Linux (trogdor). No matching issue
  exists upstream; if it reproduces on a supported Python, file it. **Exit criterion:** MediaPipe
  works ⇒ primary; otherwise OpenSeeFace with pose limits documented. This spike stays in the repo
  as a reproducible diagnostic.
- **Stage 1 — measurement + capability matrix**, with a minimal CLI brought forward so end-to-end
  verification starts here rather than at the end.
- **Stage 2 — schema and solver** (exact feasibility; interpretation rule sets; operation policy).
- **Stage 3 — render and encode** (honouring per-channel operation policy).
- **Stage 4 — validator and report contract.**
- **Stage 5 — seeded profiles and docs.**

## Verification

Four separate contracts, not one round-trip:

1. **Exact solver tests** on supplied deterministic measurements — including a narrow/singleton
   feasible interval, a source-edge solution, the horizontal-centering counterexample above, missing
   bounds, conflicting interpretations, and unsupported definitions.
2. **Measurement tests** against independently annotated points with justified tolerances, plus
   no-face and multi-face cases.
3. **End-to-end CLI tests** asserting output geometry, encoding and report contents.
4. **A historical comparison** against the 2026-09-04 photo that *explains* differences rather than
   requiring the old crop. An optimizer maximizing slack has no reason to reproduce a hand-built
   crop, and that crop was built against the wrong channel — its face width landed at 219 px, the
   exact top edge of the 191–219 band, and short of it entirely if the pixel figures scale with
   output size. The corrected 354×472 crop (scale ≈0.1934, face width ≈205 px, crown gap ≈40 px,
   eye line ≈281 px from bottom, IED ≈95 px) satisfies China's digital rules and every ICAO ratio,
   and is the reference point.

**Every negative fixture must assert its specific criterion and reason.** A non-zero exit could just
mean the process crashed. A patterned-background fixture must return *not assessed* in v1, never an
overall pass, because no background check is implemented yet.

**The real personal photo stays out of the public repository** unless its publication is explicitly
authorized; public CI needs redistributable fixtures. The ONOT synthetic ICAO-compliant mugshot
dataset is a candidate source.

## Repo

New public repo under `dweekly/`, MIT. `README.md` (plain English first), `CHANGELOG.md`,
`ROADMAP.md`, `NEGATIVE_RESULTS.md`, `THIRD_PARTY_LICENSES`. Worktree with a tracking PR from the
first commit.

**Reproducibility policy** (replacing a blanket "no pinned versions"): evidence-based dependency
constraints, a reproducible dev/test lock, **model artifacts pinned by immutable revision and
checksum**, and the exact model and spec versions recorded in every report. Selecting
`birefnet-general` by name does not reproduce a future measurement.

**Privacy, made testable:** separate model installation and official-page fetching from photo
processing; processing works offline after install; no telemetry; strip unnecessary sensitive
metadata; never include portraits in crash reports or upstream issues by default.

`NEGATIVE_RESULTS.md` seeds with: the MediaPipe abort signature and its conditions; InsightFace's
non-commercial weights; the u2net/isnet jacket erasure; `alpha_matting=True` degrading the matte;
solvePnP's benchmark MAEs with the caveat above; and the wrong-channel error of 2026-09-04.

## Seeded profiles

`cn_visa_digital`, `cn_visa_paper`, `us_visa_digital`, `us_passport_print`, `schengen_icao_base`,
`nz_nzeta` — four destination families, six profiles. Every constraint carries verbatim quote,
source URL, language, and retrieval date.

Recorded conflicts, all from official sources: China's crown gap 10–70 px (text) vs 10–85 px
(diagram); China's face width 205±14 px (text) vs 191–251 px (diagram); MFA's 420×560 max vs CVASC's
"cannot exceed 354*472"; US visa overview 22–35 mm vs State's own template 25–35 mm (22 mm is
arithmetically wrong for one inch); NZ 512 KB–3.14 MB vs 500 KB–3 MB on two other INZ pages;
**France's English FAQ saying chin-to-forehead while its French FAQ says chin-to-top-of-skull
excluding hair** — a language conflict to retain, not resolve, and not to be promoted into a settled
"EU" anatomical definition.

Schengen has **no EU-level numeric spec**: Visa Code Art. 13(4) defers to ICAO Doc 9303 Part 1
6th ed.; the Commission's guidance sheet gives width 35–40 mm and "face 70–80%" and nothing else.
(Its PDF metadata shows a 2003 QuarkXPress file authored for what appears to be the UK Passport
Service.) The widely quoted "35×45 mm, 600×750 px, 300 DPI" figure set is unsupported by any EU
source. Member-state guidance ships as clearly-labelled optional overlays.

## Explicitly out of scope for v1

OFIQ integration (right long-term answer for quality scoring; C++ dependency, and its GitHub license
shows `NOASSERTION` while BSI's deck claims a liberal one — **verify before depending on it**);
broad demographic accuracy evaluation beyond a small varied validation set; advanced anatomy
estimation and guided capture; automated monitoring of official sources; print-production assurance
beyond exporting an intended size; GPU tuning and a broad platform matrix.

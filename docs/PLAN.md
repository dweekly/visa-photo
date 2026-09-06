# Visa photo compliance tool — plan

Reviewed once by GPT-6 Astra (high reasoning) on 2026-09-04; findings folded in below.
Revised 2026-09-06 after Stage 1 merged: the Measurement section is rewritten around a
precondition-driven design (a different approach, not a tweak), Stage 1b added to implement it,
Calibration and Review-discipline sections added. Second review taken on that revision only.

Current state: Stage 1 merged (`c15c3cc`). Stage 2 built on PR #2, awaiting rebase and review.
Next: Stage 2 lands, then Stage 1b.

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

Revised 2026-09-06 after Stage 1 shipped and review found the same defect six times.

### The invariant

**A measurement is unavailable unless every precondition it declares is affirmatively
satisfied.** Not "available unless a guard fires" — the inverse. Guards enumerated one at a time
can never be complete, and Stage 1 proved it: each guard added created a new bypass, and after
six passes three instances of the class were still live (a hair tuft touching the top edge still
yields `crown_y = 0` as *measured*; a gimbal-locked pose fabricates `roll = 0.0` as available;
face-component isolation has five silent fallbacks where it quietly does not happen).

The earlier version of this section listed the failures to guard against — segmentation
fragments, clipped anatomy, matte touching the border — and named a capability matrix as a
deliverable. It was correct and it changed nothing, because prose in a plan does not bind code.
The correction is structural:

1. **The registry is the only way to construct a measurement.** A registry maps each measurement
   name to its required gate ids. Emitters supply a *name and a candidate value*; the
   construction path looks up the required ids itself, resolves each against the frozen gate
   record, and decides the status. Emitters never assemble their own evidence. Construction
   rejects an unknown name, an empty requirement set, or a gate id the record does not contain.
   This is the difference between enforcing *consistency* (measurement matches registry — which
   both can get wrong together) and enforcing *completeness*.
2. **`Precondition` is tri-state and the invariant survives construction.** `satisfied` is
   exactly `True` / `False` / `None` (not evaluated), checked by identity, not truthiness.
   `Precondition` and `Measurement` are frozen; the set's storage is private; every input —
   automatic, deserialized, or manual — enters through the same validating boundary. `AVAILABLE`
   additionally requires a present, finite value: all-true gates cannot legitimize `NaN`.
3. **Reasons are structured first, prose second.** An unavailable measurement records *every*
   gate that was `False` and every gate that was `None`, each with its own cause chain — not the
   first blocker, and never an unevaluated condition described as a demonstrated failure. Prose
   is rendered from that record. This ends the current situation where two different failures
   share one reason string, one of them false.
4. **The capability matrix is generated**, by `visa-photo --capabilities`, which must work with no
   model weights installed. Per measurement: definition, unit, backend and method, heuristic
   status, required gates, gates that are *always* `None` in this build, and whether manual
   evidence can supply them — so permanent limits are visible before anyone processes a photo.
   Per image, the JSON report carries every gate's evaluation.
5. **`MeasurementSet.add` refuses a second write to the same name.** The truncated-crown bug was
   an unavailable value overwritten by an available one; the class is closed at the container.
6. **Execution status is separate from gate truth.** `NOT_ATTEMPTED` covers "chose not to look"
   (`--no-segmentation`). A measurement that *was* attempted but blocked because an upstream
   stage was disabled is `UNAVAILABLE` with that cause. "Disabled", "blocked upstream", and
   "evaluation failed" all leave a gate `None` for different, recorded reasons.
7. **Tests check completeness in both directions.** For each run configuration — normal,
   `--no-segmentation`, no face, several faces, model failure — a test asserts the *complete*
   expected set of measurement names. "Every emitted measurement matches the registry" still
   passes when the emitter emits nothing. Alongside registry-driven tests, hand-written semantic
   tests state anatomy dependencies directly ("obscured eyes block all three iris measurements"),
   so a registry omission is not reproduced into the test suite.

### Three passes, because ordering was the structural cause

Pose and eye-occlusion are preconditions for the geometry, and today they are computed *after* the
geometry in the same pass. The information existed and arrived too late — which is why no amount of
guard-adding converged. `measure()` becomes:

- **Fit.** Run the landmarker and the segmenter. Raw outputs only; nothing is emitted.
- **Gates.** Evaluate gate facts into one record, then freeze it. Gate evaluators read raw fit
  outputs and other gates only — never emitted measurements — and Emit never computes or revises
  a gate.
- **Emit.** Each measurement looks up its required gates and is available only if all are `True`.

**The gates form an explicit acyclic graph, evaluated topologically.** Three passes remove late
emission but not dependencies *among* gates, and one cycle is concrete: occlusion is assessed from
eye patches; the patches are sized by eye separation; public IED requires occlusion to be ruled
out. The graph that breaks it:

    raw landmark candidates → diagnostic patches → occlusion assessment → public iris measurements

The *raw* eye separation used to size the patches has weaker, explicit prerequisites than
anatomical IED. It is a diagnostic candidate, recorded as such, and it never escapes as an
available `inter_eye_distance`.

**A negative detector result is not affirmative evidence.** This is the principal remaining route
to "available under an unmet precondition." `eyes_not_obscured` is `True` only when the patches
extracted, the denominator is valid, and the heuristic ran and passed; if any input is unusable it
is `None`, with the cause. `not sunglasses_detected` is not `eyes_not_obscured`. The same rule
applies to every gate: each records its own prerequisites and evidence method, and an unknown
prerequisite propagates as unknown. The constructor guarantees faithful use of recorded evidence;
it cannot make a fallible detector's assertion physically true, and the report says which it is.

**Gates are named for what they establish, not for what they might authorize.**
`transformation_matrix_present` becomes `pose_decomposition_valid`: finite values, expected shape,
nonsingular within a stated tolerance, decomposition succeeded. An undefined yaw never becomes
zero and unlocks a width. `face_component_isolated` establishes which matte component was
selected — not that segmentation retained a clipped tuft; that distinction between matte geometry
and anatomy is carried into the tiers below. Face count is a *detection assessment*: MediaPipe's
`num_faces` is a maximum, so it is configured well above one (four), and "one face" means one
face found in a search permitted to find several.

Which pose axis gates which measurement is stated per measurement: horizontal projections (IED,
head widths) are gated on yaw and roll; image-vertical distances (crown–chin, eye line) on pitch.
Rotation being out of scope for rendering does not settle these definitions. The ±15° limit is a
heuristic *operating condition* for measurement, documented in `thresholds.py`; a destination's
legal pose tolerance is assessed separately and stays indeterminate until the pose acceptance
gate passes.

### Consequences that are new rules, not guards

- **Iris-derived measurements require unobscured, open eyes.** Behind mirrored lenses the iris
  landmarks are fabricated (the gaze probe showed `eyeLookDown` 0.47 on a sunglasses photo). So
  `eye_line_y`, `eye_mid_x` and `inter_eye_distance` become unavailable on such a photo, and the
  report says *IED not measurable: eyes obscured* rather than printing a number.
- **Projected horizontal distances require yaw within a measurement-validity limit.** IED and
  both head widths shrink as `cos(yaw)`; at 30° they are understated by 13%. The limit is a
  documented heuristic in `thresholds.py` (initially ±15°, where the foreshortening is 3.4%),
  distinct from any destination's *legal* pose tolerance. Gating errs toward unavailable; we do not
  *correct* by an uncalibrated angle.
- **The brightness-ratio denominator is redefined.** The inventory found the "cheek" patch's
  x-range runs *between* the eyes: the denominator is the nose bridge and philtrum, nostrils
  included. It separated the calibration photos anyway, but the definition is wrong, and it is
  exactly where a skin-tone bias would hide. New definition: two patches lateral to and below
  each eye, on cheek proper. This changes the measured values, so the eleven-photo calibration
  table is re-derived, not carried over.
- **Every landmark-derived value requires its landmarks inside the frame.** MediaPipe extrapolates
  outside the image without complaint; today a chin below the bottom edge is reported measured.
  This is the bottom-edge twin of the crown truncation guard, and it was missing.

Unavailable remains an acceptable outcome, with an optional recorded manual override. Uncertainty
handling is unchanged: for a measurement interval `[m₋, m₊]` and band `[a, b]`, inside ⇒ passes,
disjoint ⇒ fails, straddling ⇒ **indeterminate**; model confidence is not a calibrated interval.

### Observed quantities and anatomical claims are different tiers

Some preconditions are permanently `None` in this build: the crown is not under headwear; the
cheek patch landed on skin; the chin landmark is the anatomical chin on a bearded face. If those
gate the measurements the solver needs, the reference photo — every photo — has no available
crown, and the positive regressions cannot exist. That is resolved explicitly rather than by
quietly marking the unknowns true:

- **Observed tier** — named for what was actually observed: `matte_top_row`, `chin_landmark_y`,
  `eye_line_y`, `patch_brightness_ratio`. Gated on *observation validity* (in frame, single face,
  component isolated, decomposition valid, eyes unobscured). Available on a good photo.
- **Anatomical tier** — `anatomical_crown_y`, `anatomical_chin_y`. Additionally gated on the
  permanently-unknown conditions, so unavailable unless recorded, image-specific human evidence
  supplies them. A manual override is separate provenance producing a *new* resolved result; it
  never relabels the automatic observation as measured.

Profiles bind to the observed tier and state the definition — which is honest about what China's
diagram actually measures (the top of the matte, hair included). The report shows both tiers, so
the gap between "where the mesh put vertex 152" and "the chin" is visible instead of hidden.
Derived measurements keep their dependencies: `head_height` cannot be available from an available
crown and an unavailable chin. A missing sharpness measure blocks a *sharpness* criterion, not
every geometry measurement.

### Stage 2 already consumes measurements, so it joins the invariant now

The solver lands first, and `MeasurementSet.value()` currently returns a number for any available
measurement and `None` otherwise. Acceptance condition for 1b: an unavailable or not-attempted
measurement cannot be consumed through `.value`, a default, a cached report, or a raw diagnostic
field. When a profile rule's measurement is unavailable, the plan reports *cannot solve with the
available measurements* naming the rule — not "requirements conflict", and never a solve with the
rule silently dropped. One solver/CLI test proves it.

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
- ~~**Stage 1 — measurement**~~ Merged 2026-09-06 (PR #1, `c15c3cc`). Shipped without the
  capability matrix this plan required; see the Measurement section for what that cost.
- **Stage 2 — schema and solver.** Built on `stage2-solver` (PR #2, draft, +1130). Exact interval
  feasibility, China digital and paper profiles, `--spec` CLI. Independently reproduced the
  hand-built crop to 0.14%. Needs: retarget to `main`, rebase, one review under the two-pass rule,
  merge. Lands **before** Stage 1b so 1b branches from the fuller base; the only overlap is
  `cli.py`, which is small.
- **Stage 1b — precondition-driven measurement.** The rework described under Measurement. Own
  branch off `main` after Stage 2 merges; own PR; own plan file `docs/STAGE1B-PRECONDITIONS.md`
  committed before code. Scope is exactly: `Precondition` + registry + constructor invariant;
  three-pass `measure()`; `NOT_ATTEMPTED`; `add()` refusing double writes; the seven inventory
  fixes (top-edge tuft, gimbal roll, mis-attributed reason, eye-patch bottom bound, silent
  isolation fallbacks, landmark-in-frame, `--no-segmentation` absence); the acyclic gate graph;
  yaw/roll and eye-occlusion as gates; observed and anatomical tiers; the Stage 2 consumer
  refusal; cheek patch definition finished, then re-derived; `--capabilities` output. **Not** in
  scope: any new detector, gaze, a second calibration subject, or report versioning (Stage 4).
- **Stage 3 — render and encode**, honouring per-channel operation policy. Rendering operations
  declare preconditions the same way measurements do — background replacement requires the
  policy to allow it *and* the matte to have isolated the face — so the class fixed in 1b does not
  reappear here.
- **Stage 4 — validator and report contract.** Same rule: a criterion's verdict is `not_evaluated`
  unless its inputs' preconditions held.
- **Stage 5 — seeded profiles, docs, skill.** Load `plugin-dev:skill-development` and
  `plugin-dev:plugin-structure` before writing `SKILL.md`; run `plugin-dev:skill-reviewer` over it.

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

### Stage 1b verification

Every test below drives `measure()` end to end with the model calls stubbed — never the helper —
because the pass-3 finding was a fix that existed only in a helper the production path never
called.

- Registry completeness: every registry entry declares ≥1 precondition; every emitted
  `Measurement` carries exactly the registry's set for its name. Fails on any drift.
- Constructor invariant: `AVAILABLE` with any precondition `False` or `None` raises.
- `add()` raises on a second write to the same name.
- One reproduction per inventory bug, each through `measure()`: a narrow tuft touching the top
  edge ⇒ `crown_y` unavailable, precondition `matte_clear_of_top_edge`; a gimbal-locked matrix ⇒
  `pose_roll` unavailable, `not_gimbal_locked`; IED of 2 px ⇒ eye patches unavailable with
  `ied_sufficient_for_patch`, *not* "outside the image"; eye patch off the bottom edge ⇒
  unavailable; eye pixel on matte background ⇒ `face_component_isolated` false and both matte
  measurements unavailable; chin below the frame ⇒ `chin_y_landmark` unavailable.
- Gates on the posed set, via the checked-in measurements: 8847 (yaw 35°) ⇒ IED and both head
  widths unavailable naming `yaw_within_measurement_limit`; 8850 (12°) ⇒ available. 8853 (mirrored
  shades) ⇒ iris-derived measurements unavailable naming `eyes_not_obscured`; 8864 (shades on
  head) ⇒ available.
- Regression: the reference photo still measures crown 493, eye line 1320, IED 495, width 1086.
- The cheek-patch recalibration re-derives the eleven brightness ratios and *reports whether a
  usable separation remains*. If it does not, the test asserts the gate is `None` — never a
  threshold tuned until eleven examples separate.
- `visa-photo --capabilities` output is asserted against the registry, so the matrix cannot
  drift from the code that enforces it, and it runs with no weights installed.
- **Discriminating regressions.** Each inventory reproduction asserts the target gate's exact
  evaluation and reason chain, *and* a paired case with the defect removed that yields the
  measurement — supplying explicit evidence for unrelated `None` gates where an available result
  is needed. A tuft test that "passes" because every crown is already blocked by an unknown gate
  has shown nothing. All five isolation fallbacks are covered, each eye separately, missing
  blendshapes, non-finite matrices, and yaw at both signs of the limit.
- **Both non-success states per gate.** For every required gate, `False` and `None` are each
  exercised and every dependent measurement asserted unavailable.
- **Three kinds of test, kept distinct.** Stubbed raw model outputs prove the production gates are
  called and propagated (wiring). The four reference numbers are regression targets, not
  anatomical ground truth (numerical). Empirical accuracy is the calibration stage's job. Enough
  raw output is retained to recompute the cheek patches; old final JSON cannot establish the new
  gate computation.
- **Downstream refusal.** One solver/CLI test proves an unavailable measurement stays unusable:
  the plan reports *cannot solve with available measurements* naming the rule.
- Coordinates are EXIF-normalized before any bound check, clip, or integer conversion, and each
  gate record is bound to its image and run so evidence cannot be reused across photos.

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

## Calibration beyond one subject

Every threshold is calibrated on one adult male with a beard and light skin. The signal most at
risk is the eye-region brightness ratio: its denominator is skin luminance, which varies strongly
with skin tone, while sclera brightness varies much less — so the ratio is predicted to run
*higher* on darker skin, making sunglasses *less* likely to be flagged. That fails in the unsafe
direction, and it is a testable prediction, not a worry.

Surveyed 2026-09-06. Use in this order:

1. **MST-E** (Google/TONL) — 19 consented subjects spanning the full Monk scale, each shot under
   varied lighting and pose, which is the confound to separate — verify the actual crossing of
   lighting, pose and accessories in the supplied images before calling the factors independent.
   Direct download. Its grant is **research or human-annotator-training use, ML training
   prohibited** — record that exact grant, not "CC BY" inherited from the scale. Running a fixed
   algorithm to characterize a bias is research evaluation; tuning a shipped threshold on it is a
   further question, stated in the fixture README rather than assumed. Nineteen subjects is a
   *pilot*: enough to expose a large monotonic trend, not to bound subgroup error. Analyse at
   subject level (repeated photos are within-person variation, not more people), inspect within
   lighting condition, split development and evaluation by subject, and allow "inconclusive".
2. **Chicago Face Database** — studio, frontal, neutral, uniform background, 2444×1718: the
   closest public analogue to a passport photo, across self-identified race and gender, with a
   *measured median face luminance* per subject to regress the cheek term against. Happy-
   expression subsets calibrate the smile flag. Licence forbids publishing "materials" and
   facial-recognition use; derived scalars are neither, but **get that in writing from the
   Center for Decision Research before committing fixtures**.
3. **ONOT** — ~960k synthetic ICAO-compliant mugshots, CC BY-NC. Geometry regression only. It is
   compliant by construction, so it contains none of the failure modes, and generative models are
   documented to lighten non-white skin, so it must not calibrate any brightness or glare
   threshold.

Do not use: CelebA (its licence attaches non-commercial terms to *derived data* by name);
BUPT-Balancedface and DiveFace (built on retracted MS-Celeb-1M and MegaFace); UTKFace, LFW, FFHQ,
CASIA-WebFace (scraped without consent — indefensible for a tool that handles identity photos).

**We have not identified a dataset** with consented, passport-framed photographs across skin tones
in the *matched* conditions — sunglasses on and off, glare and no glare, eyes shadowed, eyes closed.
MST-E is described as including glasses and masks, so inventory it before asserting absence. Those
matched conditions are exactly the advisory thresholds that most need demographic validation, and
the answer is 15–25 consenting volunteers spanning the Monk scale, same phone, same lighting, the
same posed set already shot once. Consent is tiered to the artefact: local evaluation, public
scalar fixtures, public portraits, and commercial reuse are separate permissions, and taking part
never silently implies the later ones.

**Calibration includes the abstentions.** Measuring the ratio only where 1b declares it available
would remove the very sunglasses-on-dark-skin failures under investigation. Record numerator,
denominator, patch locations, human patch-validity labels, and every gate failure; report
availability alongside false flags and missed occlusions; analyse the eye and cheek terms
*separately* — a sunglasses patch measures lenses and reflections, so the direction-of-error
hypothesis is conditional on numerator behaviour, not settled by sclera brightness. Regressing the
ratio against a quantity close to its own denominator (CFD's face luminance) shows association, not
mechanism.

**The cheek-patch definition is finished before recalibration begins**: landmark anchors, offsets,
dimensions, clipping policy, per-eye treatment, aggregation, colour space, luminance computation,
minimum usable denominator. Each eye satisfies its own visibility condition; averaging must not let
one clear eye hide the other's failure. The recalibration then *reports whether a usable separation
remains*. A more defensible definition is allowed to invalidate the old heuristic; if it does, the
gate stays `None` rather than being tuned until eleven examples separate.

Fixtures derived from restricted sources keep *that source's* actual terms, not a blanket CC BY-NC,
and live in an optional evaluation separate from the default, commercially-usable test suite.

Related prior work: Kabbani et al., *Demographic Variability in Face Image Quality Measures*
(arXiv 2501.07898), evaluated the ISO/IEC 29794-5 measures across skin tone and found material
variation in two — **dynamic range and luminance mean**. That supports investigating a luminance
ratio; it does not test our ratio or the sunglasses false-negative direction, which remain to be
established. Their method also discards images where no face is detected, which our availability
reporting must not.

This is a stage of its own after 1b, not part of it.

## Review discipline, as actually applied to Stage 1

Recorded because it is the second failure of that stage and it is not in the working rules'
vocabulary yet.

The rule is two passes, with pass two as the decision. Stage 1 ran six, with the cap overridden
twice. The tell was visible by pass two and was misread as progress: **every finding after pass
one was the same class** — a value reported as measured under an unmet precondition — in a new
location each time. A repeated *class* of finding is the signal that the design is wrong; fixing
the instances is what keeps the loop alive. The wrapper's three-pass cap is the backstop for
exactly that judgement, and it fired, and it was overridden. Next time the backstop fires, the
answer is the reflection above, not `--override-cap`.

Two mechanisms follow, one in this repo and one not:

- In this repo, the registry test under Measurement turns the design lesson into something that
  fails at commit time rather than at review time.
- The process lesson cannot be mechanized here; it lives in the wrapper's cap, which already
  exists. The commitment is to lean on it.

## Explicitly out of scope for v1

OFIQ integration (right long-term answer for quality scoring; C++ dependency, and its GitHub license
shows `NOASSERTION` while BSI's deck claims a liberal one — **verify before depending on it**);
broad demographic accuracy evaluation beyond a small varied validation set; advanced anatomy
estimation and guided capture; automated monitoring of official sources; print-production assurance
beyond exporting an intended size; GPU tuning and a broad platform matrix.

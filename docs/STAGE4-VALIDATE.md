# Stage 4 — validate the written file, and the report contract

Working plan for the stage. The *why* behind per-criterion verdicts and the limits of a
geometry-only validator is in [PLAN.md](PLAN.md) → Validation; not repeated here. Fresh as of
2026-09-06.

**Where:** worktree `~/dev/visa-photo-validate`, branch `stage4-validate` off `main`, tracking PR
#6 opened with this commit. Reviewed once by Codex (GPT-6 Astra, high reasoning) on 2026-09-06
against this worktree; its ten failure findings are folded in below, each marked *(review)*, with
two adjustments under Declined.

## Why

Stage 3 writes a file and records what it did to the pixels. Nothing yet says whether the file
*satisfies the rules*. The solver's plan predicted it would — from measurements of the source —
and the written file is a different image: colour-converted, resampled, JPEG-encoded, and measured
again by the same model at a different scale. Two things can go wrong that the plan cannot see:
a landmark or matte edge moves under resampling, and a verdict gets claimed from a measurement
whose preconditions did not hold on the output. Both are the class Stage 1b closed for
measurement, reappearing at the last step.

The second reason is an applicant who already has a photograph and wants to know whether it
passes, without cropping it. The same validator answers that.

## What must be true

1. **The written file is validated, from the file.** After `--out`, the file is reopened,
   measured through Stage 1b, and each of the profile's rules gets a verdict from the *output's
   own* measurements — `pass`, `fail`, `indeterminate`, or `not_evaluated` — with the observed
   value, the prediction where there is one, the bound, and the reason. *Check:* end to end
   from a photo on disk with only the fits stubbed, the stubs answering to the image they are
   handed so source and output fits differ; the reference photo's actual outcomes recorded in
   the PR — investigated if unexpected, never tuned to a pass.
2. **A file you already have can be checked.** `visa-photo FILE --spec cn_visa_digital --validate`
   checks the file as-is against the profile at the file's own size; no crop is planned.
   *Check:* the file written in (1), fed back with `--validate`, gives identical observed
   quantities, bounds and encoding verdicts; geometric verdicts are identical for that
   comfortably-interior fixture, and a deliberate near-bound case shows where the two paths
   differ (see 4). A 600×800 photograph fails dimensions.
3. **A rule's quantity has one definition, and only rules get verdicts.** *(review)* The
   validator evaluates the constraints `build_constraints` builds for the profile's *rules* —
   selected by membership in `profile.rules`, never the source-containment constraints or the
   `eye_centred` preference — at the identity transform (`value(1, 0, 0)`) on the output's
   measurements; the plan's prediction for the same rule is the same constraint at the plan's
   transform on the source's measurements. *Check:* exactly one rule criterion per profile
   rule, none for containment or preferences; the observed quantity equals the constraint's
   value at identity.
4. **Uncertainty is stated, not invented — and its consequence is stated too.** *(review)*
   When a render preceded validation, `delta = observed − predicted` is recorded per rule and
   the verdict is taken on the interval `[x − |delta|, x + |delta|]`: inside the band ⇒
   `pass`, disjoint ⇒ `fail`, straddling ⇒ `indeterminate`. Because a feasible plan's
   prediction satisfies the band and the interval always contains it, a post-write geometric
   disagreement of any size is `indeterminate`, never `fail`; the report shows both numbers so
   the reader can see which. The delta is one model's disagreement with itself at two scales —
   self-consistency, not accuracy — and the report says so. Standalone `--validate` has no
   prediction: verdicts are point comparisons and the report says "no uncertainty interval".
   *Check:* value 69.5 against `[10, 70]`: prediction 68.5 ⇒ `indeterminate`; prediction 69.4
   ⇒ `pass`; no prediction ⇒ `pass`. Prediction 40, observation 120 ⇒ `indeterminate`.
5. **Strict bounds are strict.** *(review)* China's sheet says inter-eye distance "> 60 pixels"
   and eye line "> 256 pixels"; the rule and constraint schema record inclusivity, the
   validator fails a value equal to an exclusive bound, and the solver refuses a solution whose
   only feasible point sits on one. No pixel tolerance is added to approximate ">". *Check:*
   equality on each strict bound fails; 60.01 passes; an interval touching an exclusive
   endpoint is `indeterminate`.
6. **Encoding is checked from the file, in the file's own frame.** *(review)* Format, mode, bits
   per channel and *stored* dimensions are read from the file before any conversion; the
   orientation-normalized dimensions measurement used are recorded beside them, and when the
   two differ the dimensions criterion is `indeterminate` — which one the portal checks is not
   established. Dimensions are checked against the profile's listed sizes. Size in bytes is
   checked against *both* readings of KB, stored as named bands on the profile (decimal
   40,000–120,000; binary 40,960–122,880) from which the encoder's intersection is derived:
   both ⇒ `pass`, one ⇒ `indeterminate` naming the readings, neither ⇒ `fail`. *Check:*
   40,500, 41,000, 121,000 and 39,000 bytes and the exact endpoints; a PNG; a greyscale JPEG
   (fails 24-bit RGB); an EXIF-rotated JPEG (dimensions `indeterminate`).
7. **The listed sizes and the sizes pixel rules apply at are different sets.** *(review)*
   354×472: dimensions pass, pixel rules evaluated. 420×560: dimensions pass, pixel rules
   `not_evaluated` — "stated at 354×472 as an example and not scaled" — and the aggregate is
   `incomplete` when encoding passes. 600×800: dimensions fail, pixel rules `not_evaluated`.
   Reference-size refusal never loses the encoding results. *Check:* one test per size.
8. **An unavailable measurement is `not_evaluated` with its own reason chain.** *(review)* The
   rule's measurement is looked up on the output's set; its status (`unavailable`,
   `not_attempted`), failed gates and unknown gates are the criterion's detail. *Check:* a
   fixture where the source gate passes and the output gate fails (the output matte touching
   the top edge): observed value null, the output's specific blocker named.
9. **`--spec` selects the destination's advisories.** *(review)* A profile names its jurisdiction;
   `--spec cn_visa_digital` runs China's preflight without `--for`, and a conflicting `--for`
   is a usage error. Attestations are built from the applicable requirements (recency, and
   head coverings conditionally, for China); the profile's operation policies are reported as
   declarations, without implying a finished file proves its editing history. The output's
   preflight is the one `measure_photo` returns for it, never a second run. *Check:* the
   validation's preflight mode is `jurisdiction`/`CN`; `--for NZ --spec cn_visa_digital` is
   refused.
10. **The aggregate covers implemented checks and never reads as "compliant".** `fails` when any
    rule or encoding criterion fails; otherwise `incomplete` when any is `indeterminate` or
    `not_evaluated`; otherwise `passes_implemented_checks`. Advisory outcomes, the attestations
    still required, and the requirements this build cannot assess (background, borders,
    sharpness, exposure, skin tone — each `not_evaluated` with that reason) are listed beside
    it, outside the reduction, so `passes_implemented_checks` is reachable and honest.
    *Check:* one test per aggregate value.
11. **The report has a contract, and the input keeps its place.** *(review)* Top level, for
    every photo run (not `--capabilities`): `report_version` (1), `tool` (`version`,
    `backends`), `error` (null unless a stage could not run), then `measurements`, `preflight`,
    `plan`, `render`, `encode`, `validation` — each present, null when unreached, all but
    `validation` describing the *input*. `validation` holds the validated file's path and
    facts, the profile key, its own `measurements` and `preflight`, `criteria`, `aggregate`,
    `attestations`, `not_assessable`, and `uncertainty` ("delta" or "none"). Under `--json`,
    an input that cannot be decoded still emits the envelope with `error` set. *Check:* the key
    set; `plan`/`render`/`encode` null under `--validate`; source and output measurements
    distinct.
12. **Exit codes have a decision table.** *(review)* 2: the input, or the written output, could
    not be measured (the JSON says which; a written file is never called "not written"). 4: no
    feasible crop. 5: no file written. 6: a written or validated file `fails`. 1: advisory
    warnings on the input or the output when nothing above applies. 0 otherwise. A known
    encoding failure with unavailable geometry is `fails`, exit 6. *Check:* one test per row.
13. **What is on disk stays on disk.** A written file remains at `--out` when its validation
    fails or is incomplete; the report is the record. Recovery is out of scope.
14. **No new heuristic constants.** The interval comes from the delta, not a tolerance.

## Out of scope, and why

- **Background, borders, sharpness, exposure, skin tone.** China requires all five; none has a
  check in this build, and each needs calibration before a threshold is defensible. Reported
  `not_evaluated` with that reason, never omitted. ROADMAP, under calibration, alongside the
  existing gaps (glasses frames, gaze).
- **Print profiles.** Millimetre rules need a DPI the file does not carry; `--validate` with
  `cn_visa_paper` is a usage error naming the profile, as `--out` is.
- **Independent accuracy.** The delta bounds self-consistency. Whether such intervals have any
  empirical coverage is a calibration question, with source/output scale pairs and annotated
  landmarks; this stage assigns no confidence to them.
- **Captured detail.** Output pixel IED cannot establish facial detail captured; standalone
  validation cannot reconstruct a file's history. The report preserves source measurements and
  render scale where it has them; a calibrated detail assessment is ROADMAP.
- **Recovery** after an unsatisfactory validation: recropping, a joint geometry/encoding
  search, alternate backends, transactional outputs. ROADMAP.
- **Photo age.** An attestation; the file cannot establish it.

## Design, concretely

**Schema changes, small:** `Rule` and `Constraint` gain `lo_strict` / `hi_strict` (default
False); China's `inter_eye_distance` and `eye_line_from_bottom` set `lo_strict`. `Profile` gains
`jurisdiction`. `Encoding` gains `size_readings: tuple[SizeReading, ...]` (name, min, max) and
derives `min_bytes` / `max_bytes` as their intersection for the encoder. `solve()` reports
`Infeasible` naming the rule when the chosen point lies on a strict bound within `EPS`.

**`validate.py`**

- `Verdict`: `pass`, `fail`, `indeterminate`, `not_evaluated`.
- `Criterion(key, kind, verdict, observed, predicted, delta, lo, hi, lo_strict, hi_strict, unit,
  expected, detail, quote)`; `kind` is `rule` or `encoding`; `expected` carries structured
  non-numeric expectations (permitted sizes, format, mode).
- `file_facts(path)`: `format`, `mode`, `bits`, `stored_size`, `bytes`, from Pillow's header
  and the file, before any conversion; `measured_size` from the oriented image.
- `observe(profile, measured_size, measurements)`: `build_constraints` at the file's own size,
  filtered to rules; `value(1, 0, 0)` per rule; a `ProfileError` for a non-reference size marks
  every pixel rule `not_evaluated` with that reason and keeps going.
- `predict(profile, plan, source_measurements)`: the same constraints at the plan's `(s, u, v)`.
- `validate(profile, facts, measurements, preflight, predicted=None) -> Validation`.
- The interval rule with strictness: with half-width `d` (0 when no prediction), `[x − d, x + d]`
  inside the band ⇒ `pass`; disjoint from it ⇒ `fail`; otherwise `indeterminate`. An inclusive
  endpoint belongs to the band, so an interval touching it is inside; an exclusive endpoint does
  not, so an interval touching it is `indeterminate` and a value equal to it, with no interval,
  is outside.

**CLI**

- `--validate` (requires `--spec`; exclusive with `--out`); effective jurisdiction from the
  profile unless `--for` agrees.
- After `--out` writes: `load_source` + `measure_photo` on the output (its own preflight),
  `validate` with `predict`. Failures to reopen or measure set `validation.error` and exit 2
  with `encode` intact.
- Text: a `validation` block, one line per criterion — verdict, observed, predicted, delta,
  bound — and the aggregate with the attestations and not-assessable list. `_render`'s
  "geometry has not been checked" line is replaced by the validation outcome when there is
  one. README's status line is updated.

## Declined or adjusted from the review

- *Honour strictness in solver solution acceptance* is taken in its smallest form: the solver
  still maximizes slack over closed intervals — its optimum is interior whenever the feasible
  set has positive width — and refuses only the case where the chosen point lies on a strict
  bound. A strict-inequality feasibility calculus for a single-point feasible set is not built.
- *Return structured unapplied information from `build_constraints`* is met by the validator
  looking the rule's measurement up on the measurement set, which already carries the status
  and both gate lists; the planner's rendered strings are unchanged.

## Verification

The checks under "What must be true", each a test from a file on disk with only the fits
stubbed, plus the real run: the reference photo through `--out`, its validation block in the PR,
and the written file through `--validate` giving the same verdicts.

## Sequence

- [x] This document, reviewed once by Codex (GPT-6 Astra, high); ROADMAP entries.
- [x] Schema: strict bounds, `jurisdiction`, size readings; solver strict-point refusal.
- [x] `validate.py`: file facts, observe, predict, verdicts, aggregate.
- [x] CLI: `--validate`, post-write validation, exit table, report envelope; README report
      section and status line.
- [x] Tests as above; real run.
- [ ] Review under the two-pass rule; merge.

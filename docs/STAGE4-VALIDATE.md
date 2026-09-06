# Stage 4 — validate the written file, and the report contract

Working plan for the stage. The *why* behind per-criterion verdicts and the limits of a
geometry-only validator is in [PLAN.md](PLAN.md) → Validation; not repeated here. Fresh as of
2026-09-06.

**Where:** worktree `~/dev/visa-photo-validate`, branch `stage4-validate` off `main`, tracking PR
opened with this commit.

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
   value, the bound, and the reason. *Check:* end to end from a photo on disk with only the
   fits stubbed; the reference photo's output passes every implemented check, recorded in the
   PR.
2. **A file you already have can be checked.** `visa-photo FILE --spec cn_visa_digital --validate`
   checks the file as-is against the profile's rules at the file's own size; no crop is planned.
   *Check:* the file written in (1), fed back with `--validate`, yields the same verdicts; a
   600×800 photograph fails dimensions.
3. **A rule's quantity has one definition.** The validator evaluates the same `Constraint`s the
   solver builds (`build_constraints`), at the identity transform (`value(1, 0, 0)`) on the
   output's measurements; the plan's prediction for the same rule is the same constraint at the
   plan's transform on the source's measurements. "Eye line from bottom is height minus
   eye-line y" is written once. *Check:* a test asserts the validator's observed quantity equals
   the constraint's value at identity, for every rule.
4. **Uncertainty is stated, not invented.** When a render preceded validation, the difference
   between the predicted and observed quantity is recorded per rule as `delta`, and a verdict
   whose observed value lies within `|delta|` of a bound is `indeterminate`, with both numbers.
   The delta is the disagreement of one model with itself at two scales — self-consistency,
   not accuracy — and the report says so. Standalone `--validate` has no prediction: verdicts
   are point comparisons and the report says "no uncertainty interval". *Check:* a value 0.5 px
   inside a bound with a delta of 1.0 px is `indeterminate`; the same value with a delta of
   0.1 px is `pass`; with no delta, `pass`.
5. **Encoding is checked from the file, not from what the encoder intended.** Dimensions among
   the profile's sizes; format JPEG; mode RGB, 8 bits per channel; size in bytes against the
   band under *both* readings of KB — satisfies both ⇒ `pass`, one ⇒ `indeterminate` naming
   the readings, neither ⇒ `fail`. *Check:* files of 40,500, 41,000 and 39,000 bytes; a PNG;
   a 600×800 JPEG.
6. **Advisories run on the file too.** Preflight on the output's fit — expression, eyes,
   glasses, pose, the attestations and operation policies — reported in the same shape as for
   the source and labelled as observed on the written file. *Check:* the section is present and
   carries the mode and findings.
7. **The aggregate never reads as "compliant".** `fails` when any rule or encoding check fails;
   otherwise `incomplete` when any implemented check is `indeterminate` or `not_evaluated`;
   otherwise `passes_implemented_checks` — and in every case the report lists the attestations
   still required (recency, for China) and the requirements this build cannot assess
   (background, borders, sharpness, exposure, skin tone). Exit code 6 when a written or
   validated file `fails`. *Check:* one test per aggregate value; exit 6.
8. **The report has a contract.** Top level: `report_version` (1), `tool` (`version`,
   `backends`), then `measurements`, `preflight`, `plan`, `render`, `encode`, `validation` —
   each present, `null` when the run did not reach it. *Check:* the key set is asserted, and a
   README section describes it.
9. **No new heuristic constants.** The interval comes from the delta, not a tolerance.

## Out of scope, and why

- **Background, borders, sharpness, exposure, skin tone.** China requires all five; none has a
  check in this build, and each needs calibration before a threshold is defensible. They are
  reported `not_evaluated` with that reason, never omitted. ROADMAP, under calibration.
- **Print profiles.** Millimetre rules need a DPI the file does not carry; `--validate` with
  `cn_visa_paper` is a usage error naming the profile, as `--out` is.
- **Independent accuracy.** The delta bounds self-consistency; accuracy against annotated
  fixtures is the calibration stage.
- **Photo age.** An attestation; the file cannot establish it.
- **Validating at a size the profile does not list.** China's pixel rules are stated at 354×472
  "as an example" and the plan already refuses to scale them; the validator refuses the same
  way: dimensions outside the listed sizes `fail` dimensions and the pixel rules are
  `not_evaluated` with "pixel rules are stated at 354×472 and not scaled" — never applied
  literally at a size they were not written for.

## Design, concretely

**`validate.py`**

- `Verdict`: `pass`, `fail`, `indeterminate`, `not_evaluated`.
- `Criterion(key, kind, verdict, value, lo, hi, unit, delta, detail, quote)`; `kind` is `rule`
  or `encoding`.
- `observe(profile, size, measurements) -> (constraints at identity, unapplied)`: the solver's
  `build_constraints` for the file's own size; each applied constraint's `value(1, 0, 0)` is
  the observed quantity; each unapplied rule is `not_evaluated` with the measurement's reason
  chain.
- `predict(plan, source_measurements) -> {rule: value}`: the same constraints at the plan's
  `(s, u, v)`; the delta is `observed − predicted`.
- `file_facts(path) -> {format, mode, bits, width, height, bytes}` from Pillow and the file.
- `validate(profile, measurements, facts, predicted=None) -> Validation(criteria, aggregate,
  attestations, not_assessable, note)`; `to_dict`.
- Verdict rule for a band `[lo, hi]` and observed `x` with half-width `d` (`|delta|`, or 0):
  `[x − d, x + d]` inside ⇒ `pass`; disjoint ⇒ `fail`; straddling ⇒ `indeterminate`.

**CLI**

- `--validate` (requires `--spec`; exclusive with `--out`): measure the input, `validate` at the
  input's own size, no plan. Exit 6 on `fails`, else the usual codes.
- After `--out` writes a file: reopen it through `load_source` + `measure_photo`, `validate`
  with `predict(plan, source measurements)`, run preflight on the output's fit. Exit 6 on
  `fails`; exit 5 stays for "not written".
- JSON gains `report_version`, `tool` and `validation`; text gains a `validation` block: one
  line per criterion with verdict, value, bound, delta.
- `EXIT_FAILS = 6` in the module docstring's table.

## Verification

The checks under "What must be true", each a test from a file on disk with only the fits
stubbed, plus the real run: the reference photo through `--out`, its validation block in the PR,
and the written file through `--validate` giving the same verdicts.

## Sequence

- [ ] This document, reviewed once by Codex (GPT-6 Astra, high); README report section;
      ROADMAP entry.
- [ ] `validate.py`: observe, predict, file facts, verdicts, aggregate.
- [ ] CLI: `--validate`, post-write validation, exit 6, `report_version` and `tool`.
- [ ] Tests as above; real run.
- [ ] Review under the two-pass rule; merge.

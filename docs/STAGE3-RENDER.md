# Stage 3 — render and encode

Working plan for the stage. The *why* is in [PLAN.md](PLAN.md) → Operation policy and → Encoding;
not repeated here. Fresh as of 2026-09-06.

**Where:** worktree `~/dev/visa-photo-render`, branch `stage3-render`, stacked on
`stage1b-preconditions` (PR #3). Tracking PR opened with this commit.

## What this stage delivers

Given a feasible `Plan` from Stage 2, produce the file — and refuse, by name, when a step is not
permitted, not possible, or not achievable within the profile's encoding limits. Nothing is
validated against the profile here beyond what encoding needs; that is Stage 4.

## Operations declare preconditions, exactly as measurements do

The class Stage 1b closed — a confident result under an unmet precondition — has an obvious
twin here: a rendered file produced under an operation the channel prohibits, or a background
replaced from a matte that never isolated the face. So each operation is built the way a
measurement is: a name, a candidate, and gates looked up from a record. No operation runs
because its inputs happened to be present.

| Operation | Requires |
|---|---|
| `crop_resize` | a feasible `Plan`; profile policy for `crop` and `resize` is `allowed` |
| `replace_background` | policy `allowed` (never `unresolved`, see below); `matte_present`; `face_component_isolated`; the isolated subject — the component that gate selected, with its attached soft edge, the only alpha rendering is given — is clear of the crop's top and side edges |
| `encode` | `crop_resize` done; a candidate satisfying the profile's format, colour space and byte band exists |

**`unresolved` is treated as prohibited by default.** China's sheet says nothing about editing,
and doing something a channel is silent about — to an identity photograph — is not a decision
this tool makes for the applicant. `--allow-unresolved-operations` opts in, and the operation
history records that it was an opt-in. NZeTA is `prohibited` outright and no flag overrides it.

## Rendering, concretely

- **Crop and resize are one resample.** Pillow's `Image.resize(size, LANCZOS, box=(x0, y0, x1, y1))`
  takes a float box, so the crop origin and scale from the plan are applied in a single uniform
  resample. Rounding the crop to integers and then resizing independently introduces a small
  non-uniform scale, which the plan forbids.
- **Colour comes first:** output is 8-bit sRGB. A source with an embedded profile (Display P3 on
  iPhone photographs) is converted to sRGB in source space, relative colorimetric, before any
  other operation; a source with none, or with one LittleCMS cannot read, is assumed sRGB and the
  assumption — and which case it was — is recorded in the history. No colour *adjustment* is
  performed (a separate operation, `unresolved` everywhere seeded).
- **Background replacement happens in source space, before the resample**, by compositing the
  matte over the profile's background colour. Compositing after resampling puts a resampled
  alpha edge against a hard fill.
- **Metadata:** none. The encoder is handed a fresh image built from pixels alone, so nothing in
  the source's `info` (a COM comment, EXIF, the ICC profile) can be copied into the file.
  Orientation is already normalized at load.
- **The destination is never destroyed by a failed search.** Candidates are written to a
  temporary file beside `--out` and replace it only when one fits; `--out` naming the input
  photo is refused outright. A destination that cannot be written is a reported result
  (`write_failed`, exit 5) with the report still emitted, not a traceback.
- **Encoding search:** JPEG, 4:4:4 (no chroma subsampling — a 354-px-wide face does not have
  chroma to spare), quality candidates `(98, 96, 94, 92, 90, 88, 85, 82, 80, 75, 70)`. Encode each,
  measure the **bytes of the written file**, keep the highest quality inside the byte band. Below
  70 the output is visibly degraded and the search stops: **if nothing satisfies the band, that is
  the result** — `no_encoding_satisfies`, with the trace. Never pad to reach a floor; never
  degrade past the list.

## Profile additions

`Encoding(format="jpeg", colour="srgb_24bit", min_bytes, max_bytes, subsampling="4:4:4")`
on `cn_visa_digital` (JPEG, 40–120 KB, from the MFA sheet). `cn_visa_paper` has no digital
encoding rules and gets none.

## Operation history

The report records, in order: each operation, its status (`done` / `skipped` / `refused`), its
gates, the parameters used (crop box, scale, quality chosen, bytes), and for background
replacement whether it was default-allowed or an opt-in. A finished JPEG cannot establish any of
this after the fact; the history is the only record.

## Verification

- End to end through `visa-photo PHOTO --spec cn_visa_digital --out FILE` with stubbed fits:
  the written file reopened and measured — dimensions equal the chosen size, mode RGB, bytes
  within the band, no EXIF, no chroma subsampling.
- The rendered file re-measured through Stage 1b's `measure_all`: eye line and matte top land
  where the plan predicted, within a pixel. This is the pipeline agreeing with itself, not
  accuracy; the plan already says which is which.
- `replace_background`: refused on `prohibited`; refused on `unresolved` without the flag,
  performed with it and recorded as opt-in; refused when `face_component_isolated` is not True
  even with the flag.
- Encoding: a synthetic image that cannot fit the band at any listed quality ⇒
  `no_encoding_satisfies` with the trace; a normal one ⇒ the highest passing quality.
- Uniform scale: a crop whose box is non-integer produces the same output as the float-box
  path and differs from round-then-resize by measurable pixels — asserted, so the shortcut is
  never quietly reintroduced.

## Open finding — holds the merge

Review pass three (423c36d) reproduced a bypass of the isolation gate in `subject_alpha`. The
selected solid component is extended into its soft edge by labelling connectivity over *all
nonzero alpha*; a faint bridge (alpha 1) between the subject and a rejected solid fragment
reconnects them, so the fragment is composited while the history reports "composited the
isolated subject". On the synthetic fixture: `alpha[100:130, 70:100] = 255;
alpha[115, 100:150] = 1` gives the gate "component 2 of 2 selected", `subject_alpha[115, 85]
== 255`, and output pixel (30, 50) grey.

**Candidate fix, spiked 2026-09-06, not on the branch:** attribute every nonzero-alpha pixel to
the component of its *nearest solid pixel* (`scipy.ndimage.distance_transform_edt(~solid,
return_indices=True)`) and keep those attributed to the selected component. No radius constant
and no connectivity through bridges. On the reviewer's fixture the fragment and its soft halo
are 0, the subject's soft edge is kept, and the bridge splits at its midpoint (the subject's
half kept at alpha 1). On the reference photo's 2316×3088 matte it costs 0.29 s and drops
15,390 of 3.56 M nonzero pixels across the seven rejected components.

**Why it is held rather than fixed here:** three review passes were taken, and the findings of
passes two and three were each in code written for the previous pass's fix (the print writer;
the soft-edge extension). That is the not-converging signature the review rule names, and the
pass cap is its backstop. Landing the fix and its regressions (bridged fragment, halo, split
bridge) needs a receipt at the new head, which is a fourth run — a decision for the author of
the rule, not for the branch.

## Sequence

- [x] This document.
- [x] `Encoding` on profiles; operation policy consulted through one function.
- [x] `render.py`: operation gates and record; crop+resize via float box; background
      replacement in source space with the opt-in flag.
- [x] `encode.py`: bounded candidate search measuring written bytes; `no_encoding_satisfies`.
- [x] `--out` on the CLI; operation history in text and JSON.
- [x] Tests as above.
- [ ] Open finding above resolved, with its regressions; receipt at HEAD.

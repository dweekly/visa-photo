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
| `replace_background` | policy `allowed` (never `unresolved`, see below); `matte_present`; `face_component_isolated`; the matte's alpha at the crop's border rows/columns is background (no subject touches the crop edge) |
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
- **Background replacement happens in source space, before the resample**, by compositing the
  matte over the profile's background colour. Compositing after resampling puts a resampled
  alpha edge against a hard fill.
- **Colour:** output is 8-bit sRGB. A source with an embedded profile is converted; a source with
  none is assumed sRGB and the assumption is recorded in the history. No colour *adjustment* is
  performed (a separate operation, `unresolved` everywhere seeded).
- **Metadata:** stripped. Orientation is already normalized at load; the output carries none.
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

## Sequence

- [x] This document.
- [x] `Encoding` on profiles; operation policy consulted through one function.
- [x] `render.py`: operation gates and record; crop+resize via float box; background
      replacement in source space with the opt-in flag.
- [x] `encode.py`: bounded candidate search measuring written bytes; `no_encoding_satisfies`.
- [x] `--out` on the CLI; operation history in text and JSON.
- [x] Tests as above.

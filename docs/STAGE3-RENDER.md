# Stage 3 — render and encode

Working plan for the stage. The *why* behind encoding limits and per-channel operation policy is in
[PLAN.md](PLAN.md) → Encoding and → Operation policy; not repeated here. Fresh as of 2026-09-06.
Reviewed once by Codex (GPT-6 Astra, high reasoning) on 2026-09-06 against this worktree; its
five failure findings are folded in below, each marked *(review)*, and two suggestions are
adjusted rather than taken, under Declined.

**Where:** worktree `~/dev/visa-photo-render-lean`, branch `stage3-render-lean` off `main`,
tracking PR opened with this commit. An earlier attempt (`stage3-render`, PR #4) is closed unmerged
and kept for reference; this plan rebuilds it by subtraction, and the reasons are under Scope.

## Why

Stages 1 and 2 end at a plan: a scale and crop origin that satisfy one destination's rules, or a
named reason none does. Nothing writes a file. Stage 3 turns a feasible plan into the file the
applicant uploads, inside the destination's encoding limits, and refuses by name when it cannot.
The plan is the only input that carries authority; rendering adds no judgement of its own.

## What must be true

Each criterion names its check.

1. **A file that matches the plan.** `visa-photo PHOTO --spec cn_visa_digital --out FILE` writes a
   JPEG at the chosen output size. Reopened: mode RGB, 4:4:4 chroma, no EXIF, no ICC profile, no
   comment, size inside the profile's byte band. *Check:* end-to-end through the CLI from a
   synthetic photo *on disk* — EXIF orientation tag, embedded ICC profile, COM comment — with
   only the two model fits stubbed, asserting on the reopened file; one real run on the
   reference photo recorded in the PR.
2. **One decode, one snapshot.** *(review)* The photo is decoded once, orientation-normalized,
   and that snapshot is what measurement reads and what rendering resamples. The oriented image
   is kept in its native mode with its embedded profile until colour conversion; measurement
   gets the RGB view of the same snapshot. *Check:* the CLI test counts decodes; a source that
   is unreadable at all is exit 2 with the existing measurement error, never a traceback.
3. **Colour is converted, or the assumption is stated.** A source with a readable embedded ICC
   profile is converted to sRGB from its native mode before resampling and the report names the
   profile. A source with none is written as-is and the report says sRGB was assumed. A profile
   that does not parse, and a profile that parses but whose transform fails, are two different
   recorded reasons; the second keeps the profile's name *(review)*. RGB sources are tested;
   non-RGB sources take the same path and are not claimed until a portable fixture exists (see
   ROADMAP). *Check:* a synthetic ICC profile whose red and green colorants are swapped, through
   the real loader from a PNG on disk, so the assertion is on a colour that must change; the
   no-profile and unparseable cases each asserted on their history entry.
4. **One resample, from a box Pillow accepts.** Crop and resize are a single Lanczos pass through
   the float crop box. The solver's containment bounds carry float noise — a feasible plan can
   put the origin at −3e−14 — and Pillow rejects a negative box offset, so the box is clamped to
   the source at the solver's tolerance (`geometry.EPS`) before the call and the box supplied is
   the one recorded *(review)*. *Check:* the box params equal the values derived from the plan;
   a plan whose crop touches the source edge renders rather than raising; the output differs,
   in measured pixels, from rounding the box and resizing.
5. **Nothing fits is a result, not a file.** When no listed quality lands inside the band, no file
   is written, whatever was at `--out` is untouched, the report lists every quality tried with its
   bytes, exit code 5. Every listed quality is tried: file size is not monotone in quality at
   small sizes (measured 657, 657, 658 bytes at 92, 90, 88 on a 32×32 image), so there is no
   early exit *(review)*. *Check:* a flat image under China's floor with a sentinel file at
   `--out`; the trace length equals the list length.
6. **Write failures are reported, never raised.** A destination that cannot be written (a
   directory, a permissions error, a disk that fills mid-write) is `write_failed` in the report
   with the OS message, exit 5, report still emitted. Cleanup of the temporary file is attempted;
   if it fails, the result says so and names the path, and the original failure is the one
   reported *(review)*. `--out` naming the input photo is a usage error before anything runs,
   checked only after the photo argument itself is validated. *Check:* `--out` pointing at a
   directory with `--json`; a save that dies after partial bytes with an existing file at
   `--out`; a cleanup that fails after a failed write; `--out` equal to the input; `--out` with
   no photo argument.
7. **Print profiles are refused, not half-served.** `--out` with a profile that states no digital
   encoding rules (`cn_visa_paper`) is a usage error naming the profile. *Check:* CLI test.
8. **The history is complete and claims nothing else.** `render.history` is exactly
   `["colour_convert", "crop_resize"]`, in that order, and encoding is recorded separately under
   `encode` with quality, bytes and the full trace. Box values are full precision in JSON and
   rounded only for text; the text formatter prints box, scale and output size. *Check:* both
   output formats asserted on those fields.
9. **Exit codes keep their precedence.** 2 for a photo that cannot be measured, 4 for no feasible
   crop, 5 only for a failure after a feasible plan.
10. **No new heuristic constants** beyond the quality list, which is documented at its definition.

## Scope: what is out, and why

- **Background replacement.** The digital profile marks it `unresolved` and the paper profile
  does not address it; of the four planned destinations, New Zealand prohibits editing, the US
  prohibits digital alteration, and ICAO — the basis of the Schengen profile — does too. No
  planned destination turns it on. The first cut built it anyway: component isolation, a
  soft-edge extension, an edge gate. On the reference photo its opt-in path refused because the
  shoulders cross the crop's sides — the expected case for a China-compliant crop, where the face
  spans 54–62% of the frame width — and all of review passes two and three landed inside it,
  each finding in the previous fix. It goes to ROADMAP with these facts attached, for when a
  destination allows it and someone needs it. The operation policy table stays, because preflight
  already reports "this destination prohibits editing" — the part with value.
- **Print output.** A file at Pillow's defaults with no DPI or physical size is half a feature.
  A later stage sets both from the profile's millimetres.
- **Huffman-table optimization** (`optimize=True`). 2.5% smaller files on the reference photo,
  bought with Pillow's encoder overrunning its output buffer on high-entropy content and ten lines
  of buffer sizing. Not worth it.
- **Rotation and colour adjustment** stay `unresolved`; **pixel synthesis** stays `prohibited` on
  the digital profile. Unchanged.
- **Non-RGB sources** (CMYK, greyscale with a grey profile) are converted through the same path
  but not claimed: no portable non-RGB ICC fixture exists in the test suite. ROADMAP.

## Design, concretely

**`load_source(photo) -> Source(native, rgb)`** in `measure.py`, replacing the CLI's second
decode. `native` is the orientation-normalized image in its original mode with `info` intact;
`rgb` is its RGB view for measurement. `measure_photo` accepts a `Source` so the CLI decodes once
and hands the same snapshot to both stages.

**`render(source, plan) -> RenderResult(image | None, history)`**

- Refuses with an empty image when the plan is not feasible; that is the only precondition, and
  it is checked once. No gate lookups: nothing here depends on a measurement's availability
  beyond what the solver already required.
- Colour first, from `source.native`. Profile present and parsed ⇒
  `ImageCms.profileToProfile(native, profile, sRGB, relative colorimetric, outputMode="RGB")`.
  No profile ⇒ `native.convert("RGB")`, history "assumed sRGB: no embedded profile". Profile does
  not parse ⇒ same, "assumed sRGB: profile unreadable". Profile parses but the transform fails ⇒
  same, "assumed sRGB: conversion from '<name>' failed: <reason>". Relative colorimetric because
  this is a display-to-display conversion: in-gamut colours exact, the rest clipped.
- Then the box: `(x0, y0, x0 + W/s, y0 + H/s)` from the plan, each edge clamped into
  `[0, source size]` when it lies within `geometry.EPS` outside; a box further outside than that
  is a solver bug and raises. `Image.resize((W, H), LANCZOS, box=box)`.
- `OperationRecord(name, status, detail, params)`; statuses `done` / `skipped` / `refused`.
  History is exactly `colour_convert`, `crop_resize`.

**`encode(image, encoding, out) -> EncodeResult`**

- The encoder is handed a pixels-only copy (`Image.frombytes`) so nothing in the source's `info`
  can reach the file — Pillow copies `info["comment"]` into the JPEG it writes.
- Qualities `(98, 96, 94, 92, 90, 88, 85, 82, 80, 75, 70)`, highest first. 70 is the chosen floor
  of the search, a tool choice documented at the definition, not a published threshold. Each
  candidate is written to a temporary file beside `out` and its size measured on disk (the number
  the upload form will see). First fit ⇒ `os.replace` into `out`. Every listed quality is tried;
  nothing fits ⇒ `no_encoding_satisfies` with the full trace; the temporary file is removed and
  `out` never touched.
- Any `OSError` on the write path ⇒ `write_failed` with the message. Cleanup of the temporary
  file is attempted in every exit; a cleanup failure is appended to the result's detail with the
  path left behind and never replaces the original outcome.
- `Encoding(format, colour, min_bytes, max_bytes, subsampling)` on the profile. The source quote
  is the published rule; the numbers beside it are this tool's interpretation, labelled as such:
  `cn_visa_digital` is JPEG, "40KB–120KB" from the MFA sheet, read as **40,960–120,000 bytes** —
  the intersection of the 1,000- and 1,024-byte readings, so a file inside it satisfies either.
  sRGB and 4:4:4 are tool choices where the sheet states only the format. `cn_visa_paper`: none.

**CLI**

- `--out FILE` requires `--spec`; refuses `--out` equal to the input; refuses a profile without
  `encoding`. After a feasible plan: render, encode, print the history (or include it in
  `--json` under `render` and `encode`), exit 5 when no file was written.

**Carried over from the parked branch:** `_convert_to_srgb` (now from the native image, with the
two failure reasons split), the crop+resize (now clamped), `encode` minus its buffer sizing and
early exit, the staged-write helper (cleanup errors caught), the CLI wiring (single decode, photo
argument validated first), and the tests for colour, metadata, staged writes, write failure,
usage errors and the uniform-scale check, rewritten to run from a file on disk with only the fits
stubbed. **Removed:** `replace_background` and the crop-edge check, `subject_alpha` and its
plumbing through `evaluate.py`, `measurements.py` and `segmentation.py`, `write_unconstrained`,
`ENCODER_BUFFER_RAW_MULTIPLE`, and their tests.

## Declined or adjusted from the review

- *Compare the output against a direct float-box Lanczos reference computed from the plan.* A
  reference built with the same call proves only that the call was made; the check kept is that
  the recorded box equals the plan-derived values exactly, plus the rounded-box difference.
- *Add a valid non-RGB ICC case through the loader.* The reproduction used macOS's Generic CMYK
  profile, which the public suite cannot depend on, and a synthetic LUT-based profile is not
  worth building for a source type no phone or scanner produces. The native mode is preserved to
  the conversion, so the path is the same; the claim is withheld and the fixture is on ROADMAP.
- The review's roadmap items — validating the written file with predicted-versus-observed deltas
  (Stage 4), a joint plan-and-encoding search when no quality fits, operation permission as a
  planning prerequisite before profiles that prohibit an executed operation, non-RGB fixtures —
  are recorded in ROADMAP and not built here.

## Verification

The checks under "What must be true", each a test, plus the real run: the reference photo through
the CLI, reopened and measured, with the history shown in the PR. The rendered file re-measured
through Stage 1b's `measure_all` — eye line and matte top within a pixel of where the plan put
them — is the pipeline agreeing with itself, not accuracy, and is recorded as such.

## Sequence

- [x] This document, reviewed once by Codex (GPT-6 Astra, high); ROADMAP entries; README row.
- [ ] `Encoding` on profiles; `load_source` and `measure_photo` taking a `Source`.
- [ ] `render.py`, `encode.py`, CLI `--out`.
- [ ] Tests as above; real run.
- [ ] Review under the two-pass rule; merge.

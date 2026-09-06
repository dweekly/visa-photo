# Stage 3 — render and encode

Working plan for the stage. The *why* behind encoding limits and per-channel operation policy is in
[PLAN.md](PLAN.md) → Encoding and → Operation policy; not repeated here. Fresh as of 2026-09-06.

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
   comment, size inside the profile's byte band. *Check:* end-to-end through the CLI with stubbed
   fits, asserting on the reopened file; one real run on the reference photo recorded in the PR.
2. **Colour is converted, or the assumption is stated.** A source with a readable embedded ICC
   profile is converted to sRGB before resampling and the report names the profile. A source
   with none, or one LittleCMS cannot parse, is written as-is and the report says sRGB was
   assumed and why. *Check:* a synthetic ICC profile whose red and green colorants are swapped,
   so the assertion is on a colour that must change; the no-profile and unreadable cases each
   asserted on their history entry.
3. **One resample.** Crop and resize are a single Lanczos pass through the float crop box.
   *Check:* the output differs, in measured pixels, from rounding the box and resizing.
4. **Nothing fits is a result, not a file.** When no listed quality lands inside the band, no file
   is written, whatever was at `--out` is untouched, the report lists every quality tried with its
   bytes, exit code 5. *Check:* a flat image under China's 40 KB floor with a sentinel file at
   `--out`.
5. **Write failures are reported, never raised.** A destination that cannot be written (a
   directory, a permissions error, a disk that fills mid-write) is `write_failed` in the report
   with the OS message, exit 5, report still emitted. `--out` naming the input photo is a usage
   error before anything runs. *Check:* `--out` pointing at a directory with `--json`; a save that
   dies after partial bytes with an existing file at `--out`; `--out` equal to the input.
6. **Print profiles are refused, not half-served.** `--out` with a profile that states no digital
   encoding rules (`cn_visa_paper`) is a usage error naming the profile. *Check:* CLI test.
7. **The history is complete and claims nothing else.** Text and `--json` record, in order: colour
   conversion (done or skipped, from what), crop+resize (box, scale, output size), encode (quality,
   bytes, trace). *Check:* the JSON report's `render.history` operation names asserted exactly.
8. **No new heuristic constants** beyond the quality list, which is documented at its definition.

## Scope: what is out, and why

- **Background replacement.** Both existing profiles mark it `unresolved`; of the four planned
  destinations, New Zealand prohibits editing, the US prohibits digital alteration, and ICAO — the
  basis of the Schengen profile — does too. No planned destination turns it on. The first cut
  built it anyway: component isolation, a soft-edge extension, an edge gate. Its opt-in path
  refused every ordinary portrait (a China-compliant face spans 54–62% of the frame width, so
  shoulders always cross the sides), and all of review passes two and three landed inside it,
  each finding in the previous fix. It goes to ROADMAP with these facts attached, for when a
  destination allows it and someone needs it. The operation policy table stays, because preflight
  already reports "this destination prohibits editing" — the part with value.
- **Print output.** A file at Pillow's defaults with no DPI or physical size is half a feature.
  A later stage sets both from the profile's millimetres.
- **Huffman-table optimization** (`optimize=True`). 2.5% smaller files on the reference photo,
  bought with Pillow's encoder overrunning its output buffer on high-entropy content and ten lines
  of buffer sizing. Not worth it.
- **Rotation, colour adjustment, pixel synthesis:** `unresolved` everywhere seeded, unchanged.

## Design, concretely

**`render(image, plan) -> RenderResult(image | None, history)`**

- Refuses with an empty image when the plan is not feasible; that is the only precondition, and
  it is checked once. No gate lookups: nothing here depends on a measurement's availability
  beyond what the solver already required.
- Colour first. `image.info["icc_profile"]` present and readable ⇒
  `ImageCms.profileToProfile(image, source, sRGB, relative colorimetric)`; otherwise the image is
  used as-is and the history entry says "assumed sRGB" with the reason (none / unreadable).
  Relative colorimetric because this is a display-to-display conversion: in-gamut colours exact,
  the rest clipped.
- Then `Image.resize((W, H), LANCZOS, box=(x0, y0, x0 + W/s, y0 + H/s))` with the plan's float
  origin and scale.
- `OperationRecord(name, status, detail, params)`; statuses `done` / `skipped` / `refused`.

**`encode(image, encoding, out) -> EncodeResult`**

- The encoder is handed a pixels-only copy (`Image.frombytes`) so nothing in the source's `info`
  can reach the file — Pillow copies `info["comment"]` into the JPEG it writes.
- Qualities `(98, 96, 94, 92, 90, 88, 85, 82, 80, 75, 70)`, highest first, 4:4:4, no optimize. Each
  candidate is written to a temporary file beside `out` and its size measured on disk (the number
  the upload form will see). First fit ⇒ `os.replace` into `out`. A candidate under the floor
  ends the search: lower quality only gets smaller. Nothing fits ⇒ `no_encoding_satisfies` with
  the trace; the temporary file is removed and `out` never touched.
- Any `OSError` in that path ⇒ `write_failed` with the message; the temporary file is removed.
- `Encoding(format, colour, min_bytes, max_bytes, subsampling)` on the profile, with the source
  quote. `cn_visa_digital`: JPEG, 40–120 KB, from the MFA sheet. `cn_visa_paper`: none.

**CLI**

- `--out FILE` requires `--spec`; refuses `--out` equal to the input; refuses a profile without
  `encoding`. After a feasible plan: render, encode, print the history (or include it in
  `--json` under `render` and `encode`), exit 5 when no file was written.

**Carried over from the parked branch as written:** `_convert_to_srgb`, the crop+resize, `encode`
minus its buffer sizing, the staged-write helper, the CLI wiring, and the tests for colour,
metadata, staged writes, write failure, usage errors and the uniform-scale check. **Removed:**
`replace_background` and the crop-edge check, `subject_alpha` and its plumbing through
`evaluate.py`, `measurements.py` and `segmentation.py`, `write_unconstrained`,
`ENCODER_BUFFER_RAW_MULTIPLE`, and their tests.

## Verification

The checks under "What must be true", each a test, plus the real run: the reference photo through
the CLI, reopened and measured, with the history shown in the PR. The rendered file re-measured
through Stage 1b's `measure_all` — eye line and matte top within a pixel of where the plan put
them — is the pipeline agreeing with itself, not accuracy, and is recorded as such.

## Sequence

- [ ] This document, reviewed once by Codex (GPT-6 Astra, high); ROADMAP entry for background
      replacement; README row.
- [ ] `Encoding` on profiles.
- [ ] `render.py`, `encode.py`, CLI `--out`.
- [ ] Tests as above; real run.
- [ ] Review under the two-pass rule; merge.

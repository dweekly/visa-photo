# Stage 5 — seeded profiles, the skill, and a first release

Working plan for the stage. The *why* behind the three-layer architecture and "absence is not a
requirement" is in [PLAN.md](PLAN.md); not repeated here. Fresh as of 2026-09-06.

**Where:** worktree `~/dev/visa-photo-profiles`, branch `stage5-profiles` off `main`, tracking PR
opened with this commit. Two PRs: **5a** (this branch) seeds the profiles; **5b** (a branch off
main after 5a merges) ships the skill and cuts `0.1.0`.

Reviewed once by Codex (GPT-6 Astra, high reasoning) on 2026-09-06 against this worktree and the
source files; its thirteen failure findings are folded in below, each marked *(review)*, with the
declined items under Declined.

**Sources.** Every rule below is quoted from an official page fetched on 2026-09-06 and kept
verbatim in [sources/](sources/): [United States](sources/us-state-department-2026-09-06.md),
[New Zealand](sources/nz-immigration-2026-09-06.md),
[Schengen, ICAO, France, Germany](sources/schengen-icao-2026-09-06.md). A profile quotes the
sentence it applies; nothing is applied that no sentence states, and where a sentence is not a
computable definition the reading applied is named on the rule and printed in every report.

## Why

One destination is a demonstration; the tool's claim — plan, write and check a photo against
*this* destination's rules, and say what it could not check — is only tested by destinations
whose rules differ in kind. The three sourced here do: the US states its geometry as fractions
of a square image and caps file size *and* compression ratio; New Zealand states a pixel range,
a byte band its own pages disagree about, and a head rule with no definition; the EU states
almost nothing numeric and defers, by a stale citation, to an ICAO document whose head rule
excludes hair — a quantity this build cannot measure. A useful release is one that crops where
the rules allow it, refuses where they do not with the reason, and can be installed in one line.

## What must be true — 5a, profiles

1. **`us_visa_digital` is complete and honest, and the reference photograph is a refusal.**
   *(review)* Square, 600×600 first (the size the Department's own photo tool produces) then
   1200×1200; head height — matte top, which is "the top of the head, including the hair", to
   chin — 50–69% of image height; eye line 56–69% of image height from the bottom, quoted
   from the label on the composition-template graphic and marked as such (no sentence states
   it); JPEG; "24 bits per pixel in sRGB" — the source's rule; ≤ 240 kB under both readings
   of kB; compression ratio ≤ 20:1, applied under a named reading (uncompressed bytes = width
   × height × 3; file bytes include headers) as a *floor* of `w × h × 3 / 20` — 54,000 at
   600×600, 216,000 at 1200×1200. The reference photograph's head is 1785 px tall in a source
   2316 px wide; the 69% ceiling needs a 2587-px square, so the plan is `source_too_small`
   with that arithmetic, and the successful path is proven on a synthetic photograph on disk.
   *Check:* the refusal on the reference measurements naming the rule; end to end on the
   synthetic; the byte floor at 53,999/54,000 and 215,999/216,000; the graphic-label note in
   the report.
2. **`nz_nzeta` crops and validates end to end, under a named reading.** 3:4; sizes tried in
   listed order, largest first (2250×3000, 1500×2000, 900×1200); JPG; head height 70–80% of
   image height under the reading *"face covers between 70% and 80% of the image" read as
   hair-inclusive head height over image height*, supported by INZ's photographer sheet ("the
   length of the head fills 75% of the frame"), printed wherever the rule appears. Size band:
   four readings — the applicant page's 512 KB–3.14 MB and the error page's 500 KB–3 MB, each
   under both kilobyte meanings — the encoder targeting their intersection
   (524,288–3,000,000 bytes) and the validator reporting each. Background replacement
   `prohibited` on "cropping your head and shoulders to place it on a plain background".
   *Check:* the reference photo through `--out`; the interpretation in plan and validation;
   each reading's own outcome at 524,287/524,288 and 3,000,000/3,000,001.
3. **Sizes are tried in the profile's order, and encoding failure advances to the next.**
   *(review)* `make_plan` keeps every feasible size in listed order; the CLI renders and
   encodes the first, and on `no_encoding_satisfies` moves to the next feasible size, keeping
   every attempt's history; the destination is untouched until one succeeds. China is
   unchanged (one solvable size). *Check:* a profile whose first size cannot reach its byte
   floor and whose second can.
4. **Fraction rules are compared in one unit.** *(review)* Every quantity the validator
   handles — observed, predicted, delta, bounds — is in output pixels at the file's size;
   a `fraction_height` bound is converted with the file's height and the criterion shows both
   the stated fraction and the pixel bound. *Check:* fraction rules at three heights,
   standalone and post-write, and an interval crossing a converted bound.
5. **`us_passport_print` plans, naming the readings it borrows.** *(review)* 2 inches governs
   (50.8 mm; the source's "51 mm" is its rounding, noted); head 25–35 mm chin to top of head
   with the visa page's "22 mm" recorded as a conflict; eye line 1 1/8–1 3/8 in from the
   bottom from the *visa-side* template graphic. The passport page allows hair past the frame
   while the visa FAQ measures to the hair: the hair-inclusive matte top and the visa template
   are named as interpretations on those two rules, not left to the handler. `--out` and
   `--validate` refuse print profiles as today. *Check:* a feasible plan on a synthetic
   fixture (the reference photograph is a refusal here too: 35 mm in 50.8 needs 2591 px);
   the conflict and both interpretations in the report.
6. **`schengen_print` applies no composition rule, and says why.** *(review)* The Visa Code
   binds photos to "ICAO document 9303 Part 1, 6th edition"; the only numeric head rule any
   source states is Part 3, eighth edition, §3.9.1.3, which measures the portrait *inside
   Zone V of the finished document*, not the submitted photograph; the EU sheet's "face takes
   up 70–80% of the photograph" defines nothing. So the profile carries the print size (45.0 ×
   35.0 mm from Part 3 §3.9.1.2, with the EU sheet's "35–40mm in width" beside it), no
   applied rules, and a plan that is *blocked* with that reason — never solved from the matte,
   never from an anatomical stand-in. Advisories from the EU sheet: "no more than 6-months
   old", "plain light-coloured background", the glasses and head-cover sentences. `--validate`
   refuses it as a print profile; the advisories are checked through the ordinary
   `--spec schengen_print` run. *Check:* the blocked plan's reason; the notes printed even
   though no size is chosen.
7. **A reading is printed wherever the rule is.** *(review)* `Rule.interpretation` appears in
   the plan's JSON (an `applied_rules` list with quote, bounds, unit, interpretation and
   derivation for each rule the solver used or could not) and text, and on every validation
   criterion; `_render_plan` prints the profile's notes when the plan is blocked as well as
   when it is not. *Check:* asserted for NZ and for the blocked Schengen plan; empty for
   China's rules.
8. **Dimensions can be a range.** `Profile.dimensions` is either the listed sizes (China) or a
   range with an exact integer aspect (US: 1:1, 600–1200; NZ: 3:4, 900×1200–2250×3000);
   validation checks range and aspect on the stored frame, with the EXIF-oriented frame
   handled as today; `--list-specs` shows permitted dimensions apart from the sizes the solver
   tries. *Check:* inside, outside and wrong-aspect files for each profile.
9. **Colour requirements are the source's, not the encoder's.** *(review)* `Encoding.colour`
   splits into the requirement the source states (`rgb_24bit` for China's "RGB 24bit true
   colour"; `srgb_24bit` for the US's "24 bits per pixel in sRGB"; none for NZ, whose
   applicant page states none — the photographer sheet's sRGB instruction is a note) and the
   encoder's fixed choice (sRGB, 4:4:4). The validator checks `srgb_24bit` from file evidence:
   RGB, 8 bits, and an ICC profile that is absent (a JPEG without one is sRGB by convention —
   stated in the detail) or names sRGB; another profile fails; an unreadable one is
   indeterminate. *Check:* untagged, sRGB-tagged, Display-P3-tagged and corrupt-tagged files.
10. **Operation policy governs what the renderer does.** *(review)* The renderer performs
    `crop`, `resize`, `colour_convert` (colour-space conversion for encoding, distinct from
    `adjust_colour`, appearance) and `encode`, and refuses any of them a profile marks
    `prohibited`; for these four `unresolved` means allowed, because every destination states
    dimensions and a format, and the reading is recorded. NZ's and the US's editing sentences
    are quoted per channel; crop and resize are `allowed` under the reading that the pages
    instruct the applicant to "size and format the photo correctly"; `replace_background`,
    `adjust_colour`, `synthesize_pixels` are `prohibited` where the channel's own sentence
    says so, and `unresolved` where none does. *Check:* a profile with `resize: prohibited`
    makes the renderer refuse; NZ's policies quoted.
11. **Advisories follow the channel where the source does — and a permitted smile is a
    requirement, not a gap.** *(review)* Requirements can be restricted to named profiles,
    and profile selection reaches preflight for the input, `--validate`, and the written file.
    The passport page's "You can smile ... eyes open and your mouth closed" is a requirement
    that *covers* the smile signal permissively, so the generic neutral-expression fallback
    does not fire; `--for US` with no profile keeps the generic set. *Check:* the smile
    fixture warns under `us_visa_digital` and not under `us_passport_print`; generic under
    `--for US`.
12. **Provenance is per rule, and derivation is separate from interpretation.** *(review)*
    `Rule` gains `source` and `retrieved` (inheriting the profile's when unset) and
    `derivation` for arithmetic the quote implies ("205 ± 14 → 191–219"; "1 3/8 in →
    34.925 mm"; "% of height"); dimensions, encoding and operations carry a source too. A test
    walks every profile: every rule has quote, source and retrieved; every numeric bound
    appears in the quote, or has a derivation, or has an interpretation. Existing advisories
    are audited on migration: `background_nz` moves its "not white" to the photographer PDF
    it comes from; NZ's expression sentence is added. *Check:* the walk; China's rules carry
    derivations and no interpretation.
13. **Existing profiles unchanged in behaviour.** The China receipt recorded before this
    branch — [sources/china-reference-run-2026-09-06.json](sources/china-reference-run-2026-09-06.json):
    baseline commit, source hash, backends, transform, quality, bytes, verdicts — is
    reproduced after it, in the same environment. *Check:* the numbers.

## What must be true — 5b, skill and release

14. **The repo installs as a Claude plugin in one line, and the install is tested.**
    *(review)* The repository carries a marketplace definition and a plugin with
    `skills/visa-photo/SKILL.md`, whose content is the ROADMAP's prohibitions: run the CLI,
    never hand-crop; never invent a spec for an unlisted country — refuse and list
    `--list-specs`; never collapse `indeterminate` or `not_evaluated` into "compliant" — quote
    the criteria; set-up is `uvx --python 3.12 visa-photo --fetch-models` once, then offline.
    Written after loading `plugin-dev:skill-development` and `plugin-dev:plugin-structure`,
    reviewed by `plugin-dev:skill-reviewer`. *Check:* the reviewer's findings addressed; from
    a clean Claude configuration, the marketplace added and the plugin installed in one shell
    line, then the skill invoked outside this checkout against the built wheel and found to
    run the intended version.
15. **`0.1.0` is cut docs-first, with one version.** *(review)* The version lives in one place
    (`pyproject.toml` reads it from `visaphoto.__version__`); a test asserts the built wheel's
    metadata, the CHANGELOG, the README and the plugin manifest agree with it; the wheel is
    built and installed outside the checkout before tagging. The CHANGELOG's unreleased
    sections become `0.1.0`; the README status names which profiles crop, which only plan,
    and which refuse; `docs/PUBLISHING.md` carries the checklist (`uv build`, the wheel smoke
    test, `uv publish` with David's PyPI token — his action — then `uvx visa-photo
    --list-specs` from a clean machine). The tag lands on the commit whose docs already say
    all of this. *Check:* the version test; the tag's commit.

## Out of scope, and why

- **Member-state overlays** (France 32–36 mm, Germany 70–80% "Kinnspitze bis zum oberen
  Kopfende", children 50–80%). Every one is hair-exclusive or ambiguous about hair; without the
  anatomical crown they block exactly as Schengen does. Recorded with quotes; ROADMAP.
- **US passport online renewal** (JPG/PNG/HEIC, 54 KB–10 MB, no pixel spec) — a different
  channel with its own page; not seeded.
- **Print output** stays deferred; print profiles plan only.
- **Background checks, and everything else the calibration stage owns.** NZ's "plain,
  light-coloured (not white)" against the applicant page's "neutral and plain" is a recorded
  conflict, not a check.
- **Hosting.** Unchanged.

## Design, concretely — 5a

**Schema:**
- `Rule`: `unit` gains `fraction_height`; `interpretation` (a reading applied where the quote
  defines nothing); `derivation` (arithmetic the quote implies); `source` and `retrieved`
  (inherit the profile's when unset). `to_px` converts a fraction with the output height, and
  the validator converts bounds the same way so every compared quantity is in output pixels.
- `Profile.dimensions`: `Listed(sizes)` or `Range(min, max, aspect)` with exact integer aspect;
  `Profile.sizes` stays the ordered list the solver tries, in the profile's order.
- `Encoding`: `colour_required` (`rgb_24bit` | `srgb_24bit` | None, the source's) beside the
  encoder's fixed choice; `max_compression_ratio` with its reading, applied by the encoder as a
  floor beside the readings' intersection and reported by the validator as `compression_ratio`.
- `Requirement.profiles: tuple[str, ...] | None`; a permissive requirement covers a signal
  without warning on it; `for_jurisdiction(code, profile=None)`; `measure_photo` and preflight
  take the profile.
- `make_plan` keeps every feasible size in listed order; the CLI tries them in that order and
  advances on `no_encoding_satisfies`.
- Renderer consults `profile.operations` for `crop`, `resize`, `colour_convert`, `encode`.
- Plan JSON gains `applied_rules`; `_render_plan` prints notes when blocked.

**Profiles:** `us_visa_digital`, `us_passport_print`, `nz_nzeta`, `schengen_print`, each with
`jurisdiction`, per-rule quotes, sources and retrieval dates, notes for every conflict the source
files record, and `operations` quoted per channel.

**Advisories added to `requirements.py`:** US visa expression/background/head-covering/recency;
US passport expression (smile permitted, covering the signal), background, recency; NZ
expression, recency and "not a photo of a photo"; EU recency and background. Each with quote and
source; existing NZ and US entries re-attributed where the source files show a different page.

## Design, concretely — 5b

Plugin layout per `plugin-dev:plugin-structure`; `SKILL.md` per `plugin-dev:skill-development`;
`docs/PUBLISHING.md`; `tests/test_version.py`; CHANGELOG `0.1.0`; README status and install
lines; tag `v0.1.0` after the docs commit. PyPI publication is David's action with his token;
the plan does not perform it.

## Declined or adjusted from the review

- *Retain the anatomical head-height handler as tested infrastructure.* Not built: no profile
  uses it after the Schengen correction, and code no rule reaches is the kind of surface this
  project has learned not to add.
- *Preserve the template graphics or their hashes.* travel.state.gov blocks scripted fetches
  and the graphics were read through a browser; the transcriptions in the source file name
  each dimension line and are marked as graphic labels. Saving the assets is recorded as a
  follow-up, not done here.
- *A separate, sufficiently wide photograph for a successful US run.* Not in the repository
  (no redistributable portrait exists yet — ROADMAP, calibration); the successful path is proven
  on a synthetic photograph on disk, and the reference photograph's refusal is the real run.

## Verification

Per criterion above, from the reference measurements and from photos on disk with stubbed fits
as in Stages 3–4; real runs of the reference photo through `--out` for `us_visa_digital` and
`nz_nzeta` with the validation blocks recorded in the PR; the China run re-recorded to show it
is unchanged.

## Sequence

- [x] This document, reviewed once by Codex (GPT-6 Astra, high); sources and the China
      receipt committed; README rows.
- [x] Schema: `fraction_height` in solver and validator, `interpretation`, `derivation`,
      per-rule provenance, `dimensions`, colour requirement, compression floor, ordered sizes
      with encode retry, renderer policy, `Requirement.profiles`, `applied_rules` in the plan.
- [x] Profiles and advisories, with tests; the provenance walk.
- [ ] Real runs (China receipt reproduced; NZ written; US refused with the arithmetic);
      review under the two-pass rule; merge 5a.
- [ ] 5b: plugin and skill; version test; CHANGELOG and README; PUBLISHING.md; review; merge;
      tag `v0.1.0`; David publishes.

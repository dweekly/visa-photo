# Stage 5 — seeded profiles, the skill, and a first release

Working plan for the stage. The *why* behind the three-layer architecture and "absence is not a
requirement" is in [PLAN.md](PLAN.md); not repeated here. Fresh as of 2026-09-06.

**Where:** worktree `~/dev/visa-photo-profiles`, branch `stage5-profiles` off `main`, tracking PR
opened with this commit. Two PRs: **5a** (this branch) seeds the profiles; **5b** (a branch off
main after 5a merges) ships the skill and cuts `0.1.0`.

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

1. **`us_visa_digital` crops and validates end to end.** Square, 600×600 first (the size the
   Department's own photo tool produces) then 1200×1200; head height — matte top, which is
   "the top of the head, including the hair", to chin — 50–69% of image height; eye line
   56–69% of image height from the bottom, quoted from the label on the composition-template
   graphic and marked as such (no sentence states it); JPEG; "24 bits per pixel in sRGB" (the
   source's rule, not our choice); ≤ 240 kB under both readings of kB; compression ratio
   ≤ 20:1, which is a *floor* on bytes of `width × height × 3 / 20` at the output size — 54,000
   at 600×600 — and is enforced and reported as such. *Check:* the reference photo through
   `--out`, outcomes recorded; the byte floor asserted at both sizes; the graphic-label note on
   the eye rule asserted in the report.
2. **`nz_nzeta` crops and validates end to end, under a named reading.** 3:4, sizes tried
   largest first (2250×3000, 1500×2000, 900×1200 — the byte floor is easier to reach with more
   pixels); JPG; head height 70–80% of image height under the reading *"face covers between
   70% and 80% of the image" read as hair-inclusive head height over image height*, supported by
   INZ's photographer sheet ("the length of the head fills 75% of the frame") and printed as an
   interpretation on the rule, in the plan, and in validation. Size band: four readings — the
   applicant page's 512 KB–3.14 MB and the error page's 500 KB–3 MB, each under both kilobyte
   meanings — with the encoder targeting their intersection (524,288–3,000,000 bytes) and the
   validator reporting each. Background replacement `prohibited` on the strength of "cropping
   your head and shoulders to place it on a plain background" under "Do not edit or enhance
   the photo". *Check:* reference photo through `--out`; the interpretation string present in
   `plan`, `render` and `validation`; the four readings reported.
3. **`us_passport_print` plans, and says why it cannot write.** 2×2 in (51×51 mm); head
   25–35 mm chin to top of head, with the visa page's "22 mm" recorded as a conflict (1 inch is
   25.4 mm; two of three official pages say 25); eye line 1 1/8–1 3/8 in from the bottom from
   the paper template's graphic label. `--out` and `--validate` refuse print profiles as
   today. *Check:* a feasible plan on the reference measurements; the conflict in `notes`.
4. **`schengen_print` refuses to crop, with the reason, and still advises.** 35×45 mm; the
   only computable-looking rule any source states is ICAO Doc 9303 Part 3 §3.9.1.3 — "the
   crown-to-chin portion ... 70 to 80 per cent", crown being "the top of the head ignoring any
   hair" — a hair-exclusive height bound to the anatomical tier, which this build cannot
   measure; the plan is therefore *blocked* naming `anatomical_crown_y` and its always-unknown
   gate, never solved from the hair-inclusive matte. The EU sheet's "face takes up 70–80% of
   the photograph" and "35–40mm in width", France's 32–36 mm and Germany's 70–80% are recorded
   as notes and as national overlays deferred to ROADMAP, not applied. Advisories: recency
   ("no more than 6-months old"), plain light background, the glasses and head-cover sentences.
   *Check:* `make_plan` blocked with the anatomical reason; `--validate` reports the EU-level
   encoding facts it can (none numeric) and the advisories.
5. **A rule that applies a reading says so everywhere.** `Rule.interpretation` is printed
   beside the rule in the plan, the render history and every validation criterion that uses
   it. *Check:* asserted for NZ; empty for China.
6. **Dimensions can be a range.** `Profile.dimensions` is either the listed sizes (China) or a
   range with an aspect (US: square 600–1200; NZ: 3:4 from 900×1200 to 2250×3000); validation
   checks the range and the aspect; a 800×800 US file passes dimensions. *Check:* one test per
   profile, inside and outside the range, wrong aspect.
7. **Advisories follow the channel where the source does.** The US visa page requires "a
   neutral facial expression"; the passport page says "You can smile ... eyes open and your
   mouth closed". Requirements can be restricted to named profiles so the passport profile
   does not warn on a smile the source permits. *Check:* the smile fixture warns under
   `us_visa_digital` and not under `us_passport_print`.
8. **No profile invents.** For every rule: a `quote`, a `source` URL and a retrieval date; a
   test walks every profile and fails on any rule without them, and on any bound not present
   as a number in the quote or the named interpretation.
9. **Existing profiles unchanged in behaviour.** The China digital real run gives the same
   crop, bytes and verdicts as before this branch. *Check:* the recorded numbers.

## What must be true — 5b, skill and release

10. **The repo installs as a Claude plugin in one line**, carrying `skills/visa-photo/SKILL.md`
    whose content is the ROADMAP's prohibitions: run the CLI, never hand-crop; never invent a
    spec for an unlisted country — refuse and list `--list-specs`; never collapse
    `indeterminate` or `not_evaluated` into "compliant" — quote the criteria; `--fetch-models`
    once, then offline. Written after loading `plugin-dev:skill-development` and
    `plugin-dev:plugin-structure`, reviewed by `plugin-dev:skill-reviewer`. *Check:* the
    reviewer's findings addressed; the install line in the README tested on this machine.
11. **`0.1.0` is cut docs-first.** `__version__` becomes `0.1.0`; a test asserts the CHANGELOG
    and README name it; the CHANGELOG's unreleased sections become the `0.1.0` section; the
    README status names which profiles crop and which only plan; `docs/PUBLISHING.md` carries
    the checklist (`uv build`, `uv publish` with David's PyPI token — his action — then
    `uvx visa-photo --list-specs` from a clean machine as the smoke test); the tag lands on the
    commit whose docs already say all of this. *Check:* the version test; the tag's commit.

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

**Schema, small:**
- `Rule.unit` gains `fraction_height` (bound × output height, in `to_px`).
- `Rule.interpretation: str = ""` — the reading applied when the quote is not a definition;
  carried on the `Constraint` (`interpretation`) and the validation `Criterion`.
- `Profile.dimensions: DimensionRule` — `Listed(sizes)` or `Range(min_w, min_h, max_w, max_h,
  aspect)`; `Profile.sizes` stays the ordered list the solver tries.
- `Encoding.max_compression_ratio: float | None` — a byte floor of `w × h × 3 / ratio` at the
  output size, applied by the encoder (as a floor beside the readings' intersection) and
  reported by the validator as its own criterion, `compression_ratio`.
- `Requirement.profiles: tuple[str, ...] | None` — restricts a requirement to named profiles;
  `for_jurisdiction(code, profile=None)`.
- `build_constraints` gains a handler for `anatomical_head_height` (anatomical crown to
  anatomical chin), which is unavailable on every image this build can process, so a rule bound
  to it blocks the plan with the tier's reason.

**Profiles:** `us_visa_digital`, `us_passport_print`, `nz_nzeta`, `schengen_print`, each with
`jurisdiction`, `source`, `retrieved="2026-09-06"`, quotes, notes for every conflict named in the
source files, and `operations` (NZ and US: `replace_background` and `adjust_colour`
`prohibited` — "Do not change your photo using computer software, phone apps or filters";
`synthesize_pixels` `prohibited`; Schengen: unresolved — no EU sentence addresses editing).

**Advisories added to `requirements.py`:** US visa expression/background/head-covering/recency;
US passport expression (smile permitted), background, recency; NZ recency and "not a photo of a
photo"; EU recency and background. Each with quote and source.

## Design, concretely — 5b

Plugin layout per `plugin-dev:plugin-structure`; `SKILL.md` per `plugin-dev:skill-development`;
`docs/PUBLISHING.md`; `tests/test_version.py`; CHANGELOG `0.1.0`; README status and install
lines; tag `v0.1.0` after the docs commit. PyPI publication is David's action with his token;
the plan does not perform it.

## Verification

Per criterion above, from the reference measurements and from photos on disk with stubbed fits
as in Stages 3–4; real runs of the reference photo through `--out` for `us_visa_digital` and
`nz_nzeta` with the validation blocks recorded in the PR; the China run re-recorded to show it
is unchanged.

## Sequence

- [ ] This document, reviewed once by Codex (GPT-6 Astra, high); sources committed; README rows.
- [ ] Schema: `fraction_height`, `interpretation`, `dimensions`, compression floor,
      `Requirement.profiles`, anatomical head height.
- [ ] Profiles and advisories, with tests.
- [ ] Real runs; review under the two-pass rule; merge 5a.
- [ ] 5b: plugin and skill; version test; CHANGELOG and README; PUBLISHING.md; review; merge;
      tag `v0.1.0`; David publishes.

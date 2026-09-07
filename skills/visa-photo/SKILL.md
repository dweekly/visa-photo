---
name: visa-photo
description: This skill should be used when the user asks to "make this photo visa compliant", "crop this for a visa photo", "make a passport photo", "check my visa photo", "is this photo OK for my visa", or names a channel - "DS-160 photo", "NZeTA photo", "Chinese visa photo", "Schengen visa photo" - or wants a portrait cropped, resized or checked against a country's visa or passport photo rules. It runs the visa-photo CLI and reports its verdicts; it never crops by hand and never invents a specification.
version: 0.1.0
---

# visa-photo

Turn a portrait into a photo that satisfies one destination's visa or passport photo rules, or
report exactly why it cannot. The tool measures the face, solves the crop against the sourced
rules, writes the file, and re-measures the written file to check it. This skill exists to keep
an agent from doing by hand what the tool exists to prevent.

## Never do these

1. **Never crop, resize, rotate, recolour or retouch a photograph by hand** to meet a photo
   rule - not with ImageMagick, Pillow, `sips`, or any editor. Run the CLI. When it refuses,
   report the refusal and its reason verbatim; do not work around it.
2. **Never invent a specification.** `visa-photo --list-specs` is the complete list of
   destinations and channels. For anything not on it, say so, show the list, and offer the
   contribution path (a profile is built from quoted sentences on the official page; see
   `docs/STAGE5-PROFILES.md` in the repository). Reading a consulate page and synthesising
   numbers is the worst failure this project guards against.
3. **Never collapse `indeterminate` or `not_evaluated` into a pass.** Quote each criterion's
   verdict and detail. The aggregate is `passes_implemented_checks` at best - the tool cannot
   check background, sharpness, exposure or when the photo was taken - and the report lists
   what the applicant must still attest and what this build cannot assess. Say those.
4. **Never call a photo "compliant"**. Say what passed, what could not be checked, and what
   remains the applicant's word.
5. **Never guess the channel.** China alone has a digital photo and a paper photo with
   different aspect ratios and different rules. Ask which the user is submitting.

## Set up once

```sh
uvx --python 3.12 visa-photo --fetch-models
```

`--python 3.12` is required: the face landmarker aborts on later interpreters. The fetch is the
only network use; every later run is offline and no photo leaves the machine.

## Workflow

1. **Establish destination and channel.** Run `uvx --python 3.12 visa-photo --list-specs`.
   Match the user's request to one profile key; if two could apply, ask. Do not proceed on a
   country alone.
2. **Plan and write.**
   ```sh
   uvx --python 3.12 visa-photo PHOTO --spec KEY --out OUT.jpg --json > report.json
   ```
   HEIC input is fine. `--out` requires a digital profile; print profiles plan only and say so.
3. **Or check a photo the user already has**, without cropping it:
   ```sh
   uvx --python 3.12 visa-photo PHOTO --spec KEY --validate --json > report.json
   ```
4. **Read the exit code first**, then the report (`references/report.md`):

   | exit | meaning |
   |---|---|
   | 0 | done; advisories clear |
   | 1 | done, with advisory warnings on the input or the written file |
   | 2 | the input, or the written file, could not be measured (`error` says which) |
   | 3 | usage error |
   | 4 | no crop satisfies the profile - the report names the rules that conflict |
   | 5 | a crop exists but no file could be written within the encoding rules |
   | 6 | the written or validated file fails a rule or an encoding check |

5. **Report to the user** in this order: what was written (path, size, quality, bytes);
   `validation.aggregate` with every criterion's verdict and detail; `validation.attestations`
   as questions the user must answer; `validation.not_assessable` as checks nobody performed;
   every rule whose `interpretation` is non-empty, quoting the reading applied; advisory
   warnings from `preflight`. On exit 4, quote the plan's `attempts` and their reasons.

## What the report is

`--json` emits one envelope per run: `report_version`, `tool`, `error`, then `measurements`,
`preflight`, `plan`, `render`, `encode`, `validation` - each `null` when not reached. Rule
verdicts are `pass`, `fail`, `indeterminate` (the value, with its interval, straddles a bound,
or the source's own readings disagree) and `not_evaluated` (the measurement was unavailable or
the rule is not stated at this size). The interval is the model's disagreement with itself
between the source and the written file, not an accuracy claim. Details in
`references/report.md`; the profiles and what each can do in `references/profiles.md`.

## Additional Resources

### Reference Files

- **`references/report.md`** - the report envelope, field by field, with the verdict rules
- **`references/profiles.md`** - the six profiles, what each does, the readings and conflicts
  each records, and the sources they quote

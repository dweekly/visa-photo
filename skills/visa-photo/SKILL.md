---
name: visa-photo
description: This skill should be used when the user asks to "make this photo visa compliant", "crop this for a visa photo", "make a passport photo", "check my visa photo", "is this photo OK for my visa", names a channel ("DS-160 photo", "NZeTA photo", "Chinese visa photo", "Schengen visa photo", "2x2 passport photo"), or wants a portrait cropped, resized or checked against a country's visa or passport photo rules. Runs the visa-photo CLI and reports its verdicts; never crops by hand, never invents a specification.
version: 0.1.0
---

# visa-photo

Turn a portrait into a photo that satisfies one destination's visa or passport photo rules, or
report exactly why it cannot. The tool measures the face, solves the crop against the sourced
rules, writes the file, and re-measures the written file to check it.

## Never do these

1. **Never crop, resize, rotate, recolour or retouch a photograph by hand** to meet a photo
   rule - not with ImageMagick, Pillow, `sips`, or any editor. Run the CLI. When it refuses,
   report the refusal and its reason verbatim; do not work around it.
2. **Never invent a specification.** `visa-photo --list-specs` is the complete list of
   destinations and channels. For anything not on it, say so, show the list, and offer to
   open an issue at https://github.com/dweekly/visa-photo/issues that quotes the official
   page's sentences verbatim - every profile is built from such quotes (kept under
   `docs/sources/` in the repository). Reading a consulate page and synthesising numbers is
   the worst failure this project guards against.
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

`--python 3.12` is required: the face-landmark library publishes no wheels past 3.12, so the
package declares `requires-python <3.13` and will not install on a newer interpreter. The fetch
is the only network use; every later run is offline and no photo leaves the machine. If a run
exits 2 and `error` names a missing model, run `--fetch-models` and retry; do not run it before
every session.

## Workflow

1. **Establish destination and channel.** Run `uvx --python 3.12 visa-photo --list-specs`.
   Match the user's request to one profile key; if two could apply, ask. Do not proceed on a
   country alone.
2. **Plan and write** (a profile `--list-specs` does not mark "plans only"):
   ```sh
   uvx --python 3.12 visa-photo PHOTO --spec KEY --out OUT.jpg --json > OUT.report.json
   ```
   HEIC input is fine. Write the report beside the output, not into whatever project the
   session is in.
3. **Plan only** (a profile `--list-specs` marks "plans only"): omit `--out`. Passing `--out`
   or `--validate` with a print profile exits 3.
   ```sh
   uvx --python 3.12 visa-photo PHOTO --spec KEY --json > PHOTO.plan.json
   ```
   Report the plan; say no file was written.
4. **Or check a photo the user already has** (digital profiles only), without cropping it:
   ```sh
   uvx --python 3.12 visa-photo PHOTO --spec KEY --validate --json > PHOTO.report.json
   ```
5. **Read the exit code first**, then the report (`references/report.md`):

   | exit | meaning |
   |---|---|
   | 0 | done; advisories clear |
   | 1 | done, with advisory warnings on the input or the written file |
   | 2 | the input, or the written file, could not be measured (`error` says which) |
   | 3 | usage error |
   | 4 | no crop satisfies the profile - the report names the rules that conflict |
   | 5 | a crop exists but no file could be written within the encoding rules |
   | 6 | the written or validated file fails a rule or an encoding check |

6. **Report to the user** in this order: what was written (path, size, quality, bytes);
   `validation.aggregate` with every criterion's verdict and detail; `validation.attestations`
   as questions the user must answer; `validation.not_assessable` as checks nobody performed;
   every rule whose `interpretation` is non-empty, quoting the reading applied; advisory
   warnings from `preflight`. On exit 4, quote the plan's `attempts` and their reasons.

## What the report is

`--json` emits one envelope per run: `report_version`, `tool`, `error`, then `measurements`,
`preflight`, `plan`, `render`, `encode`, `validation` - each `null` when not reached. Verdicts
are `pass`, `fail`, `indeterminate` and `not_evaluated`; their definitions, and the interval
they are taken on, are in `references/report.md`. The profiles and what each can do are in
`references/profiles.md`.

## Additional Resources

### Reference Files

- **`references/report.md`** - the report envelope, field by field, with the verdict rules
- **`references/profiles.md`** - the six profiles, what each does, the readings and conflicts
  each records, and the sources they quote

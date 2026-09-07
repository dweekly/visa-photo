# The report

`visa-photo ... --json` writes one JSON object per run. Every key is present; a stage not
reached is `null`.

| key | what |
|---|---|
| `report_version` | `1` |
| `tool` | `version` and the model backends with their versions |
| `error` | `null`, or why a stage could not run (unreadable input; a written file that could not be measured) |
| `measurements` | the input photo: every measurement with its status, value and the gates behind it; `image` is the orientation-normalized size |
| `preflight` | advisories on the input: `mode` (`jurisdiction`, `generic`, `unseeded`), `jurisdiction`, and `findings` |
| `plan` | the crop chosen for `--spec`: `chosen` (size, scale, crop origin, slack per rule), every `attempts` entry (skipped / blocked / infeasible / ok with its reason), `applied_rules` (each rule's quote, bounds, unit, `interpretation`, `derivation`, source, retrieval date, and whether it was applied), `notes` |
| `render` | the operations performed on the pixels, in order, with status and parameters |
| `encode` | quality, bytes, the sizes tried, `earlier_sizes` that could not be encoded, `size` written |
| `validation` | the written file (after `--out`) or the given file (`--validate`) |

## `validation`

| key | what |
|---|---|
| `profile` | the profile key |
| `file` | path, format, mode, bits, `stored` and `measured` (after EXIF orientation) dimensions, bytes, `icc_state` and `icc_profile` |
| `uncertainty` | `delta` when a render's prediction supplied an interval; `none` for a point comparison |
| `criteria` | one per encoding check (`dimensions`, `format`, `colour` where the source requires one, `size_bytes`, `compression_ratio` where the source caps it) and one per rule |
| `aggregate` | `fails`, `incomplete`, or `passes_implemented_checks` - over implemented checks only |
| `attestations` | requirements only the applicant can answer (recency, head coverings) |
| `not_assessable` | requirements this build has no check for (background, sharpness, exposure, skin tone) |
| `policies` | what the channel permits of each operation |
| `measurements`, `preflight` | the validated file's own |

## A criterion

`key`, `kind` (`rule` or `encoding`), `verdict`, `observed`, `predicted` (the plan's value, after
a render), `delta` (`observed - predicted`), `lo`, `hi`, `lo_strict`, `hi_strict`, `unit` (output
pixels for a rule), `stated` (the bound as the source states it when it was converted, e.g. a
fraction of image height), `expected` (structured, for non-numeric checks), `detail`, `quote`,
`interpretation`, `derivation`, `source`, `retrieved`.

## Verdicts

- `pass`: the value, with its interval, lies inside the band.
- `fail`: the value, with its interval, lies outside it. A strict bound (`> 60`) excludes its
  endpoint.
- `indeterminate`: the interval straddles a bound, or the source's own readings disagree (a
  byte band under two meanings of "KB"; a rotated file whose stored and displayed dimensions
  differ). After a render, a large disagreement between prediction and observation is
  `indeterminate`, never `fail`, because the prediction satisfied the band.
- `not_evaluated`: the measurement was unavailable (its reason chain is in `detail`), or the
  rule is not stated at this file's size.

The interval is `|observed - predicted|`: one model's disagreement with itself at two scales.
It is self-consistency, not accuracy.

## Exit codes

0 done; 1 advisory warnings; 2 could not measure (input or written file); 3 usage; 4 no crop;
5 not written; 6 the file fails. Precedence: 2, 4, 5, 6, 1, 0.

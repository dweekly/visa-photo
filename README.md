# visa-photo

[![CI](https://github.com/dweekly/visa-photo/actions/workflows/ci.yml/badge.svg)](https://github.com/dweekly/visa-photo/actions/workflows/ci.yml) [![PyPI](https://img.shields.io/pypi/v/visa-photo)](https://pypi.org/project/visa-photo/)

Turn an ordinary portrait into a photo that satisfies a specific country's visa or passport
photo rules — and, just as importantly, tell you honestly when it can't.

**Status: 0.1.0.** Six profiles from four destinations, each built from sentences on the
official pages (kept verbatim under [docs/sources/](docs/sources/)). China's digital visa photo,
the US visa photo (DS-160) and New Zealand's NZeTA photo are cropped, written and checked end to
end; China's paper photo and the US printed passport photo are planned but not printed; the
Schengen photo is refused with the reason — no source defines its head size in a way this build
can measure — and advised on. What is next is in [ROADMAP.md](ROADMAP.md).

## Install and run

```sh
uvx --python 3.12 visa-photo --fetch-models        # once: model weights, the only network use
uvx --python 3.12 visa-photo --list-specs            # the destinations and channels that exist
uvx --python 3.12 visa-photo photo.heic --spec cn_visa_digital --out out.jpg
uvx --python 3.12 visa-photo out.jpg --spec cn_visa_digital --validate   # a photo you already have
```

`--python 3.12` matters: the face-landmark library publishes no wheels past 3.12, so the
package declares `requires-python <3.13` and will not install on a newer interpreter (its
newer major version aborts outright on macOS; see [NEGATIVE_RESULTS.md](NEGATIVE_RESULTS.md)).
After `--fetch-models` nothing leaves your machine. Add `--json` for the report described below.

**From Claude Code**, the repository is its own plugin marketplace:

```sh
claude plugin marketplace add dweekly/visa-photo
claude plugin install visa-photo@visa-photo
```

The skill it installs tells Claude to run the tool rather than crop by hand, to refuse
destinations it does not know rather than invent a specification, and to quote the report's
verdicts rather than summarise them as "compliant".

## The problem this solves

Visa photo requirements look simple and are not. A worked example, which is why this project
exists:

China publishes one requirements sheet containing **two** photo templates — a digital one
(354×472 to 420×560 pixels) and a paper one (33×48 mm). They have different aspect ratios, so
their measurements do not convert into each other. The digital template constrains **face width,
crown gap and eye line**. It sets **no head-height rule at all**. The paper template constrains
**head height in millimetres** and says nothing about pixels.

Build a digital photo using the paper template's head-height rule — a completely reasonable
mistake, and one a careful human made by hand before this repo existed — and you produce a face
that is too small, sized by a constraint that does not govern the file you are uploading.

That class of error is invisible without measurement, and it is what this tool exists to prevent.

## What it does

1. **Measure** the photo — eye centres, chin, crown, head pose — with stated uncertainty, and say
   *unavailable* rather than guessing when a measurement can't be made reliably.
2. **Solve** the crop geometry exactly against one country's rules, for one submission channel.
3. **Render** the output, honouring what that channel actually permits — background replacement is
   *prohibited* for some destinations, not merely unnecessary.
4. **Validate** the produced file per criterion, reporting pass, fail, indeterminate, or
   not-evaluated, each with a reason.

## Design commitments

These are the non-obvious ones, each earned rather than assumed.

**Absence is not a requirement.** If a destination's rules are silent about head height, the tool
does not fill the gap from ICAO or from another channel. Destination requirements, ICAO assessment
and composition preferences are three separately-evaluated layers, and only the first can fail
your photo.

**Official sources contradict themselves, and we record both readings.** China's own sheet gives
the crown gap as 10–70 px in its text and 10–85 px in its diagram. The US visa overview says head
size 22–35 mm where State's own template page says 25–35 mm. New Zealand publishes two different
file-size bands on three pages. We store competing interpretations as complete named rule sets and
never compose a specification nobody published by mixing them.

**Silence is a distinct answer.** `not_specified`, "qualitative requirement", "ambiguous
definition" and "explicitly unrestricted" are four different things, and the validator reports
"the reviewed sources state no bound" rather than passing quietly or inventing a threshold.

**Infeasibility is a first-class result.** When a face cannot satisfy a spec, the tool names the
conflicting rules and the size of the gap. Feasibility is decided exactly, never by sampling — a
sampled search can miss a narrow feasible window and report a conflict that isn't real.

**Everything runs locally.** Your photo is never uploaded. Model downloads and official-page
fetches are separate steps from photo processing, which works offline once installed.

## Not a legal guarantee

This tool reports what it measured against rules we transcribed from official sources on a stated
date. Requirements change, sources disagree, and consular officers exercise judgement. A passing
report is evidence, not a promise of acceptance.

## The report

`--json` emits one envelope for every photo run, whatever stage it reached:

| key | what |
|---|---|
| `report_version` | the envelope's version, `1` |
| `tool` | `version` and the model backends with their versions |
| `error` | null, or why a stage could not run |
| `measurements`, `preflight` | the input photo: every measurement with its gates, and the advisories |
| `plan` | the crop the solver chose for `--spec`, or why none exists |
| `render`, `encode` | what was done to the pixels and how the file was written |
| `validation` | the written file (after `--out`) or the given file (`--validate`): its own facts, measurements and advisories, one criterion per rule and per encoding check with verdict, observed value, the plan's prediction and their delta, and an aggregate over implemented checks only, beside the attestations still required and what this build cannot assess |

A stage not reached is `null`. Verdicts are `pass`, `fail`, `indeterminate` (the value, with its
interval, straddles a bound — or the source's own readings disagree) and `not_evaluated` (the
measurement was unavailable, or the rule is not stated at this file's size). The interval is the
model's disagreement with itself between the source and the written file, not an accuracy claim.
Exit codes are in `visa-photo --help`.

## Documentation

| Document | What it is |
|---|---|
| [docs/PLAN.md](docs/PLAN.md) | The full design and staged delivery plan. Fresh as of 2026-09-06. |
| [docs/STAGE2-SOLVER.md](docs/STAGE2-SOLVER.md) | Working plan for the geometry solver. Fresh as of 2026-09-04. |
| [docs/STAGE1B-PRECONDITIONS.md](docs/STAGE1B-PRECONDITIONS.md) | Gate graph, registry and sequence for precondition-driven measurement. Fresh as of 2026-09-06. |
| [docs/STAGE3-RENDER.md](docs/STAGE3-RENDER.md) | Working plan for rendering and encoding: what is in, what is out and why. Fresh as of 2026-09-06. |
| [docs/STAGE4-VALIDATE.md](docs/STAGE4-VALIDATE.md) | Working plan for validating the written file and the report contract. Fresh as of 2026-09-06. |
| [docs/STAGE5-PROFILES.md](docs/STAGE5-PROFILES.md) | Working plan for the US, New Zealand and Schengen profiles, the Claude skill, and the 0.1.0 release. Fresh as of 2026-09-06. |
| [docs/PUBLISHING.md](docs/PUBLISHING.md) | How a release is cut: docs first, one version, the wheel checked outside the checkout, then the tag and PyPI. Fresh as of 2026-09-07. |
| [skills/visa-photo/SKILL.md](skills/visa-photo/SKILL.md) | The Claude Code skill: what it must and must not do with this tool. Fresh as of 2026-09-07. |
| [docs/sources/](docs/sources/) | Verbatim quotations from the official pages each profile is built from, with URLs and retrieval dates. Fresh as of 2026-09-06. |
| [NEGATIVE_RESULTS.md](NEGATIVE_RESULTS.md) | Approaches that failed, so they aren't retried. Fresh as of 2026-09-04. |
| [ROADMAP.md](ROADMAP.md) | Stack-ranked next steps. Fresh as of 2026-09-06. |
| [CHANGELOG.md](CHANGELOG.md) | User-facing changes per release. |
| [THIRD_PARTY_LICENSES.md](THIRD_PARTY_LICENSES.md) | Licences of bundled models and libraries. Fresh as of 2026-09-04. |

## Licence

MIT — see [LICENSE](LICENSE). Model weights carry their own licences; see
[THIRD_PARTY_LICENSES.md](THIRD_PARTY_LICENSES.md).

# visa-photo

Turn an ordinary portrait into a photo that satisfies a specific country's visa or passport
photo rules — and, just as importantly, tell you honestly when it can't.

**Status: early. Stage 1 of 5 complete** — it measures a portrait and checks it against sourced
requirements, but does not yet produce a photo. See [ROADMAP.md](ROADMAP.md).

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

## What it will do

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

## Documentation

| Document | What it is |
|---|---|
| [docs/PLAN.md](docs/PLAN.md) | The full design and staged delivery plan. Fresh as of 2026-09-06. |
| [NEGATIVE_RESULTS.md](NEGATIVE_RESULTS.md) | Approaches that failed, so they aren't retried. Fresh as of 2026-09-04. |
| [ROADMAP.md](ROADMAP.md) | Stack-ranked next steps. Fresh as of 2026-09-06. |
| [CHANGELOG.md](CHANGELOG.md) | User-facing changes per release. |
| [THIRD_PARTY_LICENSES.md](THIRD_PARTY_LICENSES.md) | Licences of bundled models and libraries. Fresh as of 2026-09-04. |

## Licence

MIT — see [LICENSE](LICENSE). Model weights carry their own licences; see
[THIRD_PARTY_LICENSES.md](THIRD_PARTY_LICENSES.md).

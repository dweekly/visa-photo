# Stage 2 — spec schema and geometry solver

Working plan for the stage. Cited from [PLAN.md](PLAN.md), which holds the overall design and
the sourcing notes. Fresh as of 2026-09-04.

**Where:** worktree `~/dev/visa-photo-solver`, branch `stage2-solver`, stacked on
`stage1-measurement`. Tracking PR opened with the first commit.

## What this stage delivers

Given measurements from Stage 1 and a destination profile, decide **exactly** whether a
compliant crop exists, produce the best one when it does, and name the conflicting rules when
it does not.

Nothing here renders pixels. That is Stage 3.

## The maths, settled

Unknowns are the scale `s` and the crop origin. Substituting `u = cy0·s` and `v = cx0·s` makes
every constraint **linear in `(s, u, v)`**, so each is stored as

    lo ≤ a·s + b·u + c·v + k ≤ hi        (lo or hi may be absent)

| Rule | a | b | c | k |
|---|---|---|---|---|
| head height in band | `HH` | | | |
| head width in band | `HW` | | | |
| crown gap from top | `crown_y` | −1 | | |
| eye line from bottom | `−eye_y` | +1 | | `OH` |
| eye midpoint horizontal | `eye_x` | | −1 | |
| crop inside source, vertical | | +1 | | (and `s·H − u ≥ OH`) |
| crop inside source, horizontal | | | +1 | (and `s·W − v ≥ OW`) |

**No constraint couples `u` and `v`.** Given `s`, the vertical and horizontal problems are
independent one-dimensional interval intersections.

### Feasibility is decided exactly, never sampled

For a constraint containing `u`, rearranging gives a lower bound `Lᵢ(s) = pᵢ + qᵢ·s` or an
upper bound `Uⱼ(s)`. A feasible `u` exists for a given `s` exactly when

    Lᵢ(s) ≤ Uⱼ(s)   for every pair (i, j)

and each such pair is itself a linear inequality in `s`, contributing an interval. Intersecting
those with the `s`-only bands, and doing the same for `v`, yields the exact feasible set of `s`
as a single interval. Dense sampling can miss an arbitrarily narrow feasible window and report
a conflict that does not exist, which is the worst failure available to a tool whose headline
feature is honest conflict reporting.

### Choosing among feasible scales

Maximize the minimum normalized slack: find the largest `t` with

    aᵢ + t·dᵢ ≤ fᵢ ≤ bᵢ − t·dᵢ

for every two-sided band, with `dᵢ` a documented positive normalization. Source-containment
stays a hard constraint and earns no reward, so a crop is not pushed toward the middle of the
photograph for its own sake.

The value function is **concave in `s`** — for fixed `s` the inner problem is a max of a min of
linear functions, and its optimum is concave in the parameter — so ternary search converges to
the true optimum rather than approximating it. Note the distinction from the paragraph above:
sampling is unsound for deciding *feasibility*, and perfectly sound for *optimizing* a concave
objective once feasibility is settled exactly.

Ties break deterministically, so the same photograph and profile always give the same crop.

### Output size is an outer loop

China permits any size from 354×472 through 420×560, and failure at one size must not be
reported as failure at all sizes. The solver runs per permitted size and reports the best
feasible one. China's pixel figures are stated "as an example" at 354×472; the profile records
that reference size and the solver **does not** rescale them to other sizes without an
explicitly named interpretation policy.

### Absent and one-sided bounds are first class

China's digital channel states **no head-height rule at all**. A missing bound must not become
`(0, ∞)` folded in silently, nor inherit from ICAO. It simply contributes no constraint, and
the report says the rule was not evaluated because the source states none.

## Infeasibility must explain itself

Four failure modes, distinguished because they call for different user action:

| Reported as | Means |
|---|---|
| `conflicting_requirements` | two published rules cannot both hold for this face, with both intervals and the gap |
| `source_too_small` | the crop would leave the photograph; a different photo is needed |
| `insufficient_resolution` | the output size cannot be met without upscaling |
| `no_permitted_output_size` | every permitted size failed, with the reason per size |

Every derived bound carries the id of the rule that produced it, so an explanation names actual
rules rather than saying "infeasible".

## Acceptance criteria

1. Feasibility decided by interval algebra, with a test asserting a singleton feasible interval
   is found.
2. The 2026-09-04 wrong-channel case reproduced: `cn_visa_digital` has no head-height bound, and
   the solver must not invent one.
3. Infeasibility names the conflicting rules and the size of the gap.
4. The horizontal-centring counterexample from review (source 1000 wide, output 600, `s`=1, eye
   midpoint 280) yields a feasible crop at origin 0, not a rejection.
5. Same input, same output, every run.
6. Solving is pure: no image decoding, no model calls, no file access.

## Sequence

- [ ] Profile schema: channels, permitted output sizes, typed constraints with provenance.
- [ ] Linear constraint representation and exact interval feasibility.
- [ ] Slack objective and deterministic selection.
- [ ] Infeasibility diagnostics naming rules.
- [ ] `cn_visa_digital` and `cn_visa_paper` profiles, from the quotes already transcribed.
- [ ] CLI: `visa-photo plan PHOTO --spec cn_visa_digital` printing the crop or the conflict.

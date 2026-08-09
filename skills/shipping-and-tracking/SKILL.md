---
name: shipping-and-tracking
description: Use after a SHIP verdict, when parameters are about to be frozen, when a position list or order is about to be produced, when a tracking period has closed and needs reconciliation, and when live or paper results differ from the backtest. Also use whenever a result is presented to a human — closing a round, reporting a sweep or random control, or citing an out-of-sample number — since the figure requirements apply to every report, not only to shipped strategies.
---

# Shipping and Tracking

## Overview

Two things happen at the end of a research loop, and both are places where
something that looks like evidence turns out not to be.

**The evidence package.** A chart in quantitative research has one
legitimate job: make a specific claim falsifiable at a glance. Almost every
chart people produce does the opposite — it makes a claim *persuasive* at a
glance, the same operation with the sign flipped.

**The tracking record.** Once frozen and live, the strategy produces the one
kind of evidence a backtest cannot: results computed on data that did not
exist when the decision was made. Everything before that is retrospective
simulation. A tracking file that has never had a realized return actually
written into it is not a record, no matter how long it has existed.

The order below is the order of the work: assemble the evidence, freeze,
confirm the order with the user, then reconcile one period at a time.

## The Iron Law

```
A FIGURE THAT CANNOT FALSIFY A NAMED CLAIM DOES NOT SHIP,
AND A DEVIATION MEANS NOTHING UNTIL IT IS SPLIT INTO DATA, EXECUTION, AND STRATEGY
```

Both halves are definitions rather than findings and cost nothing to apply
anywhere, but the *specific* figures and layer weightings below reflect one
setting. Which reconciliation layer dominates depends heavily on account
size: at small scale, whole-lot rounding and idle cash usually dominate; at
institutional size, market impact can dominate instead. Measure your own
layer-2 budget rather than assuming the ranking transfers.

Name the claim in the caption, not the metric: "cumulative return of
strategy A" is a metric, "the advantage is not rebalance-date luck" is a
claim. And investigate deviations in the stated order, because data problems
invalidate conclusions, execution frictions are bounded and subtractable,
and only what remains after both says anything about the strategy.

## Part A — the evidence package

### The anti-pattern: the equity curve

The cumulative return curve is the least informative figure in quantitative
research and the one that appears in every report. It cannot distinguish
skill from a favorable window, or show whether the result survives a
different rebalance date, whether the parameters sit on a plateau, or
whether the benchmark it beat was itself a fluke.

The test that removes it is one sentence, applied to every figure: **"this
chart would look different if ___ were false."** If you cannot complete it,
the figure is decoration. Applied honestly it deletes the equity curve from
most reports and adds five or six figures nobody drew. Two curves overlaid
on identical costs and window orient a reader, but they are not evidence and
never figure one.

### The required set

Nine figures, each mapped to a claim it can kill. Produce the ones that
apply.

| # | Figure | Claim it can falsify | Read it for |
|---|---|---|---|
| 1 | Backtest vs OOS percentile scatter from a random control, incumbent highlighted, both medians drawn | "Hindsight bias explains our advantage" | The quadrant — bias is high-x, low-y. Annotate the rank correlation; near zero, the blob is the finding |
| 2 | Parameter grid heatmap, chosen cell marked | "These parameters sit on a plateau" | A bright *region*, not a bright square. A cell on the range edge means you have not found the plateau |
| 3 | Multi-offset dispersion, sorted by mean, coloured by σ | "The advantage is not rebalance-date luck" | Whether the spread exceeds the edge claimed |
| 4 | Pareto frontier along the swept lever, target and risk budget drawn | "The target is achievable" | Whether the target sits on the curve |
| 5 | Per-period increment bars, zero line emphasized | "The edge is not from one stretch of market" | Count the bars. Most positive plus one explainable negative is structural; one huge bar is a window |
| 6 | Correlation matrix, average correlation and effective independent count in the title | "We tested a diverse set of ideas" | Whether the effective count is close to the nominal count |
| 7 | Exposure profile: average, bear-year average, share of months below a threshold | "We need the ability to hold cash" | Whether the capability already exists. Draw it before adding any defensive layer |
| 8 | Year-by-year grouped bars against the passive control | "We beat buy-and-hold" | The composition the summary row hides |
| 9 | Rolling-window benchmark distribution, your evaluation window marked | "The benchmark is a stable bar" | How much of your result is the market |

Figure 9 belongs at the front rather than the back: where a benchmark's
rolling-window dispersion is several times any alpha the strategies produce,
where your evaluation window sits in that distribution dominates every
comparison made afterwards. Optional additions: a **realization-rate** chart
per strategy family, and an **underwater plot** when the audience's binding
constraint is drawdown.

### Four annotations, on every figure

Without these a figure is not comparable to any other, including your own
from last week.

1. **Sample window**, exact start and end dates.
2. **Cost tier** — baseline or double, with the one-way rate.
3. **Offset basis** — single offset (and which) or staggered mean over
   which.
4. **Control group by name** — the incumbent and/or passive control, not
   "the baseline."

Two more when applicable: whether drawdown is within-window or continuous
across the holding period, and whether returns are net of costs. The
drawdown one is not hypothetical — reporting the within-window figure while
a reader is thinking about the continuous one is a gap large enough to
change whether a strategy appears to have met its risk budget.

**Never annualize a window shorter than a year**, in a chart or a table.
Annualization multiplies signal and noise together, and a reader will
compare the result against multi-year numbers on the same axis. Label
partial-period panels "cumulative, N days" and never place one beside
annualized bars.

### Presenting to a human

**Conclusion first, then the figure.** State the verdict in one sentence,
then show the chart that could have refuted it. A gallery that invites the
reader to draw conclusions outsources the judgment you were asked to make.

**Each figure must stand alone**, because it will be screenshotted out of
context: the title states the claim, the caption carries the four
annotations, axis labels avoid private abbreviations. Put the falsification
verdict in the title, *computed from the data*, so the figure cannot
silently contradict its caption. Fix colour semantics report-wide, and save
every figure beside the JSON or CSV it came from, named identically — a
figure you cannot regenerate is not evidence.

**Lead with what would change the reader's decision.** If the answer is
"nothing, the frontier does not contain your target," the frontier plot is
figure one and the equity curves do not appear. And **put the honest
boundary in the same figure as the good news**: a caption reporting a design
principle at a high percentile against a random control, then adding how
many random draws still did better, is what makes the other percentiles
believable.

## Part B — freeze, then confirm the order

### What freezing means

Freezing means the strategy stops being a research object. Write the
configuration into the tracking file itself, with a freeze date and an end
date, so it cannot drift silently. Freeze the whole list; anything omitted
will be re-tuned without you noticing.

| Category | Examples |
|---|---|
| Universe | Every eligible instrument, by identifier |
| Weighting rule | The formula, its lookback, any per-instrument cap |
| Fixed-weight slots | Slot and weight |
| Rebalance schedule | Cadence and the offset within the period |
| No-trade band | The drift threshold below which you do not trade |
| Cost model | One-way rate, and what it applies to |
| Vehicle and data source | Market, account type, data chain, as-of policy |

**How long.** Six months minimum; twelve is where inference becomes
possible. Anchor the end date to the review schedule, not to convenience.

**During the freeze you record; you do not adjust** — not the weights, not
the lookback, not the universe. If a genuine defect appears, fix it, note
the fix, and restart the clock on the affected evidence. "It underperformed
this month" is not a defect.

The file's `meta` block holds the champion id, the vehicle,
`params_frozen_at`, `frozen_until`, `true_oos_start` equal to the freeze
date, `frozen_params` covering every category above, a `prereg` object with
`review_dates`, `trigger_conditions` and `not_failure`, and a `disclaimer`.
Records append below.

The disclaimer is not boilerplate; it travels with every number quoted out
of the file: *all pre-freeze "out-of-sample" figures are retrospective
backtests computed with that data visible, and genuine out-of-sample
evidence accrues from `params_frozen_at` forward.*

**An unfrozen strategy does not get a position list.** If any parameter is
still being chosen, say so and stop: the list would be a backtest artifact
wearing a timestamp.

### The order is a hard stop

Producing the order list is autonomous. **Placing it is not.** A real order
is one of the six conditions that require interrupting the user, and no
written rationale substitutes for confirmation. → `using-autoquant`

Present the position list with the frozen configuration, the honest
expectation stated separately from the backtest number, and the not-failure
list. Then wait.

### Pre-register the verdict lines, in both directions

Before the first period, write down what counts as failure **and what does
not**. The second list is the one people skip, and without it the first
uncomfortable month becomes a reason to abandon a strategy behaving as
designed.

**Trigger conditions** — each triggering a *review*, not an automatic exit.
Three shapes cover most cases: cumulative return trailing the backtest basis
by a stated margin over several consecutive months (investigate execution
and data first); a rolling twelve-month return below zero *while* the
passive control is clearly positive (investigate whether the assumptions
still hold); and tracking-period drawdown exceeding the backtest worst by a
stated buffer.

**Not failure** — each entry must be backed by evidence gathered *before*
the freeze, or it is an excuse waiting to be used. A single month behind the
benchmark, because monthly dispersion across rebalance offsets is large by
construction. A diversifier slot losing money on its own, *if* it was stress
tested under an assumed zero future return. Trailing a pure-equity portfolio
in a bull market, *if* the per-regime test showed the defensive component
positive in most regimes with the negative one being exactly this case. The
conditional licenses the entry.

**Nothing should fire before twelve months**, and the reporting script
should print that refusal with the earliest meaningful review date rather
than leaving it to judgement in the month someone is impatient.

### Snapshot, with prices

Reconciliation is impossible without a per-period snapshot. Per position:
target weight, **price at signal time**, whole-lot share count, amount,
actual weight after rounding, signal inputs used. Per record: capital,
invested amount, cash residual, signal date, data as-of date, generation
timestamp. The price is what makes layer 1 possible — without it, a later
data correction silently rewrites your tracking history and you cannot tell.

## Part C — the three-layer reconciliation

Run it every period, including the periods where results look fine.
Reconciliation that runs only when you are worried has a selection bias, and
the first one is what calibrates the execution layer and surfaces
snapshot-format mistakes. Paper tracking counts, provided it is reconciled.

### Layer 1 — data

Compare the price recorded in the snapshot against what the database now
reports for that date, flagging any relative difference above a tolerance
wide enough to absorb legitimate re-basing of adjustment factors and tight
enough to catch real edits. Any breach is serious: correcting genuine
historical errors mid-project can require re-running every result computed
before the correction.

### Layer 2 — execution

Quantify the frictions the backtest does not contain. Whole-lot rounding
produces weight drift — the largest gap between actual and target weight —
and the unallocated remainder sits as idle cash. Both scale inversely with
account size, so report them rather than assuming they are negligible, and
name the worst offender, usually the highest-priced instrument.

### Layer 3 — strategy

Three numbers per period, same window. **Paper return** values actual share
counts at both ends, adds the untouched cash residual, subtracts cost on
traded value, and divides by capital. **Backtest-basis return** is the
cost-adjusted weighted sum of asset returns at target weights, with no
rounding or residual. **Controls** are the passive control on the same
universe plus a broad market index.

The first two differ by the execution difference, which should be small and
fully explainable by layer 2. What remains, measured against the controls,
is the strategy's own contribution; flag it past a stated threshold. Without
the separation, lot rounding gets recorded as decay and a working strategy
can be retired for the wrong reason.

### The reconciliation formulas need unit tests

If the formulas are biased, every divergence you find is a false signal and
every real one is masked. Six tests cover it.

| Test | Asserts |
|---|---|
| Frictionless convergence | At very large capital, rounding vanishes and paper return converges to the backtest basis |
| Paper-return identity | Paper return **exactly** equals Σ(actual weight × asset return) − Σ(actual weight) × cost |
| Friction is measurable | At small capital, idle cash > 0, and both idle cash and weight drift exceed the large-capital case |
| Cost is deducted | Zero-cost return exceeds default-cost return by exactly cost × Σweights |
| Missing instrument returns `None` | Never silently zero — a silent zero produces a fake reconciliation |
| Single-asset cross-check | A 100% position equals raw price change minus cost, computed the most naive way available |

**Tests must not depend on market direction.** An identity test that
asserts a small account's paper return will be *lower* than the backtest
basis, on the reasoning that idle cash is a drag, can fail in a falling
market — idle cash is protection there, not drag. An identity that holds
regardless of direction is both stronger and stable; a directional
assumption baked into a test will fail, or worse pass for the wrong reason,
whenever the period changes.

### Execution risks a backtest cannot show you

Tracking is the only source of data on these, so record them as they occur:
purchase quotas that stretch position building over weeks; minimum holding
periods and short-holding fees, hard constraints that belong in the engine;
premium to fair value, which can account for part of a measured vehicle
advantage and reverses if you buy at a wide one; and settlement lag, which
belongs in a pre-ship sweep so you later know it is not the explanation for
a divergence.

### Reading a short tracking record

A partial year is weak evidence by construction, so report cumulative
return and send a candidate that wins live while losing in backtest to the
watchlist rather than into production. What a short window *can* do is
falsify: live behaviour contradicting the backtest promise in a clean,
monotone way is informative in a few months. Asymmetry of evidence is
legitimate here, but state which direction you are using it in and check
that you would have accepted it pointing the other way.

## Common rationalizations

| Thought | What it actually is |
|---|---|
| "The equity curve shows it works." | It cannot. Complete "this would look different if ___ were false" and see what you get. |
| "The table already has the numbers." | Tables hide shape. An isolated peak around the best grid cell is obvious as a heatmap and invisible sorted by rank. |
| "One offset is enough for the chart." | Date sensitivity between two candidates can differ by an order of magnitude, and it isn't visible at a single offset. |
| "I will annualize the partial year so it is comparable." | That is the opposite of comparable. |
| "More charts make it more thorough." | Nine falsifying figures is a complete report. Twenty descriptive ones is a slide deck. |
| "We have a tracking file, so we are tracking." | A file with every realized-return field left null is not a record. Tracking is the reconciliation, not the file. |
| "The holdout period is out-of-sample." | Only if its data was unavailable while you experimented. Otherwise it is a retrospective backtest and must be labelled one. |
| "It is behind the backtest, the strategy is decaying." | Split the layers first. Lot rounding and idle cash are measurable and bounded. |
| "The data cannot have changed." | It changes whenever you fix an error or re-fetch. That is why the snapshot stores prices. |
| "We will adjust the weights slightly, it is still the same strategy." | Then it is not frozen, and the out-of-sample clock restarts. |
| "This month was bad, we should reconsider." | Check the not-failure list you wrote before the freeze. It exists for this moment. |
| "The formula is simple, it does not need tests." | An untested formula with a hidden directional assumption can fail on real data. |

## Handoff

**Artifacts this skill must have produced:**

- `reports/<round>/` — the applicable figures, each with its claim in the
  title and the four annotations in the caption, saved beside the JSON or
  CSV that generated it
- `tracking/live_tracking.json` — every category in the freeze table, the
  freeze and end dates, the disclaimer, and `prereg` with both the trigger
  conditions and the not-failure list
- `tracking/orders_<date>.json` — the snapshot with price at signal time,
  share counts, actual weights, and cash residual
- `tracking/reconcile_<period>.md` — all three layers, with the layer-2
  budget measured for this account size and the layer-3 residual against the
  controls
- `tests/test_reconcile.py` — the six tests, passing
- `docs/research_log.md` — the reconciliation outcome, including periods
  where nothing happened

**Before placing any order:** stop and confirm with the user. This is one of
the six interrupt conditions and it is never waived.

**If the strategy is not frozen:** stop, do not produce a position list,
name the parameter still being chosen, and route back to `judging-the-round`.

**If a layer-1 check fires:** stop and escalate to `building-the-foundation`.
Every conclusion built on the modified data has to be recomputed before
tracking continues, and results already reported may need correcting —
itself an interrupt condition.

**If a pre-registered trigger fires after the minimum period:** load
`judging-the-round` with the reconciled record as new evidence. Live decay is
the one evidence class a backtest cannot produce, and it re-enters the loop
as an ordinary input to the verdict, not an automatic exit.

**Otherwise:** the loop is complete. Keep reconciling on schedule;
out-of-sample evidence accrues one period at a time.

## Related

- [Reporting checklist](../../references/metrics-and-traps.md#reporting-checklist)
  — the same annotations, in checklist form
- `templates/tracking/` — the snapshot writer and the six reconciliation
  tests
- `running-experiments` — produces the offsets, windows and cost tiers every
  caption must cite
- `judging-the-round` — where SHIP arrives from, and where a fired trigger
  hands control back
- `building-the-foundation` — what a layer-1 breach escalates into

---
name: running-experiments
description: Use before implementing any strategy idea, before adding a round of experiments, whenever you are about to sweep a parameter, whenever a candidate set has more than about five members, whenever the previous round was rejected and you need to decide what to try next, whenever a strategy has produced a number, and always before a comparison, replacement, or adoption decision. Also use when re-examining a shelved candidate under a changed objective, or when the strategy contains a gate, circuit breaker or threshold trigger. Produces the search plan, the pre-registered decision line, and the validated result.
---

# Running Experiments

## Overview

This skill has two halves that belong together because one produces what the
other has to validate.

**Where candidates come from.** This is the part most quant material skips.
The literature is dense on how to validate a strategy and nearly silent on
how to generate one, so the default behaviour — for a person and much more so
for an agent — is to take the first idea that works and sweep its parameters.
That produces a large number of results and a very small amount of evidence.
The distinction this half runs on: **a parameter value is a variant, a
mechanism is a hypothesis.** Lookback 60 versus 120 days are two variants of
one hypothesis, which is that recent relative strength persists. If that
hypothesis is wrong in your universe, no lookback rescues it. Rounds are
expensive; spend them on hypotheses.

**Whether the result means anything.** A single full-history backtest
produces one number, and one number cannot be argued with. That is not a
strength. Every question you would want to ask — did it work in more than one
regime, does it depend on which day of the month you trade, does it survive a
cost assumption you are unsure of — has been averaged away before you saw the
output. This half replaces the one number with a structure: three report
layers, two orthogonal stress axes, and an explicit statement of what the
whole apparatus still leaves open.

The operating principle throughout the second half: report the mean across
rebalance offsets as the result and the spread across them as the error bar.
An edge smaller than its own error bar is not an edge.

## The Iron Law

```
TEN VALUES OF ONE PARAMETER ARE ONE EXPERIMENT.
A SINGLE-REBALANCE-DATE RESULT CARRIES REAL, MEASURABLE LUCK.
```

The condition that makes both halves of this law necessary is the same, and
it is invisible from the inside: each new variant genuinely feels like a new
idea to whoever wrote it, and a single backtest run genuinely feels like a
result. Measurement is the only defence against both. Compute your own
effective independent count before concluding you have searched broadly, and
measure your own dispersion across rebalance offsets before concluding an
edge is real — neither number transfers from a different program, and
neither trigger threshold you set elsewhere should be assumed to transfer
either.

## Part A — mapping the mechanisms

### A1. Draw the map before the first run

Write down the dimensions your strategy space actually has, and for each one
list **categories** rather than values. The point of the exercise is to see
how much of the space you have never visited.

| Dimension | Categories, not parameter values |
|---|---|
| **Signal family** | cross-sectional momentum · time-series momentum · mean reversion · volatility / risk state · carry or yield · macro regime · *no signal* (static allocation) |
| **Weighting** | equal · inverse-volatility · risk parity · signal-proportional · fixed strategic weights |
| **Risk layer** | none · drawdown circuit breaker · volatility targeting · permanent ballast sleeve · explicit hedge leg |
| **Rebalance trigger** | fixed calendar (monthly / biweekly / weekly) · threshold on drift · event-driven |
| **Universe shape** | narrow and homogeneous · broad cross-asset · tiered (pick category, then instrument within it) |
| **Concentration** | concentrated (1–3 holdings) · moderate (5–8) · fully diversified |
| **Composition** | one mechanism · orthogonal blend of two from *different* families · sequential (one mechanism selects, another sizes) |

The composition row is easy to skip and shouldn't be: a fixed-weight blend of
two mechanisms from different families, combined at a constant ratio, is
routinely a larger improvement than another round of signal tuning inside
one family — provided the blend ratio is fixed rather than made dynamic, and
the two legs genuinely fail at different times rather than merely looking
uncorrelated in one sample.

Two things usually become obvious immediately once the map is drawn. First,
most programs have explored one cell of the signal column and every value in
the concentration column, which is the shape that yields an effective
independent count near one. Second, the `no signal` entry is not a joke — a
static allocation is a legitimate hypothesis, it is the one the passive
control tests, and it can beat every active strategy tried against it.

Include the dimensions you have decided **not** to vary, and say why. A
dimension excluded for a stated reason is a scoping decision; a dimension
excluded silently is a blind spot that will show up later as an unexplained
ceiling.

### A2. Audit the constraints, because that is usually where the leverage is

Step A1 maps the space of strategies. This step questions the walls of the
room.

Strategy design searches inside a constraint set. If that set has flattened
the feasible region — long-only, fixed universe, no leverage, and every
candidate is the same long portfolio at a different exposure level — then
searching it carefully only establishes that you searched the same thing
repeatedly. No mechanism recovers a degree of freedom the constraints
removed.

This is not a theoretical concern. Ranked by size, changes to the *walls* of
the room — which vehicle you execute through, which asset classes are
eligible, which self-imposed rules actually need to hold — routinely dominate
changes to the *strategy inside* the room. A vehicle change with identical
signals, a widened universe, or a dropped self-imposed constraint can each
move the objective by more than several rounds of signal, weighting and
risk-layer variation combined.

**The procedure.**

1. **List every constraint, including the ones you did not notice you were
   assuming.** A starting checklist: execution vehicle and account type;
   investable universe; direction (can you be short); leverage; rebalance
   frequency ceiling; how money arrives; which information sources you may
   use (price only, or also volume, premium/discount, positioning, macro);
   minimum holding period; tax and fee treatment.

2. **Label each one.** *Hard* — fixed by regulation, account permissions or
   the nature of the capital. *Soft* — habit, convenience, or "I assumed it
   had to be this way." *Unverified* — you do not actually know which of the
   two it is.

3. **Start with the unverified ones.** Checking a constraint usually costs
   one conversation, one look at an account, or one search of a rulebook.
   That is one or two orders of magnitude cheaper than a round of
   experiments.

4. **Confirm an instrument exists before designing anything that needs it.**
   A relaxation that looks attractive on paper can turn out to have no
   available instrument under the relevant regulatory regime — check
   feasibility before spending design effort.

The output is a table — one row per constraint, its label, and what the
strategy space would gain if it were relaxed. Together with the mechanism
map, this is the search plan.

**The counterintuitive corollary.** If your effective independent count is
low (Step A4), do not respond by inventing more mechanisms. Audit the
constraints. A low independent count is a property of the feasible region,
not a shortage of imagination, and adding another mechanism inside an
unchanged room produces another near-duplicate.

### A3. Rank the dimensions before optimizing inside any of them

Do not start with the dimension you find most interesting. Start by
measuring which dimension moves your objective at all.

The procedure is deliberately crude, because its output is an ordering and
not an estimate:

1. Fix a **centre configuration** — one defensible category per dimension.
   It does not need to be good.
2. Change **one dimension at a time** to each of its other categories,
   holding everything else at centre. One run each.
3. Record the objective metric for every run.
4. Rank the dimensions by the spread they produced.

Six dimensions with two or three alternatives each is on the order of a
dozen runs — cheaper than one round of parameter sweeping, and it tells you
where the leverage is instead of how one cell behaves.

**Why this ordering matters more than it sounds.** A dominant lever — one
dimension whose effect exceeds the combined effect of everything else — is
common, and it is easy to spend many rounds refining a low-leverage
dimension purely because it happens to be the most interesting one, when a
dozen cheap runs would have said otherwise.

**How to tell a real dominant lever from a lucky one.** Three checks, all
checkable independent of how large the effect looks:

- **The response is monotone and smooth** across the swept range. Noise does
  not produce a clean exchange rate between two metrics.
- **The optimum is interior.** A genuine trade-off has a turning point
  inside the range, not at an edge.
- **A one-dimensional sweep explains more than any mechanism substitution
  does.** That is what "dominant" means, and it is a comparison you can only
  make after this ranking step rather than a claim you can make about your
  favourite dimension in advance.

The corresponding warning: **if your best value sits at the edge of the
range you swept, you have not found a peak, you have found the edge of your
grid.** Widen it until the objective turns, or state explicitly that the
optimum is unlocated. An edge optimum is also the signature of a constraint
doing the work — which sends you back to Step A2.

Two cautions on reading the ranking:

- A dimension with a small spread is not proven irrelevant, only irrelevant
  *near the centre configuration*. Interactions exist. Record it as "small
  effect at centre" rather than "no effect."
- A dimension with a large spread is where your **overfitting risk** also
  concentrates, because it is where a lucky draw has the most room to look
  like a finding. High leverage raises the standard of evidence rather than
  lowering it.

### A4. Measure what you have actually searched

Before adding a round, compute the effective independent count of the
candidates you already have. It is cheap and it changes decisions.

1. Collect the daily net return series of every candidate.
2. Compute the correlation matrix, take its eigenvalues, and evaluate
   `N_eff = (Σλ)² / Σλ²`. The average-correlation approximation
   `N / (1 + (N−1)·ρ̄)` is close enough for the decision.
3. Repeat on **exposure-normalized** series: divide each day's return by
   that day's total invested weight. This separates two very different
   situations that look identical in raw correlation — strategies that pick
   different instruments, versus strategies that pick the same instruments
   and differ only in how much they hold.

Read it like this:

| Result | What it means |
|---|---|
| `N_eff` close to `N` | Genuinely diverse. Multiple-comparison concerns are real and should be handled |
| `N_eff` below `N/3` | You are repeating one search. Adding candidates in the same style adds nothing |
| Exposure-normalizing barely lowers correlation | The candidates differ mainly in position sizing, not in selection — you have been testing risk appetite, not signals |
| Correlation **rises** during drawdowns | The diversification is absent exactly when it is needed; do not describe the set as diversified |

If `N_eff` is low, the correct next move is a different cell of the map from
A1 — or a constraint from A2 — not another member of the current family.

**Record which candidates the count covers, and don't let it travel further
than that.** `N_eff` is a property of the set you computed it over. Quoting
it next to a larger, unrelated total count produces a claim about the total
that nobody actually measured — keep the two numbers separate and label each
with the set it describes.

### A5. Where hypotheses are allowed to come from

Three legitimate sources:

**Published priors.** A documented risk premium or anomaly, with its
original parameters. The parameters matter: taking a published lookback is a
prior, tuning it on your data is fitting, and the difference is whether the
value existed before you saw your results.

**Structural reasoning.** A mechanism you can state in terms of who is on the
other side and why they are there — a mandate constraint that forces some
participant to trade at a predictable time, a settlement or quota friction, a
liquidity mismatch. If you cannot name the counterparty and their reason, you
have a pattern, not a mechanism.

**The negation of a failed category.** If momentum fails across the whole
universe, that is information about the universe, and it points at mean
reversion or at a risk-state overlay rather than at another lookback.

Two illegitimate sources, both of which feel like research:

**The backtest maximum.** "This value performed best" is not a hypothesis,
it is a description of the sample. It becomes a hypothesis only if you can
say why that value and not its neighbour.

**"Let's just try it."** Acceptable exactly once, as exploration, and only
if logged as exploration with no adoption pathway. The failure mode is that
an untheorized variant that happens to win becomes an adopted strategy, and
nobody can later say what would falsify it.

### A6. Pre-register the decision line

For each experiment, write these five fields **before the run**:

1. **Hypothesis** — the mechanism, in falsifiable form
2. **Incumbent** — the named strategy being challenged, with its actual figures
3. **Decision line** — the threshold, on which metric, over how many windows
4. **Rejection condition** — written symmetrically; what result makes you
   drop it
5. **Predicted failure mode** — how you expect it to fail if it does

The fifth field is the one people skip and the one that does the most work. A
predicted failure mode makes the result informative in both directions: if
it fails the way you predicted, you have learned about the mechanism; if it
fails some other way, your model of the universe is wrong in a way you did
not know.

Fields 3 and 4 must reference conventions by name — which drawdown
definition, which return definition. Both metrics have two defensible
definitions whose gap can exceed the adoption margin, so an unnamed
convention means the convention decides the verdict rather than the
evidence.

## Part B — evaluating the candidate

### B1. The three report layers

Run all three. They answer different questions and none substitutes for
another.

**Layer 1 — individual windows.** Rolling out-of-sample windows, typically
calendar years, each preceded by its own warm-up period. Score **only** the
test slice — the warm-up existed so the strategy had history, not so it
could pad the result. Stateful strategies get `reset()` between windows or
state leaks across the boundary. The Layer 1 artifact is a pivot: one row
per year, one column per rebalance offset, at baseline cost. Read it before
any summary statistic, because a strategy that earned everything in one year
cannot hide inside an average that has not been taken yet.

**Layer 2 — cross-window stability.** The distribution across windows,
where the **ratio** fields matter more than the mean:

| Field | Why it decides things |
|---|---|
| `positive_window_ratio` | A high win rate at a modest return usually beats a coin-flip win rate at a higher one |
| `beat_benchmark_ratio` | Beating the passive control in *every* sub-period is the conditional goal that replaces an absolute target |
| `worst_window_return` | The number the user will actually experience and remember |
| `after_cost_positive_ratio` | At the double tier, where turnover-heavy strategies die |
| `std_annual_return` | Cross-window dispersion; a mean without it is not a result |

Write the bar as a conjunction over these fields before the round, not
after — mean, drawdown, Sharpe, *and* a minimum count of positive windows,
all holding at double cost. A bar written only on the mean can adopt a
candidate with a strong average and two consecutive negative years.

**Layer 3 — market-regime attribution.** Bucket daily returns into
bull / bear / sideways using the benchmark's own trend — a fast moving
average over a slow one, with a small buffer so a ratio hovering near zero
does not flip the label daily. Two rules make this honest. **The labels must
be causal** — both moving averages use only past data, so you could have
computed them live. Any labelling that peeks turns regime attribution into a
way of confirming what you already believed. And **the rule is deliberately
crude**, because it exists to answer "where did the return come from," not to
be a signal.

What to look for: **a strategy whose entire excess sits in one bucket is a
bet on that regime recurring**, a far stronger claim than the headline
number implies. Also report average exposure per bucket — it can reveal that
a capability a user is asking for already exists as a byproduct of something
built for a different reason.
→ [exposure profile](../../references/metrics-and-traps.md#exposure-profile)

### B2. The two stress axes

**Staggered rebalance dates.** Split capital into four equal parts and
rebalance them on staggered trading days spread through the rebalance period
— for a monthly cadence, the 1st, 6th, 11th and 16th. Combine equally
weighted, then compare. Report the mean across offsets as the result and the
standard deviation as the error bar, for both the challenger and the
incumbent, in the same run.

The decision rule: if offsets disagree by more than the edge you are
claiming, you have measured the calendar, not the strategy. Set a
disqualifying threshold on offset σ against your own measured dispersion, not
against a number from elsewhere. Staggering is also worth adopting as the
live execution scheme, not just as a test — it removes the luck from real
results and makes reconciliation cleaner.

**Binary switches are structurally worse on this axis.** A strategy that
relies on a gate, circuit breaker, or threshold trigger has a discontinuity
in it. Price crossings of a moving average happen inside very short windows,
so moving the observation day flips the decision and the whole period's
positioning with it. Static-weight strategies have no such discontinuity.
**Therefore, for any strategy containing a gate, circuit breaker, or
threshold trigger, multi-offset validation is mandatory rather than
optional** — their single-run results have systematically lower credibility
as a structural property of the mechanism, not as a comment on the
implementation. The corollary is useful for design: a passive or static leg
*suppresses* date sensitivity, because that part of the book never reacts to
the observation date at all.
→ [rebalance timing](../../references/optimization-dimensions.md#3-rebalance-timing)

**What staggering cannot do.** This is the boundary of the entire skill.
Staggering rules out *micro*-luck in rebalance timing and says nothing about
*macro*-luck in what the window happened to contain — a candidate can pass
four-way staggering with a tight offset spread, genuinely proving the result
is not rebalance-date luck, and still owe most of its backtest performance to
a window that will not repeat. These are orthogonal dimensions; only
genuinely unseen data resolves the second, and there is no substitute.
Concretely: **if a candidate ballast or diversifier has just been through a
large one-directional move, its backtest is structurally optimistic** — put
the forward test at the entry gate rather than at the end as a formality.

The positive control matters as much as the catch. When the incumbent's
out-of-sample behaviour tracks its backtest promise closely, that
divergence-free result is positive evidence its edge was structural rather
than borrowed from one rally. Report both directions.

**Cost tiers.** Baseline and double, as two columns on every window — not a
sensitivity check run on winners. The cost assumption is the input you know
least well, so a strategy that clears the bar only at baseline is an
artifact of it. Whether the tier decides a case depends almost entirely on
turnover, so define your turnover unit before you quote one.
→ [turnover](../../references/metrics-and-traps.md#turnover)

### B3. Conventions that decide the verdict before you do

Every headline number is a convention, and several of them have two
defensible definitions that differ by more than a typical adoption margin.

| Convention | Both definitions are in use |
|---|---|
| **Drawdown** | Worst drawdown *within* each window, vs drawdown over a continuous multi-year hold |
| **Return** | Arithmetic mean of per-window annualized figures, vs geometric return of the concatenated path |
| **Sharpe** | With and without the risk-free rate |
| **Turnover** | Σ\|Δw\| versus one-sided — a factor of two, applied directly to modelled cost |
| **Short windows** | Cumulative versus annualized (see below) |

Two properties of this table are what make it dangerous. **The gaps are
decision-sized** — either convention can flip a verdict about whether a
strategy sat inside a stated risk budget, or produce a return gap wider than
the adoption margin the decision used. Two researchers following the rules
exactly could reach opposite verdicts without either making a mistake.
**Some of them do not announce themselves.** The drawdown gap at least shows
two obviously different numbers. The return gap does not: both figures are
called "annualized return," both are computed correctly, and the arithmetic
mean of per-window figures always exceeds the geometric return of the
concatenated path once windows disperse. Nothing looks wrong.

Two rules follow. **Report both members of every pair, always** — a single
figure for either drawdown or return is a convention silently chosen on your
behalf. And **fixing the convention for one metric does not fix it for the
others**: enumerate every metric your decision line references and write
down which definition each uses. Any metric quoted to a human carries its
definition next to the number, not in an appendix.

### B4. Short samples

**Never annualize a partial year.** Annualization multiplies signal and
noise together — for a half-year window, by roughly two — and a reader will
compare the annualized figure directly against multi-year numbers. Sub-year
windows get cumulative return only.

**Attach a standard error to any Sharpe you quote.** A serviceable rule of
thumb is SE ≈ 1/√(years). Over a handful of walk-forward windows that is
still large enough that a small Sharpe difference between two strategies is
not a difference; over a half-year forward stub it is large enough that any
measured value has a very wide interval. That arithmetic is why every
out-of-sample conclusion from a short stub is weak evidence by construction,
in both directions.

**Correct for multiple comparisons using the *effective* trial count**, not
the nominal one, and quote the conservative version anyway. Where the
effective count collapses toward one or two, the significance bar computed
from it is generous enough to be worthless; report the bar you would clear
if all your attempts had been independent, and if the mechanism is what
actually supports the strategy, say that instead of leaning on a
t-statistic.
→ [effective independent count](../../references/metrics-and-traps.md#effective-independent-count)

**Realization rate** — out-of-sample annualized ÷ backtest annualized — is
worth computing per strategy family once any out-of-sample period exists.
Treat it as a ranking signal across strategies, not as a point estimate.
→ [realization rate](../../references/metrics-and-traps.md#realization-rate)

### B5. Parameter values: plateau, not peak

Report a neighborhood delta next to every chosen parameter value. The
failure this prevents is adopting a cell that is maximal because it is
noise — a cell standing well above the average of its immediate neighbours
is the signature of an isolated peak rather than a region.

The value worth selecting on is a plateau centre, and a useful secondary
criterion is the highest *worst-window* return in the grid rather than the
highest mean. Where a sweep shows a cliff on one side and a plateau on the
other, stay on the plateau and do not move a frozen parameter toward a
marginally higher cell — moving a frozen parameter toward a backtest maximum
is the thing this discipline exists to prevent.

Two further rules. If the chosen cell is pinned to the edge of the swept
range, widen the range; you have not found the plateau. And for any
continuous mixture weight there is *mathematically* some value maximizing
in-sample Sharpe, so use the sweep to verify the surface is smooth, then
choose from precedent or structural reasoning, typically away from the peak.

### B6. The neighbourhood sweep, and what to do at a cliff

Once a candidate passes, sweep the immediate neighbourhood of its parameters
— not to find a better value, but to find out whether the result is a
plateau or a spike. A spike is a fitted artifact regardless of how well it
validated.

| What the sweep shows | Verdict |
|---|---|
| Plateau: neighbours within noise | The parameter is not load-bearing. Adopt, report the plateau width |
| Mild gradient | Acceptable. Report the neighbourhood deltas alongside the headline |
| Spike: neighbours much worse | Reject. The value was selected by the sample |
| **Cliff: the frozen centre is much worse than a neighbour** | See below |

The cliff case needs its own rule because the tempting move is wrong. If the
pre-registered parameter turns out to sit at a bad point and a neighbour is
far better, you may **not** adopt the neighbour under the existing
registration — that is choosing the parameter from the results, which is the
thing pre-registration exists to prevent.

Instead: record the pre-registered experiment as **rejected**, then open a
*new* pre-registration with the revised parameter and a fresh decision line.
The cost is one extra round. The alternative silently converts a
pre-registered test into a search, and every subsequent verdict inherits
that.

A wide spread across a parameter grid is also a warning in its own right. If
plausible values of one parameter produce very different outcomes, the
strategy depends on a quantity you do not know the true value of, and the
best cell of the grid is the one with the most luck in it.

### B7. Audit the report in a fresh subagent

The agent that ran the round already believes it is finished — that is not a
flaw, it is what "finished" feels like from the inside, and it is exactly why
it is the wrong agent to grade the report against the checklist below.
Dispatch a subagent with the report file and the checklist — not your
summary of it — and have it name anything missing: an unreported convention,
a missing offset σ, a caveat line that was skipped. Treat what it finds as
blocking, the same as if you had found it yourself before writing the report.

## What a complete result looks like

```
<strategy id>   N windows x 4 offsets x 2 cost tiers

[Layer 1]  annual return by year x offset, baseline cost
[Layer 2]  mean_annual_return AND annual_return_continuous, median / std,
           positive_window_ratio, beat_benchmark_ratio, worst_window_return,
           max_drawdown_worst_window AND max_drawdown_continuous,
           after_cost_positive_ratio  -- at BOTH cost tiers
           (both members of each pair, always; a single figure for either
            metric is a convention silently chosen on your behalf)
[Layer 3]  bull / bear / sideways annualized, excess, avg exposure, days
[Stress]   offsets: mean +- std (min, max)  -> reject above your threshold
           cost:    baseline and double side by side
           lag:     {0, 1, 3} settlement days
[Context]  incumbent and BOTH passive controls -- static-pool and
           walk-forward-pool -- same protocol, same table. The threshold
           reads against the walk-forward-pool one; the static-pool gap is
           read as attribution, not as a bar
           Sharpe SE for this sample length; realization rate if OOS exists
[Caveats]  what this evaluation does NOT rule out
```

Anything missing from that block is not a partial result; it is an
uninterpretable one, because the reader cannot tell which convention or
which offset produced the headline. The caveat line in particular is not
decoration — write it every time, and see `detecting-self-deception` for the
table of what each technique leaves open.

Two passive controls appear there rather than one because they answer
different questions, and a threshold pointed at the wrong one either rejects
strategies for failing to beat a portfolio nobody could have held, or
credits them for a pool that was assembled with hindsight.
→ `building-the-foundation`, D8

## Common rationalizations

| Thought | What it actually is |
|---|---|
| "Let me just try one more parameter" | The tenth variant of one experiment |
| "We've tested lots of strategies, that's a broad search" | Possibly a much smaller number of independent attempts. Compute `N_eff` |
| "This variant feels genuinely different" | Feeling is not the measurement; correlation in return space is |
| "The grid found a much better value, let's use it" | Selecting the parameter from the results. Re-register |
| "I'll pick the metric once I see which one looks best" | Guaranteed to find a metric where it wins |
| "The signal is the interesting part, so that's where I'll iterate" | Possibly the low-leverage dimension. Rank first |
| "No point testing a static allocation, it's obviously worse" | It has beaten active strategies before; test it |
| "It beat the incumbent." | On one rebalance date. Check the average across offsets before believing it |
| "The strategy has no parameters, so there is nothing to overfit." | The execution date is a degree of freedom regardless |
| "Multi-offset passed, so it is not luck." | It is not *date* luck. Regime luck is a separate, unresolved question |
| "The advantage is large enough that timing cannot explain it." | A double win on return and drawdown can be fully erased by staggering |
| "Double cost is a check for the finalist." | It is a column in every report, from the start |
| "The out-of-sample Sharpe is respectable." | Compute its standard error at that sample length before saying so |
| "We tested many strategies, so the best one is well-vetted." | Compute the effective independent count. Correct against that |
| "The best grid cell is the parameter." | Report the neighbourhood delta. An isolated peak is noise that happens to be maximal |
| "Drawdown is inside the budget." | On which convention? The two can differ by enough to flip that sentence |

## Handoff

**Artifacts this skill must have produced:**

- `docs/mechanism_map.md` — the dimension table with categories, which
  cells are tested, which are excluded and why
- `docs/sensitivity_ranking.md` — the one-dimension-at-a-time results and
  the resulting dimension ordering, including the centre configuration used
- `docs/experiments/<id>.md` — one pre-registration per planned experiment,
  with all five fields and the conventions named
- `docs/independence.json` — `N_eff` raw and exposure-normalized, over the
  current candidate set
- `evaluation/<strategy_id>_layers.json` — all three layers, both cost
  tiers, one entry per offset, with the incumbent and the passive control
  evaluated under the identical protocol in the same run
- `evaluation/<strategy_id>_stress.json` — offset mean and σ, cost tiers
  side by side, settlement-lag variants
- `evaluation/<strategy_id>_report.md` — the complete-result block above,
  with every metric pair reported in both conventions and the caveat line
  written
- `docs/research_log.md` — updated with the run, the conventions used, and
  any autonomous decision taken

**If all present:** load `judging-the-round` and continue without asking.

**If any missing:** stop. State which artifact is missing and which
decision it blocks. In particular, running experiments without a
pre-registration is not a partial completion of this stage, and a missing
offset σ or incumbent row blocks the verdict entirely — the fix is to route
back to `building-the-foundation` for a passive control rather than to
proceed.

**If `N_eff` is below `N/3` and the planned experiment is in the same family
as the existing candidates:** do not run it. Return to Step A1 and pick an
untested cell. This is a decision to make autonomously, recorded in the log,
not a question for the user.

## Related

- [Orthogonal optimization dimensions](../../references/optimization-dimensions.md)
  — the concrete inventory behind Step A1's categories, with the mechanism
  and general verdict behind each one
- [Metrics and their traps](../../references/metrics-and-traps.md) —
  definitions for every field above, and the
  [reporting checklist](../../references/metrics-and-traps.md#reporting-checklist)
  this skill's output has to satisfy
- `templates/framework/walk_forward.py` — three layers, both stress axes,
  runnable
- `framing-the-goal` — supplies the objective metric this skill ranks
  dimensions against, and where a rejection on the target itself routes back
  to
- `building-the-foundation` — supplies the offset grid, the cost tiers, and
  the passive control row of every table here
- `detecting-self-deception` — the full table of what each validation
  leaves open
- `judging-the-round` — turns these outputs into SHIP, ITERATE, or STOP

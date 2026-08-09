# Orthogonal Optimization Dimensions

> Where to look when the signal formula is settled and you're out of ideas.
> Thirteen dimensions, each with the mechanism behind why it tends to help or
> hurt.

**The problem this solves.** After a few rounds, research tends to collapse
into writing signal formula #N — sweeping a parameter inside one dimension
you've already explored, rather than moving to a dimension you haven't. This
is the list of dimensions to check before writing another variant.

**How to use it.** When [judging-the-round](../skills/judging-the-round/SKILL.md)
returns ITERATE, pick a dimension you haven't exhausted rather than a new
formula in a dimension you have. Set a pre-registered decision line for each
attempt before running it.

**Read these as hypotheses about mechanism, not universal laws.** Which
dimensions pay off depends on your asset pool, rebalance frequency, and
constraint set. The mechanism reasoning is the transferable part; whether a
given dimension helps *your* strategy is something you still have to measure.

---

## 1. Turnover and cost

**The idea.** Reduce turnover with hysteresis bands — enter on a strong
signal, exit only on a much weaker one.

**Why this tends to backfire.** A hysteresis band is mathematically
equivalent to "hold losers longer." During a sharp regime change, the path
from a strong ranking to a weak one is often the steepest part of a drawdown,
so the turnover saved is bought with drawdown added — and the drawdown cost
can exceed the turnover savings.

**Rule.** Low turnover has to come from the signal itself being slow, not
from a patch bolted onto a fast signal. A structurally slow signal and a fast
signal with a buffer are not equivalent even at the same measured turnover.

## 2. Mechanism-orthogonal ensembling

**The idea.** Combine two strategies whose *mechanisms* differ — for
example, cross-sectional momentum and time-series trend — rather than two
variants of the same mechanism.

**Why this tends to help.** Two engines that fail in different regimes cover
each other. The requirement is that the *mechanisms* be orthogonal, not just
that the return streams look uncorrelated in one sample — two momentum
strategies with different lookback windows are not mechanism-orthogonal even
if their measured correlation looks low.

**Caveat.** Verify the mixing weight sits on a plateau rather than at a sharp
optimum, and don't assume a dynamically adjusted mix beats a fixed one — an
adaptive weighting scheme is an additional thing to validate, not a free
upgrade.

## 3. Rebalance timing

**The idea.** Not an optimization — a source of noise to neutralize before
trusting any other comparison.

**The mechanism.** Which calendar day you rebalance on is not a property of
the strategy, yet it measurably changes the reported result. A single-date
backtest therefore always contains some amount of pure timing luck mixed
into its headline number.

**What to do.** Split capital across several staggered dates and report the
mean across them as the result, the spread across them as the error bar. This
both removes the luck from live results and makes reconciliation cleaner.

**Bonus finding.** A strategy with a passive leg tends to show a narrower
offset spread than one without — a passive component structurally suppresses
timing-luck sensitivity, independent of anything else it does.

## 4. Universe boundaries

**The idea.** Add instruments to give the strategy more to choose from.

**Why this can fail expensively.** An added instrument that has just
completed a multi-year boom is guaranteed to top a momentum-style ranking
immediately before a mean-reverting decline. Low measured correlation with
the existing pool does not imply low harm; an asset mid-way through a
completed boom-bust cycle can be more dangerous to a momentum-style selector
than a highly correlated one.

**Rule.** What you add matters more than how many. Screen candidates for
recent-cycle position, not only for correlation.

**Note the mechanism differs for static allocation.** There, expansion is a
trade between diversification gain and constituent-quality dilution rather
than a momentum-poisoning risk — same caution about adding instruments
carelessly, different arithmetic behind it.

## 5. Number of holdings

**The idea.** Sweep the number of concurrent holdings to find the best
concentration level.

**Use for robustness, not for tuning.** This typically produces a plateau
across a middle range and a cliff at very low concentration (pure
single-name risk). The sweep is worth running once to confirm you're sitting
on the plateau — it is not worth re-running to chase a marginal improvement
on an already-frozen parameter.

## 6. Depth of defense

**The idea.** The strategy has one timing/risk layer; add a second.

**Why this tends to fail.** Defensive layers have sharply diminishing
returns. Once a stack already contains one timing mechanism, a second one
mostly de-risks at the same moments the first one already did, paying the
turnover and whipsaw cost twice for largely the same protection.

**Do this first, before building anything new.** Produce the exposure
profile of what you already have. It is common for an existing stack to
already produce the defensive behavior being requested as a byproduct of a
mechanism built for a different reason — in which case the "missing"
capability was never actually missing.

## 7. Check frequency

**The idea.** A slower rebalance cadence misses moves that happen between
checks. Check more often.

**Why this tends to fail.** Higher frequency increases the *density* of
checks on the same underlying signal — it adds no new information between
checks, only more opportunities for the signal to whipsaw on noise. A risk
that occurs between scheduled checks is not, in general, a sampling-rate
problem.

**Rule.** The answer to risk that occurs between rebalances is usually a
diversifying leg or a mechanism-orthogonal addition, not a faster clock on
the same signal.

## 8. Layer ablation

**Not an optimization — a diagnostic.** Turn each layer of an inherited
signal stack on and off, one at a time, binary only (don't sweep continuous
parameters while doing this).

**What it produces.** A measured contribution for every layer in the stack,
turning "should we keep this layer?" from an argument into arithmetic. If
every layer shows a positive, non-redundant contribution once measured this
way, the stack is self-consistent and there's no need to keep disassembling
it looking for dead weight.

## 9. Passive-engine blending

**The idea.** If your passive control is the return leader among everything
you've tried, stop treating it only as a benchmark and use it as a leg —
blended with your best active strategy.

**Why this tends to help.** It's a direct way to buy the passive leg's
stability without giving up all of the active leg's edge, and as a side
effect it suppresses rebalance-timing luck (dimension 3) for free, since the
passive component structurally narrows offset spread.

## 10. Multi-offset re-validation

**Mandatory, not optional.** Any claim of "beats the incumbent" must be
re-run across staggered offsets before it counts as a claim at all — this is
one of the highest-value checks per unit of effort in the whole list, because
it has repeatedly reversed apparent winners.

**Where the credibility gap is largest.** Strategies containing binary
switches — gates, circuit breakers, threshold triggers — tend to be far more
date-sensitive than static-weight strategies, because a discrete trigger can
flip its decision within a very short window around the observation date
while a continuous weight cannot.

## 11. Smarter static weights

**The idea.** An underrated dimension: change the weighting *formula* without
changing the assets, the ranking, or adding any timing — for example, inverse
volatility weighting instead of equal weighting.

**Why it's underrated.** It has no timing, no ranking, and no new tunable
parameters, so it doesn't feel like "research" — which is exactly why it
tends to be skipped in favor of dimensions that feel more like progress.

**Caveat.** A marginal improvement measured on a base engine does not
necessarily propagate linearly into a larger ensemble; other legs' risk
controls can dilute or dominate the same change.

## 12. Portfolio-level continuous insurance vs. asset-level binary gates

**These are three different things, and conflating them wastes rounds:**

| Mechanism | Level | Type |
|---|---|---|
| Trend gate (buy above a moving average, cut below) | Asset | Binary |
| Circuit breaker (daily-loss threshold → flat) | Portfolio | Binary |
| TIPP/CPPI (buffer from peak sets exposure) | Portfolio | Continuous |

**The general trade-off.** A continuous mechanism is theoretically smoother
and can genuinely improve crisis-year drawdown, but tends to fail on calm
years instead: once its buffer is consumed, exposure typically recovers
slowly, and the strategy can systematically miss mild recoveries that follow.

**Rule.** For path-dependent insurance mechanisms, execution frequency is a
structural constraint on how well the mechanism can track its own model, not
just an implementation detail to tune away.

## 13. Searching for a new asset class

**The idea.** Once signal and combination space on one pool is exhausted,
the remaining independent dimension is *changing the input space* — finding
a genuinely low-correlation asset class that hasn't been considered.

**Method.** Search broadly by category keyword, then verify history length
and *actual* measured correlation before trusting anything. Product names and
marketing descriptions ("stable", "absolute return", "market-neutral") are
not reliable indicators of realized behavior in a stress period.

**Three requirements that matter more than they look:**

1. **Isolate a new candidate before it's validated.** Mark it non-holdable
   and reference it only from strategies that explicitly opt in. Otherwise it
   silently enters every existing strategy's candidate pool and changes
   already-published numbers as a side effect.
2. **Scan every candidate matching the category, not just the first hit.**
   A systematic scan is the only way to distinguish "the first adequate
   candidate found" from "the best candidate available," and it can surface
   a better option that a narrower search would have missed entirely.
3. **Run artifact checks before trusting a suspiciously good number.** A very
   low annualized volatility can indicate a cash-like instrument rather than
   a genuinely low-risk one; a high share of zero-return days can indicate
   irregular NAV publication rather than real stability; unexpectedly high
   correlation with a known asset class can indicate hidden exposure to that
   class rather than genuine diversification.

**Validate theoretical properties against actual products, not against the
textbook description of the asset class.** A class that is textbook convex
in theory can behave nothing like that in the specific products actually
available to trade.

---

## Choosing a dimension

| If your problem is… | Try dimension | Be cautious with |
|---|---|---|
| Returns too low | 9 (passive blend), 11 (static weights), 13 (new asset class) | 4 (universe expansion) — can poison momentum-style selection |
| Drawdown too high | 2 (orthogonal ensemble), 13 (diversifying asset) | 6 (deeper defense), 12 (insurance) — both have a documented history of failing to deliver |
| Costs too high | A structurally slower signal, not a buffer bolted onto a fast one | 1 (hysteresis) — tends to trade cost for drawdown, not eliminate it; 7 (higher frequency) — tends to add whipsaw, not information |
| Results unstable across dates | 3, 9, 10 | — |
| Everything looks the same | 13 (new information source), or relax a constraint | Another variant in a dimension you've already exhausted |
| Can't tell what's contributing | 8 (layer ablation) | — |

**When several dimensions are exhausted:** three or more mechanism
*categories* failing in the same direction is a diagnosis, not a coincidence.
It means the shape of your losses isn't something this family of mechanisms
addresses. Change dimensions entirely, or accept the measured frontier and
report it as such.

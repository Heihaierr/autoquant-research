# Metrics and Their Traps

> Definitions matter more than they look. Each metric below has a standard trap
> that changes a conclusion while every line of code stays correct.

---

## Sharpe ratio

**Definition.** `(annualized return − risk-free rate) / annualized volatility`.

**The trap: forgetting the risk-free rate.** Computing
`annualized return / volatility` with no risk-free subtraction overstates every
Sharpe by roughly the risk-free rate itself. The error is uniform across
strategies, so every cross-strategy comparison still looks internally
consistent — nothing appears wrong until the number is checked against an
external reference or a textbook definition.

**Rule.** Uniform errors are the hardest to notice precisely because internal
consistency is preserved. Periodically check at least one metric against an
external source, not just against your own other numbers.

**When fixing, preserve comparability.** Add a new, correctly-defined field
rather than silently changing the existing one. A metric definition change
invalidates every number already logged under the old name, and a silent
change makes that invalidation invisible.

**Other traps.** A Sharpe well above 2 on a retail-accessible, unlevered
vehicle is unusual enough to warrant a specific check for a low-volatility
accounting artifact before it is trusted. And Sharpe as a *selection*
criterion systematically prefers low-volatility, low-return assets over
high-return ones — it is not a proxy for "will grow my capital."

---

## Annualized return

**The trap: annualizing partial periods.** A window shorter than a year
annualizes with a multiplier that amplifies noise exactly as much as signal —
a 7-month window carries a multiplier around 2×, so a modest actual return
becomes a large-looking annualized one, and the noise in it is amplified by
the same factor.

**Rule.** For windows under one year, report cumulative return only. Never
place an annualized partial period in a comparison table next to multi-year
numbers.

**Second trap: mean-of-periods vs. compound.** "Average of per-period
returns" and "compound annualized return of the concatenated path" are
different quantities, and the gap between them widens with volatility. Pick
one, name it explicitly in the table header, and never let the two coexist
unlabeled in the same report.

---

## Maximum drawdown

**The trap: two definitions that both call themselves MaxDD.**

- **Worst within-window drawdown** — computed inside each walk-forward
  window, then averaged or maxed across windows
- **Continuous-period drawdown** — computed over the whole holding period,
  across window boundaries

The second is always worse, sometimes much worse, because real drawdowns span
window boundaries. It is also the one that matches what a person actually
holding the portfolio experiences, since nobody's capital resets at a window
edge.

**Rule.** State which definition you use, in the table header, every time.
When reporting to a human who will hold the portfolio, use the continuous
definition — it is the one they will live through.

---

## Turnover

**Define the unit.** A turnover number means nothing without knowing whether
it is one-way or two-way, annualized or per-rebalance, and whether it counts
the passive drift of weights between rebalances or only executed trades.

**Why it matters.** Turnover is the direct input to your cost model, and cost
is frequently the entire difference between a signal that survives contact
with reality and one that does not. A mechanism that looks identical in
gross terms can differ by an order of magnitude in net terms once its true
turnover is measured correctly.

**Watch for near-zero turnover as evidence, not just as a number.** A
trigger-based mechanism with turnover near zero fired almost never — that is
not neutral information, it is direct evidence that the trigger condition is
chronically unmet, which changes what you should try next.

---

## Asymmetry (upside beta minus downside beta)

**Definition.** Regress strategy returns on the benchmark separately for
benchmark-up and benchmark-down days. Asymmetry is `β_up − β_down`. Positive
means you capture more upside than downside — the precise statement of
"gains more, loses less."

**Why you need it.** Return, drawdown, and Sharpe *cannot see this property*
on their own. A strategy can post good numbers on all three and still lose in
exactly the shape you built it to avoid.

**Rule.** Any strategy described as "defensive" must report asymmetry
separately from its headline numbers. A label like "defensive" describes an
intent, not a measured property, and the two can diverge — a mechanism built
to cushion sustained declines does not necessarily cushion sharp, fast ones,
or vice versa.

**And know what static ballast buys.** Adding an uncorrelated ballast asset
produces *proportional shock absorption*, not convexity — it moves upside and
downside beta together rather than reshaping the ratio between them. Ballast
changes exposure *size*; it does not change exposure *shape*. Convexity is
not purchasable by ballast weight alone.

---

## Realization rate

**Definition.** `out-of-sample annualized ÷ backtest annualized`.

**Why it's useful.** As a ranking signal across candidate strategies, this
tends to be a better predictor of live behavior than backtest Sharpe alone,
because it directly measures how much of the backtest's promise survived
contact with unseen data.

**Mechanism worth checking.** If realization rate rises monotonically with
the weight of some low-variance component, that component may be buying
backtest *credibility* — predictability of the realized path — rather than
buying genuine risk reduction. The two are easy to conflate and worth
separating explicitly.

**Caveat.** Requires a real out-of-sample period long enough to be more than
noise. On a short window, treat this as a ranking signal across strategies,
not as a trustworthy point estimate for any one of them.

---

## Effective independent count

**Definition.** From the pairwise correlation matrix of strategy daily
returns, an estimate of how many genuinely independent strategies you have.
Simplest form: sum of eigenvalues over the largest eigenvalue, or `1 / Σwᵢ²`
on normalized eigenvalues.

**Why you need it.** A pool of strategies with high average pairwise
correlation can have an effective independent count far below its nominal
size. Any multiple-testing correction applied to the nominal count rather
than the effective one understates how much of the search was one search
repeated under different names.

**Diagnostic use.** Compute inter-strategy correlation during drawdowns
separately from the full-sample figure — correlation across supposedly
diversified strategies often *rises* precisely during the periods when
diversification was needed most. And normalize for exposure level before
concluding two strategies are "different": if correlation barely changes
after normalizing for how much each was invested, the strategies differ
mainly in position size, not in what they hold.

---

## Diversification ratio and effective number of bets

**Definitions.** Diversification ratio is `weighted average asset volatility
÷ portfolio volatility`. Effective number of bets (ENB) measures independent
risk sources via the eigen-decomposition of the covariance matrix.

**The trap: assuming more diversification means better.** These metrics can
improve by every measure while portfolio volatility itself rises, because
diversification ratio and ENB describe how well-spread the risk is, not how
large it is. A wider pool can raise the diversification ratio while raising
average constituent volatility even faster, so the net result is a worse,
not better, portfolio.

**Rule.** Always report DR/ENB alongside weighted average constituent
volatility. Diversification is a ratio; its numerator can degrade faster
than the ratio improves.

---

## Information coefficient

**Definition.** Rank correlation between a signal and forward returns,
cross-sectionally, averaged over time. Report the t-statistic alongside it.

**The trap: treating IC as sufficient.** A signal can clear every standard
bar — strong IC, significant t-statistic, look-ahead bias already corrected,
economically motivated, present only where theory predicts it — and still
produce a strictly worse strategy once turnover, tail behavior and
cross-sectional width are accounted for.

**Three things IC cannot see:**
1. **Turnover cost.** IC is computed on signal values, not on the trades
   required to act on them.
2. **The tail.** IC measures average direction. A mean-reversion signal can
   systematically buy into an ongoing decline, which shifts the return
   distribution's left tail without moving the mean much — invisible to IC,
   visible to drawdown.
3. **Cross-section width.** With too few usable instruments, no IC is high
   enough to diversify into a stable return.

**Rule.** Report a with-signal / without-signal pair on the same pool. That
isolates net contribution to the portfolio; IC on its own does not.

---

## Exposure profile

**Not a single number — a picture.** Average exposure, average exposure
during bear periods, share of periods at zero exposure, the full exposure
distribution.

**Why it earns its place.** Before building a new mechanism to add a
capability ("it should be able to go to cash"), check whether the existing
stack already produces that behavior as a byproduct. Building a redundant
mechanism is easy to do unknowingly when the existing exposure profile was
never actually plotted.

**Rule.** Produce the exposure profile *before* building anything intended to
change exposure.

---

## Reporting checklist

Every results table should state:

- [ ] Sample period, and whether it includes the reserved OOS window
- [ ] Cost tier (baseline / double)
- [ ] Offset (single date, or staggered average — and the spread across offsets)
- [ ] Which drawdown definition (within-window / continuous)
- [ ] Whether short windows are cumulative or annualized (they should be cumulative)
- [ ] The named incumbent, in the same table
- [ ] A passive control on the same universe

Missing any of these makes the table uninterpretable by someone who wasn't
there — including you, three months later.

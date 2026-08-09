---
name: building-the-foundation
description: Use after the protocol is fixed and before any strategy file exists. Mechanical triggers - the first fetch of a program, adding an instrument to the universe, evaluating a new source or MCP server, a request that fails or truncates or hits a quota, a source switch or repair, any change to the backtest function or cost model or metric definitions, adopting an engine written elsewhere, a universe or vehicle or cost change that invalidates the current controls, any report that quotes a return or drawdown or Sharpe, and the words "it beat the baseline". Nothing reaches a strategy without passing through here.
---

# Building the Foundation

## Overview

Nothing about a strategy can be interpreted until three things exist: data
that says what it appears to say, an engine that is tested rather than
trusted, and a control group that turns a number into a comparison. They
belong in one stage because they fail the same way — by accepting an
appearance in place of a measurement — and because none of them can be
retrofitted. A strategy bug shows up as an absurd number; a data or engine bug
shows up as an excellent one, which is why it has to be ruled out first rather
than diagnosed later.

The natural instinct in every part of this stage is backwards. The natural
order is to build the integration and then discover its limits, to look at
the data and then decide what to check, to write strategies and then test the
engine underneath them. The correct order inverts all three: probe the limits
before building on them, decide what would disqualify a series before judging
it by its shape, and run the engine's own test suite before the first
strategy number exists.

## The Iron Law

```
TEST WHAT WOULD DISQUALIFY BEFORE BUILDING ON IT.
NOTHING RUNS THROUGH AN UNTESTED ENGINE.
NO STRATEGY NUMBER MEANS ANYTHING WITHOUT A DO-NOTHING CONTROL BESIDE IT.
```

Order of preference for validating a data series, strictly: **exchange rules
> independent second chain > judgment.** Never validate a price series
against its own shape — a spike detector built on "big moves that reverse are
suspicious" cannot distinguish an error from a genuine sharp rally, because
price shape alone carries no information about validity.

Order of operations for the engine: build the correctness suite, then the
control group, then the first strategy — not the reverse. And "beats a
control" means beats a do-nothing portfolio on the same universe, cost,
window and schedule, not beats a generic market index.

## Part A — acquiring the data

### A1. Probe the boundaries before writing the integration

Run these gates in order. Each is cheap and can eliminate the source before
you spend anything on the next.

**Quota.** How many requests, over what period, and what happens at the
limit? A per-day allowance and a lifetime allowance are different products.
If the documentation does not say, measure it: call until it stops and record
the count. Ask too whether batch requests are permitted, because one
instrument code per call multiplies every history pull by the size of the
universe. A quota that dies partway through a first full fetch does not
describe a base source, it describes a spot-check tool — and that difference
determines the integration design.

**Endpoint availability.** Call every endpoint *class* you plan to depend on,
once, with a minimal payload. Do not infer availability from a capability
list. The high-value case is a source you are evaluating because it offers
information your existing chains do not — valuation, fundamentals, factor
exposures — since a genuinely new information axis is often the most valuable
relaxation available to a program whose signals are all price-derived. That is
where a handful of calls is worth most: a direction closed in minutes is a
result, the same direction closed after a week of integration is a loss.

**Deployment path,** if you are considering self-hosting. Prebuilt packages
can be platform-locked, and the fallback can be compiling a native stack and
syncing tens of gigabytes.

### A2. Decide the role, not just the quality

A source can be excellent for extending history and unusable as a base.
Deciding this up front prevents the outcome where a program's foundation
rests silently on an anonymous endpoint someone put on the internet.

| Role | Requirements | Disqualifier |
|---|---|---|
| **Base chain** | Identifiable operator, stable access, full universe coverage, known adjustment, no exhaustible quota | Anonymous, no SLA, lifetime quota below universe size |
| **Cross-check chain** | Independent of the base, enough coverage to adjudicate disputed points | Mirrors the base's own pipeline, so it cannot disagree |
| **History extension** | Reaches further back, agrees with the base over the overlap | An unreconciled adjustment convention |
| **Rejected** | Failed an earlier gate | The endpoint class your research needs errors out |

Record the role and the measured limits that produced it in the fetch
script's docstring. The next agent to consider this source should start from
evidence rather than from the capability list.

### A3. Budget for two chains from the start

Single-chain data cannot be validated, and this is a structural claim rather
than a robustness preference. The alternatives — statistical anomaly
detection, and correlation against a reference — each have a specific blind
spot: anomaly detection cannot distinguish "impossible" from "unusual," and
correlation is a shape statistic that is nearly blind to the level errors
that actually change a backtest.

A second chain also pays for itself outside QC. Chains differ in how far back
they reach, and the one that reaches each instrument's actual listing date
rather than a uniform later start can push a multi-asset common start date
back far enough to add a distinct market regime to every walk-forward window
— which is worth more than any parameter you could tune. Retrofitting a
second chain after results exist means re-running all of them.

### A4. Ask what the series *is* before computing returns from it

Coverage checks come first: first date, last date, row count, gap count, per
instrument. Then four questions a row count cannot answer.

**Is the return expressible from this series at all?** Some instruments hold
price constant by construction and accrue return through share growth. A
money-market fund used as an on-exchange cash proxy produces a price series
carrying approximately zero return forever: correct data, wrong series for a
backtest.

**Is the early history usable?** An instrument's first weeks of trading can
be genuinely recorded and still not describe the asset, because an illiquid
launch period produces volatility belonging to the launch rather than the
exposure. Compare against a peer fund in the same sector; if the early
segment is an outlier, truncate it or exclude the instrument.

**Is anything being invented before inception?** Never backfill. Pre-listing
values stay NaN and the strategy layer filters on a minimum-history
requirement. Synthesizing pre-inception history from an index manufactures a
survivorship advantage, and it is usually done by accident: a library default
that forward-fills across the listing gap hands a late-listed instrument
fabricated zero-return history, which reads as unnaturally low volatility and
attracts overweight from any risk-based allocator.

**Is it adjusted?** An unadjusted series understates return by the
distribution yield, and nothing about the series announces which one you
have. Cross-compare against a source whose status you know, on two axes:
daily-return correlation catches shape mismatch, and the difference in
annualized return over the overlap catches the level error correlation
cannot see. The point cuts both ways — adjustment status is a measurable
property rather than a fatal category, so measure before rejecting a source
and before trusting one. Instruments that paid no distributions during the
sample show no gap at all, and a source labelled "unadjusted" is perfectly
usable for them.

### A5. Getting data out when the source resists

These tactics resolve most acquisition failures, roughly in the order to try
them.

- **Verify with a different client before concluding a source is blocked.**
  What looks like being blocked by the server can be a TLS handshake rejected
  by one HTTP client and accepted by another from the same host. Shell out
  and let a different client do the request if in doubt.
- **Segment the range when a single request truncates.** A truncated series
  often means a per-request bar cap rather than a limited source. Requesting
  one calendar year at a time with an explicit start and end returns complete
  data, and is naturally resumable.
- **Follow redirects and specify HTTPS.** An endpoint that redirects from
  plain HTTP can silently produce nothing.
- **Serialize and rate-limit deliberately.** A fixed sleep between requests
  both respects the source and avoids triggering the limiter that caused the
  problem.
- **Cache per instrument, resume by default.** A fetch that fails two-thirds
  through should cost the remaining third to finish, not the whole thing.
- **Record the adjustment flag alongside the data,** and assemble the wide
  table as a separate step from fetching. Which response key served the data
  is metadata you need at QC time and cannot reconstruct later.

## Part B — validating before the first backtest

Every dataset passes this before its first backtest, including refreshed
data from a source that passed last time, and including a chain that arrived
with a vehicle change.

### B1. Tier 1 — physical constraints, which cannot be wrong

**Daily price limits.** If an instrument can only move a fixed percentage in
a day, a larger recorded move is not unusual, it is impossible. This finds
real errors that statistical methods miss entirely, with no false-positive
space at all — but only if the rule is written correctly, and four details
decide that.

- **The limit is a function of board *and* date.** Boards differ, and a
  board's limit can change mid-sample. Applying one threshold uniformly flags
  legitimate moves on the wider boards and, worse, makes the whole check look
  unreliable. Instruments with no limit at all should be reported separately
  rather than dropped from the scan: their large moves carry no verdict, but
  you want them visible.
- **Leave a rounding buffer.** Test slightly above the exact limit.
  Adjustment-factor rounding produces returns marginally over it on
  legitimate limit-hitting days.
- **Classify explicitly in the universe metadata,** and read it. Code-prefix
  heuristics have exceptions, and an exception here becomes a silent false
  kill.
- **Emit a machine-readable breach file.** The repair step consumes it, which
  keeps detection and repair separable and auditable.

**Other hard records worth encoding.** A return on a day the instrument
could not trade is impossible. A series pinned by construction cannot express
return. Runs of consecutive unchanged values are a mechanical property of the
feed, not a judgment about the market. And two floors exist because of what
they prevent downstream: above roughly 20% zero-return days the instrument
publishes irregularly, so its computed volatility is fake, and annualized
volatility under about 2% means it is cash-like — both produce spectacular
fake Sharpe ratios in any risk-adjusted ranking.

### B2. Tier 2 — two chains, adjudicated

Where no physical constraint applies you need a second chain, and the
principle it rests on is simple: **a data error appears in one chain; a real
market move appears in both.**

Read disputed dates against each other rather than against a threshold. In a
real event both chains move together, and their *magnitudes* may still
differ for a structural reason — an exchange price capped at a board limit
against an uncapped fund NAV, for instance. In an error, one chain moves
violently while the other is flat. That contrast is the whole method and it
needs no statistical assumption.

**A disagreement has three dispositions, not two.**

- **Repair** — isolated bad points in an instrument you need. Core
  instruments get repaired, not dropped.
- **Exclude** — *systematic* disagreement: year-level gaps of tens of
  percentage points, or an adjusted price magnitude that is itself anomalous.
  Not a repairable point set.
- **Flag** — correct data carrying a return the backtest should not credit.
  One case is an instrument whose history contains one-directional premium
  expansion driven by a purchase restriction that has since changed; pricing
  that into a strategy is a leak, not an error. The other is a slot where the
  two chains track genuinely different underlyings, such as an actively
  managed fund against an index fund, where disagreement is expected and the
  slot carries a caveat.

**Write the cleaned dataset to a separate artifact.** Never repair in place
over the raw cache; you lose the ability to re-adjudicate when a third chain
arrives.

**QC is two passes, and the dependency runs one way.** Adjudication must read
the *raw* cache. An adjudicator pointed at the cleaned artifact cannot see
the disputes it exists to settle and will report a clean bill of health
produced by its own input. The order is raw → adjudication table → cleaned
artifact.

### B3. When there is no second chain at all

Common and easy to hit: newly listed and niche instruments frequently have no
counterpart. Look for a substitute first — two different funds tracking the
same index are two chains, explicitly weaker evidence than two independent
pipelines for the same fund but not nothing. If no substitute exists, decide
by whether Tier 1 already found something.

| Situation | Verdict |
|---|---|
| No second chain **and** a Tier-1 physical violation | **Exclude.** The violation is real and unadjudicable — no evidence could clear it, so keeping the instrument is a bet rather than a decision. |
| No second chain **and** no physical violation | **Keep, flagged** as unverified by cross-check, and carry the caveat into every result that depends on it. |

The asymmetry is deliberate. A physical violation is positive evidence of a
problem and stands on its own; the absence of a second chain is only absence
of confirmation. Excluding every single-chain instrument would quietly bias
the universe toward older, more established products — a survivorship
advantage introduced by the QC step itself.

### B4. Avoiding false kills

This is the half of the discipline that gets skipped, and where a naive QC
pass does the most damage.

**Low correlation is not evidence of error.** Cross-border instruments
routinely show daily-return correlations against their off-exchange
counterparts far below any plausible threshold, and none of it is a data
error. The cause is timezone mismatch: the exchange instrument trades during
local hours and prices overnight overseas moves, while the fund NAV is struck
at the overseas close and lands a day later. A correlation floor applied here
removes core instruments from the universe. The correct criterion for these
slots is **year-by-year return agreement**.

**The three checks are not substitutes.**

| Check | Catches | Blind to |
|---|---|---|
| Daily return correlation | Shape mismatch, wrong instrument mapped to a slot | **Level errors** — high correlation coexists with a large annualized gap |
| Year-by-year annualized gap | Level errors, systematic drift | Isolated single-day points |
| Physical constraint scan | Impossible single-day points | Errors inside the legal range |

Any one alone produces both false negatives and false positives.

**Verify your survivors.** After cleaning, re-scan and trace every remaining
large move to a specific real event — a post-holiday session, an index
rebound, a commodity collapse. "Unexplained large moves" and "explained large
moves" are different QC outcomes, and only the second closes the check.

### B5. Repair by segment, then re-scan

**Replace the whole affected segment from a single source. Do not
interpolate point by point.** Point interpolation looks less invasive and is
worse: an adjusted price series carries an internally consistent
adjustment-factor chain, and splicing individual values from another source
breaks that consistency and introduces a fresh discontinuity at each splice.

1. Read the breach file produced by the physical-constraint scan.
2. Skip instruments on boards where the flagged moves are legal.
3. Check the replacement source's coverage of that instrument — require
   something like 90% of the original's non-null count — and skip rather
   than partially replace if it falls short.
4. Replace the entire instrument series, reindexed onto the master calendar.
5. Re-run the constraint scan and report the remaining breach count. It
   should be zero; if it is not, the replacement source has the same
   problem.
6. Write to a new artifact and log what was replaced.

Step 5 is the one people skip. A repair you did not re-scan is a hypothesis.

### B6. Quantify the damage before redoing the work

Finding real errors triggers an instinct to invalidate everything downstream.
Measure first: re-run the incumbent on the corrected chain and compare period
by period. Bad data does not automatically mean bad conclusions — the correct
action is often to record the correction and continue rather than discard
prior work wholesale.

**Report the direction as well as the magnitude.** Symmetric noise mostly
cancels; a systematic bias in the flattering direction survives averaging and
inflates every comparison equally. If all your errors ran one way, that is
the finding, not the size.

## Part C — the engine

### C1. Look-ahead protection: the spy strategy

A fake strategy records the data window it was handed; the test asserts it
never saw anything dated on or after its own decision date.

```python
spy = SpyStrategy()   # records (asof, prices.index.max()) on every rebalance
run_backtest(make_prices(), spy)

assert len(spy.calls) > 5, "strategy was barely called; test proves nothing"
for asof, max_seen in spy.calls:
    assert max_seen < asof, f"look-ahead: {asof.date()} saw {max_seen.date()}"
```

Four details carry the weight. **The inequality is strict**, because `<=`
lets a strategy use the closing price of the day it trades on — real, very
profitable, and undetectable in the output. **The guarantee is structural**:
the engine slices the frame before calling the strategy, so a strategy
written next year by someone who never read the engine still cannot see the
current bar. **The call count is asserted**, because a test that passes on an
uninvoked strategy is worse than none. And **it runs on every schedule**,
since a denser grid makes more decisions and aligns differently at period
boundaries.

**Ship a standalone `assert_no_lookahead(frame, asof)`** for scripts that
slice by hand. Diagnostics are where leaks actually live and the engine
cannot reach them: a NAV published at day end makes same-day NAV future
information, and any signal study built on it needs to lag it before its
information coefficient means anything.

### C2. Execution lag: pick a convention, then lock it with a test

Any coherent convention works; an unstated one does not. State three facts
and test each: the signal on day `t` sees data through `t-1`, the order is
placed on `t`, the first return attributed to the new weights is `t+1`. So
the rebalance day earns the *old* weights, and a strategy switching assets at
a known date pins the boundary in two assertions. Booking new weights on the
decision day instead credits a day of performance the portfolio could not
have captured, once per rebalance.

**Settlement lag needs its own test.** Where proceeds are not immediately
available, the part of the book that is *not* changing must keep earning
while the changing part sits in cash: with a three-day lag and a full switch,
the three intervening days return exactly zero and the fourth returns the new
asset's. Then sweep the lag on every candidate, since it can move a result
by a small but non-negligible amount worth proving rather than assuming.

### C3. Cost deduction: assert the exact amount

"Costs are deducted" is not a test; the deducted number is. Run the same
strategy free and charged, and assert the difference at two rebalances whose
turnover you know exactly — an opening trade from cash, where it must equal
`cost × 1.0`, and a full switch between two assets, where it must equal
`cost × 2.0`. Two exact equalities catch half-counted round trips, costs
charged on the wrong day, and costs applied to weights instead of weight
*changes*, none of which produce implausible output. Also test that the
double-cost tier bites by exactly `cost × Σ turnover`, and, where the venue
has a minimum-holding penalty, that fast round trips are charged at the
penalty rate and the violation counter fires.

**Not a formality.** An engine that holds weights fixed between rebalances,
quietly restoring the target allocation every day for free, will report a
passive baseline with zero turnover and digit-identical returns at both cost
tiers — which reads as insensitivity to costs when it is actually the absence
of costs. Assert non-zero turnover before reporting that doubling costs did
not matter. The general form reaches far beyond costs: **perfect
insensitivity to a parameter is a bug report until proven otherwise.**

### C4. Fix the turnover convention, then never change it

The two common conventions differ by exactly 2×, and the number lands
directly on the cost line. Counting `Σ|Δw|` scores a full rotation between
two assets as 2.0, so `annual cost = one-way rate × turnover` — which is why
it is the useful one, and why it is not the broker's definition of the word.
Put that sentence in the docstring, because two numbers a factor of two apart
describe the same strategy. The convention decides cases: a signal that
works gross can lose net purely on rotation rate, and the gap between a
static allocation and an aggressive ranking rule is an order of magnitude,
not a few percent.
→ [turnover and cost](../../references/optimization-dimensions.md#1-turnover-and-cost)

### C5. Assert the research cutoff in the loader

```python
def load_prices(cfg, research: bool = True) -> pd.DataFrame:
    df = pd.read_parquet(cfg.price_file).sort_index()
    if research:
        end = pd.Timestamp(cfg["research_end"])
        df = df.loc[:end]
        assert df.index.max() <= end, "research-mode leak: data past research_end"
    return df
```

Every strategy, diagnostic and throwaway notebook goes through one function,
so the guarantee holds for code that does not exist yet. The leak is almost
never a deliberate peek — it is a helper that resamples full history, or a
benchmark loaded through a different path. Live generation passes
`research=False` explicitly, making every use of recent data a greppable
decision. Test both directions, or live signals go stale and nobody notices.

### C6. Common-mode errors leave rankings intact

An engine that omits the risk-free rate from Sharpe is biased by exactly
`risk_free / volatility`, and that bias can survive many rounds of reports
unnoticed. Why it survives is the transferable part: the bias is
**common-mode** — every strategy shifted by the same amount, so rankings are
untouched and every internal comparison stays self-consistent, and only
absolute levels quoted outside the program are wrong. That is a whole class
of defect.

| Common-mode error | What it corrupts |
|---|---|
| Risk-free rate omitted from Sharpe | Every absolute Sharpe, by `rf / vol` |
| Wrong annualization factor | Return and volatility together, so the ratio hides it |
| Turnover counted one-sided | Modelled cost, by half |
| Drawdown within window, not continuous | The number the user checks against their real tolerance |

None is caught by comparing strategies to each other, which is the only check
most programs run. Catch them by asserting the *formula*: that `sharpe`
equals `(mean − rf/N) × N / vol`, that a legacy field (if kept) omits the `rf`
term, and that the two differ by exactly `rf / vol`.

**Fix by adding a field, not mutating one.** A program mid-flight keeps the
existing field unchanged because prior reports depend on it and adds a
correct one; either serves for comparison, but any absolute level quoted to a
human uses the correct version. A program starting fresh gives the plain
name to the correct one, as the templates do. Separately, keep a frozen
control strategy and assert its daily returns are bit-identical after any
change you believe changes nothing.

### C7. Missing data must not become fake data

**A held asset with no prices contributes zero, not NaN** — one NaN poisons
the whole return series and every metric downstream. **No return is computed
before an instrument's first observation**, because back-filling a late
listing gives it a flat, zero-volatility history that any inverse-volatility
or momentum screen will overweight — manufactured survivorship, and the
cheapest kind to create by accident. **A missing print mid-series is
forward-filled, not dropped**, since dropping the bar deletes the move across
it.

### C8. Test that a mechanism is not silently inert

Anything conditional can be wired up and never fire. A drawdown circuit
breaker armed only when an optional argument is passed will silently disable
itself for every caller that omits the argument, and "the kill switch changes
nothing" is then a conclusion about a mechanism that was never switched on.

The test is structural: construct data where the mechanism *must* trigger,
then assert the protected run differs from the unprotected one. The matching
research habit is to report every time whether a mechanism was active — a
triggered strategy whose turnover shows it never fired has told you more than
its performance did.

### C9. The suite

Each line is one test, and each protects against a specific, real error mode.

| # | Test | Protects against |
|---|---|---|
| 1 | Spy strategy, `max_seen < asof`, base schedule | Look-ahead |
| 2 | Spy strategy on every other schedule | The unchecked path |
| 3 | Standalone `assert_no_lookahead` helper | Leaks in diagnostics |
| 4 | Rebalance day earns old weights, `t+1` earns new | One-day return gift |
| 5 | Settlement lag parks only the changing part in cash | Overstated rotation |
| 6 | Cost equals `rate × Σ\|Δw\|` at two known turnovers | Mis-scaled costs |
| 7 | Double-cost tier worse by exactly `rate × Σ turnover` | Stress not wired |
| 8 | Minimum-hold penalty fires at the penalty rate | Regulatory cost ignored |
| 9 | Offsets produce different results | Offset grid not wired |
| 10 | Offset clamps in short months | Index error at period ends |
| 11 | Alternate schedule is a superset of the base | Two-variable comparisons |
| 12 | Held asset with no data contributes zero, not NaN | Poisoned series |
| 13 | No returns before first observation | Manufactured survivorship |
| 14 | Mid-series gap forward-filled | Deleted moves |
| 15 | `sharpe` subtracts risk-free; legacy differs by `rf / vol` | Overstated Sharpe |
| 16 | Before-cost return exceeds after-cost | Cost drag not reported |
| 17 | Conditional mechanisms are not inert | Measuring nothing |
| 18 | Research mode truncates; live mode does not | Contaminated hold-out |
| 19 | Passive control renormalizes over available assets | Control stuck in cash |

Rows 9 to 11 are easy to miss and are exactly what a multi-offset protocol
silently depends on.

## Part D — the controls

### D1. Three controls, three questions

Every result is scored against all three, and none substitutes for another.
The **passive** control — a fixed diversified basket on the same universe,
rebalanced on a schedule — asks whether this mechanism class is worth
anything at all. The **naive** control — the simplest version of *your*
mechanism, with no volatility weighting, correlation filter or overlay — asks
whether your sophistication is worth anything. The **incumbent** — whatever
is in production or currently best, by name, with its numbers — asks whether
anything should change.

### D2. Constructing smart buy-and-hold

Getting the passive control wrong in the easy direction inflates every
conclusion that follows. Six requirements:

1. **Same universe** — the assets your strategy may hold, not a market index.
2. **Diversified across categories,** not concentrated in one region or
   asset class.
3. **A real weighting rule,** rebalanced to target on a schedule. Equal
   weight is obvious; inverse volatility is a reasonable default, since it
   can improve Sharpe and drawdown at similar return without depending on a
   timing draw.
   → [smarter static weights](../../references/optimization-dimensions.md#11-smarter-static-weights)
4. **Identical costs, execution semantics and engine.** A control computed a
   different way is not a control.
5. **Renormalized over available assets,** so it is never accidentally part
   in cash when an instrument has no data yet.
6. **A never-rebalanced version too,** if your edge might be the rebalancing
   premium. Rebalancing to fixed weights is itself an active decision: it
   sells winners.

### D3. The naive control is the cheapest hard truth

The one most often skipped. Ablating the layers off a mature stack gives
each layer a price tag, and the tags can surprise — a volatility-targeting
overlay can cost return while buying a large amount of drawdown protection,
which is a trade to state rather than a free improvement. Whether your stack
is self-consistent is a *measured* claim that exists only once a stripped
version has been run.
→ [layer ablation](../../references/optimization-dimensions.md#8-layer-ablation)

### D4. The control has its own distribution, and it is wide

The passive basket's figure in your backtest window is one draw. The same
portfolio across rolling windows can span a range several times wider than
any alpha a retail-scale strategy produces, and it can be negative.

Composition matters as much as window: attribute the return to its
constituents, since a small number of drag assets can be masking a much
stronger core. "We beat passive" is also a claim about *which* passive. So
report the control as a distribution — in-window annualized, rolling median
and dispersion, rolling worst and best, the share of windows above the bar,
and the per-constituent attribution.

Absolute return targets are therefore indefensible, since the number is
dominated by regime rather than skill, which is why `framing-the-goal` writes
targets conditionally. And when your excess is smaller than the control's own
dispersion, say so rather than letting the reader infer a precision that is
not there.

### D5. Cold start: promote a passive variant, and say that you did

On a new program the incumbent does not exist. Promoting the best passive
variant into that slot is the right, conservative move, but the variant was
chosen *because* it was best, so its headline number carries the same
selection premium as any best-of-N. So name it a **promoted control** rather
than an incumbent; record which percentile of its rolling distribution the
headline figure occupies; state the adoption bar against that **distribution**
rather than the point estimate, since a top-decile bar rejects strategies
genuinely better than what the user would have held; and re-derive the bar
once a real incumbent exists.

That third step is why this stage hands control back to `framing-the-goal`
before mechanism work begins: the provisional target written before any data
existed can now be calibrated against a measured frontier.

### D6. Compare against the current best, not the convenient one

The cheapest self-deception to prevent, because the weak baseline is usually
the one already wired into your reporting script. A challenger can beat "the
baseline" clearly and still lose to the program's actual incumbent once
re-scored under the same protocol — the conclusion can invert on nothing but
the choice of opponent.

Keep an incumbent registry: one file naming the strategy, its annualized
return as a multi-offset mean at baseline cost, its max drawdown under the
continuous convention, its excess-of-risk-free Sharpe, its spread across the
offset grid, and the command that produced them. Then **re-derive the
incumbent under the challenger's exact protocol** — same windows, cost tier,
offset set and drawdown convention. A comparison across conventions is not a
comparison, and the drawdown convention alone can move one strategy by more
than a typical adoption margin. If you cannot state the incumbent's name and
its three numbers, you do not have a comparison. You have a number.

### D7. The universe is a degree of freedom, and the control inherits it

The universe your control runs on was chosen by someone who already knew how
those assets performed. Put universe selection inside the walk-forward loop
— each period, pick the pool from prior data only, then apply it forward.

Note the direction: hindsight in the pool makes the control *harder* to
beat, which is the safe direction for an active claim, but it means "we beat
passive by X" understates how much of X came from choosing that basket
knowing the outcome. Watch also for the **Sharpe-selection trap** — selecting
a pool by historical Sharpe prefers low-volatility, low-return assets, buys
bond funds every period, and has a savings account as its extremum. Sharpe is
a reporting metric, not a selection criterion.

**Report both numbers for the passive control,** static-pool and
walk-forward-pool. The gap is your universe selection bias and it belongs in
public. Attributing it is a separate, easy-to-botch problem — a whole gap
recorded as bias can turn out, on closer measurement, to be mostly or
entirely something else.

### D8. Which control the threshold reads against

Reporting both leaves one question open, and it has to be settled before a
verdict rather than in the middle of one: an adoption threshold is a single
number, so it has to name a single control. The two are not interchangeable,
because they do not represent the same thing.

| Control | Represents | Role |
|---|---|---|
| **Walk-forward pool** | What someone using only information available at the time could have held | **The threshold.** Your actual opportunity cost |
| **Static pool** | What someone who already knew which instruments to own could have held | Not a threshold. Its gap is a diagnostic |

The threshold cannot be the static-pool number because nobody could have held
that portfolio — the basket was chosen knowing how its members turned out, so
requiring an active strategy to clear it sets the bar above what was
available. Doing it anyway rejects strategies for failing to beat something
that did not exist, and that rejection is indistinguishable from a strategy
having no edge.

The static-pool comparison earns its place as an attribution question
instead. A strategy that lands **between** the two controls — clearing the
walk-forward pool but losing to the static pool — is telling you that most of
what looks like active return comes from *which instruments are in the pool*
rather than from the signal, and that the pool was assembled with hindsight.
A strategy that clears the static-pool control has beaten an opponent
holding a hindsight advantage, which is stronger evidence than adoption
requires and worth stating as such.

## Common rationalizations

| Thought | What it actually is |
|---|---|
| "The docs list dozens of endpoints including fundamentals" | Advertised is not available. A few calls settle it. |
| "Let me design the integration, then handle the limits" | The limits determine the design, not the other way around. |
| "It returned data, so it works" | Returned data can be unadjusted, price-inexpressible, or from an illiquid launch period. |
| "The source is blocked from this host" | Verify with a different client first. It can be your TLS stack, not the server. |
| "The series is truncated, so the source is limited" | Usually a per-request bar cap. Segment by year. |
| "Unadjusted prices make this source unusable" | Measure the annualized gap over the overlap. Adjustment status is a property, not a category. |
| "One good source is enough" | Correlation is nearly blind to level errors, and level errors are the ones that move a backtest. |
| "This move is huge and reverses tomorrow, must be bad data" | Price shape carries no information about validity on its own. |
| "One threshold for daily limits is simpler" | Board limits differ; a uniform threshold flags legal moves on wider boards. |
| "We found errors, so all prior results are invalid" | Quantify before you redo. The measured impact often changes no conclusion. |
| "I'd notice a look-ahead bug" | You would notice it as a good Sharpe. That is the problem. |
| "The engine is simple enough to read" | A missing subtraction can survive many rounds of review undetected. |
| "I'll write the tests once the strategies work" | Then the tests match whatever the engine already does, including the bug. |
| "Doubling costs changed nothing, so it's robust" | Check turnover is non-zero first. Perfect insensitivity is a bug report. |
| "Rankings matter, absolute Sharpe is cosmetic" | Common-mode errors leave rankings intact by construction. That is why they survive, not why they are harmless. |
| "It beat the baseline" | Which baseline? A convenient one and a real incumbent can be far enough apart to invert a verdict. |
| "The universe is the investable set, not a choice" | A degree of freedom, whose hindsight the control inherits. |

## Handoff

**Artifacts this skill must have produced:**

- `data/cache/<source>/` — one raw file per instrument per chain, never
  modified in place, with the adjustment flag recorded alongside
- `data/cache/prices.parquet` — the cleaned wide table, a separate artifact
  from the raw cache, produced by the order raw → adjudication → cleaned
- `data/qc_findings.json` — the machine-readable breach file, re-run after
  repair with the remaining count
- `docs/data_qc.md` — source roles with the measured limits that assigned
  them; the adjudication table; every repair, exclusion and flag with its
  reason; the single-chain instruments carried as flagged; and an explanation
  for each large move that survived
- `tests/test_engine_correctness.py` — the C9 suite, passing, run against the
  execution semantics in `config.yaml` rather than inherited
- `framework/` — the backtest function, the metric functions, and the
  loader with the research-cutoff assertion wired in
- `strategies/s0_passive.py` — the passive control, with its construction
  choices and known weaknesses in the docstring
- `docs/baselines.md` — the passive control's rolling distribution and
  constituent attribution, its static-pool and walk-forward-pool figures, the
  naive control, and the incumbent registry entry with three metrics and the
  producing command
- `docs/research_log.md` — the autonomous decisions taken here, in
  particular every exclusion, every instrument kept without a cross-check,
  and whether the incumbent slot holds a promoted control or a real incumbent

**If all present:** load `framing-the-goal` for its second pass, which
calibrates the provisional target against the distribution just measured,
then continue to `running-experiments` without asking. The detour is not
optional: every verdict downstream inherits the target, and an unexamined
provisional target is indistinguishable from a measured one in the log.

**If any missing:** stop. State which artifact is missing and which decision
it blocks.

**Interrupt conditions reachable from here.** Two of the six.
→ `using-autoquant`
If *every* source failed there is no research to do, and if the only
remaining path is a paid source that is the user's spend. A single source
failing is neither — demote it, record why, continue on the remaining
chains. And if an engine fix changes numbers already reported, say so,
because they may have acted on them.

## Related

- `templates/data/qc_price_limits.py` — the Tier-1 scan, with the per-board
  rule table and the rounding buffer already wired
- `templates/tests/test_engine_correctness.py`,
  `templates/strategies/s0_passive.py` — the C9 suite and the passive
  control, runnable
- `framing-the-goal` fixes the vehicle, cutoff and required series;
  `shipping-and-tracking` re-checks these values against the live snapshot,
  where a chain that silently restated history shows up
- `running-experiments` consumes the offset grid, cost tiers and registry;
  `judging-the-round` takes the static-versus-walk-forward gap

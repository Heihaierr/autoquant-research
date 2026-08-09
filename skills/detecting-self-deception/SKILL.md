---
name: detecting-self-deception
description: Use when ANY of these holds - a strategy is about to be adopted, replaced, shipped, or recommended; a reported Sharpe exceeds 1.5; excess return over the passive control exceeds 2pp annualized; a result is described anywhere as best, strongest, promising, or clean; a validation check has just passed; out-of-sample exceeds in-sample; a new asset or data source is entering the pool. These are mechanical conditions, not judgement calls. Catches reasoning errors that produce correct code computing meaningless answers.
---

# Detecting Self-Deception

## Overview

Code linters catch code errors. This skill catches the other kind: **research
where every line is correct and the conclusion is still wrong.**

Those are the expensive ones. A look-ahead bug gets caught by review. A
sentence like "we validated across four rebalance offsets and the standard
deviation was small" does not get caught by anything, because it can be
entirely true and still support the wrong conclusion — offset validation
rules out one kind of luck and is silent about every other kind.

**Core principle:** Every validation technique answers a narrower question
than the one you are actually asking. Self-deception lives in the gap.

## The Iron Law

```
WHEN A RESULT LOOKS GOOD, THE RESULT IS THE HYPOTHESIS — NOT THE CONCLUSION
```

The trigger thresholds below (`sharpe > 1.5`, a 2pp excess bar) are a
starting point, not a universal constant. Calibrate them against what your
own strategy class actually achieves — on an intraday, high-frequency, or
options book the same numbers can fire on every run, and a trigger that is
always true is not a trigger. Likewise, recompute the effective independent
count on your own returns rather than assuming a number from a different
program transfers.

A good number is the beginning of an investigation, not the end of one. The
stronger your reaction to a result, the more of this skill applies.

## Why the triggers are mechanical

These are conditions you check against the numbers and against your own
draft text, not against your impression of how the result feels. Each is
either true or false without judgement.

| Condition | How to check it |
|---|---|
| A verdict is about to be written — adopt, replace, ship, recommend | You are drafting one |
| `sharpe > 1.5` | Read it off the report |
| `annual_return − passive_annual_return > 0.02` | Read it off the report |
| "best", "strongest", "promising", "clean" appears in your draft | Search your own output |
| A validation check just passed | You just ran one |
| Out-of-sample exceeds in-sample | Read it off the report |
| A new asset, data source, or information type is entering the pool | The protocol diff is non-empty |

**If any row is true, run all five questions before writing another
sentence.**

Why mechanical rather than "when the result looks good": the moment a result
looks good is the moment you least want to interrogate it. A trigger whose
activation condition is the same mental state it exists to counteract does
not fire when it matters. `sharpe > 1.5` fires whether or not you feel like
it.

**Don't skip when:**
- The result is modest (modest results can be equally wrong)
- You already ran validation (that's exactly when the gap opens — see Level 3)
- You are near the end of a session and want to wrap up

The subtle human trigger still holds and is worth keeping as a supplement:
when you notice you *want* the result to be true, that is a signal to run
this skill. It is listed last because it cannot be verified — by you or by
anyone reading your work — and the table above can.

## The Five Questions

Run all five. They are ordered so the cheapest come first, but none is
optional.

### Q1: Compared to what, exactly?

Name the incumbent. Not "the baseline" — the specific strategy currently in
production or currently best, with its specific numbers.

**Failure mode:** the baseline wired into your reporting script is usually
the weakest available, not the strongest, and a challenger that beats a weak
baseline can still lose badly to the strongest one actually in contention.

**Check:** Can you state the incumbent's name and its three key metrics from
memory? If not, you don't have a comparison, you have a number.

**Also verify a passive control exists** on the same universe, costs, and
period. What a comparison against a passive control actually establishes is
often narrower than it looks: a strategy can underperform buy-and-hold on the
specific vehicle tested while the same signals would have beaten it on a
different vehicle, in which case the finding is "price-derived alpha was zero
*on this vehicle*," not "active management does not work."

### Q2: Was the decision criterion written before the result?

Pre-registration is the difference between an experiment and a search for
justification.

**Check:** Find where the adoption threshold is written. Confirm its
timestamp precedes the result. If it doesn't exist, you cannot adopt from
this run — write the criterion now and re-run, or explicitly mark the finding
as exploratory and requiring confirmation.

**Warning sign:** if you're constructing an argument for why the
pre-registered line was set wrong, stop. That argument is nearly always
available and nearly always wrong. Relaxing a decision line after seeing
results is the failure mode this whole discipline exists to prevent. When a
line seems genuinely mis-specified, the correct move is to record the
current result as rejected, then run a *new* pre-registered experiment with
the revised line.

### Q3: What does this validation NOT rule out?

This is the highest-value question in the skill, and the one people skip
because it feels like paranoia after a check has passed.

Every technique has a scope. Write down what falls outside it.

| Technique | Rules out | Leaves completely open |
|---|---|---|
| Multi-offset staggering | Rebalance-date luck | **Window-regime luck** |
| Walk-forward on parameters | Parameter overfit | **Universe selection** |
| Out-of-sample holdout | Fitting to the training window | **Multiple-testing across strategies** |
| Double-cost stress test | Cost-model optimism | Liquidity, capacity, market impact |
| Passing an IC test | Signal has no cross-sectional direction | **Turnover cost, tail risk, cross-section width** |
| High correlation to a reference source | Shape errors | **Level errors** |
| Randomized control | The layer you randomized | The layers you held fixed |

A result can pass every one of these techniques correctly and still be
misleading, because passing a technique only rules out the specific failure
mode that technique targets. A backtest window that happens to end at the
peak of an unusually strong run in one holding can survive multi-offset
validation cleanly — proving the result was not rebalance-date luck — while
still owing most of its performance to a window that will not repeat.

### Q4: How many effective independent trials?

Not how many strategies you ran — how many *independent* ones.

**Procedure:** compute the pairwise correlation matrix of strategy daily
returns. Report the average pairwise correlation and an effective
independent count.

**Why this matters:** a large number of strategies with high average
pairwise correlation is not a broad search; it can be one search repeated
many times under different names, and the multiple-comparison correction
should be computed against the effective count, not the nominal one.

The same measurement diagnoses convergence: when strategies all fail
together, inter-strategy correlation during a drawdown is often higher than
the full-sample average — highest precisely when diversification was needed.
If exposure-normalizing barely reduces correlation, your strategies differ
only in position size, and the fix is to relax a constraint rather than to
write the next signal formula.

### Q5: What would have to be true for this to be luck?

State the luck hypothesis concretely, then test it. Vague skepticism is not
this step; a specific alternative explanation is.

Useful concrete forms:
- "This works because the window ended after a large one-directional move in
  holding X." → Check X's return in the final year of the window.
- "This ranks well by chance among N variants." → Enumerate the variants and
  find the incumbent's percentile, in-sample *and* out-of-sample.
- "This asset's low correlation is an accounting artifact." → Check
  annualized vol < 2%, zero-return days > 20%, bond correlation > 0.5.
- "This edge is really just exposure." → Normalize for average exposure and
  see what survives.

## Level 3 Deep Checks

Run these when the result would change a production decision.

### Random control with directional percentile comparison

The single most useful diagnostic in the library, and the one most likely to
overturn a conclusion that a shallower check already declared settled.

**Procedure:**
1. Identify the layer under test (e.g. within-class instrument selection).
2. Fix it. Randomize every other layer. Generate the full distribution —
   enumerate if the space is small enough, sample if not.
3. Locate your configuration's percentile **in-sample**.
4. Locate its percentile **out-of-sample**.
5. Compare the *direction*.

**Interpretation:**

| In-sample percentile | OOS percentile | Meaning |
|---|---|---|
| High | Low | **Hindsight bias confirmed** |
| Low | High | **No bias** — the config is robust, not fitted |
| High | High | Genuine edge, or a shared regime dependence — investigate further |
| Low | Low | The layer isn't where your edge lives |

A mediocre in-sample percentile is not automatically evidence of a defect —
check its out-of-sample percentile before recording it as bias. If it rises
out-of-sample, the direction is the opposite of hindsight bias, and treating
the in-sample shortfall as a defect would have been the wrong conclusion.

### In-sample to out-of-sample rank correlation

Before chasing a better percentile, establish whether the ranking means
anything.

**Procedure:** for all variants, compute Spearman correlation between
in-sample and OOS rank.

**Interpretation:** low correlation means the entire spread is noise. A
mediocre in-sample rank is then not a defect, and chasing a better one is
overfitting across N variants on one window.

### Decompose before attributing

When a gap appears between what you achieved and what an "honest" rule
achieves, do not record the whole gap as bias.

**Procedure:** list the decision layers. For each, ask whether a competent
practitioner could have chosen it from priors alone, without seeing outcomes.
Prior-derivable layers are knowledge; outcome-derived layers are bias. Test
them separately with random control.

**And check your benchmark rule.** If the "honest executable rule" you're
measuring against is itself bad — selection by historical return
systematically buys tops — then the gap measures the value of competence, not
the size of your bias. Deducting it charges yourself for knowing what you're
doing.

## Common rationalizations

| Excuse | Reality |
|---|---|
| "We already validated across offsets." | That rules out date luck only. Regime luck needs unseen data. There is no substitute. |
| "The out-of-sample period is short, but the direction is clear." | A short window does not overturn several years of backtest. Record it, keep observing, don't adopt. |
| "The pre-registered line was set too conservatively." | This argument is always available. Reject the current result, then re-register. |
| "IC is significant." | IC cannot see turnover cost, tail risk, or cross-section width. A significant IC can still produce a strictly worse strategy. |
| "It's the best Sharpe we've produced." | A retail-accessible Sharpe well above 2 is nearly always an artifact. Run the falsification checks first. |
| "The data errors are small." | Probably true — measure it. Also check whether they're biased in the flattering direction. |
| "More assets means more diversification." | Measure it. Effective bets and portfolio volatility can both rise at once if constituent quality dilutes faster than diversification improves. |
| "We tested dozens of strategies, that's thorough." | Compute the effective independent count before calling a search broad. |
| "This asset class is theoretically convex." | Textbook properties are not product properties. Check actual NAVs. |
| "We diagnosed the exact bottleneck and fixed it." | Fixing the bottleneck can just move you along the same frontier. Re-plot it. |

## The checks, ordered by what they cost

| Level | Check | Cost |
|---|---|---|
| 1 | Named incumbent + passive control exists | seconds |
| 1 | Decision criterion predates the result | seconds |
| 2 | What this validation leaves open | minutes |
| 2 | Effective independent trial count | minutes |
| 2 | Concrete luck hypothesis, tested | minutes |
| 3 | Random control, in-sample vs OOS percentile direction | hours |
| 3 | In-sample to OOS rank correlation | hours |
| 3 | Layer decomposition before attribution | hours |

## Handoff

This skill produces answers, not a verdict. File them where the verdict gets
written — the round's entry in `docs/blacklist.md` or `docs/hall_of_fame.md` —
because an interrogation whose result goes unrecorded will be repeated in
full on the next result that looks equally good.

**Deliverable.** For each of the five questions: the answer, and what it
changed. "Nothing changed" is a valid answer and worth writing down, because
it is the only thing that distinguishes a result which survived scrutiny from
one that never received any.

Where to go next depends on what you found:

| Finding | Next |
|---|---|
| The comparison was against the wrong baseline | `building-the-foundation` — rebuild the control, then re-read every number that was computed against the old one |
| The decision criterion did not predate the result | `running-experiments` — re-register, then rerun. Do not re-register after seeing this result and call it pre-registered |
| The candidate set is less diverse than assumed | `running-experiments` — the constraint audit, not another mechanism |
| A luck hypothesis survived testing | `running-experiments` — the stress axis that would settle it |
| An attribution rests on a quantity nobody measured | `judging-the-round` — measure it before writing the verdict |
| Nothing changed | Back to what you were doing, with the record filed |

## Related

- `running-experiments` — where multi-offset validation is implemented, and
  the effective independent count is computed
- `judging-the-round` — the decomposition procedure in full, and what to do
  once you know what you actually have

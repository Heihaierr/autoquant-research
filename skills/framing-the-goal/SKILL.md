---
name: framing-the-goal
description: Use at the very start of a research program, when a user states a return target or risk limit, when they change the objective mid-program, and again after the passive baseline exists in order to calibrate the provisional target against the measured frontier. Also use before any data is fetched, to fix the vehicle, costs and execution semantics that everything downstream inherits.
---

# Framing the Goal

## Overview

This is the only stage that talks to the user, and it decides more than any
other. A target set badly cannot be rescued later: too high and every honest
result reads as failure, so the loop terminates in either a fake success or an
abandoned program; too low and a mediocre strategy clears the bar and stops
the search.

The stage has two halves with different modes. **Part A is a conversation** —
eliciting what the user actually needs, refusing goal forms that cannot be
tested, writing the target down in a falsifiable shape. **Part B is not** — it
fixes the vehicle, the execution semantics and the cost model, and those
follow from facts about the user's account rather than from preference.

## The Iron Law

```
A GOAL MUST LIE INSIDE A FRONTIER YOU HAVE MEASURED,
AND THE VEHICLE YOU MEASURE IT ON MUST BE THE ONE YOU TRADE
```

Both halves are measurements. A target set from an assumption about what is
achievable, rather than from a measured ceiling, cannot be defended later —
and a frontier measured on the wrong instrument is not a conservative
estimate of the right one, it is a different number, because implementation
gaps between similar-looking vehicles can run large enough to reverse a
conclusion. What matters is the ordering: measure, then promise.

## Part A — the conversation

### A1. Elicit constraints before discussing any number

Ask about the account and the person, not about returns. Returns are the
output of the constraint set, and a target named before the constraints are
known is a wish that will later be defended as a requirement.

What actually binds:

- **Capital and vehicle access.** What can this account buy? Exchange-traded
  funds, off-exchange funds, individual equities, derivatives? Access is
  usually narrower than assumed, and it is a fact you can check rather than
  infer.
- **Drawdown the user will actually sit through.** Not the number they say.
  Ask what they did the last time a holding fell 20%. Stated tolerance and
  revealed tolerance differ, and the revealed one governs whether the
  strategy survives contact with a bad quarter.
- **Attention budget.** Minutes per month, and whether a mid-month
  intervention is possible at all. This sets the rebalance frequency ceiling
  before any research happens.
- **Horizon and withdrawal risk.** Money that might be withdrawn in a
  drawdown changes the objective from terminal wealth to path.
- **Taxes and fees specific to this account**, including any minimum holding
  period. These can turn a viable frequency into a losing one.

### A2. Verify factual boundaries before researching around them

Questions like "can this account short?", "is there an inverse product?",
"can I rebalance weekly?" have definite answers in regulations and product
documentation. Checking takes minutes. Researching in the wrong direction
takes weeks, and the failure is silent because nothing about a well-run
backtest of an unavailable instrument looks wrong.

Do this before the target is written, because a discovered constraint changes
what is reachable, and the constraint that turns out to bind is not always
the one you went looking for — checking a fee schedule can turn up a
holding-period penalty nobody had asked about, which tightens the achievable
rebalance frequency as a side effect of an unrelated check.

### A3. Refuse goal forms that cannot be tested

Some targets are not hard, they are unfalsifiable. Rewrite them before
proceeding.

| The user says | The problem | Rewrite as |
|---|---|---|
| "Beat the market" | Which market, over what window, net of what costs? | Excess over a named benchmark, measured per window, after costs |
| "15% a year" | An absolute target ignores what the period offered; 15% in a year the passive basket returned 30% is underperformance | Excess over a passive control on the same universe |
| "Never lose money" | Achievable only by not investing | A drawdown budget, plus which convention measures it |
| "High Sharpe" | No threshold, so no possible refutation | A number, against a measured baseline distribution |
| "Beat my current strategy" | Beat it on which metric, by how much, over how many windows? | A named incumbent with its actual figures and a margin |

### A4. Write the target in conditional form

The output of Part A is a written statement with four parts: **the metric**,
**the comparison**, **the margin**, and **the number of windows it must hold
across**. Conditional because a target that does not say what would falsify
it cannot be missed, and a target that cannot be missed cannot be met.

Also record the **drawdown convention** and the **return convention** by name
at this point. Both have two defensible definitions, the definitions differ
by more than typical adoption margins, and choosing one silently later means
the convention decides the verdict.
→ [running-experiments](../running-experiments/SKILL.md)

### A5. The cold start problem, and why this skill runs twice

The law requires a measured frontier. On a new program there is no frontier
yet, because measuring one needs data and an engine — which come later. This
is a real circular dependency and the resolution is to split the target in
two:

**First pass (now).** Write a **provisional** target from priors: published
long-run returns for the asset classes involved, the user's constraints, and
explicit arithmetic. Label it provisional in the log. Its job is to be
falsifiable enough to guide the first round, not to be right.

**Second pass (after `building-the-foundation`).** The passive control now
exists, and so does its rolling distribution. Return here and calibrate:

1. Where does the passive control's headline figure sit in its own rolling
   distribution? A figure at the 90th percentile of its own history is a
   lucky draw, and a bar set against it will reject strategies that are
   genuinely better than what the user would actually have held.
2. Restate the target against the **distribution**, not the point estimate.
3. If the provisional target is outside the frontier, this is one of the six
   conditions that justify interrupting the user.
   → [using-autoquant](../using-autoquant/SKILL.md)

Do not skip the second pass because the first target "still seems fine." An
unexamined provisional target is indistinguishable from a measured one in the
log, and every verdict downstream inherits it.

### A6. When the goal is outside the frontier

Say so, with the measurement. Then present the trade explicitly: a lower
return target, a wider drawdown budget, a broader instrument universe, a
higher attention budget, or a longer horizon. These are the only levers, and
choosing between them is the user's call, not yours.

What not to do: quietly relax the target, or keep searching in the hope that
the next round finds what the previous ones did not. Both convert a
measurement into an unbounded search.

## Part B — the protocol, decided rather than discussed

Everything here is inherited by every experiment that follows, which is why
it is fixed before any data arrives. Changing any of it later invalidates
comparisons across the change.

### B1. Fix the vehicle

Name the exact instrument the user will buy, at the price they will pay. Not
a similar index, not the underlying, not an exchange-traded proxy for
something they will buy off-exchange. A vehicle change is a new program, not
a variant: two instruments that track the same index can differ enough in
their actual tradable price that a signal validated on one reverses its
conclusion on the other, and the size of that gap is not predictable from
how similar the instruments look on paper.

### B2. Pin execution semantics

Write down, in the engine's terms: which bar the decision is made from, which
bar it fills at, and how many days pass between them. The rule that keeps
this honest is that the strategy must never see the bar it trades on. Encode
it in the engine rather than in a comment.

### B3. Build the cost model

One-way cost as a fraction of traded notional, charged on the change in
weights. Include commission, half the spread, and any purchase or redemption
fee. Then define the stress tier — every result gets reported at baseline and
at double, because a strategy that survives only at baseline is a cost-model
artifact.

State any minimum holding period and its penalty. This interacts with
rebalance frequency and can invalidate a frequency the user assumed was
available.

### B4. Write the data protocol

Fix the research cutoff and assert it in the loader. Reserve recent months as
untouched out-of-sample. "We simply won't look" is not a control: the leak is
rarely a deliberate peek, it is a helper that resamples full history or a
benchmark loaded through a different function.

### B5. Declare what you cannot model

Capacity, market impact, borrow availability, tracking error against the
index a fund claims to follow. Name them and state that results do not
account for them. An unnamed limitation reads, three months later, as a
limitation that was checked.

## Common rationalizations

| Thought | What it actually is |
|---|---|
| "Let's start researching and set the target once we see what's possible" | The target will become whatever the best result was |
| "The user said 15%, so 15% is the requirement" | 15% is an opening position; the constraints determine feasibility |
| "Close enough on the vehicle, they track the same index" | Vehicle gaps between similar-looking instruments can be large and can run in either direction |
| "We'll add costs later" | Cost changes which strategy wins, not just by how much |
| "The provisional target held up, no need to recalibrate" | Unexamined and measured look identical in the log |

## Handoff

**Artifacts this skill must have produced:**

- `docs/goal.md` — the conditional target with metric, comparison, margin,
  window count; the drawdown and return conventions named; and whether the
  target is provisional or calibrated
- `config.yaml` — vehicle, execution semantics, cost tiers, research cutoff,
  rebalance frequency ceiling, universe
- `docs/research_log.md` — started, with the constraint elicitation recorded
  including revealed rather than stated drawdown tolerance
- `docs/limitations.md` — what cannot be modelled

**If all present:** load `building-the-foundation` and continue without
asking.

**If the target is outside the frontier, or constraints are mutually
unsatisfiable:** stop and put the trade to the user. These are two of the six
interrupt conditions.

**On the second pass** (arriving from `building-the-foundation` with a
passive control in hand): update `docs/goal.md` from provisional to
calibrated, then return to `running-experiments`.

## Related

- `building-the-foundation` — produces the passive control this skill needs
  for its second pass
- `judging-the-round` — where a persistent gap between target and frontier
  routes back to here

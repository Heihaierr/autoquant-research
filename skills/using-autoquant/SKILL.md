---
name: using-autoquant
description: Use at the start of any quantitative research task - finding a strategy, backtesting an idea, factor research, portfolio construction, or going live. Sets the goal with the user, then runs the loop autonomously. Also read this before asking the user anything mid-loop, because most mid-loop questions should not be asked.
---

# Using Autoquant

## Overview

You are being asked to find a strategy worth trading. That is the goal, and it
is worth saying plainly, because a research loop built only out of checks
converges on a different answer: that nothing passes. A program that runs
fifty strategies and rejects all fifty has not been rigorous. It has been
searching the wrong space carefully.

So this library has two halves, and they fail in opposite directions:

**Finding something.** Where candidate strategies come from, how to search
mechanism categories instead of parameter grids, how to find which dimension
actually moves your objective before spending rounds on the ones that don't.
Skip this half and you produce fifty variants of one idea.

**Believing it.** Whether a good number means anything: walk-forward, passive
controls, staggered rebalance dates, cost stress, pre-registered decision
lines. Skip this half and you ship noise.

Most quant material online is the second half. Most retail research is
neither. The mistake this library is built to prevent is doing the second half
well and the first half not at all — validating rigorously inside a strategy
space that was never actually searched, and mistaking a well-validated null
result for a finished program.

## The Iron Law

```
THE SEARCH SPACE IS NOT THE PARAMETER SPACE
```

Ten variants of one signal are one experiment reported ten times. Before
adding a round, ask which *category* of mechanism is untested — not which
parameter is unswept. Compute the effective independent count of your own
candidate set before concluding you have searched anything; a set of
strategies with high average pairwise correlation is a narrower search than
its size suggests, and the narrowing is invisible from the inside because
each new variant genuinely feels like a new idea to whoever wrote it.

## The loop

```
  ① framing-the-goal        ← the ONLY step that talks to the user
       ▼
  ② building-the-foundation ← data, then engine, then the passive control
       ▼
  ③ running-experiments     ← what to try, how to test it, in what order  ◀─┐
       ▼                                                                   │
  ④ judging-the-round       ← attribute, then SHIP/ITERATE/STOP            │
       │                                                                   │
       ├── ITERATE ────────────────────────────────────────────────────────┘
       ▼ SHIP
  ⑤ shipping-and-tracking   ← freeze, hold out, reconcile
```

Plus **detecting-self-deception**, which is not a stage. It fires on
mechanical conditions — a Sharpe above 1.5, excess above 2pp, a verdict about
to be written — and those conditions are listed in that skill rather than left
to your judgement about whether a result "looks good."

## Running without asking

Step ① is a conversation. Steps ② through ⑤ are not. Each skill ends with a
**Handoff** block naming the artifacts it must have produced; check that they
exist, then load the next skill and keep going.

This matters more than it sounds. An agent that asks permission at every
stage turns a research loop into a series of interruptions, and the user who
wanted a strategy gets a quiz instead. But an agent that asks nothing at all
will, when the target turns out to be unreachable, quietly lower the target —
which is the exact self-deception this library exists to prevent.

So the rule is neither "always ask" nor "never ask." It is a closed list.

### Interrupt the user only when one of these holds

| Condition | Why it cannot be decided for them |
|---|---|
| The goal sits outside the measured frontier | The only options are a worse goal or a looser constraint, and both are the user's to trade |
| Every data source failed | There is no research to do, and the fix may cost money |
| Money is required | A paid data source or a live order |
| An order is about to be placed | Real consequences, always confirmed |
| The user's constraints are mutually unsatisfiable | e.g. 20% annualized with a 5% drawdown budget — no strategy resolves this |
| A defect invalidates results already reported | They may have acted on them |

**Everything else: decide, record the decision and its reasoning, continue.**

The principle underneath the list: interrupt when continuing would produce a
*meaningless* result, or when continuing has *real-world consequences*. Not
when a choice is merely difficult. A difficult choice with a written
rationale is reviewable after the fact; an interruption is not free, and a
loop that stops twenty times never finishes.

Write every autonomous decision into the research log as you go. The log is
what makes the run auditable, and it is the substitute for having asked.

## Verification runs in a fresh subagent, not in yours

An agent that runs on top of a general-purpose coding agent can do something
a closed trading-bot product cannot: spin up a second, fully independent
instance of itself to check its own work. Use that. Four checkpoints in this
loop are specifically checks on the agent that just did the work, and each is
weakest when run in the same context that produced the thing being checked —
the agent already believes the data is clean, the engine is correct, or the
result is good, because it just finished building it.

| Checkpoint | Where | What the subagent gets |
|---|---|---|
| Data adjudication | `building-the-foundation`, B7 | Raw caches from both chains and the disputed dates — not your working theory of which source is right |
| Engine correctness | `building-the-foundation`, C10 | The engine alone, before any strategy code exists |
| Experiment audit | `running-experiments`, B7 | The report file and the checklist — not your summary of it |
| Next mechanism | `judging-the-round`, ITERATE | The mechanism map and blacklist — not your narrative about what almost worked |
| Self-deception check | `detecting-self-deception` | The report artifacts — never your draft conclusion |

Each skill above states this explicitly at the point it applies; this table
is the index. Treat a subagent's independent answer as evidence, not as a
rubber stamp — when it disagrees with your own read, the disagreement is
usually the finding.

## Entering in the middle

Two stages are useful on their own and are written to be callable directly.

**"Evaluate this strategy I already have"** → `running-experiments`. It needs
a price table, a strategy object exposing `target_weights`, and a named
incumbent to compare against. If there is no incumbent yet, it will route you
into `building-the-foundation` for a passive control first, because a
headline return with nothing to compare it to is not a result.

**"I have $100k, what do I buy today?"** → `shipping-and-tracking`. It needs a
frozen strategy. If the strategy is not frozen — if any parameter is still
being chosen — that skill will say so rather than produce a position list,
because a position list from an unfrozen strategy is a backtest artifact
wearing a timestamp.

## Non-negotiables

Each of these exists because skipping it produces a specific, silent failure
mode described in the skill that owns it.

1. **Walk-forward, never single-period.** A single-period backtest is not
   evidence.
2. **The vehicle you backtest is the vehicle you trade.** Same instrument,
   same price you will actually pay.
3. **A passive control on the same universe, always.** An active signal that
   cannot beat smart buy-and-hold has no net increment.
4. **Two cost tiers**, baseline and double.
5. **Multi-offset validation before any replacement decision.** Single-date
   results carry pure timing luck.
6. **Research cutoff asserted in the loader**, not in your discipline.
7. **Engine correctness tests before strategy code.** An engine bug
   invalidates everything downstream.
8. **Parameters from priors or structural reasoning**, never from what
   maximized the backtest.
9. **Every rejected mechanism written down with its cause.** A mechanism
   rules out a class; a number rules out one attempt.
10. **Verify regulatory and product facts before researching around them.**
    Minutes to check, weeks to research in the wrong direction.
11. **Count mechanism categories, not experiments.** Ten parameter values are
    one experiment.
12. **Data adjudication, engine tests, experiment audits, next-mechanism
    proposals, and self-deception checks run in a fresh subagent** — never in
    the context that built the pipeline, ran the experiment, or wants the
    result to be true.

## Red flags

Load `detecting-self-deception` if any of these appears in your reasoning or
your draft output:

- "This is the best result we've had."
- "It beat the baseline." — which baseline, at what percentile of its own
  distribution?
- "The IC is significant."
- "Let me just try one more parameter." — a parameter, or a mechanism?
- "The out-of-sample period is short but the direction is clear."
- "I'll write down the decision criteria once I see the numbers."

## Reference material

- `references/metrics-and-traps.md` — precise definitions for every metric
  used downstream, and the standard trap in each.
- `references/optimization-dimensions.md` — thirteen dimensions to search when
  a signal formula alone has stopped moving the objective, with the mechanism
  behind why each tends to help or hurt.
- `templates/` — a runnable project with the guards from non-negotiables 5, 6
  and 7 already wired in, plus two demo datasets so the loop can be run before
  you have any data of your own.

## Handoff

**Artifacts this skill must have produced:** none. It is the router.

**Next:** `framing-the-goal`, unless the user's request maps onto one of the
two mid-loop entry points above.

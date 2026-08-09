---
name: judging-the-round
description: Use when an experiment round has finished and before any verdict is written, and again at the start of every round to read what has already been tried. Also use when you are about to write the words bias, luck, regime or overfit next to a number, when a candidate appears to beat the incumbent, when two or more mechanisms in the same family have failed, when a numeric target has resisted three or more rounds, when a candidate loses in backtest and wins out-of-sample or the reverse, and when you are about to argue that a pre-registered line was set wrong.
---

# Judging the Round

## Overview

This is the hinge of the loop: everything before it produces evidence,
everything after depends on the verdict being honest. The stage does three
jobs in order, and skipping any one corrupts the others.

**Attribute.** A gap is a measurement; a cause is a hypothesis. Assign the
wrong cause and every later decision inherits the story, because nothing
downstream re-derives it.

**Adjudicate.** There are exactly three exits — SHIP, ITERATE, STOP — and the
common failure is a fourth: keep tuning without deciding, which looks like
diligence and is an unbounded search on a finite window.

**File.** A champion is one point on one window; a mechanism rules out a
class.

The judgment people expect here is "did we hit the target?" That is the
wrong question, since tuning cannot move a frontier. Ask instead whether the
*mechanism categories* available to you are exhausted — only that
distinguishes "we have not found it yet" from "it is not there."

## The Iron Law

```
A ROUND ENDS WITH A MECHANISM, NOT A NUMBER:
ATTRIBUTE IT TO A LAYER, DECIDE BY CATEGORY EXHAUSTION, FILE IT EITHER WAY
```

Attribution is a reasoning discipline, and reasoning errors are not
asset-class specific — but the *inventory* of mechanism categories in
`optimization-dimensions.md` reflects one particular constraint set. Anyone
able to short, lever, or trade derivatives holds categories that were never
tested there and must not read those verdicts as closed for their own
situation. Filing scales with volume: at a few experiments per round a plain
log file works; at high volume the same fields need a database and the
mechanism field needs enforcing by something other than the author's
conscience.

Before leaving this stage you must be able to name the layer each gap came
from, the mechanism category you have not yet tried, and the entry you
wrote.

## Step 1 — attribute before you adjudicate

The failure has a signature: a single number gets a single explanation. Real
strategies are stacks of decisions — asset classes, instruments within
classes, weighting scheme, cadence, cost model, vehicle — and a gap measured
at the top says nothing about which layer produced it. Run this step even
when the explanation is obvious; an attribution error is not less likely to
occur just because the wrong explanation seemed obvious at the time.

### Decompose the stack, then audit your benchmark rule

List the layers of the decision under test and mark each **prior-derivable**
or **outcome-derived**. A multi-asset skeleton chosen from priors is
knowledge; the instrument picked inside each class is hindsight bias *only
if* it was chosen by historical performance. Lumping them together books
domain knowledge as a defect.

Then audit the rule you are measuring yourself against. Attributing a
shortfall to a benchmark rule that is itself bad charges you for competence:
selection by trailing return systematically buys assets after their run, and
selection by trailing Sharpe degenerates into whatever has the lowest
volatility. A gap against a rule that bad measures *the value of prior
knowledge*, not your bias.

When a measured gap turns out, on proper testing, to be smaller than assumed
or zero, the deduction should be reversed rather than carried forward as
received wisdom — a setup whose surface matches an old conclusion closely can
still have a different underlying cause, and reusing the old answer instead
of re-deriving it is where borrowing does the most damage.

### The random control, read by direction

The highest-value diagnostic in this library, and the only clean test for
hindsight bias. Name the layer under test, fix it, and randomize every other
one — enumerate the space if small, sample if not. Evaluate every draw under
the *same* protocol as the incumbent: same cost tier, same offsets, same
windows. Then locate the incumbent's percentile in-sample and
out-of-sample, and compare the **direction**, not the level.

| In-sample pct | OOS pct | Meaning |
|---|---|---|
| High | Low | **Hindsight bias confirmed.** Deduct it. |
| Low | High | **No bias.** The configuration is robust, not fitted. |
| High | High | Genuine edge, or shared regime dependence. Investigate. |
| Low | Low | The layer is not where your edge lives. Stop optimizing it. |

A mediocre in-sample percentile is not automatically a defect — if the
out-of-sample percentile is higher, that is the opposite signature from
hindsight bias, and the in-sample shortfall was evidence rather than a flaw.

**Two design rules.** The randomization must respect the same priors as the
incumbent — drawing one instrument per class tests within-class selection,
drawing freely from the universe tests something else — and the control
should also be run on *alternative skeletons*, which is what turns "keep one
defensive slot" from a preference into a prior.

### Test whether the ranking carries information

Before chasing a better percentile, compute the Spearman correlation between
in-sample rank and out-of-sample rank across variants. Where it is near zero
the spread is noise, a mediocre percentile is not a defect, and chasing a
better one across N variants on one window is overfitting with extra steps.
The useful follow-up is whether a *prior* rule reproduces your configuration
— if "take the broadest instrument in each class" selects exactly what you
hold, it was never picked by performance at all.

### Measure the quantity your explanation depends on

The obvious mechanism is often the wrong one, and "same conclusion, different
cause" matters because the two imply opposite next experiments. Expanding a
static pool can produce a worse portfolio for a reason other than "more
instruments don't help" — the actual cause can be that constituent
volatility rose faster than the diversification ratio improved, which is a
measurable, different claim from "diversification doesn't work" and implies
a different fix.

The same discipline applies when every strategy behaves alike.
Exposure-normalize the returns and see whether inter-strategy correlation
actually falls. If it barely moves, the strategies differ in *how much* they
are invested rather than *what* they hold — under long-only, fixed-universe,
no-leverage constraints that is a property of the constraint set, not a
design flaw to fix with another signal formula, and the correct attribution
points at relaxing a constraint.

Three decomposition shapes are worth knowing. **By layer, cross-validated** —
find a second, structurally different route to the same number. **By
period** — positive in most sub-periods with the single negative being
exactly the regime a component's own prior predicts it loses in is a
structural claim; positive in one period by a huge margin is a window. **By
slot** — some members of a portfolio are usually net negative while others
carry it.

### Separate data problems from strategy problems

Answer the data question first. **Quantify, then re-run** — genuine errors
in a chain do not automatically invalidate prior work, though the direction
matters, because errors that flattered you are the dangerous kind. And
**shape agreement is not correctness, structure is not corruption**:
correlation is nearly blind to level errors, so it cannot clear a chain,
while low day-to-day correlation between two venues quoting the same
underlying is usually a timezone mismatch rather than damage. The criterion
is year-by-year return agreement.

## Step 2 — the verdict

### Exit 1: SHIP

| Gate | Standard |
|---|---|
| Named incumbent | Beaten on the pre-registered dimensions, by name and number |
| Passive control | Beaten on the same universe, costs, and period |
| Multi-offset | Re-validated across staggered rebalance dates, with σ reported |
| Cost tiers | Clears the line at baseline *and* double cost |
| Mechanism | Explainable without reference to the backtest |
| Unseen data | Not contradicted by any genuinely out-of-sample evidence |
| Honest expectation | Stated separately from the backtest number |

**Ship with the statistical honesty attached.** A champion can clear a
generous multiple-comparison bar and miss a conservative one, and the
verdict can still be SHIP — on mechanism interpretability, a low
cross-offset σ, and the realization rate, *not* on significance. The honest
sentence in that case is: "the most reasonable choice under current
evidence, not a strategy confirmed by strong evidence." Write that sentence
when it is true.

### Exit 2: ITERATE

Return to `running-experiments` with a **named, untried mechanism category**.
If the problem is the target rather than the dimension — the frontier is
where it is, and the goal was set against an assumption — return to
`framing-the-goal` instead. **Iterating within the mechanism family that
just failed is not iteration.**

The inventory of categories, each with a mechanism and general verdict, lives
in [optimization-dimensions](../../references/optimization-dimensions.md),
whose [selection table](../../references/optimization-dimensions.md#choosing-a-dimension)
maps a symptom to the dimensions worth trying. Read those verdicts as
hypotheses about mechanism, not as law for your own setup.

Two patterns worth checking against your own instinct before iterating.
**The biggest wins are often in carrier and input space** — what you
actually buy, and which asset classes are eligible — rather than in signal
formulas. And **"defense" dimensions have a history of diminishing returns**:
if drawdown is the complaint, mechanism-orthogonal ensembling and
static-weight ballast are usually worth trying before another protective
layer stacked on an existing one.

Verify a direction is available before iterating into it. A constraint
relaxation that looks attractive can turn out to be regulatorily impossible
— minutes to check, weeks to iterate the wrong way.

### Exit 3: STOP

STOP means the target is not inside the achievable frontier and you are
going to say so, with numbers. It is the hardest exit and the one that
distinguishes research from fabrication.

**The two-possibility test.** When you are stuck, either a structural
mechanism you have not tried exists — name it, change dimensions, continue,
which is ITERATE — or the known categories are exhausted and every
remaining path fits specific numbers to a finite window, which is STOP. The
whole test is whether you can name the category. "A different threshold" is
not one.

**Draw the frontier instead of guessing again.** When a target has resisted
several rounds, sweep the most influential continuous lever end to end. A
frontier gives a definite answer where another round of tuning gives another
data point, and it quantifies the gap on both axes. Sometimes no point on
the curve satisfies every one of the user's conditions at once, and stating
that plainly is itself a deliverable.

**Three failures in one family is a diagnosis, not bad luck**, and the
byproducts usually say why. A mechanism's own turnover can show it almost
never fired, which establishes something about the underlying regime rather
than about that one threshold — and retires a whole dimension rather than
three separate parameter guesses. **Check whether the mechanism was even
active before concluding the threshold was mistuned.**

**Fixing the diagnosed bottleneck may just move you along the frontier.**
Diagnosing why a mechanism failed, obtaining the tool that addresses it, and
re-running can improve the targeted symptom exactly as predicted while the
overall return and Sharpe both fall. **After a targeted fix, re-plot the
frontier — do not check whether the symptom improved.** Still on the same
curve means the binding constraint is deeper than your diagnosis: a STOP for
the family.

**A STOP report contains five items**, and without them it is
indistinguishable from giving up: the empirical frontier and the lever that
generated it; the quantified gap on both axes; every mechanism category
tried, with verdict and evidence; which initial constraint would have to be
relaxed, which is a user decision; and the honest expectation for the best
available strategy, separate from its backtest number.

## Step 3 — when the two samples disagree

### Backtest loses, out-of-sample wins

This is where pre-registration earns its cost. A candidate trips the
rejection line in a multi-year backtest while several independent indicators
point the other way out-of-sample — better return and drawdown, higher
realization rate, lower cross-offset σ — with a theoretical reason to expect
that pattern.

**Verdict: rejected per the pre-registered line, moved to the watchlist.** A
few months does not overturn several years, and relaxing a decision line
after seeing results is the exact failure this discipline exists to
prevent. But rejection is not erasure: record every contrary indicator, the
mechanism story, and **the date at which the data will suffice to
re-adjudicate**.

### The mirror case, and the symmetry test

Now the same situation with the sign flipped: the backtest fails the line
**and** the out-of-sample period is worse still. The verdict is unchanged,
and the *reasoning* has to be unchanged too, which takes deliberate effort
because a confirming out-of-sample result is pleasant to lean on. The
arithmetic that made a short sample too weak to overturn a rejection makes
it equally too weak to confirm one. Cite it as corroboration, clearly
labelled, and let the in-sample line do the work.

The test for whether you are reasoning symmetrically: **if this evidence had
come out the other way, would you have accepted it?** If not, you cannot use
it in the direction it happens to point. Noticing the pull toward a
convenient number is most of the work — evidence that agrees with you does
not feel like it needs a standard of proof.

## Step 4 — file the round

Every exit produces an entry, STOP included. File even when the failure was
"obvious in hindsight," because obviousness is not transmissible, and even
when nothing was learned — the entry then says what was measured and that no
mechanism was found.

| File | Contains | Purpose |
|---|---|---|
| `docs/hall_of_fame.md` | Adoptions, watchlist entries, structural findings, with the caveats on each | Why the current strategy is the current strategy, and what is wrong with it |
| `docs/blacklist.md` | Every failed experiment with numbers and mechanism, plus inherited conclusions | Prevents repeats, and closes off whole mechanism families |

Keep them separate. A single "research notes" file collapses into
narrative, which is not searchable by "has this been tried?".

### Blacklist entries: four required fields

```markdown
## EXP-<round>-<id> <one-line title including the verdict>

- **What was done**: <setup, frozen parameters, their source, the pre-registered
  adoption line>
- **Result**: <exact numbers vs the named incumbent, on which cost tier and
  offset basis>
- **Why it failed**: <mechanism, plus the byproduct evidence supporting it>
- **Transferable lesson**: <what class this closes off; note if this is the Nth
  confirmation of an existing entry>
- **Verdict**: <blacklist / watchlist, and what would reopen it>
```

Field 2 needs exact numbers, because vague results produce vague
prohibitions and vague prohibitions get ignored. Field 3 does the real work:
"it underperformed" blocks nothing, while a mechanism blocks a family — a
finding like "swapping a volatility denominator for a drawdown statistic
blows out turnover because maximum drawdown is an extreme-value statistic
determined by single points" generalizes into "prefer moment-based
statistics over extreme-value ones when formalizing an intuition," and can
stop a later, more sophisticated version of the same mistake.

**Byproduct evidence is often the most valuable line in the entry**, and the
most useful byproduct is whether the mechanism was ever active — record
turnover, fire count, or exposure change for anything conditional. An entry
that closes a whole *class* rather than one attempt is worth more than three
entries that each close one attempt in the same class.

The blacklist also does what a related-work section cannot: it records
**which of your own prior conclusions do not transfer**. Open it with an
inheritance statement naming what carries over by default, then add an entry
whenever a context change invalidates one, so that "we already know this"
and "this needs re-testing" are decidable from the log rather than from
argument.

### Hall of fame entries carry four disclosures

An adoption entry without disclosed weaknesses is marketing.

| Disclosure | What it looks like |
|---|---|
| **Tailwind dependence** | Which conditions the result depends on, with per-regime evidence rather than an average |
| **Survivorship / selection** | What was chosen with hindsight and its measured size — static-pool and walk-forward-pool numbers side by side |
| **Sample limitations** | Why this evidence is weaker than some other result in the same log, named |
| **Residual selection bias** | Whatever is still unresolved, stated as unresolved |

The template for adopting something you know is flawed: name the flaw,
quantify it, and state which property you are actually buying.

### The watchlist, and superseding yourself

Two cases are neither adopt nor reject. **Missed the line but never
falsified** — record the exact line and the gap, because objectives change;
a candidate shelved for missing a return line can come back into contention
without the entry looking like a new discovery, only if the entry exists.
**Loses in backtest, wins out-of-sample** — as in Step 3. A watchlist
without re-review dates is where candidates go to be forgotten.

When a prior conclusion turns out to be wrong: **never delete or silently
edit.** Add a correction entry naming what it supersedes, keep the original
visible with a pointer forward — the reasoning error is the transferable
content — and state the diagnostic that overturned it. Then **propagate the
numbers**, because a corrected attribution changes the honest expectation
wherever it appears.

### Seven questions the log must answer in under a minute

If any takes longer, the format is wrong and the log is a diary.

1. Has this direction been tried, by whom, in which round?
2. Why was it dropped — did it fail, or merely miss a line?
3. What were the numbers, on which cost tier and offset basis?
4. Which mechanism family does it belong to, and how many members have
   failed?
5. What would reopen it?
6. What is the current honest expectation for the champion, and which
   caveats produced it?
7. Which prior-generation conclusions are inherited, and which are known not
   to transfer?

A log you do not re-read is decoration, and the clean test is whether a new
failure re-commits a filed lesson. When one does, record it as *a filed
lesson re-committed in a new setting* rather than "the rule did not work."

## Common rationalizations

| Thought | What it actually is |
|---|---|
| "The honest rule underperforms us, so that is our bias." | Decompose the layers, and check whether the honest rule is any good first — the bias could be zero and the deduction double-counted |
| "We rank below the median, so we should improve it." | Measure in-sample-to-OOS rank correlation first. Near zero, the whole spread is noise. |
| "Being conservative is the safe error." | A wrong downgrade retires working strategies. Conservative and correct are different properties. |
| "That defense did not work, let me try a different trigger." | Count categories, not attempts. Several independent principles failing on one pool is a diagnosis. |
| "One more parameter combination." | Name the mechanism category. If you cannot, the round is over. |
| "The pre-registered line was too conservative." | That argument is always available. Record the rejection, then register a new experiment with a revised line. |
| "The out-of-sample period is short, but the direction is clear." | A sample too short to promote is too short to demote. Watchlist with a re-review date. |
| "We diagnosed the bottleneck and fixed it." | Re-plot the frontier. The symptom improving does not mean the strategy left the curve. |
| "Stopping means we failed." | Reporting a measured frontier and the distance to the target is a result. Manufacturing the number is not. |
| "It failed, there is nothing to write." | The mechanism is the content. An entry that closes a family is worth writing even when the result itself is negative. |
| "This is basically last round's entry." | Say so and count it: "third confirmation." |

## Handoff

**Artifacts this skill must have produced:**

- `docs/research_log.md` — the round's attribution, naming the layer each
  gap was assigned to and the diagnostic that established it
- `docs/blacklist.md` or `docs/hall_of_fame.md` — one entry per experiment,
  with all four required fields, or the four disclosures for an adoption
- `docs/verdict_<round>.md` — the exit taken: the gate table for SHIP, the
  named untried category for ITERATE, or the five items for STOP

**If the verdict is SHIP:** load `shipping-and-tracking` and continue
without asking. Do not place an order here — that skill freezes the
parameters first, and the order itself is a confirmed interrupt.

**If the verdict is ITERATE:** load `running-experiments` and continue
without asking, carrying the named untried category. If what needs revising
is the target rather than the dimension, load `framing-the-goal` instead and
expect it to interrupt the user, because choosing between a lower target and
a looser constraint is theirs.

**If the verdict is STOP:** the program ends here. Deliver the STOP report;
do not start another round.

**If any artifact is missing:** stop. State which artifact is missing and
which decision it blocks. A verdict written before the attribution exists is
the specific failure this skill prevents, and an unnamed mechanism category
is not an ITERATE.

## Related

- [Orthogonal optimization dimensions](../../references/optimization-dimensions.md)
  — the ITERATE inventory, one mechanism and general verdict per dimension
- `running-experiments` — supplies the evidence this skill adjudicates
- `detecting-self-deception` — run first when the result looks good rather
  than merely surprising
- `shipping-and-tracking` — where SHIP goes, and where a fired tracking
  trigger routes back from

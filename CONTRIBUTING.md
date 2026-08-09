# Contributing

## What this repository is

A set of behavioral instructions for coding agents doing quantitative
research — not documentation, and not a place for strategy code, signals, or
live configurations. Contributions should improve the methodology itself:
sharper procedures, better-calibrated defaults, corrections for markets the
current material handles badly, or gaps in the loop that let an agent (or a
person) fool themselves.

## Contributing to skills

Skills are behavioral instructions for coding agents. Some consequences for
how they should be written:

- **State a mechanism, not just an outcome.** "Validate across rebalance
  dates" is advice an agent can nod at and skip. "A single-date result
  carries measurable timing luck, and multi-offset validation is mandatory
  for any strategy containing a discrete trigger" is an instruction with a
  reason attached, and reasons are what make an agent actually follow a rule
  under pressure to ship.
- **Predict the rationalization.** The `Common Rationalizations` table
  exists because agents (and people) reliably talk themselves out of process
  steps. If you add a step, add the excuse someone will use to skip it.
- **State what a check leaves open.** Every validation technique answers a
  narrower question than it appears to. Being explicit about the boundary of
  each technique is what distinguishes a methodology from a checklist.
- **Keep it general.** Calibrated thresholds, specific market structure, and
  narrative case studies belong in a comment noting that they're
  illustrative, not in the rule itself. A rule stated as "recalibrate this
  against your own measured distribution" travels to a reader's situation; a
  rule stated as a single borrowed number usually does not.

Follow the structure in `skills/detecting-self-deception/SKILL.md`, which is
the reference format: `Overview`, `The Iron Law`, the procedure itself,
`Common rationalizations`, `Handoff`, `Related`.

## The second most valuable contribution: a market this doesn't cover

The reference material assumes long-only, unlevered, exchange-traded funds,
off-exchange funds, or individual equities, daily data, and
monthly-or-slower rebalancing. Several checks have thresholds that are
simply wrong outside that setting — a price-limit table calibrated to one
exchange's board rules is meaningless on a market with no price limits, and
the cost model assumes retail fund fees rather than a commission schedule
with margin.

If a check is wrong for your market, say so in an issue with what the right
version looks like. Corrections that widen applicability are welcome; so are
notes marking a rule as market-specific rather than general.

## Templates

`templates/` must stay runnable. If you change it:

- `pytest templates/tests/` passes
- No hardcoded instrument codes — market specifics go in config with a
  comment explaining what to change
- Every guard keeps the comment explaining which failure mode it prevents. A
  guard without its rationale gets deleted by the next person who finds it
  inconvenient.

## Process

1. Fork, branch from `main`
2. One logical change per PR
3. If you're proposing a rule change, say what evidence or reasoning backs it
4. English for all committed content; a Chinese edition lives under
   `docs/zh/`

## What gets rejected

- Strategy code, signals, or parameters — this is a methodology repository,
  and we don't publish live configurations either
- Rules stated as universal that are actually calibrated to one narrow
  setting, without saying so
- Advice with no mechanism behind it — "this tends to work" without a
  statable reason why

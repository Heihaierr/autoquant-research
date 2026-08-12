# autoquant-research

![A grey-haired veteran investor peels back a beautiful backtest with a loupe to find a crashing one hidden underneath, surrounded by the research loop and a museum of framed failures](../assets/hero.jpg)

<p align="center">
  <a href="https://github.com/Heihaierr/autoquant-research/actions/workflows/ci.yml"><img alt="CI" src="https://github.com/Heihaierr/autoquant-research/actions/workflows/ci.yml/badge.svg"></a>
  <a href="../../LICENSE"><img alt="License: MIT" src="https://img.shields.io/badge/license-MIT-yellow.svg"></a>
  <a href="../../skills/"><img alt="Agent Skills" src="https://img.shields.io/badge/agent%20skills-7-blue"></a>
  <a href="https://github.com/Heihaierr/autoquant-research/stargazers"><img alt="GitHub Repo stars" src="https://img.shields.io/github/stars/Heihaierr/autoquant-research?style=flat&color=yellow"></a>
</p>

<p align="center">
  <a href="../../README.md">简体中文</a> | <b>English</b>
</p>

**The superpowers of quant strategy research — an automated research
methodology that runs inside your AI agent, surfacing the strategies that
actually hold up and screening out the ones that only look good.**

A systematic trading research methodology for ETF rotation, stock
picking, and multi-asset allocation: walk-forward backtesting, strict
data quality checks, and honest performance attribution that separate
strategies that look profitable from ones that actually are. Ships as a
set of Agent Skills for Claude Code, Cursor, Codex, or any AI agent — not
a framework to import, nothing to install.

## Core features

- **Sharper experiments.** Finds the mechanism first, then validates it
  step by step — aimed at a strategy with a real chance of working
  forward, not a curve that only looks good in hindsight.
- **Stricter validation.** Every price series passes a quality check, and
  every strategy is tested across time windows and cost assumptions
  before it's trusted.
- **A goal that fits you.** Shaped by your risk tolerance, trading habits,
  and what your account can actually buy — not a generic default.
- **Fewer wasted steps.** Built from real research, so common failure
  modes are already in the process — fewer conversations, fewer tokens,
  to a conclusion worth trusting.

## Quick start

<details open>
<summary><b>Claude Code</b></summary>

```bash
/plugin marketplace add Heihaierr/autoquant-research
/plugin install autoquant-research@autoquant-research
```
</details>

<details>
<summary><b>Cursor</b></summary>

```text
/add-plugin autoquant-research
```

Or clone into your skills directory:
```bash
git clone https://github.com/Heihaierr/autoquant-research ~/.cursor/skills/autoquant-research
```
</details>

<details>
<summary><b>Any agent that reads portable Agent Skills</b></summary>

```bash
git clone https://github.com/Heihaierr/autoquant-research
```
Point your agent's skill directory at `skills/`. The skills are plain Markdown
with YAML frontmatter and no runtime dependencies.
</details>

Then just talk to your agent about a strategy idea. `using-autoquant` is the
entry point every other skill is reached from, and it will ask you the one
thing it cannot decide for you — the target — before running the rest of the
loop on its own.

Want to see it work before pointing it at your own data? Two demo price tables
ship in `templates/`, so the full loop runs with no network access and no API
key:

```bash
cd templates && pip install -r requirements.txt
pytest tests/ -q
PYTHONPATH=. python framework/walk_forward.py --config config.us.yaml --strategy s0_passive
```

## Why this exists

Tools that scan your backtest code for look-ahead bias and missing costs
already exist, and they're useful — but **static analysis catches code
errors. It cannot catch reasoning errors.** A conclusion like "the executable
rule underperforms our benchmark, so that gap must be hindsight bias" can be
built entirely out of correctly computed numbers and still be wrong, because
attributing a measured gap to the right cause is a judgment call, not a
statistic — and nothing about the arithmetic checks whether the judgment was
sound. That's the narrower thing this closes the loop on: run the standard
validation methods in the right order, and name the reasoning traps that show
up *after* a check has correctly passed, before they turn into a shipped
conclusion.

## The research loop

`using-autoquant` is the entry point. It executes none of the stages below —
it dispatches them, checks each handoff, and keeps the loop turning without
asking you at every step.

| | Skill | What it owns |
|---|---|---|
| | [`using-autoquant`](../../skills/using-autoquant/SKILL.md) | The entry point: dispatches the stages below, and holds the closed list of conditions that justify interrupting you |
| ① | [`framing-the-goal`](../../skills/framing-the-goal/SKILL.md) | The target, the vehicle, the execution semantics and the cost model. The only stage that is a conversation |
| ② | [`building-the-foundation`](../../skills/building-the-foundation/SKILL.md) | Data acquisition and QC, engine correctness tests, and the passive control every later number is read against |
| ③ | [`running-experiments`](../../skills/running-experiments/SKILL.md) | Where candidates come from — the mechanism map, sensitivity ranking, pre-registered decision line — and whether a result means anything: three report layers, staggered offsets, both cost tiers |
| ④ | [`judging-the-round`](../../skills/judging-the-round/SKILL.md) | Attribute the gap to a layer, take one of three exits — SHIP, ITERATE, STOP — and file the round either way |
| ⑤ | [`shipping-and-tracking`](../../skills/shipping-and-tracking/SKILL.md) | The evidence package, the parameter freeze, and three-layer reconciliation once the strategy is live |

One skill is not a stage and has no place in that sequence:

| | Skill | What it owns |
|---|---|---|
| ★ | [`detecting-self-deception`](../../skills/detecting-self-deception/SKILL.md) | Fires on mechanical conditions — a Sharpe above 1.5, an excess above 2pp, a verdict about to be written — rather than on your judgement that a result looks good |

It's a loop because real research goes around more than once, and each pass
back into `running-experiments` carries a named, untried mechanism category
rather than a repeat of the one that just failed.

Each skill can also be called on its own — "evaluate this strategy I already
have" goes straight to `running-experiments`, "I have capital, what do I buy
today" goes to `shipping-and-tracking` — without walking the full loop from
the top.

<p align="center">
  <img src="../assets/automation-chart.jpg" width="640" alt="Red: checked in the whole way, then breaks the moment the backtest ends. Blue: confirmed once at the start, gets there faster, and keeps climbing after the backtest ends.">
</p>

## How this compares

| | A generic coding agent | A backtesting library (backtrader, vectorbt, …) | A look-ahead / leakage linter | **autoquant-research** |
|---|---|---|---|---|
| What it is | A blank prompt | An engine you write strategies against | A static checker | A closed research loop, as Agent Skills |
| Catches code errors (look-ahead bugs, leaked timestamps) | Only if you ask | No | Yes | Yes, via engine correctness tests |
| Catches reasoning errors (right numbers, wrong conclusion) | No | No | No | Yes — this is the whole point |
| Forces walk-forward + cost stress before a verdict | No | No | No | Yes |
| Ships a runnable reference implementation | No | Yes, production-grade | No | Yes, teaching-grade — not for production |
| Something to import or depend on | — | Yes | Sometimes | No — plain Markdown, no runtime |

It composes with the other three: run your engine on a backtesting library,
run a linter over the code, and use this for the layer neither one covers —
whether the conclusion you drew from a correct number is actually true.

## Using the templates

`templates/` is the **reference implementation of the spec**, not a library
to depend on. It exists so the skills above are verifiable rather than
aspirational: you can see exactly what a look-ahead guard looks like, which
line asserts the research cutoff, and how three-layer reconciliation is
actually computed.

Two price tables ship with it — 11 US ETFs from 2006, 11 A-share ETFs from
2011, both total-return adjusted and cross-checked against a second source —
so this runs with no network access and no API key:

```bash
cd templates && pip install -r requirements.txt

pytest tests/ -q                                                     # engine + reconciliation assertions
PYTHONPATH=. python data/qc_data_quality.py --config config.us.yaml   # is the data real?
PYTHONPATH=. python framework/walk_forward.py --config config.us.yaml --strategy s0_passive
```

Swap in `config.cn.yaml` for the A-share table. Full walkthrough, including
what each script checks and why: [`templates/README.md`](../../templates/README.md).

For your own market: copy the directory and replace the market-specific parts
(instrument codes, price limits, cost model) with your own — or read it and
implement the same guards in whatever stack you already have.

```bash
cp -r templates/ my-research-project/
```

## Scope and honest limitations

The methodology is vehicle-agnostic — `framing-the-goal` asks what your
account can actually buy (ETFs, off-exchange funds, individual stocks) and
the rest of the loop follows from that answer. The reference implementation
that ships in `templates/` demonstrates it on global multi-asset ETF
rotation — US and Chinese onshore/offshore vehicles, daily data, monthly
rebalancing, long-only, no leverage — because that's the simplest complete
example, not the ceiling on what the loop handles.

Individual stocks add concerns an ETF basket doesn't have — single-name
delisting and corporate actions, earnings-driven jumps, sector and factor
crowding, thinner liquidity in the names you'd actually want to trade — and
the reference implementation does not ship guards for any of them. If you're
applying this to stocks, treat `building-the-foundation`'s data-quality tier
as a floor to extend, not a ceiling already met.

**What transfers:** the reasoning discipline. Attributing a gap to the right
layer, distinguishing a plateau from a spike, telling date-luck apart from
regime-luck, measuring what a validation actually leaves open. These are
about how humans and agents fool themselves with backtests, and they're
market-agnostic.

**What doesn't automatically transfer:** specific thresholds calibrated to
one market — a price-limit table, a cost model, an offset-dispersion
rejection bar. Each skill says explicitly which of its numbers are
illustrative defaults you should recalibrate and which are structural rules
that hold regardless of market.

**What this doesn't cover at all:** capacity and market impact at
institutional size, classical survivorship bias in the delisted-instrument
sense, formal multiple-testing corrections such as the deflated Sharpe ratio,
currency exposure as its own risk factor, and anything intraday, leveraged,
or derivative. If your program lives in one of those, treat this as a
starting point, not a complete answer.

## Philosophy

- **The purpose of research is not to find a good backtest.** It's to find out
  whether a good backtest means anything.
- **Every validation answers a narrower question than the one you're asking.**
  Write down what it leaves open.
- **Reporting the boundary beats manufacturing the number.** The difference
  between research and fabrication is whether you say "we looked and it isn't
  there" or quietly relax the standard until the output looks good.
- **A mechanism rules out a class. A number rules out one attempt.** File
  every round either way.

## Contributing

See [`CONTRIBUTING.md`](../../CONTRIBUTING.md). The most useful contributions
sharpen a skill's procedure, correct a threshold that's wrong outside the
reference market, or close a gap in the loop — not strategy code or live
parameters.

## License

MIT

# Templates — a research skeleton you can actually run

Most quant methodology repositories are documents. This is the part you run.

This is stripped of anything market- or strategy-specific — no tickers to
copy, no live parameters, no performance numbers. It is not a trading system
and it contains no strategies except the passive control group. It is the
scaffolding around a strategy: the engine, the evaluation protocol, the tests
that catch the mistakes that silently inflate results, and the live-tracking
loop that tells you afterwards whether any of it was real.

The defensive parts are the point. Each one exists because something went wrong
and cost real time. Those are marked in the code with a `WHY THIS EXISTS` block
and listed in [Lessons encoded in code](#lessons-encoded-in-code) below.

---

## Quick start

Two price tables ship with the repository, so this runs with no network access
and no API key:

```bash
pip install -r requirements.txt

pytest tests/ -q                                                     # engine + reconciliation assertions
PYTHONPATH=. python data/qc_data_quality.py --config config.us.yaml   # is the data real?
PYTHONPATH=. python data/qc_price_limits.py --config config.us.yaml   # is any value impossible?
PYTHONPATH=. python framework/walk_forward.py --config config.us.yaml --strategy s0_passive
```

Swap `config.us.yaml` for `config.cn.yaml` to run the same thing on A-share
ETFs. Both configs set `research_end` to 2024-12-31, which leaves 2025 onward
as a genuinely untouched out-of-sample period — spend it carefully, because you
only get to look once.

Run the tests before you write a strategy, and establish the passive baseline
before you believe any active result. Both take a minute and both change what
the rest of the numbers mean.

The `config.cn.yaml` run ends with a `SCRUTINY REQUIRED` block — exit code is
still 0, this is not a failure. The passive basket beats its CSI 300 benchmark
by 3.67pp/year, which trips the same mechanical trigger a real candidate would
trip, on nothing more exotic than a diversified basket holding assets that
outran the domestic index over this sample. The comment beside `benchmark:` in
`config.cn.yaml` has the numbers. It is left in rather than tuned away because
a demo that never triggers its own scrutiny mechanism would be demonstrating
the wrong thing.

| | `config.us.yaml` | `config.cn.yaml` |
|---|---|---|
| Price table | `data/cache/prices_us.parquet` | `data/cache/prices_cn.parquet` |
| Instruments | 11 US ETFs | 11 A-share ETFs |
| Span | 2006-02-06 to 2026-08-07 | 2011-12-09 to 2026-08-07 |
| Source | Yahoo via `yfinance` | Sina via `akshare` |
| Rebuild with | `data/fetch_us_etfs.py` | `data/fetch_cn_etfs.py` |

Each table has a `_raw` companion holding the same instruments unadjusted. The
adjusted table alone cannot be checked; the pair is what makes the implied
distribution yield in `data/qc_data_quality.py` computable, and that check is
the one that catches a broken adjustment chain.

Your own market needs its own config and its own price table. `config.us.yaml`
is the better one to copy — its `expect_yield` values are non-zero, so the
strongest data check is doing real work from the first run.

---

## What is here

```
templates/
├── config.example.yaml          every market-specific number lives here
├── config.us.yaml               US ETF demo: 11 instruments, 2006-2026
├── config.cn.yaml               A-share ETF demo: 11 instruments, 2011-2026
├── requirements.txt
├── framework/
│   ├── protocols.py             Strategy interface + evaluation record types
│   ├── data_loader.py           config/price loading + the research cutoff
│   ├── backtest.py              the engine: costs, drift, settlement lag
│   ├── metrics.py               performance metrics + regime bucketing
│   └── walk_forward.py          three-layer evaluation, offsets, cost stress
├── strategies/
│   └── s0_passive.py            the control group
├── tests/
│   ├── test_engine_correctness.py   look-ahead, timing, costs, cutoff
│   └── test_reconcile.py            reconciliation arithmetic
├── tracking/
│   ├── paper_trade.py           dated signal snapshots (real OOS evidence)
│   └── reconcile.py             three-layer divergence attribution
└── data/
    ├── fetch_us_etfs.py         rebuild the US table
    ├── fetch_cn_etfs.py         rebuild the A-share table
    ├── qc_data_quality.py       is the data real? dividends, splits, gaps
    ├── qc_price_limits.py       physical-constraint data validation
    └── cache/                   the two shipped tables and their raw companions
```

### `framework/protocols.py`

The `Strategy` protocol and the dataclasses every evaluation produces. The
strategy interface is deliberately tiny — receive a price frame, return target
weights — because a strategy that cannot fetch its own data cannot look ahead.

`summarize_stability` turns a list of windows into the numbers you decide on,
including the ratio fields that expose a strategy which earned everything in
one lucky window. `summarize_timing_luck` measures how much the result moves
when you change nothing but the rebalance date.

### `framework/data_loader.py`

Loads the config and the price table. Contains the research cutoff assertion.
`ResearchConfig` resolves relative paths against the config file's directory,
so the project works from any checkout location.

### `framework/backtest.py`

Long-only weight-based engine. The execution semantics are documented at the
top of the file and asserted in the tests; read them before comparing numbers
with anyone else's backtest, because most disagreements are semantic:

- The strategy sees data through `t-1` and trades at the close of `t`.
- Day `t` earns yesterday's weights. New weights apply from `t+1`.
- Weights **drift** with prices between rebalances, so rebalancing costs money.
- `trade_lag=L` parks the changing part of the book in cash for `L` days.
- Costs are `|Δweight| × cost_one_way`, charged on the rebalance day.

### `framework/metrics.py`

Standard metrics, plus regime bucketing that splits performance into bull /
bear / sideways using only past data. `sharpe` subtracts the risk-free rate;
`sharpe_no_rf` exists only so old reports can be reproduced.

### `framework/walk_forward.py`

The evaluation protocol. Three report layers (per-window, cross-window
stability, regime attribution), each computed under two cost profiles and
across a grid of rebalance offsets. Writes JSON and CSV artifacts plus the
daily series for every window, so a disputed number can be checked later
without re-running anything.

```bash
PYTHONPATH=. python framework/walk_forward.py --strategy my_strategy \
    --offsets 0,5,10,15 --trade-lag 3 --freq monthly
```

### `strategies/s0_passive.py`

A fixed-weight basket, rebalanced on schedule, charged the same costs as
everything else. This is the number an active strategy has to beat. Its
docstring explains why "beat the index" is the wrong bar and why this baseline
is harder than it looks.

### `tests/`

`test_engine_correctness.py` is the file to read first. A backtest engine
cannot be validated by its output — a look-ahead bug produces an excellent
Sharpe ratio, not an exception — so these assert the semantics directly.

`test_reconcile.py` checks the reconciliation arithmetic against synthetic
data with known answers, because a reconciliation tool with a wrong formula
generates infinite false alarms.

### `tracking/`

`paper_trade.py` records a dated, append-only signal snapshot: target weights,
the price of everything at the moment of the signal, position sizes after lot
rounding, and the cash that could not be invested. `reconcile.py` compares
those snapshots against reality and splits the difference into data, execution
and strategy layers.

### `data/qc_price_limits.py`

Validates prices against constraints that make a value impossible rather than
merely unusual — exchange price limits, non-positive prices, frozen series,
download gaps.

### `data/qc_data_quality.py`

The check that a plausible-looking table is actually the thing it claims to be.
It compares the adjusted table against its unadjusted companion and reports the
distribution yield that the difference implies, then holds it against the yield
the instrument really pays. A broken adjustment chain does not produce strange
prices; it produces ordinary prices that are wrong by a few percent a year, and
this is the only check here that sees that. It is how the first source tried for
the US table was rejected: it implied 12.75%/yr of dividends on a developed-
markets fund that pays about 3%, while its price series looked entirely normal.

Also flags split-shaped jumps, since split ratios are small integer fractions
and a continuous distribution of daily moves does not produce them, and reports
missing trading days without filling any of them.

Both QC scripts exit non-zero on a finding, so they work as a gate rather than a
report you can skim past.

---

## What you must change

Nothing under `framework/` should need editing to change markets. These are the
places that must be reviewed:

| Where | What | Why it is specific to you |
|---|---|---|
| `config.yaml` → `research_end` | The hard cutoff | Everything after it is your only honest out-of-sample |
| `config.yaml` → `calendar.trading_days_per_year` | 252 / 244 / 365 | Annualization; wrong value skews every annualized figure |
| `config.yaml` → `calendar.risk_free_annual` | Your cash yield | Enters Sharpe and Sortino directly |
| `config.yaml` → `cost.one_way` | Commission + half spread + fees | The single most result-changing assumption you will make |
| `config.yaml` → `cost.min_hold_days` / `short_hold_penalty` | Short-term redemption fees, if any | Can rule out a rebalance frequency entirely |
| `config.yaml` → `universe` | Your instruments | Codes must match the price table's columns |
| `config.yaml` → `benchmark` | Primary index and passive blend | Defines what "outperformance" means |
| `config.yaml` → `tracking.lot_size` | Minimum tradable increment | 100 for many Asian ETFs, 1 for US equities, ~0 for crypto |
| `data/qc_price_limits.py` → `PRICE_LIMIT_RULES` | Your venue's daily limits | The example values are from one market and are wrong elsewhere |

Two things to get right before anything else:

**Prices must be total-return adjusted.** The series you would get holding one
unit and reinvesting every distribution. Raw last-traded prices turn every
dividend into a drawdown.

**The backtest vehicle must be the execution vehicle.** Not a similar
instrument — the exact thing your account will buy, priced the way you will
be filled. An exchange-traded price and the NAV of the fund built on the same
underlying holding are not interchangeable data sources for the same signal;
swap one for the other with the signal held constant and the return series
changes even though nothing about the signal did.

---

## Lessons encoded in code

Each of these is a defensive mechanism that exists because of a specific
failure. Deleting one restores the failure.

| Mechanism | Where | The lesson, in one line |
|---|---|---|
| Research cutoff assertion | `data_loader.load_prices` | "We won't look at recent data" is not a control; block the path mechanically, because the leak is a helper function, not a deliberate peek |
| `SpyStrategy` look-ahead test | `tests/test_engine_correctness.py` | A one-bar leak produces a beautiful equity curve rather than an error, so assert `max_seen < asof` structurally for all strategies at once |
| Sharpe subtracts the risk-free rate | `metrics.compute_metrics` | Omitting it biases every Sharpe upward by the same `rf / vol` term, and the error survives review precisely because it leaves rankings intact |
| Weight drift between rebalances | `backtest._drift_weights` | An engine that holds weights constant is silently rebalancing daily for free; the tell is a fixed-weight basket reporting exactly zero turnover and identical results at 1x and 2x cost |
| Multi-offset grid | `walk_forward` + `protocols.summarize_timing_luck` | Which day of the month you rebalance can move annual return by more than the edge you are testing for; a result that only clears the bar on one offset out of several was never cleared |
| Double-cost stress profile | `walk_forward.evaluate` | Anything that only clears the bar at 1x cost is an artifact of the assumption you know least well |
| Short-hold penalty | `backtest._turnover_cost` | A punitive short-term redemption fee can make a rebalance frequency impossible; price it instead of ignoring it |
| Pre-listing returns stay NaN | `backtest.daily_returns` | Back-filling a late listing gives it a flat, zero-volatility history that momentum and volatility screens will happily overweight |
| Circuit breaker armed without `eval_start` | `backtest.run_backtest` | Ours was silently inert for callers that omitted one argument, producing a batch of "the kill switch changes nothing" results that measured nothing |
| Config-driven limit groups | `data/qc_price_limits.py` | Classifying instruments by ticker prefix mislabelled a cross-border fund as limit-constrained and reported all of its real moves as corrupt |
| Physical over statistical QC | `data/qc_price_limits.py` | Statistical outlier rules quarantine real events and pass a mis-adjusted series with plausible daily moves; impossible beats unusual |
| Three-layer reconciliation | `tracking/reconcile.py` | Collapsing data, execution and strategy into one number is how a data bug gets diagnosed as alpha decay |
| `None`, never `0.0`, on missing data | `tracking/reconcile.py` | A silent zero renders as a perfectly tracking portfolio, and it will be believed |
| Snapshot records the price at signal time | `tracking/paper_trade.py` | We repaired a price series — correctly — and silently invalidated every result derived from the old version; comparing recorded against current prices makes that detectable |
| Pre-registration refuses TODOs | `tracking/paper_trade.load_prereg` | A threshold written after a bad quarter is not a threshold; the file has to be complete before the first snapshot |
| Zero-unit position warning | `tracking/paper_trade.py` | If a target weight rounds to zero units, you are not running the strategy you evaluated, and no backtest number shows it |
| Baselines in the reconciliation output | `tracking/reconcile.py` | "Is this the strategy or the market" is a different question from all three layers, and it needs its own column |

---

## The methodology in four sentences

1. **Test the engine before writing a strategy.** Look-ahead bugs do not raise
   exceptions; they raise Sharpe ratios.
2. **Establish the passive baseline before believing an active result.** A
   fixed diversified basket at the same costs is a much harder bar than an
   index, and it is common for an active idea that beats the index to lose to
   it.
3. **Report every result across the offset grid and both cost profiles.** If
   the claimed edge is smaller than the spread across offsets, there is no
   edge.
4. **Freeze the parameters, then accumulate evidence forward.** A backtest over
   a period you have already seen is not out-of-sample, however the code is
   written.

---

## Scope and honest limits

The engine is long-only, weight-based, and rebalances on a monthly or weekly
schedule at daily resolution. It does not model intraday execution, shorting,
leverage, margin, options, borrow costs, taxes, or per-order market impact
beyond a linear cost on traded notional. If any of those matter for your
strategy, this engine will flatter it, and adding them is your job.

The methodology layer — look-ahead defenses, layered evaluation, timing-luck
grids, cost stress, layered attribution, pre-registration — is asset-agnostic.
The examples in the config are not.

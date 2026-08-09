"""Engine correctness tests. Write these before you write a single strategy.

A backtest engine is the one piece of a research stack that cannot be
validated by its output: a look-ahead bug does not produce an error, it
produces an excellent Sharpe ratio. The only defense is a test suite that
asserts the engine's semantics directly.

The most important test in this file is ``test_no_lookahead``. Everything else
protects a specific mistake we made and paid for.

Run:  pytest tests/ -q
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from framework.backtest import (  # noqa: E402
    DEFAULT_CIRCUIT_BREAKER,
    _drift_weights,
    _transit_weights,
    daily_returns,
    monthly_rebalance_dates,
    run_backtest,
    weekly_rebalance_dates,
)
from framework.data_loader import assert_no_lookahead, load_config, load_prices  # noqa: E402
from framework.metrics import compute_metrics  # noqa: E402


def make_prices(n_days: int = 260, n_assets: int = 3, seed: int = 0) -> pd.DataFrame:
    """Synthetic total-return price table starting on a month's first weekday.

    Starting on 2020-01-01 means index 0 is itself a monthly rebalance date.
    The engine skips the first bar (there is no prior close to have held from),
    so the first trade happens on ``monthly_rebalance_dates()[1]``. Several
    tests below index into that list and rely on this.
    """
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range("2020-01-01", periods=n_days)
    rets = rng.normal(0.0005, 0.01, size=(n_days, n_assets))
    values = (1.0 + rets).cumprod(axis=0) * 100.0
    return pd.DataFrame(
        values, index=dates, columns=[f"F{i}" for i in range(n_assets)]
    )


# ---------------------------------------------------------------------------
# 1. Look-ahead protection
# ---------------------------------------------------------------------------


class SpyStrategy:
    """Records the data window it was handed on every rebalance.

    It does not trade meaningfully; its only job is to let the test assert
    what the engine showed it.
    """

    def __init__(self):
        self.calls: list[tuple[pd.Timestamp, pd.Timestamp]] = []

    def target_weights(self, prices, asof):
        self.calls.append((asof, prices.index.max()))
        return {"F0": 1.0}


def test_no_lookahead():
    """The strategy must never see data dated on or after its decision date.

    WHY THIS EXISTS: this is the single assertion that separates a backtest
    from a fantasy, and it cannot be checked by inspecting results — a
    one-bar leak produces a beautiful equity curve, not an exception.
    Asserting ``max_seen < asof`` makes the guarantee structural: it holds for
    every strategy, including ones written later by someone who never read
    the engine.

    Note the strict ``<``. Allowing ``<=`` would let a strategy use the
    closing price of the day it trades on, which is a real and very
    profitable form of cheating.
    """
    prices = make_prices()
    spy = SpyStrategy()
    run_backtest(prices, spy)

    assert len(spy.calls) > 5, "strategy was barely called; test proves nothing"
    for asof, max_seen in spy.calls:
        assert max_seen < asof, (
            f"look-ahead: on {asof.date()} the strategy could see data "
            f"through {max_seen.date()}"
        )


def test_no_lookahead_weekly():
    """Same guarantee on the weekly schedule, which has ~4x more decisions."""
    prices = make_prices(130)
    spy = SpyStrategy()
    run_backtest(prices, spy, rebalance="weekly")

    assert len(spy.calls) > 15
    for asof, max_seen in spy.calls:
        assert max_seen < asof


def test_assert_no_lookahead_helper():
    """The standalone guard for research scripts that slice data themselves."""
    prices = make_prices(30)
    asof = prices.index[10]
    assert_no_lookahead(prices.loc[: prices.index[9]], asof)
    with pytest.raises(AssertionError):
        assert_no_lookahead(prices.loc[:asof], asof)


# ---------------------------------------------------------------------------
# 2. Execution timing
# ---------------------------------------------------------------------------


class SwitchStrategy:
    """All in F0 on the first rebalance, all in F1 from the second onward."""

    def __init__(self):
        self.n = 0

    def target_weights(self, prices, asof):
        self.n += 1
        return {"F0": 1.0} if self.n == 1 else {"F1": 1.0}


def test_new_weights_take_effect_the_next_day():
    """With trade_lag=0, the rebalance day still earns the OLD weights.

    Booking the new weights on the decision day itself would credit the
    portfolio with a day of performance it could not have captured, since the
    decision was made from the previous close.
    """
    prices = make_prices(80)
    result = run_backtest(prices, SwitchStrategy(), cost_one_way=0.0)
    rets = prices.pct_change(fill_method=None)

    switch_date = monthly_rebalance_dates(prices)[2]  # first trade is at [1]
    i = list(prices.index).index(switch_date)

    assert result.daily_return.iloc[i] == pytest.approx(rets["F0"].iloc[i])
    assert result.daily_return.iloc[i + 1] == pytest.approx(rets["F1"].iloc[i + 1])


def test_trade_lag_parks_the_changing_part_in_cash():
    """With trade_lag=3, a full switch earns zero for three days.

    Models a venue where proceeds are not available immediately. The part of
    the book that is NOT changing keeps earning (see the next test); only the
    part in flight sits in cash.
    """
    prices = make_prices(80)
    result = run_backtest(prices, SwitchStrategy(), cost_one_way=0.0, trade_lag=3)
    rets = prices.pct_change(fill_method=None)

    switch_date = monthly_rebalance_dates(prices)[2]
    i = list(prices.index).index(switch_date)

    for k in (1, 2, 3):
        assert result.daily_return.iloc[i + k] == pytest.approx(0.0), (
            f"day +{k} should be in cash while the trade settles"
        )
    assert result.daily_return.iloc[i + 4] == pytest.approx(rets["F1"].iloc[i + 4])


def test_transit_weights_keep_the_unchanged_overlap():
    assert _transit_weights({"A": 0.6, "B": 0.4}, {"A": 0.3, "C": 0.7}) == {"A": 0.3}


def test_weights_drift_between_rebalances():
    """Holding a fixed-weight basket must cost something.

    WHY THIS EXISTS: an engine that leaves weights untouched between
    rebalances is silently rebalancing to target every day for free. We
    shipped that bug. The symptom was subtle and easy to read past — a
    fixed-weight baseline reporting exactly 0.00 annual turnover, and the 1x
    and 2x cost profiles producing identical results, which means the cost
    stress test had been measuring nothing for the whole program.

    A constant-weight basket over 300 days must trade well beyond the initial
    purchase (turnover 1.0) to undo price drift each month.
    """
    class FixedBasket:
        def target_weights(self, prices, asof):
            return {"F0": 0.5, "F1": 0.5}

    prices = make_prices(300)
    result = run_backtest(prices, FixedBasket(), cost_one_way=0.001)

    assert result.daily_turnover.sum() > 1.05, (
        "a fixed-weight basket reported no rebalancing trades; weights are "
        "not drifting and rebalancing is free"
    )
    expensive = run_backtest(prices, FixedBasket(), cost_one_way=0.01)
    assert expensive.equity.iloc[-1] < result.equity.iloc[-1]


def test_drift_math_is_value_weighted():
    """w' = w(1+r) / (1+r_portfolio), with idle cash rescaling the same way."""
    drifted = _drift_weights({"A": 0.5, "B": 0.5}, {"A": 0.10, "B": 0.0}, 0.05)
    assert drifted["A"] == pytest.approx(0.5 * 1.10 / 1.05)
    assert drifted["B"] == pytest.approx(0.5 / 1.05)
    assert sum(drifted.values()) == pytest.approx(1.0)

    half_cash = _drift_weights({"A": 0.5}, {"A": 0.10}, 0.05)
    assert half_cash["A"] == pytest.approx(0.5 * 1.10 / 1.05)
    assert sum(half_cash.values()) < 1.0, "uninvested cash must stay uninvested"


# ---------------------------------------------------------------------------
# 3. Cost model
# ---------------------------------------------------------------------------


def test_cost_is_charged_on_turnover():
    """Cost equals ``cost_one_way × Σ|Δw|``, charged on the rebalance day."""
    prices = make_prices(80)
    cost = 0.0015
    free = run_backtest(prices, SwitchStrategy(), cost_one_way=0.0)
    charged = run_backtest(prices, SwitchStrategy(), cost_one_way=cost)
    rebals = monthly_rebalance_dates(prices)

    i_open = list(prices.index).index(rebals[1])  # cash -> F0, turnover 1.0
    diff = free.daily_return.iloc[i_open] - charged.daily_return.iloc[i_open]
    assert diff == pytest.approx(cost * 1.0)

    i_switch = list(prices.index).index(rebals[2])  # F0 -> F1, turnover 2.0
    diff = free.daily_return.iloc[i_switch] - charged.daily_return.iloc[i_switch]
    assert diff == pytest.approx(cost * 2.0)


def test_double_cost_stress_is_strictly_worse():
    """The 2x cost profile must actually bite.

    WHY THIS EXISTS: every result should be reported at 1x and 2x cost.
    A strategy that clears the bar only at 1x is an artifact of the cost
    assumption, and the cost assumption is the number you know least well.
    """
    prices = make_prices(260)
    single = run_backtest(prices, SwitchStrategy(), cost_one_way=0.0015)
    double = run_backtest(prices, SwitchStrategy(), cost_one_way=0.0030)

    assert double.equity.iloc[-1] < single.equity.iloc[-1]
    turnover = single.daily_turnover.sum()
    gap = single.daily_return.sum() - double.daily_return.sum()
    assert gap == pytest.approx(0.0015 * turnover, rel=1e-9)


def test_short_hold_penalty_applies_to_fast_round_trips():
    """Sells inside ``min_hold_days`` are charged the penalty rate.

    Some venues impose a punitive fee on short holding periods, which can rule
    out a rebalance frequency entirely. Modelling it as a cost rather than a
    ban shows how much of a strategy's edge depends on trades it would not be
    allowed to make.
    """
    prices = make_prices(120)
    plain = run_backtest(prices, SwitchStrategy(), cost_one_way=0.001)
    penalized = run_backtest(
        prices, SwitchStrategy(), cost_one_way=0.001,
        min_hold_days=60, short_hold_penalty=0.05,
    )
    assert penalized.short_hold_violations > 0
    assert plain.short_hold_violations == 0
    assert penalized.equity.iloc[-1] < plain.equity.iloc[-1]


# ---------------------------------------------------------------------------
# 4. Rebalance schedules and timing luck
# ---------------------------------------------------------------------------


def test_weekly_schedule_is_a_superset_of_monthly():
    """Weekly must include every monthly date.

    Otherwise a weekly-vs-monthly comparison differs in two ways at once (the
    extra checks AND the days the ranking was computed on) and the result
    cannot be attributed to either.
    """
    prices = make_prices(260)
    weekly = set(weekly_rebalance_dates(prices))
    monthly = set(monthly_rebalance_dates(prices))

    assert monthly.issubset(weekly)
    fridays = {d for d in prices.index if d.dayofweek == 4}
    assert fridays.issubset(weekly)
    assert len(weekly) > len(monthly) * 3


def test_offsets_produce_different_results():
    """Rebalancing on a different day of the month changes the result.

    WHY THIS EXISTS: which trading day of the month you rebalance on is not a
    property of the strategy, but it moves the annual return — by 1 to 2pp in
    our program, which was larger than most edges we were trying to detect.
    This test asserts the sensitivity is real so that nobody reports a single
    offset as if it were the answer. Always run the offset grid and quote the
    mean with the spread.
    """
    prices = make_prices(500)
    finals = [
        run_backtest(prices, SwitchStrategy(), rebal_offset=off).equity.iloc[-1]
        for off in (0, 5, 10, 15)
    ]
    assert len(set(np.round(finals, 8))) > 1, (
        "offsets gave identical results; the offset grid is not wired up"
    )


def test_monthly_offset_clamps_in_short_months():
    """A month with fewer trading days than the offset uses its last day."""
    prices = make_prices(260)
    dates = monthly_rebalance_dates(prices, offset=99)
    by_month = pd.Series(prices.index, index=prices.index.to_period("M"))
    for d in dates:
        assert d == by_month.loc[d.to_period("M")].max()


# ---------------------------------------------------------------------------
# 5. Missing data
# ---------------------------------------------------------------------------


def test_not_yet_listed_asset_contributes_zero_not_nan():
    """Holding an asset before it has prices must not poison the return series."""
    prices = make_prices(80)
    prices.loc[prices.index[:40], "F2"] = np.nan

    class HoldF2:
        def target_weights(self, prices, asof):
            return {"F2": 1.0}

    result = run_backtest(prices, HoldF2(), cost_one_way=0.0)
    assert not result.daily_return.isna().any()


def test_returns_are_not_fabricated_before_first_observation():
    """No return may be computed for a day before an instrument existed.

    Back-filling a late listing would give it a flat, zero-volatility history,
    which any volatility-weighted or momentum screen will happily overweight.
    """
    prices = make_prices(60)
    prices.loc[prices.index[:30], "F1"] = np.nan
    rets = daily_returns(prices)

    assert rets["F1"].iloc[:31].isna().all()
    assert rets["F1"].iloc[32:].notna().all()


def test_midstream_gap_does_not_lose_the_move():
    """A missing print mid-series is forward-filled, not dropped."""
    prices = make_prices(60)
    gap = prices.index[20]
    prices.loc[gap, "F0"] = np.nan
    rets = daily_returns(prices)

    assert rets["F0"].loc[gap] == pytest.approx(0.0)
    assert not np.isnan(rets["F0"].iloc[21])


# ---------------------------------------------------------------------------
# 6. Metrics
# ---------------------------------------------------------------------------


def test_sharpe_subtracts_the_risk_free_rate():
    """``sharpe`` is the excess-return ratio; ``sharpe_no_rf`` is not.

    WHY THIS EXISTS: an earlier version of this code reported
    ``mean(r) × T / vol`` as "Sharpe". The bias is exactly
    ``risk_free / volatility`` — 0.15 at a 1.5% risk-free rate and 10%
    volatility. It survived for a long time because it is a constant offset
    that leaves cross-strategy rankings intact, so nothing looked wrong
    internally. Every absolute Sharpe quoted externally was overstated.
    """
    rng = np.random.default_rng(7)
    index = pd.bdate_range("2020-01-01", periods=1000)
    returns = pd.Series(rng.normal(0.0004, 0.01, len(index)), index=index)

    trading_days, risk_free = 252, 0.04
    m = compute_metrics(
        returns, trading_days=trading_days, risk_free=risk_free
    )
    vol = returns.std(ddof=0) * np.sqrt(trading_days)

    assert m["sharpe"] == pytest.approx(
        (returns.mean() - risk_free / trading_days) * trading_days / vol
    )
    assert m["sharpe_no_rf"] == pytest.approx(returns.mean() * trading_days / vol)
    assert m["sharpe_no_rf"] - m["sharpe"] == pytest.approx(risk_free / vol)
    assert m["sharpe"] < m["sharpe_no_rf"]


def test_zero_risk_free_makes_both_sharpes_agree():
    rng = np.random.default_rng(11)
    index = pd.bdate_range("2020-01-01", periods=500)
    returns = pd.Series(rng.normal(0.0004, 0.01, len(index)), index=index)
    m = compute_metrics(returns, risk_free=0.0)
    assert m["sharpe"] == pytest.approx(m["sharpe_no_rf"])


def test_metrics_report_the_cost_drag():
    prices = make_prices(300)
    result = run_backtest(prices, SwitchStrategy(), cost_one_way=0.002)
    m = compute_metrics(
        result.daily_return, result.daily_return_gross, result.daily_turnover
    )
    assert m["return_before_cost"] > m["return_after_cost"]


# ---------------------------------------------------------------------------
# 7. Circuit breaker wiring
# ---------------------------------------------------------------------------


def test_circuit_breaker_is_armed_without_eval_start():
    """A configured breaker must act even when no ``eval_start`` is given.

    WHY THIS EXISTS: a previous version only armed the breaker at
    ``eval_start``, so every caller that omitted it got a silently disabled
    breaker — and a batch of "the kill switch changes nothing" results that
    were measuring nothing at all. A feature that can be silently inert needs
    a test that it is not.
    """
    index = pd.bdate_range("2020-01-01", periods=200)
    crashing = pd.Series(100.0 * (0.99 ** np.arange(len(index))), index=index)
    prices = pd.DataFrame({"F0": crashing, "F1": crashing})

    class AlwaysF0:
        def target_weights(self, prices, asof):
            return {"F0": 1.0}

    unprotected = run_backtest(prices, AlwaysF0(), cost_one_way=0.0)
    protected = run_backtest(
        prices, AlwaysF0(), cost_one_way=0.0,
        circuit_breaker=DEFAULT_CIRCUIT_BREAKER,
    )
    assert protected.equity.iloc[-1] > unprotected.equity.iloc[-1]


# ---------------------------------------------------------------------------
# 8. The research cutoff
# ---------------------------------------------------------------------------


def _write_project(tmp_path: Path, research_end: str, last_date: str) -> Path:
    """Minimal on-disk project: a config plus a price file."""
    cache = tmp_path / "data" / "cache"
    cache.mkdir(parents=True)
    index = pd.bdate_range("2020-01-01", last_date)
    frame = pd.DataFrame(
        {"ASSET_A": np.linspace(100, 200, len(index)),
         "ASSET_B": np.linspace(100, 150, len(index))},
        index=index,
    )
    frame.to_csv(cache / "prices.csv")

    config = tmp_path / "config.yaml"
    config.write_text(
        f"research_end: \"{research_end}\"\n"
        "data:\n"
        "  cache_dir: data/cache\n"
        "  price_file: prices.csv\n"
        "benchmark:\n"
        "  primary: ASSET_A\n"
        "universe:\n"
        "  - {code: ASSET_A, holdable: true}\n"
        "  - {code: ASSET_B, holdable: false}\n"
    )
    return config


def test_research_mode_truncates_at_the_cutoff(tmp_path):
    """Research mode must not return a single bar past ``research_end``.

    WHY THIS EXISTS: "we won't look at recent data" is not a control. The leak
    is almost never a deliberate peek — it is a helper that resamples the full
    history, or a benchmark loaded through a different function. Blocking it
    in the loader is the only place that covers every caller.
    """
    config_path = _write_project(tmp_path, research_end="2022-12-31",
                                 last_date="2024-06-28")
    cfg = load_config(config_path)

    research = load_prices(cfg, research=True)
    assert research.index.max() <= pd.Timestamp("2022-12-31")

    live = load_prices(cfg, research=False)
    assert live.index.max() > pd.Timestamp("2022-12-31"), (
        "research=False must return everything, otherwise live signals are stale"
    )


def test_holdable_flag_excludes_signal_only_instruments(tmp_path):
    from framework.data_loader import holdable_codes

    cfg = load_config(_write_project(tmp_path, "2022-12-31", "2024-06-28"))
    assert holdable_codes(cfg) == ["ASSET_A"]


# ---------------------------------------------------------------------------
# 9. The passive baseline
# ---------------------------------------------------------------------------


def test_passive_baseline_renormalizes_over_available_assets():
    """The control group must stay fully invested when an asset has no data."""
    from strategies.s0_passive import Strategy as Passive

    prices = make_prices(120)
    prices["F2"] = np.nan
    strategy = Passive(weights={"F0": 0.4, "F1": 0.4, "F2": 0.2})
    weights = strategy.target_weights(prices, prices.index[-1])

    assert set(weights) == {"F0", "F1"}
    assert sum(weights.values()) == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# Scrutiny triggers: the program noticing, so the reader doesn't have to
# ---------------------------------------------------------------------------


def _fake_stability(**summary):
    class Fake:
        pass

    obj = Fake()
    obj.summary = summary
    return obj


def _triggers_for(artifacts, capsys):
    from framework.walk_forward import _print_scrutiny_triggers

    _print_scrutiny_triggers(artifacts)
    return capsys.readouterr().out


def test_identical_cost_tiers_trigger_scrutiny(capsys):
    """Two cost tiers agreeing exactly means costs aren't charged, not robustness.

    WHY THIS EXISTS: an engine that held weights fixed between rebalances
    rebalanced for free every day. Its passive baseline reported turnover of
    0.0 and digit-identical returns at 1x and 2x cost, which was read as
    insensitivity to costs. It was the absence of costs.
    """
    out = _triggers_for({
        "offsets": [0],
        "stability_single": _fake_stability(mean_annual_return=0.10,
                                            mean_excess_return=0.0,
                                            sharpe_mean=1.0),
        "stability_double": _fake_stability(mean_annual_return=0.10,
                                            mean_excess_return=0.0,
                                            sharpe_mean=1.0),
    }, capsys)
    assert "SCRUTINY REQUIRED" in out
    assert "doubling costs changed nothing" in out


def test_separated_cost_tiers_do_not_trigger(capsys):
    """A real cost response must stay quiet, or the warning becomes noise."""
    out = _triggers_for({
        "offsets": [0],
        "stability_single": _fake_stability(mean_annual_return=0.10,
                                            mean_excess_return=0.0,
                                            sharpe_mean=1.0),
        "stability_double": _fake_stability(mean_annual_return=0.098,
                                            mean_excess_return=0.0,
                                            sharpe_mean=1.0),
    }, capsys)
    assert out.strip() == ""


def test_strong_result_triggers_scrutiny(capsys):
    """High Sharpe and large excess fire on the numbers, not on a judgement."""
    out = _triggers_for({
        "offsets": [0],
        "stability_single": _fake_stability(mean_annual_return=0.20,
                                            mean_excess_return=0.05,
                                            sharpe_mean=1.9),
    }, capsys)
    assert "Sharpe 1.90 exceeds 1.5" in out
    assert "excess over passive 5.00% exceeds 2pp" in out


def test_modest_result_stays_quiet(capsys):
    out = _triggers_for({
        "offsets": [0],
        "stability_single": _fake_stability(mean_annual_return=0.08,
                                            mean_excess_return=0.005,
                                            sharpe_mean=0.9),
    }, capsys)
    assert out.strip() == ""


def test_identical_offsets_trigger_but_small_spread_does_not(capsys):
    """Genuinely small spread is a property of static allocations. Zero is a bug."""
    base = _fake_stability(mean_annual_return=0.08, mean_excess_return=0.0,
                           sharpe_mean=0.9)

    identical = _triggers_for({
        "offsets": [0, 5, 10, 15],
        "stability_single": base,
        "timing_luck_single": {"std_annual_return": 0.0},
    }, capsys)
    assert "offsets produced identical results" in identical

    tight = _triggers_for({
        "offsets": [0, 5, 10, 15],
        "stability_single": base,
        "timing_luck_single": {"std_annual_return": 0.0011},
    }, capsys)
    assert tight.strip() == ""

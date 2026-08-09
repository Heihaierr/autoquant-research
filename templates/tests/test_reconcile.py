"""Unit tests for the reconciliation formulas.

WHY THESE EXIST. Live tracking is only worth doing if the reconciliation is
arithmetically right. If the formula is even slightly off, every "divergence"
it reports is an artifact, and you will spend weeks investigating a bug in
your own spreadsheet while believing you are investigating a strategy.

The tests are built on synthetic prices with known answers, so they run
anywhere and do not depend on a data feed.

One trap worth naming, because we fell into it: do not test with a directional
assertion like "a smaller account should earn less". Idle cash from lot
rounding drags in a rising market and *protects* in a falling one, so the sign
is not an invariant. Test the identity instead — the relationship that holds
regardless of which way prices went.

Run:  pytest tests/ -q
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tracking.reconcile import (  # noqa: E402
    _check_data_layer,
    paper_return,
    weight_return,
)

CODES = ["AAA", "BBB", "CCC", "DDD"]
START = pd.Timestamp("2024-01-02")
END = pd.Timestamp("2024-06-28")
COST = 0.0006
LOT = 100


@pytest.fixture(scope="module")
def prices() -> pd.DataFrame:
    """Synthetic total-return prices: some assets rise, some fall.

    Mixed directions on purpose, so a test that accidentally depends on the
    market going up will fail here rather than in production.
    """
    rng = np.random.default_rng(42)
    index = pd.bdate_range("2023-06-01", "2024-12-31")
    drifts = [0.0006, -0.0004, 0.0002, -0.0001]
    data = {}
    for code, drift in zip(CODES, drifts):
        steps = rng.normal(drift, 0.008, len(index))
        data[code] = 50.0 * (1.0 + steps).cumprod()
    return pd.DataFrame(data, index=index)


def make_record(prices: pd.DataFrame, weights: dict, capital: float) -> dict:
    """Build a snapshot the way tracking/paper_trade.py would."""
    orders, invested = [], 0.0
    for code, weight in weights.items():
        price = float(prices[code].loc[START])
        units = math.floor(weight * capital / price / LOT) * LOT
        amount = units * price
        invested += amount
        orders.append({
            "code": code,
            "name": code,
            "target_weight": weight,
            "price_at_signal": price,
            "units": units,
            "amount": amount,
            "actual_weight": amount / capital,
        })
    return {
        "signal_date": str(START.date()),
        "strategy": "test",
        "capital": capital,
        "orders": orders,
        "invested": invested,
        "cash_residual": capital - invested,
    }


def test_frictionless_paper_matches_backtest_convention(prices):
    """With an enormous account, rounding vanishes and the two agree.

    This is the sanity check that the two functions describe the same
    portfolio at all. If it fails, nothing downstream means anything.
    """
    weights = {c: 0.25 for c in CODES}
    record = make_record(prices, weights, capital=1e10)

    paper = paper_return(prices, record, START, END, COST)
    backtest = weight_return(prices, weights, START, END, COST)

    assert paper is not None and backtest is not None
    assert abs(paper - backtest) < 2e-4, (
        f"frictionless case should agree: paper {paper:.6f} vs "
        f"backtest {backtest:.6f}"
    )


def test_paper_return_equals_actual_weights_times_asset_returns(prices):
    """The identity that must hold in every market direction.

        paper = Σ actual_weight_i × (P_end_i / P_start_i − 1)
                − cost × Σ actual_weight_i

    Asserted at a small account size where rounding error is large, because
    that is where a wrong formula would show up.
    """
    weights = {c: 0.25 for c in CODES}
    record = make_record(prices, weights, capital=20000)
    paper = paper_return(prices, record, START, END, COST)
    assert paper is not None

    expected = 0.0
    for order in record["orders"]:
        series = prices[order["code"]].loc[START:END].dropna()
        asset_return = float(series.iloc[-1]) / float(series.iloc[0]) - 1.0
        expected += order["actual_weight"] * asset_return
    expected -= COST * sum(o["actual_weight"] for o in record["orders"])

    assert paper == pytest.approx(expected, abs=1e-12)


def test_execution_friction_shrinks_with_account_size(prices):
    """Layer 2 must be measurable, and must be a function of account size."""
    weights = {c: 0.25 for c in CODES}
    small = make_record(prices, weights, capital=20000)
    large = make_record(prices, weights, capital=1e7)

    idle = lambda rec: rec["cash_residual"] / rec["capital"]
    drift = lambda rec: max(abs(o["actual_weight"] - o["target_weight"])
                            for o in rec["orders"])

    assert idle(small) > 0
    assert idle(small) > idle(large)
    assert drift(small) > drift(large)


def test_cost_is_actually_deducted(prices):
    """A cost parameter that does nothing is worse than no cost model."""
    weights = {c: 0.25 for c in CODES}
    free = weight_return(prices, weights, START, END, cost_one_way=0.0)
    charged = weight_return(prices, weights, START, END, cost_one_way=COST)

    assert free > charged
    assert (free - charged) == pytest.approx(COST * sum(weights.values()))


def test_missing_instrument_returns_none_not_zero(prices):
    """Silent zeros are the worst possible failure for a reconciliation tool.

    A missing instrument must surface as "cannot compute". Returning 0.0 would
    render as a portfolio tracking perfectly, and would be believed.
    """
    assert weight_return(prices, {"NOPE": 1.0}, START, END, COST) is None

    record = {
        "orders": [{"code": "NOPE", "units": 100, "price_at_signal": 1.0,
                    "target_weight": 1.0, "actual_weight": 1.0}],
        "capital": 10000,
        "cash_residual": 0,
    }
    assert paper_return(prices, record, START, END, COST) is None


def test_single_asset_matches_raw_price_change(prices):
    """Cross-check against the most naive possible calculation."""
    series = prices["AAA"].loc[START:END].dropna()
    expected = float(series.iloc[-1] / series.iloc[0] - 1.0) - COST
    got = weight_return(prices, {"AAA": 1.0}, START, END, COST)
    assert got == pytest.approx(expected, abs=1e-12)


def test_data_layer_flags_a_revised_price(prices, capsys):
    """Layer 1 catches history being rewritten under a recorded snapshot.

    WHY THIS EXISTS: we repaired a price series after finding bad prints in
    it, which was correct — but it silently invalidated every earlier result
    computed from the broken version. Comparing the snapshot's recorded price
    against the current database is what makes that detectable instead of
    mysterious.
    """
    good = make_record(prices, {c: 0.25 for c in CODES}, capital=100000)
    assert _check_data_layer(prices, [good], tolerance=0.005) == 0

    tampered = make_record(prices, {c: 0.25 for c in CODES}, capital=100000)
    tampered["orders"][0]["price_at_signal"] *= 1.10
    assert _check_data_layer(prices, [tampered], tolerance=0.005) == 1

    out = capsys.readouterr().out
    assert "CHANGED" in out


def test_snapshot_strategy_cannot_see_the_close_it_fills_at(prices):
    """The tracking script must not hand the strategy its own fill price.

    WHY THIS EXISTS: this was a real bug in this template. The snapshot builder
    passed history through the final date and then filled at that same close.
    It reads as harmless — "decide from the latest data" — but it is not
    executable: you cannot act on a closing price until the close has already
    happened.

    The direction is what makes it serious. Seeing the fill bar inflates the
    tracked result relative to the backtest, so the one artifact whose entire
    purpose is detecting live decay would have been systematically biased
    toward reporting no decay.
    """
    from tracking.paper_trade import build_snapshot

    seen: dict[str, pd.Timestamp] = {}

    class Recorder:
        def target_weights(self, history, asof):
            seen["last_bar"] = history.index[-1]
            seen["asof"] = asof
            return {CODES[0]: 1.0}

    window = prices.loc[:END]
    snapshot = build_snapshot(
        window, Recorder(), capital=100000, lot_size=LOT,
        names={}, strategy_name="test",
    )

    fill_date = window.index[-1]
    assert seen["asof"] == fill_date
    assert seen["last_bar"] < fill_date, (
        "strategy saw the bar it fills at — look-ahead in the tracking path"
    )
    assert seen["last_bar"] == window.index[-2]

    # The fill still happens at the fill date's close, matching the engine.
    assert snapshot["signal_date"] == str(fill_date.date())
    assert snapshot["decision_cutoff"] == str(window.index[-2].date())
    assert snapshot["orders"][0]["price_at_signal"] == pytest.approx(
        float(window[CODES[0]].loc[fill_date])
    )

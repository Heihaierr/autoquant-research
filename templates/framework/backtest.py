"""Long-only weight-based backtest engine.

EXECUTION SEMANTICS — read this before trusting any number the engine prints.

* On rebalance date ``t`` the strategy is called with prices up to and
  including ``t-1``. It never sees ``t``. This is enforced by construction
  (the engine slices before calling) and asserted in the tests.
* Day ``t``'s return is earned on the weights held at the close of ``t-1``.
  New weights take effect for ``t+1`` onward. This models "decide after the
  close of t-1, trade at the close of t"; if your venue fills at the open of
  ``t`` instead, that is a different and slightly more optimistic assumption
  and you should say so out loud rather than change this quietly.
* ``trade_lag = L > 0`` models settlement delay: from the close of ``t``, the
  portfolio holds ``min(old, new)`` per instrument — the part of each position
  that is not changing keeps earning — and the changing part sits in cash
  earning zero until the new weights take effect ``L`` trading days later.
* Between rebalances, weights DRIFT with prices. See ``_drift_weights``; this
  is the difference between a monthly-rebalanced portfolio and a
  daily-rebalanced one, and getting it wrong makes rebalancing free.
* Costs are charged once, on the rebalance day, as ``|Δweight| × cost_one_way``
  summed over instruments, and are deducted from that day's return.
* The first bar is skipped (no prior close to hold from), so the first
  rebalance date in the sample does not trade.

Nothing here is market-specific. Fees, calendars and limits come from config.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Mapping, Tuple

import numpy as np
import pandas as pd

from framework.protocols import Strategy

# Weights below this are treated as zero when deciding whether a position was
# opened or fully closed. Only affects holding-period bookkeeping.
_EPS = 1e-9


@dataclass
class BacktestResult:
    daily_return: pd.Series          # net of trading cost
    daily_return_gross: pd.Series    # before trading cost
    daily_turnover: pd.Series        # sum of |Δweight| on each day
    equity: pd.Series                # cumulative product of net returns
    holdings: List[Tuple[pd.Timestamp, Dict[str, float]]] = field(default_factory=list)
    benchmark: pd.Series | None = None
    short_hold_violations: int = 0


def monthly_rebalance_dates(
    prices: pd.DataFrame, offset: int = 0
) -> List[pd.Timestamp]:
    """The (offset+1)-th trading day of each month.

    Months shorter than ``offset`` fall back to their last trading day.

    Run the whole evaluation at several offsets (0/5/10/15 is a reasonable
    grid) and report the spread. Which day of the month you happen to trade on
    is not part of the strategy, but it moves the result — see
    ``protocols.summarize_timing_luck``.
    """
    index = prices.index
    periods = index.to_period("M")
    dates: List[pd.Timestamp] = []
    for _, group in pd.Series(index, index=periods).groupby(level=0):
        days = list(group)
        dates.append(days[min(offset, len(days) - 1)])
    return dates


def weekly_rebalance_dates(prices: pd.DataFrame) -> List[pd.Timestamp]:
    """Last trading day of each week, union the first trading day of each month.

    Including the monthly dates makes the weekly schedule a superset of the
    monthly one, so a weekly-vs-monthly comparison differs by exactly one
    thing — the extra mid-month checks — instead of also differing by which
    days the ranking was computed on.
    """
    index = prices.index
    dates: set[pd.Timestamp] = set()
    for freq in ("W", "M"):
        grouped = pd.Series(index, index=index.to_period(freq)).groupby(level=0)
        for _, group in grouped:
            days = list(group)
            dates.add(days[-1] if freq == "W" else days[0])
    return sorted(dates)


def daily_returns(prices: pd.DataFrame) -> pd.DataFrame:
    """Simple returns, forward-filling gaps only after an instrument exists.

    Two failure modes this avoids:

    * ``prices.pct_change()`` with pandas' historical default forward-fills
      silently. A missing print in the middle of a series then produces a zero
      return followed by a two-day jump, which is right for a holder but is
      worth doing on purpose rather than by accident.
    * Forward-filling *before* an instrument's first observation would
      manufacture a flat price history back to the start of the sample, which
      makes late listings look like low-volatility assets and hands momentum
      screens a free lunch. Anything before the first real observation stays
      NaN, and the engine treats NaN as "not investable that day".
    """
    filled = prices.ffill()
    rets = filled.pct_change(fill_method=None)
    for col in prices.columns:
        first = prices[col].first_valid_index()
        if first is None:
            rets[col] = np.nan
        else:
            rets.loc[:first, col] = np.nan
    return rets


def _turnover_cost(
    w_old: Dict[str, float],
    w_new: Dict[str, float],
    entry_date: Dict[str, pd.Timestamp],
    t: pd.Timestamp,
    min_hold_days: int,
    base_cost: float,
    penalty_cost: float,
) -> Tuple[float, float, Dict[str, pd.Timestamp], int]:
    """Trading cost for moving from ``w_old`` to ``w_new``.

    With ``min_hold_days <= 0`` this is just ``base_cost × Σ|Δw|``.

    With ``min_hold_days > 0``, the part of a *sell* that unwinds a position
    entered less than ``min_hold_days`` calendar days ago is charged at
    ``penalty_cost`` instead. Some venues impose a punitive short-term
    redemption fee (an order of magnitude above normal cost), which quietly
    rules out rebalancing faster than that threshold. Modelling it as a
    penalty rather than a hard constraint lets you see how much a strategy
    depends on trades it would not be allowed to make.

    Entry dates are tracked FIFO-approximately: adding to an existing position
    does not reset its entry date. That understates the penalty slightly for
    added-to positions, so treat the reported violation count as a lower bound.

    Returns ``(cost, turnover, updated_entry_dates, n_violations)``.
    """
    codes = set(w_old) | set(w_new)
    cost = 0.0
    turnover = 0.0
    violations = 0
    new_entry = dict(entry_date)

    for code in codes:
        old_w = w_old.get(code, 0.0)
        new_w = w_new.get(code, 0.0)
        delta = new_w - old_w
        turnover += abs(delta)

        if delta < -_EPS:
            held_days = None
            if entry_date.get(code) is not None:
                held_days = (t - entry_date[code]).days
            too_soon = (
                min_hold_days > 0 and held_days is not None and held_days < min_hold_days
            )
            cost += (penalty_cost if too_soon else base_cost) * abs(delta)
            violations += int(too_soon)
            if new_w <= _EPS:
                new_entry.pop(code, None)
        elif delta > _EPS:
            cost += base_cost * delta
            if old_w <= _EPS:
                new_entry[code] = t

    return cost, turnover, new_entry, violations


def _transit_weights(
    w_old: Dict[str, float], w_new: Dict[str, float]
) -> Dict[str, float]:
    """Holdings while an order is in flight: the overlap keeps earning."""
    shared = set(w_old) & set(w_new)
    return {c: min(w_old[c], w_new[c]) for c in shared if min(w_old[c], w_new[c]) > 0}


def _drift_weights(
    weights: Dict[str, float], day_returns: Mapping[str, float], portfolio_return: float
) -> Dict[str, float]:
    """Let holdings drift with prices between rebalances.

    ``w_i' = w_i (1 + r_i) / (1 + r_portfolio)``. Any cash the strategy left
    uninvested is the residual ``1 - Σw`` and rescales the same way.

    WHY THIS MATTERS ENOUGH TO BE ITS OWN FUNCTION: an engine that leaves
    weights untouched between rebalances is not modelling a monthly-rebalanced
    portfolio. It is modelling one that is rebalanced back to target *every
    day, for free*. Two consequences, both flattering:

      * Turnover is understated. A fixed-weight basket run through such an
        engine reports zero turnover and therefore zero cost, when in reality
        it trades every rebalance to undo the drift. We found exactly this in
        our own engine: the passive baseline showed 0.00 annual turnover, and
        the 1x and 2x cost profiles returned identical numbers — the cost
        stress test was measuring nothing.
      * The return stream is wrong. Daily rebalancing systematically sells
        winners and buys losers, which is a real strategy with its own risk
        profile, not a neutral bookkeeping choice.
    """
    if abs(1.0 + portfolio_return) < 1e-12:
        return {}
    drifted = {}
    for code, w in weights.items():
        r = day_returns.get(code, 0.0)
        new_w = w * (1.0 + r) / (1.0 + portfolio_return)
        if new_w > _EPS:
            drifted[code] = new_w
    return drifted


def _normalize(weights) -> Dict[str, float]:
    """Clip to long-only and scale down if the book is over 100% invested."""
    clean = {str(k): max(0.0, float(v)) for k, v in dict(weights).items()}
    clean = {k: v for k, v in clean.items() if v > 0.0}
    total = sum(clean.values())
    if total > 1.0:
        clean = {k: v / total for k, v in clean.items()}
    return clean


def run_backtest(
    prices: pd.DataFrame,
    strategy: Strategy,
    *,
    cost_one_way: float = 0.0006,
    benchmark: pd.Series | None = None,
    rebalance: str = "monthly",
    rebal_offset: int = 0,
    trade_lag: int = 0,
    circuit_breaker: dict | None = None,
    eval_start: str | pd.Timestamp | None = None,
    min_hold_days: int = 0,
    short_hold_penalty: float = 0.015,
) -> BacktestResult:
    """Run one backtest.

    Args:
        prices: wide total-return price table, index sorted ascending.
        strategy: object implementing ``framework.protocols.Strategy``.
        cost_one_way: cost per unit of traded notional.
        benchmark: optional benchmark price series, passed through to metrics.
        rebalance: ``"monthly"`` or ``"weekly"``.
        rebal_offset: see ``monthly_rebalance_dates``.
        trade_lag: settlement delay in trading days.
        circuit_breaker: see ``DEFAULT_CIRCUIT_BREAKER``; ``None`` disables it.
        eval_start: date at which the equity/drawdown state used by the circuit
            breaker is reset. Set this to the first day of the test window so
            that a drawdown incurred during the warm-up period does not trip
            the breaker inside the window being scored.
        min_hold_days, short_hold_penalty: see ``_turnover_cost``.
    """
    prices = prices.dropna(how="all").sort_index()
    if rebalance == "monthly":
        rebal_dates = set(monthly_rebalance_dates(prices, offset=rebal_offset))
    elif rebalance == "weekly":
        rebal_dates = set(weekly_rebalance_dates(prices))
    else:
        raise ValueError(f"unknown rebalance schedule: {rebalance!r}")

    breaker = dict(circuit_breaker or {})
    # A breaker with no eval_start is armed from the first bar. Guarding this
    # on eval_start (as an earlier version of this engine did) silently
    # disabled the breaker for every caller that did not pass one, which made
    # a whole batch of "the breaker does nothing" results meaningless.
    breaker_armed = bool(breaker) and eval_start is None
    eval_start_ts = pd.Timestamp(eval_start) if eval_start is not None else None

    dates = prices.index
    rets = daily_returns(prices)

    cur_weights: Dict[str, float] = {}
    pending: Tuple[int, Dict[str, float]] | None = None  # (effective index, weights)
    entry_date: Dict[str, pd.Timestamp] = {}

    gross_list, net_list, turnover_list = [], [], []
    holdings: List[Tuple[pd.Timestamp, Dict[str, float]]] = []
    total_violations = 0
    equity, peak, cooldown = 1.0, 1.0, 0

    for i, t in enumerate(dates):
        if eval_start_ts is not None and not breaker_armed and t >= eval_start_ts:
            equity, peak, cooldown = 1.0, 1.0, 0
            breaker_armed = bool(breaker)

        if i == 0:
            gross_list.append(0.0)
            net_list.append(0.0)
            turnover_list.append(0.0)
            continue

        # --- 1. today's P&L, earned on yesterday's closing weights -----------
        day_ret = 0.0
        realized: Dict[str, float] = {}
        for code, w in cur_weights.items():
            if code in rets.columns:
                r = rets.iat[i, rets.columns.get_loc(code)]
                if not np.isnan(r):
                    realized[code] = float(r)
                    day_ret += w * r
        equity *= 1.0 + day_ret
        peak = max(peak, equity)
        drawdown = (equity / peak - 1.0) if peak > 0 else 0.0

        # Positions grow and shrink with prices; the book you hold tomorrow is
        # not the book you targeted last month.
        cur_weights = _drift_weights(cur_weights, realized, day_ret)

        # --- 2. decide the weights held into tomorrow -----------------------
        new_weights = dict(cur_weights)
        turnover = 0.0
        cost = 0.0

        breach_daily = breaker_armed and day_ret < -breaker.get("daily_loss", np.inf)
        breach_hard = breaker_armed and drawdown < -breaker.get("hard_dd", np.inf)
        breach_soft = breaker_armed and drawdown < -breaker.get("soft_dd", np.inf)

        if pending is not None and pending[0] <= i and cooldown == 0:
            new_weights = dict(pending[1])  # settled; cost was charged on order day
            pending = None

        defensive_code = breaker.get("defensive_code")
        defensive: Dict[str, float] = {}
        if defensive_code and defensive_code in prices.columns:
            if not np.isnan(prices.iat[i, prices.columns.get_loc(defensive_code)]):
                defensive = {defensive_code: 1.0}

        if cooldown > 0:
            new_weights, pending = dict(defensive), None
            cooldown -= 1
            cost, turnover, entry_date, viol = _turnover_cost(
                cur_weights, new_weights, entry_date, t,
                min_hold_days, cost_one_way, short_hold_penalty)
            total_violations += viol
        elif breach_daily or breach_hard:
            new_weights, pending = dict(defensive), None
            cooldown = (
                breaker.get("daily_loss_cool", 5) if breach_daily
                else breaker.get("hard_cool", 10)
            )
            cost, turnover, entry_date, viol = _turnover_cost(
                cur_weights, new_weights, entry_date, t,
                min_hold_days, cost_one_way, short_hold_penalty)
            total_violations += viol
        elif t in rebal_dates:
            history = prices.loc[: dates[i - 1]]  # strategy never sees date t
            target = _normalize(strategy.target_weights(history, t))
            if breach_soft:
                scale = breaker.get("soft_scale", 0.5)
                target = {k: v * scale for k, v in target.items()}
            cost, turnover, entry_date, viol = _turnover_cost(
                cur_weights, target, entry_date, t,
                min_hold_days, cost_one_way, short_hold_penalty)
            total_violations += viol
            if trade_lag <= 0:
                new_weights, pending = target, None
            else:
                new_weights = _transit_weights(cur_weights, target)
                pending = (i + trade_lag, target)

        equity *= 1.0 - cost  # today's trading cost, charged after the decision

        gross_list.append(day_ret)
        net_list.append(day_ret - cost)
        turnover_list.append(turnover)
        if turnover > 0 or t in rebal_dates:
            holdings.append((t, dict(new_weights)))
        cur_weights = new_weights

    net = pd.Series(net_list, index=dates)
    return BacktestResult(
        daily_return=net,
        daily_return_gross=pd.Series(gross_list, index=dates),
        daily_turnover=pd.Series(turnover_list, index=dates),
        equity=(1.0 + net).cumprod(),
        holdings=holdings,
        benchmark=benchmark,
        short_hold_violations=total_violations,
    )


# Reference values only. Drawdown-triggered kill switches tend to lose more
# to whipsaw than they save (see optimization-dimensions.md, dimension 6) —
# measure before enabling one. Off by default is the correct default.
DEFAULT_CIRCUIT_BREAKER = {
    "soft_dd": 0.08,
    "soft_scale": 0.50,
    "hard_dd": 0.12,
    "hard_cool": 10,
    "daily_loss": 0.02,
    "daily_loss_cool": 5,
    "defensive_code": None,
}

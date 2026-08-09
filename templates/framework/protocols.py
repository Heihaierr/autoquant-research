"""Contracts shared by the engine, the evaluator and the reports.

Two kinds of things live here:

1. The ``Strategy`` protocol — the single interface every strategy implements.
   Keeping it this narrow is deliberate: a strategy receives a price history
   that has already been truncated by the engine and returns target weights.
   It cannot reach for data on its own, so it cannot accidentally look ahead.

2. The evaluation record types. Walk-forward evaluation produces one
   ``WindowReport`` per (window x cost profile x rebalance offset), and the
   summaries are computed from those records rather than from ad-hoc dicts, so
   that "which numbers did we actually compare" is answerable months later.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from statistics import mean, median, pstdev
from typing import Dict, List, Mapping, Protocol, runtime_checkable

import pandas as pd


@runtime_checkable
class Strategy(Protocol):
    """The only interface a strategy needs to implement.

    ``target_weights`` is called on each rebalance date with the price history
    up to and including the *previous* trading day. Returning weights that sum
    to less than 1.0 leaves the remainder in cash; the engine renormalizes if
    the sum exceeds 1.0 and clips negative weights to zero (long-only).

    Optional ``reset()`` clears any internal state. The walk-forward runner
    calls it between windows so that a stateful strategy (one with a hysteresis
    band, a trailing stop, a TIPP floor...) does not carry state from one test
    window into the next — that would leak information across windows.
    """

    def target_weights(
        self, prices: pd.DataFrame, asof: pd.Timestamp
    ) -> Mapping[str, float]:
        ...


@dataclass(frozen=True)
class WindowMetrics:
    annual_return: float
    annual_excess_return: float
    max_drawdown: float
    volatility: float
    sharpe: float
    calmar: float
    turnover: float
    return_before_cost: float
    return_after_cost: float
    monthly_win_rate: float
    n_holdings_avg: float = 0.0
    avg_holding_days: float = 0.0

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class WindowReport:
    """One evaluated out-of-sample window under one set of assumptions.

    ``cost_profile`` and ``rebal_offset`` are part of the identity of the
    record, not decorations: the same window evaluated at 1x and 2x cost, or
    at two different rebalance offsets, are different experiments and must not
    be silently averaged into a single headline number.
    """

    experiment_id: str
    window_id: str
    test_period: List[str]
    strategy_spec: str
    cost_profile: str
    benchmark: str
    metrics: WindowMetrics
    rebal_offset: int = 0
    daily_metrics_path: str = ""

    def to_dict(self) -> dict:
        payload = asdict(self)
        payload["metrics"] = self.metrics.to_dict()
        return payload


@dataclass(frozen=True)
class StabilityReport:
    experiment_id: str
    strategy_spec: str
    windows_evaluated: int
    summary: Dict[str, float]

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class RegimeBucketMetrics:
    annual_return: float
    annual_excess_return: float
    turnover: float
    return_after_cost: float
    sample_days: int

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class RegimeReport:
    experiment_id: str
    regime_definition: Dict[str, str] = field(
        default_factory=lambda: {
            "trend_rule": "benchmark MA20/MA60 ratio with a 0.02 buffer",
            "states": "bull,bear,sideways",
        }
    )
    regimes: Dict[str, RegimeBucketMetrics] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "experiment_id": self.experiment_id,
            "regime_definition": self.regime_definition,
            "regimes": {k: v.to_dict() for k, v in self.regimes.items()},
        }


def summarize_stability(
    window_reports: List[WindowReport],
    continuous_returns=None,
    trading_days: int = 252,
) -> StabilityReport:
    """Aggregate windows into the numbers a go/no-go decision is made on.

    The point of the ratio fields is to make a single lucky window visible.
    A strategy with a high mean and ``positive_window_ratio`` of 0.5 earned
    everything in one or two windows; that is a different object from one with
    a lower mean and a ratio of 0.9, and no single-number score distinguishes
    them.

    ON CONVENTIONS, WHICH ARE WIDER THAN MOST DECISIONS. Two headline metrics
    here have two defensible definitions each, and in both cases the gap between
    definitions exceeded the margin a real adoption decision turned on.

    *Drawdown.* ``max_drawdown_worst_window`` is the deepest decline occurring
    *inside* any single window. It is not what a holder experiences, because a
    decline spanning a window boundary is never seen whole — window metrics
    reset at the boundary. ``max_drawdown_continuous`` measures the concatenated
    path and is the one to quote against a risk budget. One program measured
    −13.62% and −17.16% for the same strategy, with the user's stated 15% budget
    sitting between them: every report read as compliant while the strategy was
    over.

    *Return.* ``mean_annual_return`` is the arithmetic mean of per-window
    geometric annualized returns. ``annual_return_continuous`` is the geometric
    annualized return of the concatenated path. The first exceeds the second
    whenever windows disperse, and the gap is not decorative: 14.16% versus
    13.22% on the same nine windows, against an adoption margin of 1.00pp. Two
    researchers following identical rules could reach opposite verdicts by
    choosing differently, without either making an error.

    Both pairs are computed rather than chosen, and named so the name says which
    is which. Pass ``continuous_returns`` (the concatenated daily series across
    windows) to get the continuous members of each pair.
    """
    if not window_reports:
        raise ValueError("window_reports is empty")

    annual = [r.metrics.annual_return for r in window_reports]
    excess = [r.metrics.annual_excess_return for r in window_reports]
    dds = [r.metrics.max_drawdown for r in window_reports]
    turns = [r.metrics.turnover for r in window_reports]
    sharpe = [r.metrics.sharpe for r in window_reports]
    calmar = [r.metrics.calmar for r in window_reports]
    after_cost = [r.metrics.return_after_cost for r in window_reports]

    summary = {
        "mean_annual_return": mean(annual),
        "median_annual_return": median(annual),
        "std_annual_return": pstdev(annual) if len(annual) > 1 else 0.0,
        "mean_excess_return": mean(excess),
        "best_window_return": max(annual),
        "worst_window_return": min(annual),
        "positive_window_ratio": sum(x > 0 for x in annual) / len(annual),
        "beat_benchmark_ratio": sum(x > 0 for x in excess) / len(excess),
        "after_cost_positive_ratio": sum(x > 0 for x in after_cost) / len(after_cost),
        "max_drawdown_worst_window": min(dds),
        "sharpe_mean": mean(sharpe),
        "calmar_mean": mean(calmar),
        "turnover_mean": mean(turns),
    }

    if continuous_returns is not None and len(continuous_returns) > 1:
        equity = (1.0 + continuous_returns).cumprod()
        summary["max_drawdown_continuous"] = float(
            (equity / equity.cummax() - 1.0).min()
        )
        # The return convention matters for exactly the same reason the drawdown
        # convention does, and it is easier to miss because both numbers are
        # called "annualized return". mean_annual_return is the arithmetic mean
        # of per-window geometric annualized figures; this is the geometric
        # annualized return of the concatenated path. They differ by the
        # dispersion across windows, which is not small: one program measured
        # 14.16% and 13.22% on the same nine windows, a 0.94pp gap against an
        # adoption margin of 1.00pp. The convention was wider than the decision.
        years = len(continuous_returns) / trading_days
        total = float(equity.iloc[-1])
        if years > 0 and total > 0:
            summary["annual_return_continuous"] = total ** (1.0 / years) - 1.0

    first = window_reports[0]
    return StabilityReport(
        experiment_id=first.experiment_id,
        strategy_spec=first.strategy_spec,
        windows_evaluated=len(window_reports),
        summary=summary,
    )


def summarize_timing_luck(window_reports: List[WindowReport]) -> Dict[str, float]:
    """Spread of headline metrics across rebalance offsets.

    WHY THIS EXISTS: rebalancing on the 1st trading day of the month versus the
    6th is not a parameter of the strategy, it is an arbitrary implementation
    choice. The spread in annual return across a handful of offsets is
    routinely larger than the edge a strategy is being evaluated for, which
    means a result measured on a single offset can look like a discovery and
    turn out to be which offset you happened to pick.

    Report ``mean`` as the result and ``std`` as the error bar. If a claimed
    edge is smaller than ``std_annual_return`` across offsets, there is no edge.
    """
    by_offset: Dict[int, List[WindowReport]] = {}
    for r in window_reports:
        by_offset.setdefault(r.rebal_offset, []).append(r)
    if not by_offset:
        raise ValueError("window_reports is empty")

    per_offset_annual, per_offset_dd, per_offset_sharpe = [], [], []
    for _, reports in sorted(by_offset.items()):
        per_offset_annual.append(mean(r.metrics.annual_return for r in reports))
        per_offset_dd.append(mean(r.metrics.max_drawdown for r in reports))
        per_offset_sharpe.append(mean(r.metrics.sharpe for r in reports))

    n = len(per_offset_annual)
    return {
        "n_offsets": float(n),
        "mean_annual_return": mean(per_offset_annual),
        "std_annual_return": pstdev(per_offset_annual) if n > 1 else 0.0,
        "min_annual_return": min(per_offset_annual),
        "max_annual_return": max(per_offset_annual),
        "mean_max_drawdown": mean(per_offset_dd),
        "worst_max_drawdown": min(per_offset_dd),
        "mean_sharpe": mean(per_offset_sharpe),
        "std_sharpe": pstdev(per_offset_sharpe) if n > 1 else 0.0,
    }

"""Performance metrics and market-regime bucketing.

The Sharpe definition in ``compute_metrics`` is the one thing in this file
worth reading carefully. See its docstring.
"""
from __future__ import annotations

from typing import Dict

import numpy as np
import pandas as pd

from framework.protocols import RegimeBucketMetrics, RegimeReport

# MARKET-SPECIFIC. Annualization factor. US ~252, China A-share ~244,
# crypto 365. Read it from config rather than importing this constant.
DEFAULT_TRADING_DAYS = 252

# MARKET-SPECIFIC. Annual risk-free rate. Use what idle cash in this account
# actually earns, not a textbook T-bill number, if they differ materially.
DEFAULT_RISK_FREE = 0.04


def annualize(daily_return: pd.Series, trading_days: int = DEFAULT_TRADING_DAYS) -> float:
    """Geometric annualized return of a daily return series."""
    n = len(daily_return)
    if n < 2:
        return 0.0
    total = float((1.0 + daily_return).prod() - 1.0)
    years = n / trading_days
    if years <= 0:
        return 0.0
    base = 1.0 + total
    if base <= 0:
        return -1.0
    return float(base ** (1.0 / years) - 1.0)


def max_drawdown(daily_return: pd.Series) -> float:
    equity = (1.0 + daily_return).cumprod()
    return float((equity / equity.cummax() - 1.0).min())


def compute_metrics(
    daily_return: pd.Series,
    daily_return_gross: pd.Series | None = None,
    daily_turnover: pd.Series | None = None,
    benchmark: pd.Series | None = None,
    *,
    trading_days: int = DEFAULT_TRADING_DAYS,
    risk_free: float = DEFAULT_RISK_FREE,
) -> Dict[str, float]:
    """Headline metrics for one return series.

    ============================ SHARPE, CAREFULLY ============================
    ``sharpe`` here is the textbook ratio: mean *excess* daily return over the
    daily risk-free rate, annualized, divided by annualized volatility.

    WHY THIS IS CALLED OUT: an earlier version of this code computed
    ``mean(r) × T / vol`` and called it Sharpe — no risk-free subtraction. The
    bias is exactly ``risk_free / volatility``, so at a 1.5% risk-free rate and
    15% volatility every strategy in the program was reported 0.10 too high,
    and at 10% volatility, 0.15 too high. Cross-strategy *rankings* were
    unaffected because the bias is common, which is why it survived a long
    time. The absolute levels quoted in write-ups were wrong.

    ``sharpe_no_rf`` is kept so old reports can be reproduced and the gap can
    be shown. Never quote it as "the Sharpe ratio".
    ===========================================================================

    ``daily_return`` must be net of costs. ``daily_return_gross`` is used only
    to report the cost drag; if omitted, before-cost equals after-cost.
    """
    n = len(daily_return)
    if n < 2:
        return {}
    if daily_return_gross is None:
        daily_return_gross = daily_return
    if daily_turnover is None:
        daily_turnover = pd.Series(0.0, index=daily_return.index)

    annual_return = annualize(daily_return, trading_days)
    gross_annual = annualize(daily_return_gross, trading_days)

    vol = float(daily_return.std(ddof=0) * np.sqrt(trading_days))
    daily_rf = risk_free / trading_days
    excess_daily = daily_return - daily_rf
    sharpe = float(excess_daily.mean() * trading_days / vol) if vol > 0 else 0.0
    sharpe_no_rf = (
        float(daily_return.mean() * trading_days / vol) if vol > 0 else 0.0
    )

    downside = excess_daily[excess_daily < 0]
    downside_vol = (
        float(downside.std(ddof=0) * np.sqrt(trading_days)) if len(downside) > 1 else 0.0
    )
    sortino = (
        float(excess_daily.mean() * trading_days / downside_vol)
        if downside_vol > 0 else 0.0
    )

    mdd = max_drawdown(daily_return)
    calmar = annual_return / abs(mdd) if abs(mdd) > 1e-9 else 0.0

    monthly = daily_return.groupby(daily_return.index.to_period("M")).apply(
        lambda x: (1.0 + x).prod() - 1.0
    )
    monthly_win_rate = float((monthly > 0).mean()) if len(monthly) else 0.0

    # Σ|Δw| counts both sides of a switch, so a full rotation between two
    # assets reads as 2.0. Comparable across strategies, not to a broker's
    # "turnover" figure.
    turnover_annual = float(daily_turnover.mean() * trading_days)

    if benchmark is not None and len(benchmark) > 1:
        bench_ret = (
            benchmark.pct_change(fill_method=None)
            .reindex(daily_return.index)
            .fillna(0.0)
        )
        bench_annual = annualize(bench_ret, trading_days)
        excess_vs_bench = daily_return - bench_ret
        tracking_error = float(excess_vs_bench.std(ddof=0) * np.sqrt(trading_days))
        info_ratio = (
            float(excess_vs_bench.mean() * trading_days / tracking_error)
            if tracking_error > 0 else 0.0
        )
        annual_excess = annual_return - bench_annual
    else:
        bench_annual, info_ratio, annual_excess = 0.0, 0.0, 0.0

    return {
        "annual_return": float(annual_return),
        "annual_excess_return": float(annual_excess),
        "bench_annual_return": float(bench_annual),
        "max_drawdown": float(mdd),
        "volatility": vol,
        "sharpe": sharpe,
        "sharpe_no_rf": sharpe_no_rf,
        "sortino": sortino,
        "information_ratio": info_ratio,
        "calmar": float(calmar),
        "turnover": turnover_annual,
        "return_before_cost": float(gross_annual),
        "return_after_cost": float(annual_return),
        "monthly_win_rate": monthly_win_rate,
        "n_days": int(n),
    }


def regime_label(benchmark_close: pd.Series, ma_buffer: float = 0.02) -> pd.Series:
    """Label each day bull / bear / sideways from the benchmark's own trend.

    Rule: MA20/MA60 of the benchmark, with a buffer so that a ratio hovering
    around zero does not flip the label daily. Both moving averages use only
    past data, so the labels are causal — you could have computed them live.

    This is deliberately crude. It exists to answer "where did the return come
    from", not to be a signal. Any labelling that peeks at the future (for
    example, tagging a period bear because of what happened next) turns regime
    attribution into a way of confirming whatever you already believed.
    """
    wealth = benchmark_close.astype(float)
    ma_fast = wealth.rolling(20, min_periods=20).mean()
    ma_slow = wealth.rolling(60, min_periods=60).mean()
    ratio = ma_fast / ma_slow - 1.0
    label = pd.Series("sideways", index=wealth.index)
    label[ratio > ma_buffer] = "bull"
    label[ratio < -ma_buffer] = "bear"
    return label.where(ratio.notna(), "sideways")


def regime_report(
    experiment_id: str,
    daily_return: pd.Series,
    benchmark_close: pd.Series,
    daily_turnover: pd.Series,
    ma_buffer: float = 0.02,
    trading_days: int = DEFAULT_TRADING_DAYS,
) -> RegimeReport:
    """Split performance by market regime.

    What to look for: a strategy whose entire excess return sits in one bucket
    is a bet on that regime recurring, which is a much stronger claim than the
    headline number suggests.
    """
    bench_ret = (
        benchmark_close.pct_change(fill_method=None)
        .reindex(daily_return.index)
        .fillna(0.0)
    )
    labels = regime_label(
        benchmark_close.reindex(daily_return.index).ffill(), ma_buffer
    )

    regimes: Dict[str, RegimeBucketMetrics] = {}
    for state in ("bull", "bear", "sideways"):
        mask = labels == state
        days = int(mask.sum())
        if days == 0:
            regimes[state] = RegimeBucketMetrics(0.0, 0.0, 0.0, 0.0, 0)
            continue
        strat_annual = annualize(daily_return[mask], trading_days)
        bench_annual = annualize(bench_ret[mask], trading_days)
        regimes[state] = RegimeBucketMetrics(
            annual_return=strat_annual,
            annual_excess_return=strat_annual - bench_annual,
            turnover=float(daily_turnover[mask].mean() * trading_days),
            return_after_cost=strat_annual,
            sample_days=days,
        )
    return RegimeReport(experiment_id=experiment_id, regimes=regimes)

"""Walk-forward evaluation: three report layers, two cost profiles, N offsets.

THE THREE LAYERS. A single backtest over the full history is one number and
one number cannot be argued with. This runner produces three levels instead,
and a strategy has to survive all three:

  1. Window     — one out-of-sample year at a time, each preceded by its own
                  warm-up. Answers "did it work in year X", so a strategy that
                  earned everything in one regime cannot hide inside an average.
  2. Stability  — the distribution across windows. The ratio fields matter more
                  than the mean: 9-of-10 positive windows at 8% beats 5-of-10
                  at 12%, because the second is a coin flip with a good story.
  3. Regime     — performance split into bull / bear / sideways by the
                  benchmark's own trend. Answers "what is this actually a bet
                  on".

TWO ORTHOGONAL STRESS AXES, applied to all three layers:

  * Cost profiles. Every window is evaluated at 1x and at the stress multiple.
    Anything that only clears the bar at 1x is a cost-assumption artifact, and
    cost assumptions are the part of a backtest you are least sure about.
  * Rebalance offsets. The same strategy run on the 1st vs the 6th vs the 11th
    trading day of the month is the same strategy. If those disagree by more
    than the edge you are claiming, you have measured the calendar, not the
    strategy. Report the mean across offsets with the spread as the error bar.

Usage:
    PYTHONPATH=. python framework/walk_forward.py --strategy s0_passive
    PYTHONPATH=. python framework/walk_forward.py --strategy my_strategy \
        --offsets 0,5,10,15 --trade-lag 3 --freq weekly
"""
from __future__ import annotations

import argparse
import importlib
import json
import sys
from pathlib import Path
from typing import Dict, List

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from framework.backtest import DEFAULT_CIRCUIT_BREAKER, run_backtest  # noqa: E402
from framework.data_loader import load_config, load_prices  # noqa: E402
from framework.metrics import compute_metrics, regime_report  # noqa: E402
from framework.protocols import (  # noqa: E402
    WindowMetrics,
    WindowReport,
    summarize_stability,
    summarize_timing_luck,
)


def load_strategy(name: str, **kwargs):
    """Import ``strategies.<name>`` and instantiate its ``Strategy`` class."""
    module = importlib.import_module(f"strategies.{name}")
    return module.Strategy(**kwargs)


def save_window_report(report: WindowReport, daily: pd.DataFrame, out_dir: Path) -> None:
    """Persist one window: the summary JSON plus its daily series.

    Keeping the dailies is what makes a disputed result checkable later
    without re-running anything.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    daily_path = out_dir / f"{report.window_id}_daily.csv"
    daily.to_csv(daily_path)
    payload = report.to_dict()
    payload["daily_metrics_path"] = str(daily_path)
    (out_dir / f"{report.window_id}.json").write_text(json.dumps(payload, indent=2))


def evaluate(
    strategy_name: str,
    cfg,
    *,
    offsets: List[int],
    trade_lag: int,
    freq: str,
    min_hold_days: int,
    use_circuit_breaker: bool,
    top_n: int | None,
    tag: str,
    out_dir: Path,
) -> Dict[str, object]:
    prices = load_prices(cfg, research=True)  # hard cutoff enforced in the loader

    # Records any validation this run could not perform. It goes into the
    # artifacts, not just stdout: a check that was skipped is a property of the
    # result and has to travel with it. Printing alone means the next reader —
    # or the agent summarizing this run an hour later — sees a result that is
    # indistinguishable from a fully validated one.
    limitations: List[dict] = []

    if freq == "weekly" and len(offsets) > 1:
        # The weekly schedule has no month-offset parameter, so running the
        # grid would produce N identical results and a fake +-0.00% error bar.
        # Timing luck has not gone away — for a weekly schedule it lives in
        # which weekday you trade, which this engine does not parameterize.
        # If a weekly result matters, add that axis rather than assuming the
        # sensitivity is zero.
        limitations.append({
            "check": "multi_offset_timing_luck",
            "status": "NOT PERFORMED",
            "reason": "weekly rebalancing has no month-offset axis; the grid "
                      "would produce identical runs and a fake +-0.00% spread",
            "consequence": "timing-luck sensitivity is UNMEASURED for this "
                           "result, not measured as zero. For a weekly "
                           "schedule it lives in the weekday traded, which "
                           "this engine does not parameterize.",
        })
        print("WARNING: multi-offset validation NOT PERFORMED "
              "(weekly schedule has no offset axis). "
              "Timing-luck sensitivity is unmeasured, not zero.")
        offsets = offsets[:1]

    cost_cfg = cfg.get("cost", {}) or {}
    cost_single = float(cost_cfg.get("one_way", 0.0006))
    cost_double = cost_single * float(cost_cfg.get("stress_multiplier", 2.0))
    short_penalty = float(cost_cfg.get("short_hold_penalty", 0.015))

    cal = cfg.get("calendar", {}) or {}
    trading_days = int(cal.get("trading_days_per_year", 252))
    risk_free = float(cal.get("risk_free_annual", 0.0))

    wf = cfg.get("walk_forward", {}) or {}
    first_year = int(wf.get("first_test_year", 2015))
    last_year = int(wf.get("last_test_year", 2024))
    lookback_years = int(wf.get("lookback_years", 2))

    bench_code = cfg["benchmark"]["primary"]
    if bench_code not in prices.columns:
        raise KeyError(f"benchmark {bench_code!r} missing from the price table")

    breaker = DEFAULT_CIRCUIT_BREAKER if use_circuit_breaker else None
    suffix = "".join([
        f"_n{top_n}" if top_n else "",
        "_wk" if freq == "weekly" else "",
        f"_lag{trade_lag}" if trade_lag else "",
        f"_hold{min_hold_days}" if min_hold_days else "",
        "_cb" if use_circuit_breaker else "",
        f"_{tag}" if tag else "",
    ])
    experiment_id = f"{strategy_name}{suffix}"

    strategy_kwargs = {"config": cfg}
    if top_n is not None:
        strategy_kwargs["top_n"] = top_n

    reports: List[WindowReport] = []
    rows: List[dict] = []
    continuous: Dict[tuple, List[pd.Series]] = {}
    daily_dir = out_dir / "window_daily" / experiment_id

    for offset in offsets:
        for year in range(first_year, last_year + 1):
            test_start, test_end = f"{year}-01-01", f"{year}-12-31"
            warmup_start = f"{year - lookback_years}-01-01"
            window = prices.loc[warmup_start:test_end]
            if len(window) < 60:
                print(f"  skipping {year}: only {len(window)} bars of data")
                continue
            bench_window = prices[bench_code].loc[warmup_start:test_end]

            for profile, cost in (("single", cost_single), ("double", cost_double)):
                strategy = load_strategy(strategy_name, **strategy_kwargs)
                if hasattr(strategy, "reset"):
                    # Stateful strategies must not carry state across windows.
                    strategy.reset()

                result = run_backtest(
                    window, strategy,
                    cost_one_way=cost,
                    benchmark=bench_window,
                    rebalance=freq,
                    rebal_offset=offset,
                    trade_lag=trade_lag,
                    circuit_breaker=breaker,
                    eval_start=test_start,
                    min_hold_days=min_hold_days,
                    short_hold_penalty=short_penalty,
                )

                # Score only the test slice; the warm-up existed so the
                # strategy had history, not so it could pad the result.
                mask = (result.daily_return.index >= test_start) & (
                    result.daily_return.index <= test_end
                )
                daily_net = result.daily_return[mask]
                if len(daily_net) < 20:
                    continue
                daily_gross = result.daily_return_gross[mask]
                daily_turn = result.daily_turnover[mask]
                bench_test = bench_window.loc[test_start:test_end]

                m = compute_metrics(
                    daily_net, daily_gross, daily_turn, bench_test,
                    trading_days=trading_days, risk_free=risk_free,
                )
                window_id = f"W-{year}-{profile}-off{offset}"
                report = WindowReport(
                    experiment_id=experiment_id,
                    window_id=window_id,
                    test_period=[test_start, test_end],
                    strategy_spec=experiment_id,
                    cost_profile=profile,
                    benchmark=bench_code,
                    rebal_offset=offset,
                    metrics=WindowMetrics(
                        annual_return=m["annual_return"],
                        annual_excess_return=m["annual_excess_return"],
                        max_drawdown=m["max_drawdown"],
                        volatility=m["volatility"],
                        sharpe=m["sharpe"],
                        calmar=m["calmar"],
                        turnover=m["turnover"],
                        return_before_cost=m["return_before_cost"],
                        return_after_cost=m["return_after_cost"],
                        monthly_win_rate=m["monthly_win_rate"],
                    ),
                )
                daily_frame = pd.DataFrame({
                    "return": daily_net,
                    "bench_return": bench_test.pct_change(fill_method=None)
                                              .reindex(daily_net.index).fillna(0.0),
                    "turnover": daily_turn,
                    "equity": (1.0 + daily_net).cumprod(),
                })
                save_window_report(report, daily_frame, daily_dir)
                reports.append(report)
                # Test windows are consecutive calendar years, so concatenating
                # them per (offset, cost) reconstructs the experience of holding
                # continuously — the only basis on which a drawdown budget can
                # be checked.
                continuous.setdefault((profile, offset), []).append(daily_net)
                rows.append({
                    "window": window_id, "year": year, "offset": offset,
                    "cost": profile,
                    "annual": m["annual_return"], "excess": m["annual_excess_return"],
                    "maxdd": m["max_drawdown"], "sharpe": m["sharpe"],
                    "calmar": m["calmar"], "turnover": m["turnover"],
                    "monthly_win": m["monthly_win_rate"],
                    "short_hold_violations": result.short_hold_violations,
                })

    if not reports:
        raise RuntimeError("no window produced enough data to evaluate")

    out_dir.mkdir(parents=True, exist_ok=True)
    artifacts: Dict[str, object] = {
        "experiment_id": experiment_id,
        "offsets": offsets,
        "limitations": limitations,
    }
    (out_dir / f"limitations_{experiment_id}.json").write_text(
        json.dumps(limitations, indent=2))

    for profile in ("single", "double"):
        subset = [r for r in reports if r.cost_profile == profile]
        if not subset:
            continue
        # Each offset gives its own continuous path; quote the worst, because a
        # drawdown budget has to hold for the schedule you actually end up on.
        paths = [pd.concat(v).sort_index()
                 for (prof, _), v in continuous.items() if prof == profile]
        worst_path = None
        if paths:
            worst_path = min(
                paths,
                key=lambda s: ((1 + s).cumprod()
                               / (1 + s).cumprod().cummax() - 1).min(),
            )
        stability = summarize_stability(subset, continuous_returns=worst_path)
        (out_dir / f"stability_{experiment_id}_{profile}.json").write_text(
            json.dumps(stability.to_dict(), indent=2))
        artifacts[f"stability_{profile}"] = stability

        luck = summarize_timing_luck(subset)
        (out_dir / f"timing_luck_{experiment_id}_{profile}.json").write_text(
            json.dumps(luck, indent=2))
        artifacts[f"timing_luck_{profile}"] = luck

    # Regime attribution on the base configuration: first offset, 1x cost.
    base = [r for r in reports
            if r.cost_profile == "single" and r.rebal_offset == offsets[0]]
    if base:
        frames = [
            pd.read_csv(daily_dir / f"{r.window_id}_daily.csv",
                        index_col=0, parse_dates=True)
            for r in base
        ]
        stitched = pd.concat(frames).sort_index()
        regimes = regime_report(
            experiment_id,
            stitched["return"],
            (1.0 + stitched["bench_return"]).cumprod() * 100.0,
            stitched["turnover"],
            trading_days=trading_days,
        )
        (out_dir / f"regime_{experiment_id}.json").write_text(
            json.dumps(regimes.to_dict(), indent=2))
        artifacts["regime"] = regimes

    frame = pd.DataFrame(rows)
    frame.to_csv(out_dir / f"window_reports_{experiment_id}.csv", index=False)
    artifacts["rows"] = frame
    return artifacts


def _print_summary(artifacts: Dict[str, object]) -> None:
    experiment_id = artifacts["experiment_id"]
    offsets: List[int] = artifacts["offsets"]  # type: ignore[assignment]
    frame: pd.DataFrame = artifacts["rows"]  # type: ignore[assignment]

    print("\n" + "=" * 78)
    print(f"Walk-forward: {experiment_id}")
    print("=" * 78)

    pivot = (
        frame[frame["cost"] == "single"]
        .pivot_table(index="year", columns="offset", values="annual")
    )
    print("\n[Layer 1] annual return by window and rebalance offset (1x cost)")
    print(pivot.to_string(float_format=lambda x: f"{x:.2%}"))

    for profile in ("single", "double"):
        stability = artifacts.get(f"stability_{profile}")
        if stability is None:
            continue
        print(f"\n[Layer 2] stability, {profile} cost "
              f"({stability.windows_evaluated} window-evaluations)")
        for key, value in stability.summary.items():
            print(f"  {key:28s} {value: .4f}")

    for profile in ("single", "double"):
        luck = artifacts.get(f"timing_luck_{profile}")
        if luck is None or len(offsets) < 2:
            continue
        print(f"\n[Stress] timing luck across {len(offsets)} offsets, {profile} cost")
        print(f"  annual return   {luck['mean_annual_return']:.2%} "
              f"+/- {luck['std_annual_return']:.2%} "
              f"(min {luck['min_annual_return']:.2%}, "
              f"max {luck['max_annual_return']:.2%})")
        print(f"  sharpe          {luck['mean_sharpe']:.2f} "
              f"+/- {luck['std_sharpe']:.2f}")
        if luck["std_annual_return"] > 0.01:
            print("  NOTE: offsets disagree by more than 1pp. Any claimed edge "
                  "smaller than that spread is calendar luck, not signal.")

    regimes = artifacts.get("regime")
    if regimes is not None:
        print("\n[Layer 3] regime attribution (1x cost, base offset)")
        for state, bucket in regimes.regimes.items():
            print(f"  {state:9s} annual {bucket.annual_return: .2%}  "
                  f"excess {bucket.annual_excess_return: .2%}  "
                  f"days {bucket.sample_days}")

    _print_scrutiny_triggers(artifacts)


def _print_scrutiny_triggers(artifacts: Dict[str, object]) -> None:
    """Fire the self-deception triggers from the numbers, not from a judgement.

    WHY THIS EXISTS: the trigger for scrutinising a result used to be "when the
    result looks good" — which is the one moment nobody wants to scrutinise
    anything. A condition that activates on the same state it exists to
    counteract does not fire when it is needed. These conditions are read off
    the report instead, so they fire whether or not anyone feels like it.

    Printing is deliberately not optional and deliberately loud. The program
    noticing is more reliable than the reader remembering.
    """
    stability = artifacts.get("stability_single")
    if stability is None:
        return

    summary = stability.summary
    fired = []

    sharpe = summary.get("sharpe_mean")
    if sharpe is not None and sharpe > 1.5:
        fired.append(f"Sharpe {sharpe:.2f} exceeds 1.5")

    excess = summary.get("mean_excess_return")
    if excess is not None and excess > 0.02:
        fired.append(f"excess over passive {excess:.2%} exceeds 2pp")

    # Not "suspiciously small" — genuinely small spread is a real property of
    # static allocations. Only *identical* results are diagnostic, and what they
    # diagnose is usually a parameter that never reached the engine.
    luck = artifacts.get("timing_luck_single")
    if (luck is not None and len(artifacts.get("offsets", [])) > 1
            and luck.get("std_annual_return", 1.0) < 1e-9):
        fired.append(
            "offsets produced identical results — verify the offset parameter "
            "actually reaches the engine before reading this as insensitivity"
        )

    single = artifacts.get("stability_single")
    double = artifacts.get("stability_double")
    if single is not None and double is not None:
        a = single.summary.get("mean_annual_return")
        b = double.summary.get("mean_annual_return")
        if a is not None and b is not None and abs(a - b) < 1e-9:
            fired.append(
                "doubling costs changed nothing — check turnover is non-zero; "
                "identical cost tiers usually mean costs are not being charged"
            )

    if not fired:
        return

    print("\n" + "!" * 78)
    print("SCRUTINY REQUIRED — mechanical triggers fired:")
    for item in fired:
        print(f"  - {item}")
    print()
    print("  Load `doubt` and answer all five questions")
    print("  BEFORE writing any verdict on this result. A good number is the")
    print("  start of an investigation, not the end of one. Note in particular")
    print("  that passing a validation narrows what could be wrong; it does not")
    print("  establish that nothing is.")
    print("!" * 78)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--strategy", required=True,
                        help="module name under strategies/, without .py")
    parser.add_argument("--config", default=None, help="path to config.yaml")
    parser.add_argument("--offsets", default=None,
                        help="comma-separated rebalance offsets, e.g. 0,5,10,15")
    parser.add_argument("--trade-lag", type=int, default=None,
                        help="settlement delay in trading days")
    parser.add_argument("--freq", choices=["monthly", "weekly"], default=None)
    parser.add_argument("--min-hold-days", type=int, default=None,
                        help="charge the short-hold penalty on faster round trips")
    parser.add_argument("--circuit-breaker", action="store_true",
                        help="enable the drawdown kill switch (off by default)")
    parser.add_argument("--top-n", type=int, default=None)
    parser.add_argument("--tag", default="", help="suffix for the experiment id")
    parser.add_argument("--out-dir", default=None, help="default: <config dir>/evaluation")
    args = parser.parse_args()

    cfg = load_config(args.config)
    rebal_cfg = cfg.get("rebalance", {}) or {}
    offsets = (
        [int(x) for x in args.offsets.split(",")] if args.offsets
        else [int(x) for x in rebal_cfg.get("offsets", [0])]
    )
    out_dir = Path(args.out_dir) if args.out_dir else cfg.path("evaluation")

    artifacts = evaluate(
        args.strategy, cfg,
        offsets=offsets,
        trade_lag=args.trade_lag if args.trade_lag is not None
        else int(rebal_cfg.get("trade_lag", 0)),
        freq=args.freq or str(rebal_cfg.get("freq", "monthly")),
        min_hold_days=args.min_hold_days if args.min_hold_days is not None
        else int((cfg.get("cost", {}) or {}).get("min_hold_days", 0)),
        use_circuit_breaker=args.circuit_breaker,
        top_n=args.top_n,
        tag=args.tag,
        out_dir=out_dir,
    )
    _print_summary(artifacts)
    print(f"\nArtifacts written to {out_dir}")


if __name__ == "__main__":
    main()

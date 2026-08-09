"""Three-layer reconciliation of a paper-traded portfolio against the backtest.

WHY THREE LAYERS. When live tracking diverges from the backtest, the useful
question is not "how big is the gap" but "which of three unrelated things
caused it". Collapsing them into one number is how a data bug gets diagnosed
as alpha decay, and how execution friction gets diagnosed as a broken signal.

  Layer 1 — DATA.      Does the price recorded in the snapshot still match what
                       the database says for that same date? A mismatch means
                       the history was revised or repaired, and every
                       conclusion computed from the old version needs to be
                       recomputed. This layer is checked first because if it
                       fails, the other two are meaningless.
  Layer 2 — EXECUTION. Lot-size rounding and the cash it strands. The backtest
                       assumes fractional, fully invested positions; a real
                       account cannot do that. This friction is real, bounded,
                       and shrinks with account size — quantify it separately
                       instead of letting it masquerade as underperformance.
  Layer 3 — STRATEGY.  What is left after the first two are accounted for:
                       the paper portfolio's return versus the same weights
                       under backtest conventions. Only this layer is evidence
                       about the strategy.

Two baselines are printed alongside: the passive blend and the primary
benchmark over the same interval. They answer "is this the strategy or the
market", which is a different question from all three layers above.

Usage:
    PYTHONPATH=. python tracking/reconcile.py
    PYTHONPATH=. python tracking/reconcile.py --config config.yaml
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, Mapping, Optional

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from framework.data_loader import load_config, load_prices  # noqa: E402


def paper_return(
    prices: pd.DataFrame,
    record: Mapping,
    start: pd.Timestamp,
    end: pd.Timestamp,
    cost_one_way: float = 0.0006,
) -> Optional[float]:
    """Return of the actual paper position: real unit counts, idle cash earns nothing.

    Returns ``None`` — never 0.0 — if any instrument is missing from the price
    table or has too little data in the interval. A silent zero would look
    like a perfectly tracking portfolio, which is the most dangerous possible
    failure mode for a reconciliation tool.
    """
    first_px: Dict[str, float] = {}
    last_px: Dict[str, float] = {}
    for order in record["orders"]:
        code = order["code"]
        if code not in prices.columns:
            return None
        series = prices[code].loc[start:end].dropna()
        if len(series) < 2:
            return None
        first_px[code], last_px[code] = float(series.iloc[0]), float(series.iloc[-1])

    value_start = sum(o["units"] * first_px[o["code"]] for o in record["orders"])
    value_end = sum(o["units"] * last_px[o["code"]] for o in record["orders"])
    capital = float(record["capital"])
    cash = float(record["cash_residual"])
    entry_cost = value_start * cost_one_way
    return float((value_end + cash - entry_cost) / capital - 1.0)


def weight_return(
    prices: pd.DataFrame,
    weights: Mapping[str, float],
    start: pd.Timestamp,
    end: pd.Timestamp,
    cost_one_way: float = 0.0006,
) -> Optional[float]:
    """Return under backtest conventions: exact weights, no rounding, no idle cash.

    The difference between this and ``paper_return`` over the same interval is
    layer 2 (execution friction) by construction.
    """
    total = 0.0
    for code, weight in weights.items():
        if code not in prices.columns:
            return None
        series = prices[code].loc[start:end].dropna()
        if len(series) < 2:
            return None
        total += weight * (float(series.iloc[-1]) / float(series.iloc[0]) - 1.0)
    return float(total - cost_one_way * sum(weights.values()))


def _fmt(value: Optional[float]) -> str:
    return f"{value:+.2%}" if value is not None else "n/a"


def _check_data_layer(prices, records, tolerance: float) -> int:
    print("\n" + "=" * 88)
    print("LAYER 1 - DATA: snapshot prices vs the database, same dates")
    print("=" * 88)
    bad = 0
    for record in records:
        date = pd.Timestamp(record["signal_date"])
        for order in record["orders"]:
            code = order["code"]
            if code not in prices.columns or date not in prices.index:
                print(f"  MISSING  {record['signal_date']} {code}: no data on file")
                bad += 1
                continue
            now = float(prices[code].loc[date])
            then = float(order["price_at_signal"])
            drift = abs(now - then) / then if then else float("inf")
            if drift > tolerance:
                print(f"  CHANGED  {record['signal_date']} {code}: snapshot "
                      f"{then:.4f} vs database {now:.4f} ({drift:.2%}). "
                      f"History was revised - recompute anything derived from it.")
                bad += 1
    print(f"  {'all consistent' if bad == 0 else f'{bad} discrepancies'} "
          f"(tolerance {tolerance:.1%})")
    return bad


def _check_execution_layer(records) -> None:
    print("\n" + "=" * 88)
    print("LAYER 2 - EXECUTION: lot rounding and stranded cash")
    print("=" * 88)
    for record in records:
        drift = max(abs(o["actual_weight"] - o["target_weight"])
                    for o in record["orders"])
        cash_pct = record["cash_residual"] / record["capital"]
        worst = max(record["orders"],
                    key=lambda o: abs(o["actual_weight"] - o["target_weight"]))
        print(f"  {record['signal_date']}  max weight drift {drift:.3%}   "
              f"idle cash {cash_pct:.3%} ({record['cash_residual']:,.2f})")
        print(f"      worst: {worst['code']} target {worst['target_weight']:.2%} "
              f"-> actual {worst['actual_weight']:.2%}")
    print("  This friction scales inversely with account size. It is a real "
          "cost, but it is not the strategy failing.")


def _check_strategy_layer(prices, data, cfg, cost_one_way, alert) -> None:
    records = data["records"]
    latest = prices.index.max()
    blend = {str(e["code"]): float(e["weight"])
             for e in cfg["benchmark"]["passive_blend"]}
    primary = cfg["benchmark"]["primary"]

    print("\n" + "=" * 88)
    print("LAYER 3 - STRATEGY: paper vs backtest convention, with baselines")
    print("=" * 88)

    order = sorted(range(len(records)), key=lambda i: records[i]["signal_date"])
    rows = []
    for k, i in enumerate(order):
        record = records[i]
        start = pd.Timestamp(record["signal_date"])
        if k + 1 < len(order):
            end = pd.Timestamp(records[order[k + 1]]["signal_date"])
            ongoing = False
        else:
            end, ongoing = latest, True
        if (end - start).days < 1:
            print(f"  {record['signal_date']}: holding period has not started yet")
            continue

        weights = {o["code"]: o["target_weight"] for o in record["orders"]}
        paper = paper_return(prices, record, start, end, cost_one_way)
        backtest = weight_return(prices, weights, start, end, cost_one_way)
        blend_ret = weight_return(prices, blend, start, end, cost_one_way)
        primary_ret = weight_return(prices, {primary: 1.0}, start, end, cost_one_way)
        rows.append((record["signal_date"], start, end, ongoing,
                     paper, backtest, blend_ret, primary_ret))

        if paper is not None:
            record["actual_return"] = round(paper, 6)
        if backtest is not None:
            record["backtest_return"] = round(backtest, 6)

    if not rows:
        print("  Nothing to reconcile yet.")
        return

    header = (f"{'signal':12s} {'interval':26s} {'paper':>9s} {'backtest':>9s} "
              f"{'gap':>10s} {'blend':>9s} {'benchmark':>10s}")
    print(header)
    print("-" * len(header))
    for signal_date, start, end, ongoing, paper, backtest, blend_r, prim_r in rows:
        span = f"{start.date()}~{end.date()}{' (open)' if ongoing else ''}"
        gap = (paper - backtest) if (paper is not None and backtest is not None) else None
        flag = " !" if gap is not None and abs(gap) > alert else ""
        print(f"{signal_date:12s} {span:26s} {_fmt(paper):>9s} "
              f"{_fmt(backtest):>9s} {_fmt(gap) + flag:>10s} "
              f"{_fmt(blend_r):>9s} {_fmt(prim_r):>10s}")
    print("\n  'gap' is layers 1+2 combined. If layer 1 is clean, the gap IS "
          "execution friction, and only what remains is about the strategy.")


def _check_prereg(meta, latest) -> None:
    """Compare elapsed tracking against the decision rules written in advance.

    WHY THIS EXISTS: thresholds invented after seeing the result are not
    thresholds. Freezing them in the snapshot file at the moment parameters
    are frozen is what makes a later "it failed" or "it held up" mean
    anything. This function only reads them.
    """
    prereg = meta.get("prereg")
    if not prereg:
        print("\nNo pre-registered decision rules found. Write them before you "
              "need them, not after.")
        return

    print("\n" + "=" * 88)
    print("PRE-REGISTERED DECISION RULES")
    print("=" * 88)
    start = pd.Timestamp(meta["true_oos_start"])
    months = (latest - start).days / 30.4
    reference = prereg.get("backtest_reference", {})
    if reference:
        print(f"  Backtest reference ({reference.get('period', '?')}): "
              f"annual {reference.get('annual_return', float('nan')):.2%}, "
              f"maxDD {reference.get('max_drawdown', float('nan')):.2%}")
    print(f"  Out-of-sample elapsed: {months:.1f} months")

    minimum = prereg.get("min_months_before_judgement", 12)
    if months < minimum:
        print(f"\n  Under the {minimum}-month minimum. No trigger should fire "
              f"yet, in either direction. Short-horizon tracking is noise, and "
              f"reacting to it is how a sound strategy gets abandoned.")
    else:
        print("\n  Triggers now in force:")
        for condition in prereg.get("trigger_conditions", []):
            print(f"    - {condition}")

    if prereg.get("not_failure"):
        print("\n  Explicitly NOT failure (written down in advance so that a "
              "bad month cannot be reinterpreted later):")
        for item in prereg["not_failure"]:
            print(f"    - {item}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--config", default=None)
    parser.add_argument("--tracking-file", default=None)
    args = parser.parse_args()

    cfg = load_config(args.config)
    track_path = Path(args.tracking_file) if args.tracking_file \
        else cfg.path("tracking", "live_tracking.json")
    if not track_path.exists():
        print(f"{track_path} not found - run tracking/paper_trade.py first.")
        return

    data = json.loads(track_path.read_text())
    meta, records = data.get("meta"), data.get("records", [])
    if not meta or not records:
        print("Tracking file has no meta block or no records.")
        return

    tracking_cfg = cfg.get("tracking", {}) or {}
    tolerance = float(tracking_cfg.get("price_tolerance", 0.005))
    alert = float(tracking_cfg.get("divergence_alert", 0.02))
    cost_one_way = float((cfg.get("cost", {}) or {}).get("one_way", 0.0006))

    # research=False is correct here and nowhere else: reconciliation is about
    # what happened after the cutoff, which is the whole point of tracking.
    prices = load_prices(cfg, research=False)
    latest = prices.index.max()

    print("=" * 88)
    print(f"Paper-trading reconciliation: {meta.get('strategy', 'unknown')}")
    print("=" * 88)
    print(f"Parameters frozen {meta.get('params_frozen_at')} -> "
          f"{meta.get('frozen_until')}")
    print(f"True out-of-sample start {meta.get('true_oos_start')}, "
          f"data through {latest.date()}")
    if meta.get("disclaimer"):
        print(f"\n{meta['disclaimer']}")

    _check_data_layer(prices, records, tolerance)
    _check_execution_layer(records)
    _check_strategy_layer(prices, data, cfg, cost_one_way, alert)
    _check_prereg(meta, latest)

    track_path.write_text(json.dumps(data, indent=2))
    print(f"\nRealized returns written back to {track_path.name}")


if __name__ == "__main__":
    main()

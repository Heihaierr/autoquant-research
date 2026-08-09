"""Record a dated, immutable signal snapshot: the only real out-of-sample evidence.

WHY THIS EXISTS. A backtest run today over a period that ended yesterday is
not out-of-sample, however carefully the code was written, because every
choice made along the way — which assets, which lookbacks, which strategies
got a second chance — was made by someone who already knew what that period
did. Calling a year "out-of-sample" after the fact does not undo that; the
data was fully visible during every experiment that produced the result.

Genuine out-of-sample evidence has one property: it accumulates forward from
the moment the parameters were frozen, and it cannot be regenerated. That is
what this script produces. Each snapshot captures:

  - the target weights from the frozen strategy
  - the price of every instrument AT THE MOMENT OF THE SIGNAL, which lets you
    detect later that the price history was revised under you
  - the position sizes after lot rounding, plus the cash that could not be
    invested, which is the execution friction a backtest never shows
  - a generation timestamp

Snapshots are append-only. Editing one destroys the only thing that makes it
evidence. If a snapshot was wrong, add a new record with a note; do not
rewrite history.

Usage:
    PYTHONPATH=. python tracking/paper_trade.py --strategy s0_passive
    PYTHONPATH=. python tracking/paper_trade.py --strategy s0_passive --dry-run
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from framework.data_loader import load_config, load_prices, universe_meta  # noqa: E402
from framework.walk_forward import load_strategy  # noqa: E402

# Written to tracking/prereg.json on first run. Fill in every TODO BEFORE the
# first snapshot: a threshold decided after seeing results is not a threshold,
# it is a rationalization with a number attached.
PREREG_TEMPLATE = {
    "strategy": "TODO: module name under strategies/",
    "params_frozen_at": "TODO: YYYY-MM-DD, the day you stopped changing anything",
    "frozen_until": "TODO: YYYY-MM-DD, the earliest date you may touch parameters",
    "true_oos_start": "TODO: YYYY-MM-DD, normally the same as params_frozen_at",
    "frozen_params": {
        "TODO": "the exact parameter values, so the run is reproducible later"
    },
    "disclaimer": (
        "Any performance computed for periods before params_frozen_at is a "
        "backtest, not out-of-sample evidence, regardless of how it is labelled."
    ),
    "prereg": {
        "min_months_before_judgement": 12,
        "review_dates": ["TODO: YYYY-MM-DD", "TODO: YYYY-MM-DD"],
        "backtest_reference": {
            "period": "TODO: e.g. 2015-2024",
            "annual_return": 0.0,
            "max_drawdown": 0.0,
            "sharpe": 0.0,
            "note": "TODO: which cost profile and offset these came from",
        },
        "honest_expectation": {
            "annual_return_range": [0.0, 0.0],
            "basis": (
                "TODO: why you expect this, and it should be BELOW the backtest "
                "number: the backtest window was chosen with hindsight and the "
                "strategy was selected for doing well in it"
            ),
        },
        "trigger_conditions": [
            "TODO: a specific, checkable condition that would make you act",
            "TODO: each one should name a horizon, a threshold, and an action",
        ],
        "not_failure": [
            "TODO: outcomes that look bad but were expected by design",
            "TODO: writing these down now prevents abandoning a sound strategy "
            "during a drawdown it was always going to have",
        ],
    },
}


def _unfilled(node, path: str = "") -> list[str]:
    """Every remaining TODO placeholder, by path. Checked recursively."""
    if isinstance(node, str):
        return [path] if node.startswith("TODO") else []
    if isinstance(node, dict):
        return [p for k, v in node.items()
                for p in _unfilled(v, f"{path}.{k}" if path else k)]
    if isinstance(node, list):
        return [p for i, v in enumerate(node) for p in _unfilled(v, f"{path}[{i}]")]
    return []


def load_prereg(path: Path) -> dict:
    """Load the frozen parameters and decision rules, refusing placeholders.

    Hard-failing on an unfilled TODO is the point. Pre-registration only means
    anything if it is genuinely complete before the first snapshot; a file
    half-filled now and finished after two bad months is just a story.
    """
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(PREREG_TEMPLATE, indent=2))
        raise SystemExit(
            f"Created {path} from a template.\n"
            "Fill in every TODO before taking the first snapshot - the whole "
            "point is that these were written down in advance."
        )
    prereg = json.loads(path.read_text())
    todos = _unfilled(prereg)
    if todos:
        raise SystemExit(
            f"{path} still has unfilled fields:\n  "
            + "\n  ".join(todos)
        )
    return prereg


def build_snapshot(
    prices: pd.DataFrame,
    strategy,
    capital: float,
    lot_size: float,
    names: Dict[str, dict],
    strategy_name: str,
) -> dict:
    """Turn today's target weights into an executable, recorded order list."""
    if len(prices.index) < 2:
        raise ValueError("need at least two dates to separate decision from fill")

    # Two distinct dates, and conflating them is a look-ahead bug that flatters
    # live results specifically.
    #
    # The engine gives the strategy prices.loc[:dates[i-1]] and fills at the
    # close of date i. That is executable: during date i you already hold every
    # close through i-1, so a market-on-close order is placeable. If the
    # strategy here were handed history through the fill date instead, it would
    # be deciding from a close it cannot know until that close has happened —
    # and the resulting bias makes tracked performance look *better* than the
    # backtest, which is precisely the direction that hides decay in the one
    # artifact built to detect decay.
    fill_date = prices.index[-1]
    decision_cutoff = prices.index[-2]
    weights = strategy.target_weights(prices.loc[:decision_cutoff], fill_date)
    asof = fill_date

    orders, invested = [], 0.0
    for code in sorted(weights, key=lambda c: -weights[c]):
        if code not in prices.columns:
            raise KeyError(f"strategy asked for {code!r}, which has no price data")
        price = float(prices[code].loc[asof])
        target_amount = weights[code] * capital
        units = math.floor(target_amount / price / lot_size) * lot_size
        amount = units * price
        invested += amount
        orders.append({
            "code": code,
            "name": names.get(code, {}).get("name", code),
            "target_weight": round(float(weights[code]), 6),
            "price_at_signal": round(price, 6),
            "units": units,
            "amount": round(amount, 2),
            "actual_weight": round(amount / capital, 6),
        })

    return {
        "signal_date": str(asof.date()),
        "data_asof": str(asof.date()),
        "decision_cutoff": str(decision_cutoff.date()),
        "strategy": strategy_name,
        "capital": capital,
        "orders": orders,
        "invested": round(invested, 2),
        "cash_residual": round(capital - invested, 2),
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "actual_return": None,
        "backtest_return": None,
        "note": None,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--config", default=None)
    parser.add_argument("--strategy", default=None,
                        help="defaults to the strategy named in prereg.json")
    parser.add_argument("--capital", type=float, default=None)
    parser.add_argument("--dry-run", action="store_true",
                        help="print the snapshot without appending it")
    args = parser.parse_args()

    cfg = load_config(args.config)
    tracking_cfg = cfg.get("tracking", {}) or {}
    prereg = load_prereg(cfg.path("tracking", "prereg.json"))

    strategy_name = args.strategy or prereg["strategy"]
    capital = args.capital or float(tracking_cfg.get("capital", 100000))
    lot_size = float(tracking_cfg.get("lot_size", 1))

    # research=False is correct here and essentially nowhere else: a live
    # signal needs today's prices. Every other caller must stay behind the
    # research cutoff.
    prices = load_prices(cfg, research=False)
    strategy = load_strategy(strategy_name, config=cfg)
    snapshot = build_snapshot(
        prices, strategy, capital, lot_size, universe_meta(cfg), strategy_name
    )

    track_path = cfg.path("tracking", "live_tracking.json")
    if track_path.exists():
        data = json.loads(track_path.read_text())
    else:
        data = {"meta": {}, "records": []}
    data["meta"] = {k: v for k, v in prereg.items()}

    duplicate = any(
        r["signal_date"] == snapshot["signal_date"]
        and r["strategy"] == snapshot["strategy"]
        for r in data["records"]
    )

    print("=" * 88)
    print(f"Signal snapshot: {snapshot['strategy']}")
    print("=" * 88)
    print(f"Signal date {snapshot['signal_date']}   capital {capital:,.2f}   "
          f"frozen until {prereg['frozen_until']}")
    header = (f"{'code':>10s} {'name':22s} {'target':>8s} {'price':>10s} "
              f"{'units':>12s} {'amount':>12s} {'actual':>8s}")
    print(header)
    print("-" * len(header))
    for order in snapshot["orders"]:
        print(f"{order['code']:>10s} {order['name'][:22]:22s} "
              f"{order['target_weight']:>8.2%} {order['price_at_signal']:>10.4f} "
              f"{order['units']:>12,.4f} {order['amount']:>12,.2f} "
              f"{order['actual_weight']:>8.2%}")
    print("-" * len(header))
    idle_fraction = snapshot["cash_residual"] / capital
    print(f"invested {snapshot['invested']:,.2f}   "
          f"idle cash {snapshot['cash_residual']:,.2f} "
          f"({idle_fraction:.2%}, from lot rounding)")

    # An account too small for its lot size does not run the strategy that was
    # backtested. It runs a distorted version of it, and the distortion is
    # invisible in every backtest number. Say so before the first trade, not
    # after six months of unexplained tracking error.
    dropped = [o["code"] for o in snapshot["orders"] if o["units"] <= 0]
    if dropped:
        print(f"\nWARNING: {len(dropped)} position(s) rounded to zero units: "
              f"{', '.join(dropped)}")
        print("  These holdings do not exist in the paper portfolio at all, so "
              "it is not the strategy you evaluated. Increase capital, reduce "
              "the number of positions, or use an instrument with a smaller "
              "minimum size.")
    if idle_fraction > 0.02:
        print(f"\nWARNING: {idle_fraction:.1%} of capital could not be invested. "
              "Rounding friction of this size will dominate any edge you are "
              "trying to measure.")

    if duplicate:
        print(f"\nA snapshot for {snapshot['signal_date']} already exists; "
              f"not appending. Snapshots are append-only by design.")
    elif args.dry_run:
        print("\n(dry run - nothing written)")
    else:
        data["records"].append(snapshot)
        track_path.parent.mkdir(parents=True, exist_ok=True)
        track_path.write_text(json.dumps(data, indent=2))
        print(f"\nAppended to {track_path.name} "
              f"({len(data['records'])} snapshots total)")
        print("Next: re-run on the next rebalance date, then run "
              "tracking/reconcile.py to reconcile.")


if __name__ == "__main__":
    main()

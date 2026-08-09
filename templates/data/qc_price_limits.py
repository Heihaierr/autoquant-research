"""Data quality control using physical and regulatory constraints.

THE IDEA. Validate price data against rules that make a value *impossible*
rather than merely unusual. A daily move of +12.8% on an instrument subject to
a 10% exchange limit is not an outlier — it is a wrong number, and no judgement
is required to say so.

WHY NOT STATISTICAL OUTLIER DETECTION. We started with the usual approach:
z-scores, rolling-window shape rules, "this move is too large relative to
recent volatility". It flagged real events. Genuine limit-up streaks, index
reconstitutions and a currency devaluation all got quarantined, while a
systematically mis-adjusted series with plausible-looking daily moves passed
clean. A statistical rule can only tell you a value is unusual, and unusual is
exactly what you are trying to capture in the first place.

Physical constraints have no such ambiguity. Every market has some:

  * daily price limits (many Asian equity markets, most futures exchanges)
  * circuit breakers and trading halts
  * non-negative prices for cash instruments
  * an ETF's NAV cannot detach arbitrarily far from its basket
  * bond prices bounded by their redemption terms

WHAT TO DO WHEN THIS FINDS SOMETHING. Do not delete the point and interpolate.
Fetch the same series from an independent source and adjudicate: if the second
source agrees, your constraint model is wrong (a corporate action, a rule
change); if it disagrees, replace the whole affected span, not the single bar,
because a bad adjustment factor usually corrupts a range.

MOST IMPORTANT: if you repair history, every result computed from the old
version is now unverified. Re-run them. tracking/reconcile.py exists partly to
make this detectable after the fact.

Usage:
    PYTHONPATH=. python data/qc_price_limits.py
    PYTHONPATH=. python data/qc_price_limits.py --config config.yaml --json out.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, Optional

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from framework.data_loader import load_config, load_prices, universe_meta  # noqa: E402

# ===========================================================================
# MARKET-SPECIFIC. Maximum plausible single-day move per limit group, as a
# fraction. ``None`` means the venue imposes no daily limit, so this check
# cannot say anything and the instrument is only reported for information.
#
# Assign a group to each instrument via ``limit_group`` in the config's
# universe block. Replace these entries with your own market's rules — the
# values below are examples from one market and are wrong elsewhere.
# ===========================================================================
PRICE_LIMIT_RULES: Dict[str, Optional[float]] = {
    # Example: mainland China A-share main board and most listed funds.
    "cn_main": 0.10,
    # Example: growth boards with a wider band (ChiNext, STAR Market).
    "cn_growth": 0.20,
    # Example: cross-border / QDII funds, whose prices track a foreign market
    # and are NOT subject to the domestic limit. Misfiling one of these here
    # generates a flood of false positives.
    "cn_cross_border": None,
    # Most developed equity markets have no per-instrument daily limit;
    # circuit breakers are market-wide and halt trading rather than cap prices.
    "none": None,
    # Commodity futures commonly do have limits, per contract.
    "futures_example": 0.07,
}

# Total-return adjustment introduces rounding, and a distribution paid on the
# limit day can push the adjusted move slightly past the raw limit. This slack
# keeps legitimate values out of the report. Widen it and you stop detecting
# small corruptions; narrow it and you drown in noise.
LIMIT_BUFFER = 0.005

# An instrument needs at least this much history before per-instrument
# statistics mean anything.
MIN_OBSERVATIONS = 100

DEFAULT_LIMIT_GROUP = "none"


def limit_for(code: str, meta: Dict[str, dict]) -> Optional[float]:
    """Resolve an instrument's daily limit from its configured group.

    Classification is driven by config, not by parsing the ticker. Prefix
    rules ("codes starting with 5 are domestic") are tempting and wrong: in
    our universe a cross-border fund carried a domestic-looking code and a
    domestic region tag, so a prefix classifier labelled it limited and
    reported every one of its real moves as corrupt.
    """
    group = str(meta.get(code, {}).get("limit_group", DEFAULT_LIMIT_GROUP))
    if group not in PRICE_LIMIT_RULES:
        raise KeyError(
            f"{code}: limit_group {group!r} is not defined in PRICE_LIMIT_RULES"
        )
    return PRICE_LIMIT_RULES[group]


def scan_price_limits(prices: pd.DataFrame, meta: Dict[str, dict]) -> Dict[str, dict]:
    """Report every daily move that exceeds its instrument's physical limit."""
    returns = prices.pct_change(fill_method=None)
    findings: Dict[str, dict] = {}

    header = (f"{'code':>12s} {'limit':>8s} {'breaches':>9s} {'max':>9s} "
              f"{'min':>9s}  years")
    print(header)
    print("-" * (len(header) + 20))

    for code in sorted(prices.columns):
        series = returns[code].dropna()
        if len(series) < MIN_OBSERVATIONS:
            continue
        limit = limit_for(code, meta)
        if limit is None:
            continue

        breaches = series[series.abs() > limit + LIMIT_BUFFER]
        if breaches.empty:
            continue

        by_year = breaches.groupby(breaches.index.year).size()
        findings[code] = {
            "limit": limit,
            "n_breaches": int(len(breaches)),
            "max_move": float(series.max()),
            "min_move": float(series.min()),
            "by_year": {int(y): int(n) for y, n in by_year.items()},
            "dates": [str(d.date()) for d in breaches.index[:20]],
        }
        years = " ".join(f"{y}:{n}" for y, n in by_year.items())
        print(f"{code:>12s} {limit:>8.1%} {len(breaches):>9d} "
              f"{series.max():>9.2%} {series.min():>9.2%}  {years}")

    return findings


def scan_generic_anomalies(prices: pd.DataFrame) -> Dict[str, dict]:
    """Constraint checks that hold in every market.

    None of these need a threshold to be argued about: a non-positive price,
    a duplicated timestamp and an out-of-order index are wrong everywhere.
    The stale-run check is the one judgement call, and it is reported rather
    than treated as an error, because some instruments legitimately do not
    trade for days.
    """
    findings: Dict[str, dict] = {}

    if not prices.index.is_monotonic_increasing:
        findings["_index"] = {"error": "index is not sorted ascending"}
    duplicates = prices.index.duplicated().sum()
    if duplicates:
        findings.setdefault("_index", {})["duplicate_dates"] = int(duplicates)

    for code in prices.columns:
        series = prices[code].dropna()
        if len(series) < MIN_OBSERVATIONS:
            continue
        issues = {}

        non_positive = int((series <= 0).sum())
        if non_positive:
            issues["non_positive_prices"] = non_positive

        # Longest run of an unchanged price, i.e. a series that stopped
        # updating while still returning values.
        unchanged = series.diff() == 0
        longest = 0
        run = 0
        for flag in unchanged:
            run = run + 1 if flag else 0
            longest = max(longest, run)
        if longest >= 10:
            issues["longest_flat_run_days"] = int(longest)

        # Calendar gaps, which usually mean a failed download rather than a
        # market holiday once they get this long.
        gaps = series.index.to_series().diff().dt.days.dropna()
        if len(gaps) and gaps.max() > 30:
            issues["largest_gap_days"] = int(gaps.max())

        if issues:
            findings[code] = issues

    return findings


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--config", default=None)
    parser.add_argument("--json", default=None, help="path for the findings file")
    parser.add_argument("--live", action="store_true",
                        help="include data past research_end (QC only, never research)")
    args = parser.parse_args()

    cfg = load_config(args.config)
    prices = load_prices(cfg, research=not args.live)
    meta = universe_meta(cfg)

    print("=" * 88)
    print("DATA QC - physically impossible values")
    print("=" * 88)
    print(f"{len(prices.columns)} instruments, "
          f"{prices.index.min().date()} to {prices.index.max().date()}\n")

    print("Daily price-limit breaches")
    print("-" * 88)
    limit_findings = scan_price_limits(prices, meta)
    if not limit_findings:
        print("  none")

    print("\nGeneric constraint violations")
    print("-" * 88)
    generic = scan_generic_anomalies(prices)
    for code, issues in generic.items():
        print(f"  {code}: {issues}")
    if not generic:
        print("  none")

    total = sum(f["n_breaches"] for f in limit_findings.values())
    print("\n" + "=" * 88)
    print(f"{len(limit_findings)} instruments with limit breaches, "
          f"{total} bad observations")
    if limit_findings:
        print("Next step: pull the same series from an independent source and "
              "adjudicate. Replace the affected span, not the single bar. Then "
              "re-run every result that used the old data.")

    out_path = Path(args.json) if args.json else cfg.path("data", "qc_findings.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(
        {"price_limits": limit_findings, "generic": generic}, indent=2))
    print(f"Findings written to {out_path}")


if __name__ == "__main__":
    main()

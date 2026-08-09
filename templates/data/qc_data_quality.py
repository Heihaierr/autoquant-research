"""Validate a wide price table against constraints, before it reaches a backtest.

THE IDEA, same as ``qc_price_limits.py``: prefer a rule that makes a number
*impossible* over a rule that makes it unusual. A statistical outlier test
cannot separate a corrupt series from a real crisis, and a mis-adjusted series
has entirely plausible daily moves — it is wrong in the level, which is the
one thing daily-shape statistics cannot see. A mis-adjusted series can
correlate above 0.96 with its correct reference day-to-day and still be off
by double-digit percentage points per year in the level, because a high daily
correlation only says the *shape* of the two series agrees, not that their
compounded level does.

Four checks, in decreasing order of how certain their verdict is.

1. IMPLIED DISTRIBUTION YIELD. Divide the total-return series by the unadjusted
   one and the quotient is the cumulative adjustment the source applied;
   annualize it and you have the distribution yield the data claims to have
   paid, which is a number with a published answer. This is the check that
   decides whether a source can be used at all: one otherwise plausible US
   series implied 12.75% a year for EFA (real: ~3%) and 6.41% for IWM (real:
   ~1.3%), and computed a negative 21-year total return for EEM. Nothing about
   the series looked wrong until the quotient was taken. Requires the
   unadjusted companion table; the check is skipped, loudly, when it is absent.

   The sign is a hard constraint and needs no expectation to test: a
   distribution cannot be negative, so total return below price return means
   the adjustment ran the wrong way.

   THE ADJUSTMENT IS NOT ALL DIVIDENDS. A fund that re-denominates its shares
   moves the unadjusted price by a factor unrelated to any distribution, and
   left in, that factor is read as income. Three of the eleven China ETFs here
   do it, and it is not the tidy 2:1 of a US stock split — one is 3.4855:1 —
   so it cannot be recognized by rounding to a small integer ratio. It is
   recognized instead by size and shape: a distribution is a slow accumulation
   of sub-1% steps, a re-denomination is one step of tens of percent on a
   single day. Those days are split out and reported separately; only what
   remains is called yield. Without that split, the Nasdaq QDII sleeve implies
   13.76%/yr of dividends and the CSI 500 sleeve implies minus 9.14%.

2. RETURN MAGNITUDE. Long-run annualized return outside a plausible band. This
   is the weakest check here and the one most likely to fire on something real,
   so it is bounded generously and every hit is meant to be adjudicated rather
   than believed.

3. SPLIT-LIKE JUMPS. A day-over-day price ratio sitting on 1/2, 2, 1/3, 3, 1/4,
   4, 1/10 or 10 is an unadjusted corporate action. This one is a physical
   constraint in the strict sense: split ratios are small integer ratios, they
   are not drawn from a continuous distribution, and no market move lands on
   exactly 0.3333 by coincidence.

4. GAPS. Trading days missing from an instrument between its own first and last
   observation, measured against the union calendar of the table. Reported and
   counted, never filled. Forward-filling a hole invents a flat day, a flat day
   has zero return and zero variance, and both of those flatter every risk
   metric computed afterwards — lower volatility raises Sharpe, and a
   volatility-weighted allocator will overweight the instrument with the most
   missing data.

WHAT TO DO WITH A FINDING. Do not delete the point and interpolate. Pull the
same series from an independent source and adjudicate; if the second source
agrees, the constraint model is wrong, and if it disagrees, replace the whole
affected span rather than the single bar, because a bad adjustment factor
corrupts a range. Then re-run every result computed from the old data.

Expectations live in the config, not here, because they are market- and
instrument-specific: ``expect_yield`` and optionally ``expect_cagr`` on each
universe entry, plus a ``qc`` block for the tolerances. Running with only
``--prices`` is supported and performs checks 3 and 4; the other two report
themselves as NOT PERFORMED rather than silently passing.

Usage:
    PYTHONPATH=. python data/qc_data_quality.py --config config.us.yaml
    PYTHONPATH=. python data/qc_data_quality.py --prices data/cache/prices_cn.parquet \
        --raw data/cache/prices_cn_raw.parquet
    PYTHONPATH=. python data/qc_data_quality.py --config config.cn.yaml --json qc.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, Iterable, List, Optional

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from framework.data_loader import load_config, universe_meta  # noqa: E402

# Ratios a split or a fund-share re-denomination can produce. Anything landing
# on one of these within TOLERANCE is a corporate action that was not adjusted
# away, not a market move.
SPLIT_RATIOS = (0.1, 0.25, 1.0 / 3.0, 0.5, 2.0, 3.0, 4.0, 10.0)
SPLIT_TOLERANCE = 0.02

# Single-day move in the adjusted/unadjusted ratio above which the cause is a
# share re-denomination rather than a distribution.
#
# The gap between the two populations is wide, which is why this works: the
# largest single-day distribution in either demo universe is DBC's year-end
# payout at 5.3% of net asset value, while the re-denominations are x0.287,
# x2.000 and x5.000. Tightening this to 10% would start reading annual
# distributions as corporate actions and erase them from the yield.
REDENOMINATION_STEP = 0.25

# Defaults for the ``qc`` config block.
DEFAULTS = {
    # How far the implied yield may sit from the configured expectation. The
    # expectation is a rough current figure while the data spans two decades,
    # so this is deliberately loose: it is sized to catch an order-of-magnitude
    # error, which is what a broken adjustment chain produces.
    "yield_tolerance": 0.015,
    # A distribution cannot be negative. Small negatives are rounding in the
    # adjustment factors; a real one means the chain ran backwards.
    "negative_yield_floor": -0.002,
    # Long-run annualized return band for a plain long-only fund.
    "plausible_cagr": [-0.10, 0.30],
    # Fraction of the union calendar an instrument may miss inside its own
    # first/last dates before the series is treated as unusable.
    "max_missing_fraction": 0.02,
    # Below this many observations, none of the per-instrument statistics mean
    # anything and the instrument is reported but not judged.
    "min_observations": 250,
    # Published unit conversions, as ``{code: [first affected trading day]}``.
    # These are facts about the fund rather than parameters, and they are listed
    # rather than inferred because no magnitude rule separates a conversion from
    # a distribution once the two overlap in size.
    "redenominations": {},
}


def read_table(path: Path) -> pd.DataFrame:
    frame = pd.read_parquet(path) if path.suffix == ".parquet" \
        else pd.read_csv(path, index_col=0)
    frame.index = pd.to_datetime(frame.index)
    return frame.sort_index()


def cagr(series: pd.Series) -> float:
    """Annualize over elapsed calendar time rather than a bar count.

    A trading-day divisor would import a market-specific constant into a check
    whose whole purpose is to be comparable against externally published
    figures, and would bias the result on any instrument whose calendar differs
    from the assumed one.
    """
    series = series.dropna()
    years = (series.index[-1] - series.index[0]).days / 365.25
    if years <= 0 or series.iloc[0] <= 0:
        return float("nan")
    return float((series.iloc[-1] / series.iloc[0]) ** (1.0 / years) - 1.0)


def decompose_adjustment(total_return: pd.Series, price_return: pd.Series,
                         declared: Iterable[str] = ()) -> tuple[float, pd.Series,
                                                                pd.Series]:
    """Separate the distribution component of the adjustment from re-denominations.

    Works on the day-over-day steps of the ratio rather than its level, so a
    source that anchors its adjusted series anywhere it likes — at the listing
    price, at the latest price, at an arbitrary normalization — gives the same
    answer.

    Declared dates are removed by date and unconditionally, because there is no
    magnitude that separates the two events in general: a 14.5% unit conversion
    and a 14.5% distribution move the ratio identically, and only the corporate
    action record says which happened. The magnitude rule stays as the fallback
    for an unlabelled table, and anything it catches that was not declared is
    returned separately so it can be reported rather than quietly absorbed.
    """
    factor = (total_return / price_return).replace(
        [float("inf"), float("-inf")], float("nan")).dropna()
    step = (factor / factor.shift(1)).dropna()
    known = step.index.intersection(pd.to_datetime(list(declared)))
    remainder = step.drop(known)
    undeclared = remainder[(remainder - 1.0).abs() > REDENOMINATION_STEP]
    return (float(remainder.drop(undeclared.index).prod()),
            step.reindex(known), undeclared)


def check_implied_yield(total_return: pd.DataFrame, price_return: pd.DataFrame,
                        meta: Dict[str, dict], settings: dict) -> Dict[str, dict]:
    findings: Dict[str, dict] = {}
    header = (f"{'code':>10s} {'years':>6s} {'TR%':>8s} {'PR%':>8s} "
              f"{'implied%':>9s} {'expect%':>8s} {'diff pp':>8s} {'redenom':>8s}  verdict")
    print(header)
    print("-" * len(header))

    for code in sorted(total_return.columns):
        if code not in price_return.columns:
            print(f"{code:>10s}  no unadjusted series")
            continue

        # Both legs must span the same days or the ratio measures the calendar
        # rather than the distributions.
        common = total_return[code].dropna().index.intersection(
            price_return[code].dropna().index)
        if len(common) < settings["min_observations"]:
            continue
        tr = total_return[code].reindex(common)
        pr = price_return[code].reindex(common)
        years = (common[-1] - common[0]).days / 365.25
        declared = settings.get("redenominations", {}).get(code, ())
        dividend_factor, events, undeclared = decompose_adjustment(tr, pr, declared)
        implied = dividend_factor ** (1.0 / years) - 1.0

        expected = meta.get(code, {}).get("expect_yield")
        verdict, problem = "ok", None
        if len(undeclared):
            verdict = "FAIL undeclared re-denomination"
            problem = "undeclared_redenomination"
        elif implied < settings["negative_yield_floor"]:
            verdict = "FAIL negative implied yield"
            problem = "negative"
        elif expected is None:
            verdict = "no expect_yield in config"
        elif abs(implied - float(expected)) > settings["yield_tolerance"]:
            verdict = "FAIL off expectation"
            problem = "off_expectation"

        exp_txt = "n/a" if expected is None else f"{float(expected)*100:.2f}"
        diff_txt = "n/a" if expected is None else f"{(implied-float(expected))*100:.2f}"
        print(f"{code:>10s} {years:6.1f} {cagr(tr)*100:8.2f} {cagr(pr)*100:8.2f} "
              f"{implied*100:9.2f} {exp_txt:>8s} {diff_txt:>8s} {len(events):8d}  "
              f"{verdict}")
        for date, value in events.items():
            print(f"{'':>10s}   re-denomination {date.date()} "
                  f"x{value:.4f} (declared, excluded from the yield above)")
        for date, value in undeclared.items():
            print(f"{'':>10s}   step {date.date()} x{value:.4f} is too large to "
                  f"be a distribution and is not declared in qc.redenominations")

        if problem:
            findings[code] = {
                "problem": problem,
                "implied_yield": implied,
                "expected_yield": None if expected is None else float(expected),
                "tr_cagr": cagr(tr),
                "pr_cagr": cagr(pr),
                "years": years,
                "redenominations": {str(d.date()): float(v)
                                    for d, v in events.items()},
                "undeclared_steps": {str(d.date()): float(v)
                                     for d, v in undeclared.items()},
            }
    return findings


def check_magnitude(prices: pd.DataFrame, meta: Dict[str, dict],
                    settings: dict) -> Dict[str, dict]:
    findings: Dict[str, dict] = {}
    low, high = settings["plausible_cagr"]
    for code in sorted(prices.columns):
        series = prices[code].dropna()
        if len(series) < settings["min_observations"]:
            continue
        band = meta.get(code, {}).get("expect_cagr") or [low, high]
        value = cagr(series)
        if not (float(band[0]) <= value <= float(band[1])):
            findings[code] = {
                "cagr": value,
                "band": [float(band[0]), float(band[1])],
                "years": (series.index[-1] - series.index[0]).days / 365.25,
            }
            print(f"  {code}: {value:.2%}/yr outside "
                  f"[{float(band[0]):.1%}, {float(band[1]):.1%}]")
    return findings


def check_split_jumps(prices: pd.DataFrame, settings: dict) -> Dict[str, dict]:
    findings: Dict[str, dict] = {}
    for code in sorted(prices.columns):
        series = prices[code].dropna()
        if len(series) < settings["min_observations"]:
            continue
        ratio = (series / series.shift(1)).dropna()
        hits = []
        for target in SPLIT_RATIOS:
            near = ratio[((ratio - target).abs() / target) < SPLIT_TOLERANCE]
            hits.extend({"date": str(d.date()), "ratio": float(v),
                         "looks_like": target} for d, v in near.items())
        if hits:
            hits.sort(key=lambda h: h["date"])
            findings[code] = {"n": len(hits), "hits": hits[:20]}
            print(f"  {code}: {len(hits)} split-like jump(s), "
                  f"first {hits[0]['date']} ratio {hits[0]['ratio']:.4f} "
                  f"(~{hits[0]['looks_like']:.4g})")
    return findings


def check_gaps(prices: pd.DataFrame, settings: dict) -> Dict[str, dict]:
    """Trading days an instrument is missing inside its own listed span.

    The union of all instruments' dates is the best available calendar when the
    table is the only input. It understates gaps on a day the whole table is
    missing, which is why a download that failed for every instrument at once
    is a separate problem this check cannot see.
    """
    findings: Dict[str, dict] = {}
    calendar = prices.index
    header = f"{'code':>10s} {'first':>12s} {'last':>12s} {'rows':>7s} {'gaps':>6s} {'miss%':>7s}"
    print(header)
    print("-" * len(header))

    for code in sorted(prices.columns):
        series = prices[code].dropna()
        if series.empty:
            print(f"{code:>10s} {'EMPTY':>12s}")
            findings[code] = {"problem": "empty"}
            continue
        span = calendar[(calendar >= series.index[0]) & (calendar <= series.index[-1])]
        gaps = len(span) - len(series)
        fraction = gaps / len(span) if len(span) else 0.0
        print(f"{code:>10s} {series.index[0].date()!s:>12s} "
              f"{series.index[-1].date()!s:>12s} {len(series):7d} {gaps:6d} "
              f"{fraction*100:7.3f}")
        if fraction > settings["max_missing_fraction"]:
            findings[code] = {"problem": "gaps", "gaps": int(gaps),
                              "missing_fraction": fraction}
    return findings


def check_generic(prices: pd.DataFrame) -> Dict[str, dict]:
    findings: Dict[str, dict] = {}
    if not prices.index.is_monotonic_increasing:
        findings["_index"] = {"error": "index is not sorted ascending"}
    duplicates = int(prices.index.duplicated().sum())
    if duplicates:
        findings.setdefault("_index", {})["duplicate_dates"] = duplicates
    if getattr(prices.index, "tz", None) is not None:
        findings.setdefault("_index", {})["error_tz"] = str(prices.index.tz)
    for code in prices.columns:
        series = prices[code].dropna()
        non_positive = int((series <= 0).sum())
        if non_positive:
            findings[code] = {"non_positive_prices": non_positive}
    return findings


def resolve_inputs(args) -> tuple[Path, Optional[Path], Dict[str, dict], dict]:
    """Locate the tables and the expectations to judge them against.

    ``--prices`` and ``--config`` compose rather than exclude: pointing a
    configured universe's expectations at a different file is how a candidate
    replacement source gets compared against the one in use.
    """
    meta: Dict[str, dict] = {}
    settings = dict(DEFAULTS)
    prices_path = Path(args.prices) if args.prices else None
    raw_path = Path(args.raw) if args.raw else None

    if args.config or prices_path is None:
        cfg = load_config(args.config)
        data_cfg = cfg.get("data", {}) or {}
        cache = cfg.path(data_cfg.get("cache_dir", "data/cache"))
        if prices_path is None:
            prices_path = cache / data_cfg.get("price_file", "prices.parquet")
        raw_name = data_cfg.get("raw_price_file")
        if raw_path is None and raw_name:
            raw_path = cache / raw_name
        meta = universe_meta(cfg)
        settings.update(cfg.get("qc", {}) or {})

    return prices_path, raw_path, meta, settings


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--config", default=None)
    parser.add_argument("--prices", default=None,
                        help="wide parquet/csv to check; bypasses the config")
    parser.add_argument("--raw", default=None,
                        help="unadjusted companion table, enables the implied-"
                             "yield check")
    parser.add_argument("--json", default=None, help="path for the findings file")
    args = parser.parse_args()

    prices_path, raw_path, meta, settings = resolve_inputs(args)
    prices = read_table(prices_path)
    raw = read_table(raw_path) if raw_path and raw_path.exists() else None

    print("=" * 88)
    print(f"DATA QC - {prices_path}")
    print("=" * 88)
    print(f"{len(prices.columns)} instruments, {prices.index.min().date()} to "
          f"{prices.index.max().date()}, {len(prices)} rows")
    print(f"unadjusted companion: {raw_path if raw is not None else 'ABSENT'}\n")

    # Anything this run could not check is recorded next to what it did check.
    # A skipped check and a passed check are indistinguishable in a summary
    # unless the difference is written down at the point it happens.
    limitations: List[dict] = []

    print("[1] Implied distribution yield (adjusted / unadjusted, "
          "net of re-denominations)")
    print("-" * 88)
    if raw is None:
        yield_findings: Dict[str, dict] = {}
        limitations.append({
            "check": "implied_dividend_yield",
            "status": "NOT PERFORMED",
            "reason": "no unadjusted companion table was supplied",
            "consequence": "whether these prices are total-return adjusted is "
                           "UNVERIFIED. A price-only series understates return "
                           "by the distribution yield, which is largest exactly "
                           "where it matters most (bonds, REITs).",
        })
        print("  NOT PERFORMED - no unadjusted table. Adjustment status is "
              "unverified, not verified-good.")
    else:
        yield_findings = check_implied_yield(prices, raw, meta, settings)
    unexplained = [c for c in prices.columns
                   if c in meta and meta[c].get("expect_yield") is None]
    if raw is not None and unexplained:
        limitations.append({
            "check": "implied_dividend_yield",
            "status": "PARTIAL",
            "reason": f"no expect_yield configured for: {', '.join(sorted(unexplained))}",
            "consequence": "only the sign constraint was applied to these.",
        })

    print("\n[2] Long-run return magnitude")
    print("-" * 88)
    magnitude = check_magnitude(prices, meta, settings)
    if not magnitude:
        print("  none outside band")

    print("\n[3] Split-like jumps (unadjusted corporate actions)")
    print("-" * 88)
    splits = check_split_jumps(prices, settings)
    if not splits:
        print("  none")
    if raw is not None:
        # Only the adjusted table is judged. A corporate action surviving in
        # the unadjusted companion is what "unadjusted" means, and check 1
        # already removes those days before calling anything a yield.
        print("  (unadjusted companion, informational)")
        informational = check_split_jumps(raw, settings)
        if not informational:
            print("    none")

    print("\n[4] Coverage and gaps (reported, never filled)")
    print("-" * 88)
    gaps = check_gaps(prices, settings)

    print("\n[5] Generic constraints")
    print("-" * 88)
    generic = check_generic(prices)
    for code, issues in generic.items():
        print(f"  {code}: {issues}")
    if not generic:
        print("  none")

    failures = {
        "implied_yield": yield_findings,
        "magnitude": magnitude,
        "split_jumps": splits,
        "gaps": gaps,
        "generic": generic,
    }
    n_failed = sum(len(v) for v in failures.values())

    print("\n" + "=" * 88)
    for item in limitations:
        print(f"LIMITATION [{item['status']}] {item['check']}: {item['reason']}")
    if n_failed:
        print(f"FAILED: {n_failed} finding(s) across "
              f"{sum(1 for v in failures.values() if v)} check(s)")
        for name, found in failures.items():
            if found:
                print(f"  {name}: {', '.join(sorted(found))}")
        print("Next step: pull the same series from an independent source and "
              "adjudicate. Replace the affected span, not the single bar. Then "
              "re-run every result that used the old data.")
    else:
        print("PASSED: no findings")

    out_path = Path(args.json) if args.json else prices_path.with_suffix(".qc.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(
        {"prices": str(prices_path), "raw": str(raw_path) if raw is not None else None,
         "limitations": limitations, "findings": failures}, indent=2, default=str))
    print(f"Findings written to {out_path}")

    sys.exit(1 if n_failed else 0)


if __name__ == "__main__":
    main()

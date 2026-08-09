"""Fetch a multi-asset US ETF universe into the wide price table the engine reads.

This is the demo data path. It needs no account, no API key and no quota, which
is the only reason the whole loop can be run by someone who has not yet decided
whether any of this is worth their time.

TWO THINGS THIS FILE IS CAREFUL ABOUT, both of which are silent when wrong:

``auto_adjust=True`` is not a convenience flag. It returns the series you would
have held through every distribution, which is what a backtest must compound.
Raw last-traded prices turn each dividend into a one-day drawdown, and for the
bond and REIT sleeves — where most of the total return arrives as income — that
is not a rounding error. TLT and VNQ would look like decade-long declines.

Missing days are left missing. Forward-filling a gap invents a flat day, and a
flat day is not neutral: it lowers measured volatility, which inflates Sharpe
and shrinks the apparent cost of holding the instrument. The engine already
handles NaN by renormalizing over what has data, so the honest move is to hand
it the holes and let it say so.

WHY THE UNADJUSTED TABLE IS WRITTEN TOO. Nothing about a price series announces
whether it is total-return or not, and the adjustment is exactly the part that
is wrong most often. Keeping both tables lets ``qc_data_quality.py`` subtract
one annualized return from the other and read off the distribution yield the
data implies, which is a number with a published answer to check against. One
source's US series implied 12.75%/yr for EFA against a real ~3%; that source
was rejected on this test alone. Without the second table there is nothing to
subtract and the check cannot be run at all.

NETWORK FAILURES ARE NOT DATA FAILURES. Yahoo blocks by source IP, and the
block does not look like a block: yfinance surfaces it as ``YFRateLimitError``
and the underlying chart endpoint answers 403 or 429 to every retry and every
User-Agent. From one host this reproduced for hours direct while succeeding
immediately through an ordinary HTTP proxy, i.e. the address was refused rather
than the request. Before editing the ticker list, check whether the endpoint
answers at all, and try a different egress path:

    curl -s -o /dev/null -w '%{http_code}\\n' \\
        'https://query1.finance.yahoo.com/v8/finance/chart/SPY?range=5d&interval=1d'

yfinance honours the standard ``HTTPS_PROXY`` / ``HTTP_PROXY`` environment
variables, so routing around it needs no code change.

Usage:
    PYTHONPATH=. python data/fetch_us_etfs.py
    PYTHONPATH=. python data/fetch_us_etfs.py --start 2010-01-01
    HTTPS_PROXY=http://127.0.0.1:7897 PYTHONPATH=. python data/fetch_us_etfs.py
"""
from __future__ import annotations

import argparse
import time
from pathlib import Path

import pandas as pd

# A deliberately broad universe: five equity sleeves that behave differently in
# a selloff, three duration/credit sleeves, gold, broad commodities, and REITs.
#
# The point of the spread is to give a rotation signal something to actually
# choose between. A universe of five US equity ETFs looks like eleven choices
# and is one choice — the five sleeves are correlated enough in a broad selloff
# that a rotation among them is a narrower bet than the instrument count
# suggests.
UNIVERSE = {
    "SPY": "US large-cap equity",
    "QQQ": "US tech-heavy equity",
    "IWM": "US small-cap equity",
    "EFA": "Developed ex-US equity",
    "EEM": "Emerging-market equity",
    "TLT": "Long US Treasuries",
    "IEF": "Intermediate US Treasuries",
    "LQD": "Investment-grade credit",
    "GLD": "Gold",
    "DBC": "Broad commodities",
    "VNQ": "US REITs",
}

# DBC lists in Feb 2006 and is the binding constraint on a fully populated
# panel. Starting earlier is legitimate — the engine renormalizes over what
# exists — but then early windows quietly test a smaller universe than late
# ones, which is a difference between windows that has nothing to do with the
# strategy.
DEFAULT_START = "2006-02-06"

# One ticker per request rather than a batch. A batch that partially fails
# returns a frame with a missing column and no exception, and the retry then
# costs the whole universe instead of the one series that failed.
RETRIES = 4
PAUSE = 0.5


def _fetch_one(ticker: str, start: str, end: str | None, adjust: bool) -> pd.Series:
    import yfinance as yf

    last_error: Exception | None = None
    for attempt in range(RETRIES):
        try:
            frame = yf.download(ticker, start=start, end=end, auto_adjust=adjust,
                                progress=False, threads=False, actions=False)
            if frame is not None and not frame.empty:
                close = frame["Close"]
                return close.iloc[:, 0] if isinstance(close, pd.DataFrame) else close
        except Exception as exc:  # noqa: BLE001 - retried, then re-raised below
            last_error = exc
        time.sleep(2 + 3 * attempt)
    raise RuntimeError(
        f"{ticker}: no data after {RETRIES} attempts ({last_error}). "
        "Check the endpoint answers from this host before touching the ticker "
        "list — see the note on IP blocks at the top of this file."
    )


def fetch(tickers: list[str], start: str, end: str | None,
          adjust: bool = True) -> pd.DataFrame:
    columns = {}
    for ticker in tickers:
        columns[ticker] = _fetch_one(ticker, start, end, adjust)
        time.sleep(PAUSE)

    close = pd.DataFrame(columns)[tickers].sort_index()
    close.index = pd.to_datetime(close.index).tz_localize(None)
    close.index.name = "date"
    return close.dropna(how="all")


def report(prices: pd.DataFrame) -> None:
    print(f"\n{len(prices.columns)} instruments, "
          f"{prices.index.min().date()} to {prices.index.max().date()}, "
          f"{len(prices)} rows\n")
    print(f"{'code':6s} {'first':12s} {'last':12s} {'rows':>6s} {'gaps':>6s}  name")
    for code in prices.columns:
        series = prices[code].dropna()
        if series.empty:
            print(f"{code:6s} {'EMPTY':12s}")
            continue
        span = prices.loc[series.index.min():series.index.max(), code]
        print(f"{code:6s} {series.index.min().date()!s:12s} "
              f"{series.index.max().date()!s:12s} {len(series):6d} "
              f"{span.isna().sum():6d}  {UNIVERSE.get(code, '')}")

    # The date every instrument has data is where a like-for-like comparison
    # becomes possible. Reported rather than enforced: a later start is a
    # decision with a cost either way, and the engine can handle both.
    first_full = prices.dropna().index.min()
    if pd.notna(first_full):
        print(f"\nfully populated from {first_full.date()}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--start", default=DEFAULT_START)
    parser.add_argument("--end", default=None,
                        help="exclusive; default is today. Not a research "
                             "cutoff — that lives in config.yaml and is "
                             "enforced by the loader.")
    parser.add_argument("--out", default="data/cache/prices_us.parquet")
    parser.add_argument("--raw-out", default="data/cache/prices_us_raw.parquet",
                        help="companion unadjusted table; qc_data_quality.py "
                             "needs it to measure the implied dividend yield")
    args = parser.parse_args()

    tickers = list(UNIVERSE)
    prices = fetch(tickers, args.start, args.end, adjust=True)
    report(prices)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    prices.to_parquet(out)
    print(f"\nwrote {out}")

    raw = fetch(tickers, args.start, args.end, adjust=False)
    raw_out = Path(args.raw_out)
    raw_out.parent.mkdir(parents=True, exist_ok=True)
    raw.to_parquet(raw_out)
    print(f"wrote {raw_out}")
    print("\nNext: PYTHONPATH=. python data/qc_data_quality.py --config config.us.yaml")


if __name__ == "__main__":
    main()

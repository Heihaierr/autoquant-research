"""Fetch a multi-asset China A-share ETF universe into the engine's price table.

Companion to ``fetch_us_etfs.py``; same output contract, different market and a
very different source. Needs no account and no API key.

TWO THINGS THIS FILE IS CAREFUL ABOUT, both of which are silent when wrong:

The adjusted series (``hfq``, 后复权) is not a convenience flag. It is the
series you would have held through every distribution, which is what a backtest
must compound. Unadjusted prices turn each distribution into a one-day
drawdown, and for the bond sleeve — where essentially all of the return arrives
as coupon income — that is not a rounding error. Note that the failure mode is
milder here than in the US table and therefore easier to miss: most Chinese
ETFs accumulate income into net asset value instead of distributing it, so the
adjustment is worth ~1.2%/yr on the equity sleeves and ~0.3%/yr on the bond
sleeves rather than the 3-4%/yr it is worth on TLT and VNQ. Small enough to
overlook, large enough to reorder a ranking.

Missing days are left missing. Forward-filling a gap invents a flat day, and a
flat day is not neutral: it lowers measured volatility, which inflates Sharpe
and shrinks the apparent cost of holding the instrument. The engine already
handles NaN by renormalizing over what has data, so the honest move is to hand
it the holes and let it say so. This matters more here than in the US table:
A-share ETFs suspend individually, and the cross-border sleeve closes on
Chinese holidays while the market it tracks keeps trading.

WHY THE UNADJUSTED TABLE IS WRITTEN TOO. Nothing about a price series announces
whether it is total-return or not, and the adjustment is exactly the part that
is wrong most often. Keeping both lets ``qc_data_quality.py`` divide one by the
other and read off the distribution yield the data implies, which is a number
with a published answer to check against. It is written as the source returned
it, re-denominations included; sorting those out is the QC's job and doing it
here would hide the evidence from the tool built to weigh it.

WHY THE ADJUSTED SERIES IS RESCALED. Both sources anchor ``hfq`` at the listing
price and let it drift above the traded price — East Money's CSI 300 sleeve
ends at 5.63 against a real 4.75, and Tencent normalizes to yet another base.
Returns are unaffected, but ``tracking/paper_trade.py`` sizes positions from
the last price and would buy the wrong number of lots. Anchoring the last value
to the last traded price fixes that and matches the US table's convention.

THREE CHAINS WITH THREE DIFFERENT ROLES. ``--source`` selects between them and
they are not interchangeable.

  sina (default, base). Publishes the traded close and the cumulative
  distribution per unit with its ex-date, and nothing else, so the adjusted
  series is built here rather than trusted. That is more work and it is the
  reason this chain can be audited line by line: every step separating the
  adjusted series from the traded price is either a distribution Sina reports
  or a conversion ratio in REDENOMINATIONS below. It also stays on one vehicle
  throughout — the traded price — which is the property the other two lack.

  eastmoney (alternative, and the conventional choice). ``fund_etf_hist_em``
  with ``adjust="hfq"`` returns the adjusted series directly. Its kline path
  bans by IP and does so repeatedly: roughly 25 requests bought a 76-minute
  block, and the address was refused again within the hour after recovering.
  Other East Money endpoints on the same host kept returning 200 throughout,
  including the NAV record this file relies on, so a failure here says nothing
  about the network. The block is served as an empty reply, which surfaces as
  ``RemoteDisconnected`` and reads like a local fault. Budget for retries
  measured in hours, not seconds, and expect to be cut off mid-run.

  tencent (cross-check only). Agrees closely with East Money over full history
  — the cumulative adjustment factor matches to five significant figures on
  every instrument both carry — which is what makes it useful for scoring the
  other two. It is not a usable base, and ``verify`` is what establishes that:
  its adjusted series is derived from net asset value while its unadjusted
  series is the traded price, so on days when a fund trades away from NAV the
  two disagree about the day's return. The CSI 300 sleeve moved +8.02%
  adjusted against +9.41% unadjusted on 2024-09-30, during the retail surge
  that pushed on-exchange funds to a visible premium; nothing about either
  series looks wrong alone, and pairing them implies a 1.27% distribution in a
  single day. Substituting a NAV series for a traded one is a real vehicle
  swap — the same instrument's on-exchange price and its off-exchange NAV are
  not interchangeable data sources, only the same underlying holding.

  It does carry one thing the others cannot: a NAV series that runs
  continuously through a share re-denomination, which is how the conversion
  ratios below were measured.

WHERE THE CHAINS DISAGREE, and what settled it. Comparing the two adjusted
series day by day leaves 42 days out of ~31,000 where they differ by more than
0.4%, and they fall into two kinds that look nothing alike.

One is a single 12.7pp step on the CSI 500 sleeve on 2022-08-29, isolated and
far larger than anything around it. That was a re-denomination missing from the
table below; it is now in it and the two chains agree on that sleeve.

The rest are all on high-volatility days and all damped in the same direction:
the traded price moves further than the NAV series, up days and down days
alike, by more on wilder days — 31 such days on the CSI 300 sleeve, 7 on the
Hang Seng sleeve, 3 on ChiNext, peaking at 1.4pp on 2024-09-30 as on-exchange
funds ran to a visible premium. That is premium and discount opening and
closing, not a corporate action, and it does not net to zero over a sample
whose large moves are net upward — a small compounding drag on that sleeve
that a NAV-only reconstruction would miss entirely. The traded price is the
honest series there, so the disagreement is Tencent's and the reconstruction
stands.

Worth keeping in view: the volatility-damping signature is what disqualifies
Tencent as a base, and it is also what makes it a good detector, because a real
corporate action cannot hide inside it.

Tencent additionally does not carry the commodity futures ETFs or LOFs; Sina
and East Money both do.

SOURCE NOTES, measured rather than assumed:

  * All three are mainland-China endpoints and refuse connections arriving
    through an overseas proxy. If every request fails instantly, unset the
    proxy environment variables before blaming the source.
  * One instrument per request, a deliberate pause between them, exponential
    backoff, and a per-instrument cache, so a run that dies at instrument 9
    costs 3 more requests to finish rather than 24. This exists because of the
    East Money ban above and applies to every chain.
  * Tencent caps a response at 640 bars regardless of the count requested, so
    history is paged by date range.

Usage:
    NO_PROXY='*' PYTHONPATH=. python data/fetch_cn_etfs.py
    NO_PROXY='*' PYTHONPATH=. python data/fetch_cn_etfs.py --source tencent
    NO_PROXY='*' PYTHONPATH=. python data/fetch_cn_etfs.py --refresh
"""
from __future__ import annotations

import argparse
import json
import time
import urllib.request
from pathlib import Path

import pandas as pd

# Multi-asset by construction: four domestic equity sleeves that separate in a
# selloff, three cross-border equity sleeves whose returns are driven by a
# different economy and a currency, two duration sleeves, gold, and an
# agricultural commodity.
#
# The cross-border and commodity sleeves are the ones doing the work. A
# universe of domestic A-share equity ETFs looks like eleven choices and is one
# choice — they move together closely enough in a domestic selloff that a
# rotation among them alone is a much narrower bet than the instrument count
# suggests.
UNIVERSE = {
    "510300": "CSI 300 large-cap",
    "510500": "CSI 500 mid-cap",
    "159915": "ChiNext growth",
    "588000": "STAR 50",
    "513100": "Nasdaq 100 (QDII)",
    "513500": "S&P 500 (QDII)",
    "159920": "Hang Seng (QDII)",
    "518880": "Gold",
    "511010": "Treasury bonds",
    "511260": "10Y government bonds",
    "159985": "Soybean meal futures",
}

# Everything the source has. The panel is ragged — the STAR 50 sleeve lists in
# late 2020 — and that is left as it is. Backfilling a listing date from an
# index is the cheapest way to manufacture a survivorship advantage, and a
# forward-filled pre-listing stretch reads as unnaturally low volatility to any
# risk-based allocator.
DEFAULT_START = "1990-01-01"
DEFAULT_END = "2099-12-31"

RETRIES = 6
PAUSE = 1.5

TENCENT_URL = "https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param="
EXCHANGE_PREFIX = {"5": "sh", "1": "sz"}

# Share re-denominations (份额折算): the fund restates units outstanding and the
# price moves by the inverse of the ratio with no economic effect on a holder.
# Values below are NEW UNITS PER OLD UNIT, so a holder's position is multiplied
# by this and the price is divided by it. Three are splits and one is a
# consolidation, which is why the direction cannot be inferred from the sign of
# anything and has to be written down.
#
# Left in, these are the single most destructive error possible in this table:
# compounding the 5x step into a total-return series adds 12%/yr to the Nasdaq
# QDII sleeve, and applying the consolidation the wrong way round turns the CSI
# 500 sleeve into 29%/yr. Both survive a plausibility band, which is a fair
# summary of why that band is the weakest check in the QC.
#
# The observed price jump is NOT the ratio — it is the ratio multiplied by that
# day's real move, and reading it off directly gives the CSI 500 sleeve a
# spurious 2.3%. Each value below instead comes from East Money's fund NAV
# record, where 单位净值 restates at the conversion and 累计净值 stays in
# original units, so their quotient is the cumulative conversion factor and its
# one-day step is the ratio. Two of the four land on exact integers, which is
# the evidence that the method is sound rather than merely self-consistent:
#
#   513100  2022-01-13  cumulative factor 1.00000 -> 0.20000  ->  5.000000
#   513500  2022-03-29  cumulative factor 1.00000 -> 0.50000  ->  2.000000
#   510500  2015-04-14  cumulative factor 1.00000 -> 3.56726  ->  0.280327
#   510500  2022-08-26  cumulative factor 3.56724 -> 3.11444  ->  1.145389
#
# The two non-integers are index-alignment conversions: both restate the CSI
# 500 sleeve so a unit is worth one thousandth of the index, which is why the
# ratio is whatever the index happened to be rather than a round number.
#
# DATES HERE ARE THE FIRST AFFECTED TRADING DAY, which is the day after the NAV
# date above in all four cases: the fund suspends creation and trading while it
# converts, so the restated NAV is published before the market can act on it.
# Keying on the NAV date silently applies the ratio to the wrong day.
#
# The 2022 CSI 500 conversion was missing from this table until the daily
# price-limit check reported the sleeve falling 12.74% in one session against a
# 10% band. Sina lists the date with a cumulative distribution of 0.000, so it
# marks the event without pricing it and the distribution path cannot see it;
# the ±10% band is a hard exchange rule and can. Adding an instrument means
# checking whether it has one of these, and running both that check and the
# QC's split-jump scan is what surfaces a missing entry.
REDENOMINATIONS = {
    "510500": {"2015-04-15": 0.280327, "2022-08-29": 1.145389},
    "513100": {"2022-01-14": 5.0},
    "513500": {"2022-03-30": 2.0},
}


def _eastmoney(code: str, adjust: str, start: str, end: str) -> pd.Series:
    import akshare as ak

    frame = ak.fund_etf_hist_em(
        symbol=code, period="daily",
        start_date=start.replace("-", ""), end_date=end.replace("-", ""),
        adjust=adjust)
    if frame is None or frame.empty:
        return pd.Series(dtype=float)
    return pd.Series(frame["收盘"].astype(float).values,
                     index=pd.to_datetime(frame["日期"])).sort_index()


def _sina(code: str, adjust: str, start: str, end: str) -> pd.Series:
    """Market closes from Sina, adjusted here rather than by the source.

    Sina publishes the traded close and the cumulative distribution per unit
    with its ex-date, and nothing else. Building the total-return series from
    those two is more work than asking a source for ``hfq``, and it is the
    reason this chain can be checked line by line: every step that separates
    the adjusted series from the traded price is either a distribution Sina
    reports or a conversion ratio listed in REDENOMINATIONS above.
    """
    import akshare as ak

    symbol = EXCHANGE_PREFIX[code[0]] + code
    frame = ak.fund_etf_hist_sina(symbol=symbol)
    if frame is None or frame.empty:
        return pd.Series(dtype=float)
    close = pd.Series(frame["close"].astype(float).values,
                      index=pd.to_datetime(frame["date"])).sort_index()
    close = close.loc[pd.Timestamp(start):pd.Timestamp(end)]
    if not adjust:
        return close

    payouts = pd.Series(dtype=float)
    dividends = ak.fund_etf_dividend_sina(symbol=symbol)
    if dividends is not None and not dividends.empty:
        cumulative = pd.Series(
            dividends["累计分红"].astype(float).values,
            index=pd.to_datetime(dividends["日期"])).sort_index()
        # Sina reports the running total, so a single payout is its increment.
        # The first row is itself a payout, hence the zero prepended rather
        # than a dropped first event.
        payouts = cumulative.diff().fillna(cumulative)

    relative = (close / close.shift(1)).dropna()
    for date, amount in payouts.items():
        if date not in relative.index or amount <= 0:
            continue
        previous = close.shift(1).loc[date]
        relative.loc[date] = (close.loc[date] + amount) / previous
    for date_text, ratio in REDENOMINATIONS.get(code, {}).items():
        date = pd.Timestamp(date_text)
        if date in relative.index:
            relative.loc[date] *= ratio

    total_return = relative.cumprod()
    total_return.loc[close.index[0]] = 1.0
    total_return = total_return.sort_index()
    # End on the traded price so position sizing in tracking/ stays correct.
    return total_return / total_return.iloc[-1] * close.iloc[-1]


def _tencent(code: str, adjust: str, start: str, end: str) -> pd.Series:
    symbol = EXCHANGE_PREFIX[code[0]] + code
    key = f"{adjust}day" if adjust else "day"
    cursor, stop_at = pd.Timestamp(start), pd.Timestamp(end)
    closes: dict = {}
    while cursor < stop_at:
        chunk_end = min(cursor + pd.Timedelta(days=900), stop_at)
        param = (f"{symbol},day,{cursor:%Y-%m-%d},{chunk_end:%Y-%m-%d},"
                 f"640,{adjust}")
        with urllib.request.urlopen(TENCENT_URL + param, timeout=40) as response:
            payload = json.loads(response.read().decode())
        node = payload.get("data")
        node = node.get(symbol) if isinstance(node, dict) else None
        for row in (node or {}).get(key) or []:
            closes[pd.Timestamp(row[0])] = float(row[2])
        cursor = chunk_end
        time.sleep(0.2)
    return pd.Series(closes).sort_index()


SOURCES = {"eastmoney": _eastmoney, "sina": _sina, "tencent": _tencent}


def _fetch_one(code: str, adjust: str, source: str, start: str,
               end: str) -> pd.Series:
    last_error: Exception | None = None
    for attempt in range(RETRIES):
        try:
            series = SOURCES[source](code, adjust, start, end)
            if not series.empty:
                series.index.name = "date"
                return series
            last_error = RuntimeError("empty response")
        except Exception as exc:  # noqa: BLE001 - retried, then re-raised below
            last_error = exc
        time.sleep(2 * (attempt + 1) ** 2)
    raise RuntimeError(
        f"{code} (adjust={adjust!r}, source={source}): no data after "
        f"{RETRIES} attempts ({last_error}). A connection closed with no "
        "response is this source's throttle, not a bad code — wait and resume, "
        "or try the other --source."
    )


def fetch_cached(code: str, adjust: str, source: str, cache_dir: Path,
                 start: str, end: str, refresh: bool) -> pd.Series:
    path = cache_dir / f"{source}_{code}_{adjust or 'raw'}.parquet"
    if path.exists() and not refresh:
        return pd.read_parquet(path)["close"]
    series = _fetch_one(code, adjust, source, start, end)
    path.parent.mkdir(parents=True, exist_ok=True)
    series.to_frame("close").to_parquet(path)
    time.sleep(PAUSE)
    return series


def build(codes: list[str], source: str, cache_dir: Path, start: str, end: str,
          refresh: bool, allow_missing: bool) -> tuple[pd.DataFrame, pd.DataFrame]:
    adjusted, unadjusted, missing = {}, {}, []
    for code in codes:
        try:
            hfq = fetch_cached(code, "hfq", source, cache_dir, start, end, refresh)
            raw = fetch_cached(code, "", source, cache_dir, start, end, refresh)
        except RuntimeError as exc:
            if not allow_missing:
                raise
            missing.append(code)
            print(f"  {code} {UNIVERSE.get(code, ''):24s} MISSING - {exc}")
            continue
        # Rescale so the adjusted series ends on the traded price. Returns are
        # unchanged; position sizing in tracking/ is not.
        adjusted[code] = hfq * (raw.iloc[-1] / hfq.iloc[-1])
        unadjusted[code] = raw
        print(f"  {code} {UNIVERSE.get(code, ''):24s} {len(hfq):5d} rows")

    if missing:
        print(f"\n{len(missing)} instrument(s) not carried by {source}: "
              f"{', '.join(missing)}")
    kept = [c for c in codes if c in adjusted]
    total_return = pd.DataFrame(adjusted)[kept].sort_index()
    price_return = pd.DataFrame(unadjusted)[kept].sort_index()
    for frame in (total_return, price_return):
        frame.index = pd.to_datetime(frame.index)
        frame.index.name = "date"
    return total_return.dropna(how="all"), price_return.dropna(how="all")


def verify(total_return: pd.DataFrame, price_return: pd.DataFrame) -> None:
    """Assert the adjustment behaves like an adjustment.

    Distributions only ever accumulate, so the adjusted/unadjusted ratio must
    be non-decreasing apart from share re-denominations. A source that started
    returning ``qfq`` under the ``hfq`` argument, or inverted the factor, would
    change every return in the table without changing anything visible about
    its shape. This is cheap and it fails loudly.
    """
    for code in total_return.columns:
        adjusted = total_return[code].dropna()
        raw = price_return[code].dropna()
        if adjusted.empty or raw.empty:
            raise RuntimeError(f"{code}: empty series")
        if adjusted.index[0] != raw.index[0]:
            raise RuntimeError(
                f"{code}: adjusted and unadjusted series start on different "
                f"days ({adjusted.index[0].date()} vs {raw.index[0].date()})")

        ratio = (adjusted / raw).dropna()
        step = (ratio / ratio.shift(1)).dropna()
        ordinary = step[(step - 1.0).abs() <= 0.25]
        if (ordinary < 0.995).any():
            worst = ordinary.idxmin()
            raise RuntimeError(
                f"{code}: adjustment factor falls by "
                f"{1 - ordinary.min():.2%} on {worst.date()} outside any "
                "re-denomination. A distribution cannot be negative, so the "
                "adjustment convention is not what this script assumes.")


def report(prices: pd.DataFrame) -> None:
    print(f"\n{len(prices.columns)} instruments, "
          f"{prices.index.min().date()} to {prices.index.max().date()}, "
          f"{len(prices)} rows\n")
    print(f"{'code':8s} {'first':12s} {'last':12s} {'rows':>6s} {'gaps':>6s}  name")
    for code in prices.columns:
        series = prices[code].dropna()
        span = prices.loc[series.index.min():series.index.max(), code]
        print(f"{code:8s} {series.index.min().date()!s:12s} "
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
    parser.add_argument("--source", choices=sorted(SOURCES), default="sina")
    parser.add_argument("--start", default=DEFAULT_START)
    parser.add_argument("--end", default=DEFAULT_END,
                        help="not a research cutoff — that lives in config.yaml "
                             "and is enforced by the loader.")
    parser.add_argument("--out", default="data/cache/prices_cn.parquet")
    parser.add_argument("--raw-out", default="data/cache/prices_cn_raw.parquet",
                        help="companion unadjusted table; qc_data_quality.py "
                             "needs it to measure the implied dividend yield")
    parser.add_argument("--cache-dir", default="data/cache/cn_by_instrument",
                        help="per-instrument files, so a throttled run resumes")
    parser.add_argument("--refresh", action="store_true",
                        help="re-download instruments already cached")
    parser.add_argument("--allow-missing", action="store_true",
                        help="drop instruments this source does not carry "
                             "instead of failing")
    args = parser.parse_args()

    total_return, price_return = build(
        list(UNIVERSE), args.source, Path(args.cache_dir), args.start, args.end,
        args.refresh, args.allow_missing)
    verify(total_return, price_return)
    report(total_return)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    total_return.to_parquet(out)
    print(f"\nwrote {out}")

    raw_out = Path(args.raw_out)
    price_return.to_parquet(raw_out)
    print(f"wrote {raw_out}")
    print("\nNext: PYTHONPATH=. python data/qc_data_quality.py --config config.cn.yaml")


if __name__ == "__main__":
    main()

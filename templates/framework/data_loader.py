"""Config and price loading, with the research cutoff enforced by assertion.

The one non-obvious thing in this file is ``load_prices(research=True)``. It
truncates the price table at ``research_end`` and then asserts the truncation
held. See the docstring there for why an assertion and not a convention.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd
import yaml

DEFAULT_CONFIG_NAMES = ("config.yaml", "config.yml", "config.example.yaml")


@dataclass(frozen=True)
class ResearchConfig:
    """Parsed config plus the directory it was loaded from.

    Relative paths in the config resolve against ``root``, so a project can be
    checked out anywhere and tests can build a throwaway config in a tmpdir.
    """

    raw: Dict[str, Any]
    root: Path

    def __getitem__(self, key: str) -> Any:
        return self.raw[key]

    def get(self, key: str, default: Any = None) -> Any:
        return self.raw.get(key, default)

    def path(self, *parts: str) -> Path:
        return self.root.joinpath(*parts)


def find_config(start: Path | None = None) -> Path:
    """Walk up from ``start`` looking for a config file."""
    here = (start or Path.cwd()).resolve()
    for directory in [here, *here.parents]:
        for name in DEFAULT_CONFIG_NAMES:
            candidate = directory / name
            if candidate.exists():
                return candidate
    raise FileNotFoundError(
        f"no {' / '.join(DEFAULT_CONFIG_NAMES)} found at or above {here}"
    )


def load_config(path: str | Path | None = None) -> ResearchConfig:
    p = Path(path) if path is not None else find_config()
    p = p.resolve()
    if not p.exists():
        raise FileNotFoundError(f"config not found: {p}")
    raw = yaml.safe_load(p.read_text()) or {}
    return ResearchConfig(raw=raw, root=p.parent)


def _read_table(path: Path) -> pd.DataFrame:
    if path.suffix == ".parquet":
        df = pd.read_parquet(path)
    elif path.suffix in (".csv", ".txt"):
        df = pd.read_csv(path, index_col=0)
    else:
        raise ValueError(f"unsupported price file format: {path.suffix}")
    df.index = pd.to_datetime(df.index)
    return df.sort_index()


def load_prices(
    cfg: ResearchConfig,
    research: bool = True,
    filename: str | None = None,
) -> pd.DataFrame:
    """Load the wide price table (index = date, columns = instruments).

    Values must be total-return adjusted: the series you would get by holding
    one unit and reinvesting every distribution. Raw last-traded prices make
    every dividend look like a drawdown.

    ============================ THE IMPORTANT PART ============================
    ``research=True`` truncates at ``research_end`` and then asserts that the
    truncation actually happened.

    WHY THIS EXISTS: "we simply won't look at recent data" is not a control.
    Every path from raw data to a reported number has to be blocked mechanically,
    because the leak is rarely a deliberate peek. It is a helper that resamples
    the full history, a benchmark series loaded from a different function, a
    normalization computed over the whole sample. We audited a set of results
    that were labelled out-of-sample and found the current year had been fully
    visible during every experiment that produced them; the numbers were not
    wrong, but they were not evidence of anything either.

    The assertion is redundant with the ``.loc`` on the line above it, and that
    is the point. It is there to fail loudly if someone later "optimizes" the
    truncation away, or if a caller passes a pre-loaded frame.

    ``research=False`` is legitimate in exactly one place: generating today's
    live signal in tracking/. If you find yourself passing it anywhere under
    framework/ or in an experiment script, that is the bug.
    ============================================================================
    """
    data_cfg = cfg.get("data", {}) or {}
    cache_dir = cfg.path(data_cfg.get("cache_dir", "data/cache"))
    name = filename or data_cfg.get("price_file", "prices.parquet")
    path = cache_dir / name
    if not path.exists():
        raise FileNotFoundError(
            f"price file not found: {path}\n"
            "Fetch it first (see data/ for your own download script)."
        )

    df = _read_table(path)
    if research:
        end = pd.Timestamp(cfg["research_end"])
        df = df.loc[:end]
        assert df.index.max() <= end, (
            f"research-mode leak: data after research_end ({end.date()}) "
            f"reached a backtest (max index = {df.index.max()})"
        )
    return df


def load_benchmark(cfg: ResearchConfig, research: bool = True) -> pd.Series:
    prices = load_prices(cfg, research=research)
    code = cfg["benchmark"]["primary"]
    if code not in prices.columns:
        raise KeyError(f"benchmark {code!r} is not a column of the price table")
    return prices[code].dropna()


def universe_meta(cfg: ResearchConfig) -> Dict[str, dict]:
    return {str(e["code"]): e for e in cfg.get("universe", [])}


def holdable_codes(cfg: ResearchConfig) -> List[str]:
    """Instruments a strategy is allowed to hold.

    Entries with ``holdable: false`` are still loaded, because a series can be
    useful as a signal without being investable — a bond index used only as a
    risk-on/risk-off canary, or an instrument the account cannot access.
    """
    return [
        str(e["code"]) for e in cfg.get("universe", []) if e.get("holdable", True)
    ]


def assert_no_lookahead(df: pd.DataFrame, asof: pd.Timestamp) -> None:
    """Guard for strategy code that slices data itself.

    Call this at the top of any helper that receives a frame plus a decision
    date. The engine already truncates before calling a strategy, so this is a
    second line of defense for research scripts that bypass the engine.
    """
    if len(df.index) and df.index.max() >= pd.Timestamp(asof):
        raise AssertionError(
            f"look-ahead: frame contains {df.index.max()} while deciding for {asof}"
        )

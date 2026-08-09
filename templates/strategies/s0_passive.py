"""S0: the passive baseline. The control group every experiment is scored against.

WHY THIS IS THE FIRST FILE YOU SHOULD WRITE, before any signal:

An active strategy's headline return is meaningless on its own. The only
question that matters is what it adds over doing nothing intelligent, and
"nothing intelligent" is not cash and it is not a single index. It is a fixed
diversified basket, rebalanced on a schedule, with the same costs and the same
execution assumptions as the strategy under test. That is a genuinely hard
baseline: a passive multi-asset blend at the same cost drag beats a large
share of active rotation ideas after costs, and several strategies that "beat
the index" turn out to only be beating a much weaker baseline than the
passive blend.

Two honesty notes about this baseline that are easy to skip:

* The basket itself is a choice, and if you picked its members by knowing
  which assets did well, the baseline is already contaminated. If yours was,
  that makes the baseline harder to beat rather than easier — which is the
  safe direction, but it means "we beat the passive basket by X" understates
  how much of X came from selecting that basket in hindsight.
* Rebalancing back to fixed weights is itself an active decision (it sells
  winners). Compare against a buy-and-hold, never-rebalanced version too if
  your strategy's edge might just be the rebalancing premium.

The weights come from ``benchmark.passive_blend`` in the config. Nothing about
this file is market-specific; edit the config, not the code.
"""
from __future__ import annotations

from typing import Dict, Mapping

import pandas as pd

# Minimum observations before an instrument is considered investable. Prevents
# a newly listed asset from entering the basket on two days of history.
MIN_HISTORY = 20


class Strategy:
    """Fixed-weight basket, renormalized over whatever currently has data.

    Args:
        config: a ``ResearchConfig`` from ``framework.data_loader.load_config``.
        weights: optional explicit ``{code: weight}``, overriding the config.
                 Mainly for tests.

    Extra keyword arguments (such as ``top_n``) are accepted and ignored so
    that the same runner can drive this baseline and a ranking strategy.
    """

    def __init__(self, config=None, weights: Mapping[str, float] | None = None, **_):
        if weights is not None:
            self.blend: Dict[str, float] = {str(k): float(v) for k, v in weights.items()}
        elif config is not None:
            blend = config["benchmark"]["passive_blend"]
            self.blend = {str(e["code"]): float(e["weight"]) for e in blend}
        else:
            raise ValueError("s0_passive needs either a config or explicit weights")

    def target_weights(
        self, prices: pd.DataFrame, asof: pd.Timestamp
    ) -> Dict[str, float]:
        available = {
            code: weight
            for code, weight in self.blend.items()
            if code in prices.columns and prices[code].notna().sum() >= MIN_HISTORY
        }
        total = sum(available.values())
        if total <= 0:
            return {}
        return {code: weight / total for code, weight in available.items()}

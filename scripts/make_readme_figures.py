#!/usr/bin/env python3
"""Generate the research-loop illustration used in the README.

The figure is conceptual, not measured. It exists to explain a claim in
prose, not to report a result — every axis is unitless and the caption says
so explicitly. This is the line that keeps it out of `social/`: a figure
with no numbers on it cannot misrepresent a backtest, because it is not
reporting one.

The other README illustration (the AI-coding-tool vs. quant-agent
comparison) is a hand-drawn image, generated once and committed directly
to `docs/assets/tool-style-comparison.jpg` — there is nothing to regenerate.

Run:
    python3 scripts/make_readme_figures.py
"""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "assets"

NAVY = "#1f3a5f"
GRAY = "#8a8a8a"
LIGHT_GRAY = "#c9c9c9"
INK = "#2b2b2b"

ZH_FONT = ["PingFang HK", "Heiti TC", "STHeiti", "Arial Unicode MS", "DejaVu Sans"]
EN_FONT = ["Helvetica", "Arial", "DejaVu Sans"]


def _style(lang: str) -> None:
    plt.rcdefaults()
    plt.rcParams["font.sans-serif"] = ZH_FONT if lang == "zh" else EN_FONT
    plt.rcParams["axes.unicode_minus"] = False
    plt.rcParams["font.size"] = 11
    plt.rcParams["axes.edgecolor"] = INK
    plt.rcParams["text.color"] = INK
    plt.rcParams["axes.labelcolor"] = INK
    plt.rcParams["xtick.color"] = INK
    plt.rcParams["ytick.color"] = INK


def make_research_loop(lang: str) -> None:
    _style(lang)
    txt = {
        "zh": dict(
            panel_a="(a) 研究过程中需要你参与的次数",
            a_adhoc="没有方法论",
            a_this="autoquant-research",
            a_dot_goal="目标",
            a_dot_fork="关键分岔",
            panel_b="(b) 上线之后，表现是否还站得住",
            b_xlabel="时间  →",
            b_ylabel="净值（示意）",
            b_golive="上线",
            b_adhoc="没有方法论",
            b_this="autoquant-research",
            note="两张图都是示意，不是任何真实策略的回测或实盘数据。",
        ),
        "en": dict(
            panel_a="(a) Times you're asked to weigh in during research",
            a_adhoc="Ad hoc",
            a_this="autoquant-research",
            a_dot_goal="goal",
            a_dot_fork="real fork",
            panel_b="(b) Does the result hold up after going live",
            b_xlabel="time  ->",
            b_ylabel="equity (illustrative)",
            b_golive="go live",
            b_adhoc="Ad hoc",
            b_this="autoquant-research",
            note="Both panels are illustrative — not a backtest or live result for any real strategy.",
        ),
    }[lang]

    fig, (axa, axb) = plt.subplots(2, 1, figsize=(8.4, 6.8), dpi=200, height_ratios=[1, 2])
    fig.subplots_adjust(left=0.23, right=0.86, top=0.94, bottom=0.10, hspace=0.6)

    # Panel (a): interaction touchpoints as a dot-strip timeline
    axa.set_title(txt["panel_a"], fontsize=11, loc="left", color=INK)
    axa.set_xlim(0, 1)
    axa.set_ylim(-0.6, 1.6)
    for s in axa.spines.values():
        s.set_visible(False)
    axa.set_yticks([1, 0])
    axa.set_yticklabels([txt["a_adhoc"], txt["a_this"]], fontsize=10)
    axa.set_xticks([])
    axa.axhline(1, color=LIGHT_GRAY, linewidth=1, zorder=1)
    axa.axhline(0, color=LIGHT_GRAY, linewidth=1, zorder=1)

    adhoc_touchpoints = [0.05, 0.16, 0.24, 0.33, 0.41, 0.5, 0.58, 0.66, 0.74, 0.83, 0.91]
    axa.scatter(adhoc_touchpoints, [1] * len(adhoc_touchpoints), s=55, color=GRAY, zorder=3)

    axa.scatter([0.05], [0], s=70, color=NAVY, zorder=3)
    axa.annotate(txt["a_dot_goal"], (0.05, 0), xytext=(0.05, 0.42), fontsize=8.6, color=NAVY, ha="center")
    axa.scatter([0.93], [0], s=70, color=NAVY, zorder=3, marker="D")
    axa.annotate(txt["a_dot_fork"], (0.93, 0), xytext=(0.93, 0.42), fontsize=8.6, color=NAVY, ha="center")

    # Panel (b): illustrative equity-style curves, no numeric axis
    axb.set_xlim(0, 1.24)
    axb.set_ylim(0, 1)
    for side in ("top", "right"):
        axb.spines[side].set_visible(False)
    axb.set_xticks([])
    axb.set_yticks([])
    axb.set_title(txt["panel_b"], fontsize=11, loc="left", color=INK)
    axb.set_xlabel(txt["b_xlabel"], loc="left", fontsize=10)
    axb.set_ylabel(txt["b_ylabel"], loc="bottom", fontsize=10)

    golive_x = 0.55
    axb.axvline(golive_x, color=LIGHT_GRAY, linewidth=1.4, linestyle=(0, (4, 3)))
    axb.text(golive_x, 0.035, txt["b_golive"], fontsize=9, color=GRAY, ha="center", va="bottom")

    import numpy as np

    x = np.linspace(0, 1, 300)
    rng = np.random.default_rng(7)

    x_pre = x[x <= golive_x]
    x_post = x[x > golive_x]

    adhoc_pre = 0.28 + 0.55 * (x_pre / golive_x) + 0.05 * np.sin(x_pre * 40) * (x_pre / golive_x)
    adhoc_post_t = (x_post - golive_x) / (1 - golive_x)
    adhoc_post = adhoc_pre[-1] * (1 - 0.9 * adhoc_post_t**1.3) + 0.02 * np.sin(adhoc_post_t * 30)
    axb.plot(x_pre, adhoc_pre, color=GRAY, linewidth=1.8)
    axb.plot(x_post, adhoc_post, color=GRAY, linewidth=1.8, linestyle=(0, (5, 2)))

    this_pre = 0.25 + 0.42 * (x_pre / golive_x) ** 1.05
    this_post_t = (x_post - golive_x) / (1 - golive_x)
    this_post = this_pre[-1] + 0.30 * this_post_t + 0.02 * np.sin(this_post_t * 12)
    axb.plot(x_pre, this_pre, color=NAVY, linewidth=2.2)
    axb.plot(x_post, this_post, color=NAVY, linewidth=2.2)

    axb.text(x_post[-1] + 0.015, adhoc_post[-1], txt["b_adhoc"], color=GRAY, fontsize=9.5, va="center")
    axb.text(x_post[-1] + 0.015, this_post[-1], txt["b_this"], color=NAVY, fontsize=9.5, va="center", fontweight="bold")

    fig.text(0.5, 0.015, txt["note"], fontsize=8.8, color=GRAY, ha="center")

    fig.savefig(OUT / f"research-loop.{lang}.png", facecolor="white")
    plt.close(fig)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for lang in ("zh", "en"):
        make_research_loop(lang)
    print(f"wrote figures to {OUT}")


if __name__ == "__main__":
    main()

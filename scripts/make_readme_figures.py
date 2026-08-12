#!/usr/bin/env python3
"""Generate the two illustrative figures used in the README.

Both figures are conceptual, not measured. They exist to explain a claim
in prose, not to report a result — every axis is unitless and every caption
says so explicitly. This is the line that keeps them out of `social/`: a
figure with no numbers on it cannot misrepresent a backtest, because it is
not reporting one.

Run:
    python3 scripts/make_readme_figures.py
"""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch

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


def make_comparison_quadrant(lang: str) -> None:
    _style(lang)
    txt = {
        "zh": dict(
            xlabel="研究方法论的严谨程度  →",
            ylabel="能否持续受益于更强的通用 agent  →",
            p1="编码检查类工具\n(静态分析 / 未来函数扫描)",
            p2="自动交易 agent 产品\n(封闭的交易机器人)",
            p3="autoquant-research",
            caption="示意图：三类工具在两个维度上的相对位置，不是精确测量。",
        ),
        "en": dict(
            xlabel="Rigor of the research methodology  ->",
            ylabel="Benefits from a stronger general agent  ->",
            p1="Code-checking tools\n(static analysis, look-ahead scanners)",
            p2="Trading agent products\n(closed automated bots)",
            p3="autoquant-research",
            caption="Illustrative positioning, not a precise measurement.",
        ),
    }[lang]

    fig, ax = plt.subplots(figsize=(7.2, 5.4), dpi=200)
    fig.subplots_adjust(left=0.09, right=0.97, top=0.93, bottom=0.16)

    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    ax.spines["left"].set_position(("data", 0))
    ax.spines["bottom"].set_position(("data", 0))
    ax.set_xticks([])
    ax.set_yticks([])

    ax.add_patch(
        FancyArrowPatch((0, 0), (1.02, 0), arrowstyle="-|>", mutation_scale=14, color=INK, linewidth=1.1)
    )
    ax.add_patch(
        FancyArrowPatch((0, 0), (0, 1.02), arrowstyle="-|>", mutation_scale=14, color=INK, linewidth=1.1)
    )
    ax.set_xlabel(txt["xlabel"], loc="left", fontsize=10.5)
    ax.set_ylabel(txt["ylabel"], loc="bottom", fontsize=10.5)

    ax.scatter([0.20], [0.14], s=90, color=GRAY, zorder=3)
    ax.annotate(
        txt["p1"], (0.20, 0.14), xytext=(0.23, 0.08), fontsize=9.6, color=INK, ha="left", va="top"
    )

    ax.scatter([0.32], [0.30], s=90, color=GRAY, zorder=3)
    ax.annotate(
        txt["p2"], (0.32, 0.30), xytext=(0.37, 0.37), fontsize=9.6, color=INK, ha="left", va="bottom"
    )

    ax.scatter([0.84], [0.82], s=140, color=NAVY, zorder=4, edgecolor="white", linewidth=1.2)
    ax.annotate(
        txt["p3"], (0.84, 0.82), xytext=(0.84, 0.90), fontsize=11, color=NAVY, ha="center", va="bottom", fontweight="bold"
    )

    ax.text(
        0.5, -0.145, txt["caption"], transform=ax.transAxes, fontsize=9, color=GRAY, ha="center", va="top"
    )

    fig.savefig(OUT / f"comparison-quadrant.{lang}.png", facecolor="white")
    plt.close(fig)


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
        make_comparison_quadrant(lang)
        make_research_loop(lang)
    print(f"wrote figures to {OUT}")


if __name__ == "__main__":
    main()

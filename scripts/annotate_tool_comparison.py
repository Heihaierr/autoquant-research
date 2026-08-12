#!/usr/bin/env python3
"""Overlay crisp text labels onto the hand-drawn tool-comparison illustration.

The illustration itself was generated once by an image model and committed
as a source file — no amount of prompting gets legible baked-in text out of
that pipeline reliably, so text is added here instead, with a real font, in
a real layout engine. This script is deterministic and re-runnable; the
illustration underneath it is not regenerated.

Run:
    python3 scripts/annotate_tool_comparison.py
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
SOURCE = Path(
    "/Users/heihaier/.cursor/projects/"
    "Users-heihaier-Desktop-workspace-quat-learning-202608/assets/"
    "tool-style-comparison.png"
)
OUT = ROOT / "docs" / "assets"

CREAM = (236, 217, 184)
INK = (58, 48, 36)
INK_SOFT = (96, 84, 68)

ZH_BOLD = "/System/Library/Fonts/STHeiti Medium.ttc"
ZH_BOLD_INDEX = 1  # Heiti SC
EN_BOLD = "/System/Library/Fonts/Helvetica.ttc"


def _font(lang: str, size: int, bold: bool) -> ImageFont.FreeTypeFont:
    if lang == "zh":
        return ImageFont.truetype(ZH_BOLD, size, index=ZH_BOLD_INDEX)
    path = EN_BOLD if bold else "/System/Library/Fonts/HelveticaNeue.ttc"
    try:
        return ImageFont.truetype(path, size)
    except OSError:
        return ImageFont.truetype(EN_BOLD, size)


def _centered_text(draw, cx, y, text, font, fill):
    bbox = draw.textbbox((0, 0), text, font=font)
    w = bbox[2] - bbox[0]
    draw.text((cx - w / 2, y), text, font=font, fill=fill)


def _bullets(draw, x, y, lines, font, fill, line_gap=12):
    for line in lines:
        draw.text((x, y), f"\u2022  {line}", font=font, fill=fill)
        bbox = draw.textbbox((0, 0), line, font=font)
        y += (bbox[3] - bbox[1]) + line_gap
    return y


def build(lang: str) -> None:
    text = {
        "zh": dict(
            left_title="AI coding 工具",
            right_title="quant agent 产品",
            left_bullets=["逐行核对代码，抓未来函数、漏算成本", "数字算对了，结论对不对看不出来"],
            right_bullets=["一套封闭的自动化执行链", "底层 agent 变强，它不会跟着变强"],
        ),
        "en": dict(
            left_title="AI coding tool",
            right_title="quant trading agent",
            left_bullets=["Checks code line by line for bugs, uncosted turnover", "Right numbers, wrong conclusion — invisible to it"],
            right_bullets=["A closed, fixed automation pipeline", "Doesn't get smarter as the underlying agent does"],
        ),
    }[lang]

    art = Image.open(SOURCE).convert("RGB")
    w, h = art.size

    top_band, bottom_band = 100, 190
    canvas = Image.new("RGB", (w, h + top_band + bottom_band), CREAM)
    canvas.paste(art, (0, top_band))
    draw = ImageDraw.Draw(canvas)

    title_font = _font(lang, 40, bold=True)
    bullet_font = _font(lang, 26, bold=False)

    _centered_text(draw, w * 0.25, 28, text["left_title"], title_font, INK)
    _centered_text(draw, w * 0.75, 28, text["right_title"], title_font, INK)

    draw.line([(w // 2, top_band + 20), (w // 2, h + top_band - 20)], fill=(200, 182, 152), width=2)

    bullets_y = top_band + h + 26
    _bullets(draw, w * 0.045, bullets_y, text["left_bullets"], bullet_font, INK_SOFT)
    _bullets(draw, w * 0.52, bullets_y, text["right_bullets"], bullet_font, INK_SOFT)

    out_path = OUT / f"tool-style-comparison.{lang}.jpg"
    canvas.save(out_path, quality=88)
    print(f"wrote {out_path}")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for lang in ("zh", "en"):
        build(lang)


if __name__ == "__main__":
    main()

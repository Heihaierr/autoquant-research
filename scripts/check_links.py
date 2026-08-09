#!/usr/bin/env python3
"""Verify every internal Markdown link resolves to a real file and anchor.

Broken cross-references are the most common rot in a documentation-heavy
repository, and they are invisible until a reader follows one. This runs in
CI and on pre-commit.
"""
from __future__ import annotations

import re
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# [text](target) where target is not an external URL, mailto, or bare image
LINK = re.compile(r"\[([^\]]*)\]\(([^)]+)\)")
HEADING = re.compile(r"^(#{1,6})\s+(.*?)\s*#*$", re.MULTILINE)
EXTERNAL = ("http://", "https://", "mailto:", "#L")


def slugify(heading: str) -> str:
    """Reproduce GitHub's heading-to-anchor transformation.

    GitHub lowercases, strips anything that is not alphanumeric/space/hyphen
    (after removing inline formatting), then replaces spaces with hyphens.
    """
    text = heading.strip()                               # the parser trims first
    text = re.sub(r"`([^`]*)`", r"\1", text)             # inline code
    text = re.sub(r"\*\*([^*]*)\*\*", r"\1", text)        # bold
    text = re.sub(r"\*([^*]*)\*", r"\1", text)            # italic
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)  # nested links
    text = unicodedata.normalize("NFKC", text).lower()
    text = re.sub(r"[^\w\s\u4e00-\u9fff-]", "", text)
    # Two properties that are easy to get wrong, and wrong in opposite ways:
    #
    # One hyphen per space, not per run. "a & b" drops the "&" and keeps both
    # spaces, giving "a--b". Collapsing runs here breaks any anchor with
    # punctuation between words.
    #
    # No trailing trim. A heading ending in a symbol ("SD-02 ★") loses the
    # symbol but keeps the space before it, so the real anchor is "sd-02-".
    # Trimming here makes this checker self-consistent and wrong: it computes
    # "sd-02", matches a "#sd-02" link, and reports a link that is dead on
    # GitHub as healthy.
    return text.replace(" ", "-")


def anchors_of(path: Path) -> set[str]:
    if not path.is_file():
        return set()
    body = path.read_text(encoding="utf-8")
    seen: dict[str, int] = {}
    out: set[str] = set()
    for _, heading in HEADING.findall(body):
        slug = slugify(heading)
        if not slug:
            continue
        # GitHub disambiguates repeats with -1, -2, ...
        n = seen.get(slug, 0)
        out.add(slug if n == 0 else f"{slug}-{n}")
        seen[slug] = n + 1
    return out


def main() -> int:
    anchor_cache: dict[Path, set[str]] = {}
    problems: list[str] = []
    checked = 0

    files = sorted(
        p for p in ROOT.rglob("*.md")
        if not any(part.startswith(".") or part == "node_modules" for part in p.parts)
    )

    for src in files:
        body = src.read_text(encoding="utf-8")
        for text, target in LINK.findall(body):
            target = target.strip()
            if target.startswith(EXTERNAL) or target.startswith("<"):
                continue

            file_part, _, anchor = target.partition("#")
            checked += 1

            if file_part:
                dest = (src.parent / file_part).resolve()
                if not dest.exists():
                    problems.append(
                        f"{src.relative_to(ROOT)}: missing file '{file_part}' "
                        f"(link text: {text[:40]!r})"
                    )
                    continue
            else:
                dest = src

            if anchor:
                if dest not in anchor_cache:
                    anchor_cache[dest] = anchors_of(dest)
                if anchor not in anchor_cache[dest]:
                    rel = dest.relative_to(ROOT) if ROOT in dest.parents else dest
                    problems.append(
                        f"{src.relative_to(ROOT)}: anchor '#{anchor}' not found "
                        f"in {rel} (link text: {text[:40]!r})"
                    )

    print(f"checked {checked} internal links across {len(files)} files")
    if problems:
        print(f"\n{len(problems)} broken:\n")
        for p in problems:
            print(f"  {p}")
        return 1
    print("all internal links resolve")
    return 0


if __name__ == "__main__":
    sys.exit(main())

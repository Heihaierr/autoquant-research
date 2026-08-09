#!/usr/bin/env python3
"""Verify that counts claimed in prose match the entries that actually exist.

A repository about not fooling yourself with numbers cannot ship prose that
claims a skill count different from the number of skill directories that
actually exist. This check exists because that class of drift is easy to
produce by accident: a count is written once, a skill is later merged, split,
or renamed, and every other document repeating the old number goes stale
silently.

The failure mode is specific and worth naming — a claim made once and copied
into N places is not N pieces of evidence, it is one unverified assertion with
N mirrors. So the count is derived from the source of truth here, and every
mirror is checked against it.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# (source file, entry pattern, human-readable name, [patterns that quote a count])
REGISTRY = [
    (
        "skills",
        None,  # counted as directories containing a SKILL.md
        "skills",
        [
            r"(\d+) skills\b",
            r"\*\*(\d+) 个 skill\*\*",
        ],
    ),
]


# The patterns above are a whitelist of phrasings, so a new way of writing the
# same claim slips through silently — which is exactly how "25 entries" sat next
# to a 26-entry file while this script reported every count consistent. This
# matches the shape of a count instead of its wording, and only fires on lines
# that also name the file being counted, which keeps it off unrelated tallies.
#
# The "%" exclusion matters for a reason that looks unrelated at first: a
# shields.io badge URL like "documented%20failures-32-red" contains the literal
# substring "20failures" from percent-encoding a space, and without this
# exclusion the shape match fires on that "20" instead of the real "32".
COUNT_SHAPE = re.compile(
    r"(?<![\w.%])(\d+)\s*"
    r"(?:entries|entry|exhibits|cases|failures|patterns|traps|条|个)"
)


def loose_count_claims(
    md_files: list[Path], source: str, truth: int, label: str,
    already_flagged: set[tuple[str, int]],
) -> list[str]:
    """Catch count claims whose phrasing the whitelist does not anticipate."""
    if "/" not in source:  # a directory, with no filename to anchor on
        return []
    stem = Path(source).name
    found: list[str] = []
    for path in md_files:
        for lineno, line in enumerate(
            path.read_text(encoding="utf-8").splitlines(), 1
        ):
            if stem not in line:
                continue
            rel = str(path.relative_to(ROOT))
            if (rel, lineno) in already_flagged:
                continue
            for match in COUNT_SHAPE.finditer(line):
                claimed = int(match.group(1))
                if claimed != truth:
                    found.append(
                        f"{rel}:{lineno}: claims {claimed} {label}, found {truth} "
                        f"in {source} (matched {match.group(0)!r})"
                    )
    return found


def actual_count(source: str, pattern: str | None) -> int:
    if pattern is None:
        return len(list((ROOT / source).glob("*/SKILL.md")))
    text = (ROOT / source).read_text(encoding="utf-8")
    return len(re.findall(pattern, text, flags=re.M))


def main() -> int:
    # Plugin manifests carry the description shown in a marketplace listing, which
    # is the most public place a count appears and was the last place checked.
    md_files = [
        p
        for p in ROOT.rglob("*")
        if p.suffix in {".md", ".json"}
        and p.is_file()
        and ".git" not in p.parts
        and "node_modules" not in p.parts
    ]

    problems: list[str] = []
    for source, pattern, label, claim_patterns in REGISTRY:
        truth = actual_count(source, pattern)
        checked = 0
        seen: set[tuple[str, int]] = set()
        for path in md_files:
            text = path.read_text(encoding="utf-8")
            for claim_pattern in claim_patterns:
                for match in re.finditer(claim_pattern, text):
                    checked += 1
                    claimed = int(match.group(1))
                    line = text[: match.start()].count("\n") + 1
                    seen.add((str(path.relative_to(ROOT)), line))
                    if claimed != truth:
                        problems.append(
                            f"{path.relative_to(ROOT)}:{line}: claims {claimed} "
                            f"{label}, found {truth} in {source} "
                            f"(matched {match.group(0)!r})"
                        )
        loose = loose_count_claims(md_files, source, truth, label, seen)
        problems.extend(loose)
        print(f"{label}: {truth} actual, {checked} claim(s) checked"
              + (f", {len(loose)} caught by shape" if loose else ""))

    if problems:
        print(f"\n{len(problems)} inconsistent:\n")
        for problem in problems:
            print(f"  {problem}")
        return 1

    print("\nall claimed counts match reality")
    return 0


if __name__ == "__main__":
    sys.exit(main())

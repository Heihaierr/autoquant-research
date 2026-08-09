#!/usr/bin/env python3
"""Validate skill files against the conventions in CONTRIBUTING.md.

A skill with a vague description never fires, and a skill without an Iron Law
reads as advice rather than process. Both failures are silent, so they get
checked here instead of in review.
"""
from __future__ import annotations

import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
SKILLS = ROOT / "skills"

# Triggers live in the frontmatter description, which is the only text an agent
# reads when deciding whether to load a skill — so a "## When to Use" section
# duplicated it in a place nothing consults. "## Handoff" is required in its
# place: it names the deliverables and the next skill, which is what lets the
# loop advance without stopping to ask.
REQUIRED_SECTIONS = ["## Overview", "## The Iron Law", "## Handoff"]
EXPECTED_SECTIONS = ["## Common rationalizations", "## Related"]
# The entry-point skill dispatches rather than executes, so it has neither a
# rationalization table of its own nor a single successor to point at.
EXEMPT_FROM_EXPECTED = {"using-autoquant"}

# Skills exempt from the section contract. The refactor that populated this set
# is finished: every skill is on the current layout, so nothing belongs here.
# Anything added back is a temporary waiver and should say why and until when.
LEGACY: set[str] = set()


def main() -> int:
    problems: list[str] = []
    warnings: list[str] = []
    names: set[str] = set()

    skill_files = sorted(SKILLS.glob("*/SKILL.md"))
    if not skill_files:
        print("no skills found", file=sys.stderr)
        return 1

    for path in skill_files:
        directory = path.parent.name
        body = path.read_text(encoding="utf-8")
        rel = path.relative_to(ROOT)

        if not body.startswith("---\n"):
            problems.append(f"{rel}: missing YAML frontmatter")
            continue

        _, _, rest = body.partition("---\n")
        raw, sep, content = rest.partition("\n---\n")
        if not sep:
            problems.append(f"{rel}: frontmatter is not terminated")
            continue

        try:
            meta = yaml.safe_load(raw) or {}
        except yaml.YAMLError as exc:
            problems.append(f"{rel}: frontmatter is not valid YAML ({exc})")
            continue

        name = meta.get("name")
        if not name:
            problems.append(f"{rel}: frontmatter has no 'name'")
        elif name != directory:
            problems.append(f"{rel}: name '{name}' does not match directory '{directory}'")
        elif name in names:
            problems.append(f"{rel}: duplicate skill name '{name}'")
        else:
            names.add(name)

        desc = (meta.get("description") or "").strip()
        if not desc:
            problems.append(f"{rel}: frontmatter has no 'description'")
        else:
            # The description is the only thing an agent sees when deciding
            # whether to load the skill. It has to state triggers.
            if len(desc) < 40:
                problems.append(f"{rel}: description too short to convey triggers ({len(desc)} chars)")
            if not desc.lower().startswith("use "):
                warnings.append(f"{rel}: description should start with 'Use when/at/...'")

        if directory in LEGACY:
            continue

        for section in REQUIRED_SECTIONS:
            if section not in content:
                problems.append(f"{rel}: missing required section '{section}'")

        if directory not in EXEMPT_FROM_EXPECTED:
            lowered = content.lower()
            for section in EXPECTED_SECTIONS:
                if section.lower() not in lowered:
                    warnings.append(f"{rel}: missing '{section}'")

        # An Iron Law that isn't in a fenced block reads as prose and gets skimmed
        law_at = content.find("## The Iron Law")
        if law_at != -1 and "```" not in content[law_at:law_at + 400]:
            warnings.append(f"{rel}: Iron Law should be in a fenced code block")

    waived = [p for p in skill_files if p.parent.name in LEGACY]
    summary = f"checked {len(skill_files)} skills"
    if waived:
        summary += f" — {len(waived)} waived from the section contract"
    print(summary)

    if warnings:
        print(f"\n{len(warnings)} warnings:")
        for w in warnings:
            print(f"  {w}")

    if problems:
        print(f"\n{len(problems)} problems:")
        for p in problems:
            print(f"  {p}")
        return 1

    print("all skills well-formed")
    return 0


if __name__ == "__main__":
    sys.exit(main())

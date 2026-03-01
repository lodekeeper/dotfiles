#!/usr/bin/env python3
"""Generate rich entity pages from bank/state.json active entries.

Entity types generated:
- people (nico + @mentions) — role, preferences, communication style, recent interactions
- projects (lodestar/openclaw/ethereum + eip subjects) — status, key facts, decisions, lessons
- prs (subject pr:<num>) — status, key changes, review feedback
"""
from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

WORKSPACE = Path(__file__).resolve().parents[2]
STATE_PATH = WORKSPACE / "bank" / "state.json"
ENT_DIR = WORKSPACE / "bank" / "entities"

PR_SUBJECT_RE = re.compile(r"^pr:(\d+)$")
EIP_SUBJECT_RE = re.compile(r"^eip:(\d+)$")
MENTION_RE = re.compile(r"@([A-Za-z0-9_-]+)")


def load_entries() -> list[dict[str, Any]]:
    if not STATE_PATH.exists():
        return []
    data = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    entries = data.get("entries", [])
    return [e for e in entries if e.get("status") == "active" and e.get("text")]


def by_importance(entries: list[dict[str, Any]], n: int = 20) -> list[dict[str, Any]]:
    return sorted(entries, key=lambda e: (e.get("importance", 0), e.get("valid_from", "")), reverse=True)[:n]


def fmt_bullet(e: dict[str, Any]) -> str:
    date = str(e.get("valid_from", ""))[:10]
    imp = float(e.get("importance", 0))
    subj = e.get("subject", "")
    src = f"{e.get('source_path')}:{e.get('source_line')}" if e.get("source_path") else ""
    return f"- ({date} | imp={imp:.2f} | {subj}) {e.get('text')} [{src}]"


def section_by_kind(entries: list[dict[str, Any]], kinds: list[str], max_per: int = 8) -> str:
    """Group entries by kind and render as sections."""
    lines: list[str] = []
    for kind in kinds:
        items = [e for e in entries if e.get("kind") == kind]
        if not items:
            continue
        items = by_importance(items, max_per)
        label = kind.capitalize() + "s" if not kind.endswith("s") else kind.capitalize()
        lines.append(f"\n### {label}\n")
        for e in items:
            lines.append(fmt_bullet(e))
    return "\n".join(lines)


def render_person_page(name: str, entries: list[dict[str, Any]]) -> str:
    """Rich person page with sections."""
    lines = [f"# {name.capitalize()}\n"]

    # Extract preferences
    prefs = [e for e in entries if e.get("kind") == "preference"]
    decisions = [e for e in entries if e.get("kind") == "decision"]
    facts = [e for e in entries if e.get("kind") == "fact"]
    lessons = [e for e in entries if e.get("kind") == "lesson"]

    if prefs:
        lines.append("\n## Preferences & Communication Style\n")
        for e in by_importance(prefs, 8):
            lines.append(fmt_bullet(e))

    if decisions:
        lines.append("\n## Key Decisions & Rules\n")
        for e in by_importance(decisions, 10):
            lines.append(fmt_bullet(e))

    if facts:
        lines.append("\n## Facts\n")
        for e in by_importance(facts, 8):
            lines.append(fmt_bullet(e))

    if lessons:
        lines.append("\n## Lessons Learned (involving this person)\n")
        for e in by_importance(lessons, 6):
            lines.append(fmt_bullet(e))

    if not any([prefs, decisions, facts, lessons]):
        lines.append("\n- (no structured memories yet)\n")

    return "\n".join(lines) + "\n"


def render_project_page(name: str, entries: list[dict[str, Any]]) -> str:
    """Rich project page with grouped sections."""
    title = name.upper() if name.startswith("eip-") else name.capitalize()
    lines = [f"# {title}\n"]

    facts = [e for e in entries if e.get("kind") == "fact"]
    decisions = [e for e in entries if e.get("kind") == "decision"]
    lessons = [e for e in entries if e.get("kind") == "lesson"]
    prefs = [e for e in entries if e.get("kind") == "preference"]

    if facts:
        lines.append("\n## Key Facts\n")
        for e in by_importance(facts, 12):
            lines.append(fmt_bullet(e))

    if decisions:
        lines.append("\n## Decisions\n")
        for e in by_importance(decisions, 8):
            lines.append(fmt_bullet(e))

    if lessons:
        lines.append("\n## Lessons Learned\n")
        for e in by_importance(lessons, 8):
            lines.append(fmt_bullet(e))

    if prefs:
        lines.append("\n## Preferences\n")
        for e in by_importance(prefs, 4):
            lines.append(fmt_bullet(e))

    if not any([facts, decisions, lessons, prefs]):
        lines.append("\n- (no structured memories yet)\n")

    return "\n".join(lines) + "\n"


def render_pr_page(pr_num: str, entries: list[dict[str, Any]]) -> str:
    """PR page with review context."""
    lines = [f"# PR #{pr_num}\n"]

    facts = [e for e in entries if e.get("kind") == "fact"]
    decisions = [e for e in entries if e.get("kind") == "decision"]
    lessons = [e for e in entries if e.get("kind") == "lesson"]

    if facts:
        lines.append("\n## Changes & Status\n")
        for e in by_importance(facts, 8):
            lines.append(fmt_bullet(e))

    if decisions:
        lines.append("\n## Review Decisions\n")
        for e in by_importance(decisions, 6):
            lines.append(fmt_bullet(e))

    if lessons:
        lines.append("\n## Lessons\n")
        for e in by_importance(lessons, 4):
            lines.append(fmt_bullet(e))

    if not any([facts, decisions, lessons]):
        # Fallback: show all entries
        lines.append("\n## Memory\n")
        for e in by_importance(entries, 8):
            lines.append(fmt_bullet(e))

    return "\n".join(lines) + "\n"


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def generate(entries: list[dict[str, Any]]) -> None:
    people: dict[str, list[dict[str, Any]]] = defaultdict(list)
    projects: dict[str, list[dict[str, Any]]] = defaultdict(list)
    prs: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for e in entries:
        text = str(e.get("text", ""))
        subject = str(e.get("subject", ""))
        project = e.get("project")

        if "nico" in text.lower() or subject.startswith("person:nico"):
            people["nico"].append(e)

        for m in MENTION_RE.finditer(text):
            name = m.group(1).lower()
            if name != "nico":  # avoid double-counting
                people[name].append(e)

        if project:
            projects[str(project).lower()].append(e)

        if m := PR_SUBJECT_RE.match(subject):
            prs[m.group(1)].append(e)
            projects.setdefault("lodestar", []).append(e)

        if m := EIP_SUBJECT_RE.match(subject):
            eip = m.group(1)
            projects[f"eip-{eip}"].append(e)
            projects.setdefault("ethereum", []).append(e)

    for person, group in people.items():
        write(ENT_DIR / "people" / f"{person}.md", render_person_page(person, group))

    for proj, group in projects.items():
        write(ENT_DIR / "projects" / f"{proj}.md", render_project_page(proj, group))

    for pr, group in prs.items():
        write(ENT_DIR / "prs" / f"pr-{pr}.md", render_pr_page(pr, group))

    print(
        f"Generated entity pages: people={len(people)}, projects={len(projects)}, prs={len(prs)}"
    )


if __name__ == "__main__":
    generate(load_entries())

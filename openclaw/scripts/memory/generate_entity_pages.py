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
PERSON_MENTION_RE = re.compile(r"(?<![A-Za-z0-9._-])@([A-Za-z][A-Za-z0-9_-]*)")
PERSON_MENTION_DENYLIST = {
    "chainsafe",
    "fastmail",
    "libp2p",
    "mention",
    "mentions",
    "protonmail",
    "sigstore",
    "typescript",
    "typescript-eslint",
    "users",
}
VERSION_MENTION_RE = re.compile(r"v\d+$")
DURATION_MENTION_RE = re.compile(r"\d+s$")


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


def is_noise_person_mention(name: str) -> bool:
    """Return true for machine/prose tokens that are not person mentions."""
    if name in PERSON_MENTION_DENYLIST:
        return True
    if name.isdigit():
        return True
    if VERSION_MENTION_RE.fullmatch(name):
        return True
    if DURATION_MENTION_RE.fullmatch(name):
        return True
    return False


def person_mentions(text: str) -> list[str]:
    names: list[str] = []
    for match in PERSON_MENTION_RE.finditer(text):
        name = match.group(1).lower()
        next_char = text[match.end() : match.end() + 1]
        if next_char in {"/", "."}:
            continue
        if is_noise_person_mention(name):
            continue
        names.append(name)
    return names


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def prune_stale_person_noise(active_people: set[str]) -> list[Path]:
    people_dir = ENT_DIR / "people"
    if not people_dir.exists():
        return []

    removed: list[Path] = []
    for path in people_dir.glob("*.md"):
        name = path.stem.lower()
        if name in active_people or not is_noise_person_mention(name):
            continue
        path.unlink()
        removed.append(path)

    return removed


def generate(entries: list[dict[str, Any]], *, prune_stale_person_noise_flag: bool = False) -> None:
    people: dict[str, list[dict[str, Any]]] = defaultdict(list)
    projects: dict[str, list[dict[str, Any]]] = defaultdict(list)
    prs: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for e in entries:
        text = str(e.get("text", ""))
        subject = str(e.get("subject", ""))
        project = e.get("project")

        if "nico" in text.lower() or subject.startswith("person:nico"):
            people["nico"].append(e)

        for name in person_mentions(text):
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

    removed = []
    if prune_stale_person_noise_flag:
        removed = prune_stale_person_noise(set(people))

    print(
        "Generated entity pages: "
        f"people={len(people)}, projects={len(projects)}, prs={len(prs)}, "
        f"pruned_stale_person_noise={len(removed)}"
    )


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--prune-stale-person-noise",
        action="store_true",
        help="Remove stale generated people pages for known machine/prose mention noise",
    )
    args = parser.parse_args()

    generate(load_entries(), prune_stale_person_noise_flag=args.prune_stale_person_noise)

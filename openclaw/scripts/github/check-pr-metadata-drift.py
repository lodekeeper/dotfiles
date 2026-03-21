#!/usr/bin/env python3
"""check-pr-metadata-drift.py

Lightweight guard for PR metadata drift after follow-up commits.

Checks for common stale-metadata patterns:
1) Title/body mention file paths not present in current PR diff file list
2) Title/body claims narrow scope ("only", "just", "single") while diff is broad
3) Title/body semver claims appear stale vs actual semver changes in the patch

Exit codes:
  0 -> no drift signals found
  2 -> potential drift detected (review title/body)
  1 -> runtime/tooling error
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from typing import Iterable


BACKTICK_RE = re.compile(r"`([^`]+)`")
FENCED_CODE_RE = re.compile(r"```.*?```", re.DOTALL)
DIRECT_PATH_RE = re.compile(r"\b(?:[A-Za-z0-9_.-]+/)+[A-Za-z0-9_.-]+\.[A-Za-z0-9]+\b")
FULL_PATH_RE = re.compile(r"^(?:[A-Za-z0-9_.-]+/)+[A-Za-z0-9_.-]+\.[A-Za-z0-9]+$")
SEMVER_RE = re.compile(r"\b\d+\.\d+\.\d+\b")
NARROW_SCOPE_RE = re.compile(r"\b(only|just|single|one-file)\b", re.IGNORECASE)


def run(cmd: list[str]) -> str:
    p = subprocess.run(cmd, text=True, capture_output=True)
    if p.returncode != 0:
        raise RuntimeError(f"Command failed ({' '.join(cmd)}):\n{p.stderr.strip()}")
    return p.stdout


def norm_path(value: str) -> str:
    return value.strip().strip("` ").lstrip("./")


def extract_paths(text: str) -> set[str]:
    out: set[str] = set()

    # Remove fenced code blocks before scanning narrative text.
    without_fenced = FENCED_CODE_RE.sub(" ", text)

    # Direct path-like tokens in narrative text.
    narrative = BACKTICK_RE.sub(" ", without_fenced)
    for m in DIRECT_PATH_RE.finditer(narrative):
        out.add(norm_path(m.group(0)))

    # Inline code: only accept single-token backticks that are pure paths.
    for m in BACKTICK_RE.finditer(without_fenced):
        token = m.group(1).strip()
        if " " in token or "\n" in token:
            continue
        if FULL_PATH_RE.fullmatch(token):
            out.add(norm_path(token))

    return out


def extract_semvers(lines: Iterable[str]) -> set[str]:
    out: set[str] = set()
    for line in lines:
        out.update(SEMVER_RE.findall(line))
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="Check PR title/body for metadata drift against current diff")
    parser.add_argument("--pr", type=int, required=True, help="PR number")
    parser.add_argument("--repo", default="ChainSafe/lodestar", help="owner/repo (default: ChainSafe/lodestar)")
    parser.add_argument(
        "--scope-threshold",
        type=int,
        default=8,
        help="Warn when narrow-scope language is used and changed file count exceeds this threshold",
    )
    args = parser.parse_args()

    try:
        pr_json = run(
            [
                "gh",
                "pr",
                "view",
                str(args.pr),
                "--repo",
                args.repo,
                "--json",
                "title,body,url,changedFiles,files",
            ]
        )
        pr = json.loads(pr_json)

        title = (pr.get("title") or "").strip()
        body = (pr.get("body") or "").strip()
        url = pr.get("url") or f"https://github.com/{args.repo}/pull/{args.pr}"

        files = [f.get("path", "") for f in (pr.get("files") or []) if isinstance(f, dict)]
        changed_file_count = int(pr.get("changedFiles") or len(files))
        file_set = {norm_path(f) for f in files if f}

        metadata_text = f"{title}\n\n{body}"
        metadata_paths = extract_paths(metadata_text)
        metadata_semvers = set(SEMVER_RE.findall(metadata_text))

        diff_text = run(["gh", "pr", "diff", str(args.pr), "--repo", args.repo])
        added_lines = [ln[1:] for ln in diff_text.splitlines() if ln.startswith("+") and not ln.startswith("+++")]
        removed_lines = [ln[1:] for ln in diff_text.splitlines() if ln.startswith("-") and not ln.startswith("---")]
        added_semvers = extract_semvers(added_lines)
        removed_semvers = extract_semvers(removed_lines)

        warnings: list[str] = []

        missing_paths = sorted(p for p in metadata_paths if p not in file_set)
        if missing_paths:
            warnings.append(
                "Metadata references file path(s) not present in current PR diff: " + ", ".join(f"`{p}`" for p in missing_paths)
            )

        if NARROW_SCOPE_RE.search(metadata_text) and changed_file_count > args.scope_threshold:
            warnings.append(
                f"Metadata uses narrow-scope language (only/just/single) but PR changes {changed_file_count} files (threshold: {args.scope_threshold})."
            )

        if metadata_semvers:
            stale_semvers = sorted(v for v in metadata_semvers if v in removed_semvers and v not in added_semvers)
            if stale_semvers:
                warnings.append(
                    "Metadata semver value(s) look stale (removed in diff, not added back): "
                    + ", ".join(f"`{v}`" for v in stale_semvers)
                )

            if added_semvers and metadata_semvers.isdisjoint(added_semvers):
                warnings.append(
                    "Metadata semver claim(s) do not appear in added diff content. "
                    f"Metadata: {sorted(metadata_semvers)} | Added diff semvers: {sorted(added_semvers)}"
                )

        print(f"# PR metadata drift check: {args.repo}#{args.pr}")
        print(f"URL: {url}")
        print(f"Changed files: {changed_file_count}")
        print()
        print("## Snapshot")
        print(f"- Title: {title or '<empty>'}")
        print(f"- Metadata path refs: {sorted(metadata_paths) if metadata_paths else 'none'}")
        print(f"- Metadata semvers: {sorted(metadata_semvers) if metadata_semvers else 'none'}")
        print(f"- Added diff semvers: {sorted(added_semvers) if added_semvers else 'none'}")
        print(f"- Removed diff semvers: {sorted(removed_semvers) if removed_semvers else 'none'}")

        if warnings:
            print()
            print("## ⚠️ Potential drift signals")
            for idx, w in enumerate(warnings, start=1):
                print(f"{idx}. {w}")
            print()
            print("Action: update PR title/body if these signals reflect actual scope drift.")
            return 2

        print()
        print("✅ No drift signals found.")
        return 0

    except Exception as err:  # noqa: BLE001
        print(f"ERROR: {err}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

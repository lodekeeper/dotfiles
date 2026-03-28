#!/usr/bin/env python3
"""Spec-compliance checker: compare TS implementation against consensus-spec pseudocode.

Extracts the relevant pseudocode block from consensus-specs markdown files,
extracts the TS symbol from a source file, and asks an LLM to assess compliance.

Usage:
    python3 scripts/spec/check-compliance.py \
        --spec-query process_attestation \
        --ts-file ~/lodestar/packages/beacon-node/src/chain/stateTransition.ts \
        --ts-symbol processAttestation

    python3 scripts/spec/check-compliance.py \
        --spec-query "get_head" \
        --ts-file ~/lodestar/packages/fork-choice/src/forkChoice.ts \
        --ts-symbol getHead \
        --output /tmp/compliance-report.md

Outputs a markdown report with: Inputs, Spec excerpt, TS excerpt,
Assessment summary, Detailed findings.

Exit codes:
  0 — report generated (inspect verdict)
  1 — fatal error (missing required args, file not found)
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_DEFAULT_SPEC_ROOT = os.path.expanduser("~/consensus-specs/specs")
_DEFAULT_MODEL = os.environ.get("OPENAI_SPEC_MODEL", "gpt-5.3-codex-spark")
_MAX_SPEC_CHARS = 12_000
_MAX_TS_CHARS = 12_000

_SYSTEM_PROMPT = """\
You are a senior Ethereum protocol engineer reviewing whether a TypeScript \
implementation faithfully follows the consensus-spec pseudocode.

Compare the **Spec pseudocode** with the **TypeScript implementation** below.
Identify:
- Steps/checks that are correctly implemented
- Steps/checks that are missing from the TS code
- Steps/checks where the TS diverges from the spec (different logic, wrong order, etc.)

Respond ONLY with a JSON object:
{
  "implemented": ["<list of spec steps correctly present in TS>"],
  "missing": ["<list of spec steps NOT present in TS>"],
  "diverged": ["<list of spec steps where TS logic diverges, with brief explanation>"],
  "notes": "<any additional observations or caveats>",
  "verdict": "faithful" | "partial" | "mismatch" | "insufficient",
  "confidence": "high" | "medium" | "low"
}

Verdict guide:
- "faithful": all spec steps are implemented correctly (minor style differences OK)
- "partial": most steps implemented but some missing or diverged
- "mismatch": significant deviations or missing critical logic
- "insufficient": not enough context to make a meaningful assessment
"""


# ---------------------------------------------------------------------------
# Spec extraction
# ---------------------------------------------------------------------------

def _find_spec_files(spec_root: str) -> list[str]:
    """Recursively find all .md files under spec_root."""
    return sorted(glob.glob(os.path.join(spec_root, "**", "*.md"), recursive=True))


def _extract_spec_blocks(spec_root: str, query: str, max_chars: int) -> str:
    """Search spec markdown files for *query* and return nearest fenced code blocks.

    Strategy: find lines matching *query* (case-insensitive), then for each match
    locate the enclosing ```python fenced block. Deduplicate by block content.
    """
    if not os.path.isdir(spec_root):
        return f"(spec root not found: {spec_root})"

    md_files = _find_spec_files(spec_root)
    if not md_files:
        return f"(no markdown files under {spec_root})"

    query_lower = query.lower()
    # Also build a regex for flexible matching (underscores ↔ spaces)
    query_pattern = re.compile(
        re.escape(query).replace(r"\ ", r"[\s_]+").replace("_", r"[\s_]+"),
        re.IGNORECASE,
    )

    blocks: list[tuple[str, str]] = []  # (source_label, block_text)
    seen: set[str] = set()

    for md_path in md_files:
        try:
            text = Path(md_path).read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue

        lines = text.split("\n")

        # Build fence map: list of (start_line, end_line) for fenced code blocks
        fence_starts: list[int] = []
        fence_ends: list[int] = []
        in_fence = False
        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped.startswith("```"):
                if not in_fence:
                    fence_starts.append(i)
                    in_fence = True
                else:
                    fence_ends.append(i)
                    in_fence = False

        # Pair up fences
        fences: list[tuple[int, int]] = list(zip(fence_starts, fence_ends))

        # Search for query matches
        for i, line in enumerate(lines):
            if query_lower not in line.lower() and not query_pattern.search(line):
                continue

            # Find the nearest enclosing or following fenced block
            best_fence: tuple[int, int] | None = None
            best_dist = float("inf")

            for fs, fe in fences:
                # Enclosing: line is inside the block
                if fs <= i <= fe:
                    best_fence = (fs, fe)
                    best_dist = 0
                    break
                # Nearest block (prefer forward, but accept backward)
                dist = min(abs(i - fs), abs(i - fe))
                if dist < best_dist:
                    best_dist = dist
                    best_fence = (fs, fe)

            if best_fence is not None and best_dist <= 30:
                fs, fe = best_fence
                block_text = "\n".join(lines[fs : fe + 1])
                # Deduplicate
                block_hash = block_text.strip()
                if block_hash not in seen:
                    seen.add(block_hash)
                    rel_path = os.path.relpath(md_path, spec_root)
                    blocks.append((f"{rel_path}:{fs + 1}", block_text))

    if not blocks:
        return f"(no spec blocks found for query: {query})"

    # Assemble output, respecting max_chars
    parts: list[str] = []
    total = 0
    for label, block in blocks:
        entry = f"### {label}\n\n{block}\n"
        if total + len(entry) > max_chars:
            parts.append(f"\n_(truncated — {len(blocks) - len(parts)} more blocks)_")
            break
        parts.append(entry)
        total += len(entry)

    return "\n".join(parts)


# ---------------------------------------------------------------------------
# TS symbol extraction
# ---------------------------------------------------------------------------

def _extract_ts_symbol(ts_file: str, ts_symbol: str, max_chars: int) -> str:
    """Extract the TS function/method body matching *ts_symbol* via brace-matching.

    Searches for declarations like:
        function ts_symbol(
        ts_symbol(              (method in class)
        ts_symbol = (           (arrow function)
        ts_symbol = function(
        export function ts_symbol(
    Then brace-matches to find the complete body.
    """
    try:
        text = Path(ts_file).read_text(encoding="utf-8", errors="replace")
    except FileNotFoundError:
        return f"(file not found: {ts_file})"
    except OSError as exc:
        return f"(error reading {ts_file}: {exc})"

    lines = text.split("\n")

    # Build regex patterns for common declaration forms
    esc = re.escape(ts_symbol)
    patterns = [
        # function foo( | export function foo( | async function foo(
        re.compile(rf"^[\s]*(export\s+)?(async\s+)?function\s+{esc}\s*[\(<]"),
        # foo( in a class (method)
        re.compile(rf"^\s*(public|private|protected|static|async|override|\s)*\s*{esc}\s*[\(<]"),
        # foo = ( | foo = function( | foo = async (
        re.compile(rf"^\s*(export\s+)?(const|let|var)\s+{esc}\s*="),
        # foo = ( for class property arrow functions
        re.compile(rf"^\s*(readonly\s+)?{esc}\s*=\s*(async\s+)?\("),
    ]

    # Find the declaration line
    decl_line: int | None = None
    for i, line in enumerate(lines):
        for pat in patterns:
            if pat.search(line):
                decl_line = i
                break
        if decl_line is not None:
            break

    if decl_line is None:
        return f"(symbol '{ts_symbol}' not found in {ts_file})"

    # Brace-match from declaration line to find the complete body
    # Start from decl_line and track braces
    brace_depth = 0
    started = False
    end_line = decl_line

    for i in range(decl_line, len(lines)):
        line = lines[i]
        # Strip string literals and comments to avoid false brace counts
        cleaned = _strip_strings_and_comments(line)
        for ch in cleaned:
            if ch == "{":
                brace_depth += 1
                started = True
            elif ch == "}":
                brace_depth -= 1

        if started and brace_depth <= 0:
            end_line = i
            break
    else:
        # Didn't find closing brace, take reasonable chunk
        end_line = min(decl_line + 200, len(lines) - 1)

    # Include a few lines of context before declaration (decorators, comments)
    context_start = max(0, decl_line - 5)
    # Look for blank line or another declaration to limit context
    for j in range(decl_line - 1, max(0, decl_line - 10) - 1, -1):
        if lines[j].strip() == "":
            context_start = j + 1
            break

    block = "\n".join(lines[context_start : end_line + 1])

    if len(block) > max_chars:
        block = block[:max_chars] + f"\n// ... (truncated at {max_chars} chars)"

    return block


def _strip_strings_and_comments(line: str) -> str:
    """Rough removal of string literals and comments for brace counting."""
    result: list[str] = []
    i = 0
    in_single = False
    in_double = False
    in_template = False

    while i < len(line):
        ch = line[i]

        # Line comment
        if not in_single and not in_double and not in_template:
            if ch == "/" and i + 1 < len(line) and line[i + 1] == "/":
                break  # rest of line is comment

        # Escaped char inside string
        if ch == "\\" and (in_single or in_double or in_template):
            i += 2
            continue

        if ch == "'" and not in_double and not in_template:
            in_single = not in_single
            i += 1
            continue
        if ch == '"' and not in_single and not in_template:
            in_double = not in_double
            i += 1
            continue
        if ch == "`" and not in_single and not in_double:
            in_template = not in_template
            i += 1
            continue

        if not in_single and not in_double and not in_template:
            result.append(ch)

        i += 1

    return "".join(result)


# ---------------------------------------------------------------------------
# LLM assessment
# ---------------------------------------------------------------------------

def _openai_completion(
    client: Any,
    messages: list[dict[str, str]],
    model: str,
) -> dict:
    """Call OpenAI chat completion and parse JSON response."""
    resp = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=0,
        max_tokens=2000,
        response_format={"type": "json_object"},
    )
    raw = resp.choices[0].message.content or "{}"
    return json.loads(raw)  # type: ignore[no-any-return]


def _assess_compliance(
    spec_excerpt: str,
    ts_excerpt: str,
    spec_query: str,
    ts_symbol: str,
    model: str,
) -> dict:
    """Run the LLM compliance assessment. Returns parsed result dict."""
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return {
            "implemented": [],
            "missing": [],
            "diverged": [],
            "notes": "OPENAI_API_KEY not set — cannot perform LLM assessment.",
            "verdict": "insufficient",
            "confidence": "low",
        }

    try:
        import openai  # type: ignore[import-untyped]
    except ImportError:
        return {
            "implemented": [],
            "missing": [],
            "diverged": [],
            "notes": "openai package not installed — cannot perform LLM assessment.",
            "verdict": "insufficient",
            "confidence": "low",
        }

    client = openai.OpenAI(api_key=api_key)

    user_msg = (
        f"## Spec query: `{spec_query}`\n\n"
        f"## Spec pseudocode\n\n{spec_excerpt}\n\n"
        f"## TypeScript implementation: `{ts_symbol}`\n\n"
        f"```typescript\n{ts_excerpt}\n```\n"
    )

    try:
        parsed = _openai_completion(
            client,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": user_msg},
            ],
            model=model,
        )
    except Exception as exc:
        return {
            "implemented": [],
            "missing": [],
            "diverged": [],
            "notes": f"LLM call failed: {exc}",
            "verdict": "insufficient",
            "confidence": "low",
        }

    # Validate and normalize
    verdict = parsed.get("verdict", "insufficient")
    if verdict not in {"faithful", "partial", "mismatch", "insufficient"}:
        verdict = "insufficient"

    confidence = parsed.get("confidence", "low")
    if confidence not in {"high", "medium", "low"}:
        confidence = "low"

    return {
        "implemented": parsed.get("implemented", []),
        "missing": parsed.get("missing", []),
        "diverged": parsed.get("diverged", []),
        "notes": parsed.get("notes", ""),
        "verdict": verdict,
        "confidence": confidence,
    }


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------

_VERDICT_EMOJI = {
    "faithful": "✅",
    "partial": "⚠️",
    "mismatch": "❌",
    "insufficient": "❓",
}


def _render_report(
    spec_query: str,
    ts_file: str,
    ts_symbol: str,
    spec_root: str,
    model: str,
    spec_excerpt: str,
    ts_excerpt: str,
    assessment: dict,
) -> str:
    """Render the final markdown report."""
    verdict = assessment.get("verdict", "insufficient")
    confidence = assessment.get("confidence", "low")
    emoji = _VERDICT_EMOJI.get(verdict, "❓")

    lines: list[str] = []
    lines.append("# Spec Compliance Report")
    lines.append("")
    lines.append(f"Generated: {_utc_now()}")
    lines.append("")

    # Inputs
    lines.append("## Inputs")
    lines.append("")
    lines.append(f"| Field | Value |")
    lines.append(f"|-------|-------|")
    lines.append(f"| Spec query | `{spec_query}` |")
    lines.append(f"| TS file | `{ts_file}` |")
    lines.append(f"| TS symbol | `{ts_symbol}` |")
    lines.append(f"| Spec root | `{spec_root}` |")
    lines.append(f"| Model | `{model}` |")
    lines.append("")

    # Assessment summary
    lines.append("## Assessment Summary")
    lines.append("")
    lines.append(f"- **Verdict:** {emoji} **{verdict}**")
    lines.append(f"- **Confidence:** {confidence}")
    lines.append(f"- **Implemented:** {len(assessment.get('implemented', []))} steps")
    lines.append(f"- **Missing:** {len(assessment.get('missing', []))} steps")
    lines.append(f"- **Diverged:** {len(assessment.get('diverged', []))} steps")
    lines.append("")

    # Detailed findings
    lines.append("## Detailed Findings")
    lines.append("")

    impl = assessment.get("implemented", [])
    if impl:
        lines.append("### ✅ Implemented")
        lines.append("")
        for item in impl:
            lines.append(f"- {item}")
        lines.append("")

    missing = assessment.get("missing", [])
    if missing:
        lines.append("### ❌ Missing")
        lines.append("")
        for item in missing:
            lines.append(f"- {item}")
        lines.append("")

    diverged = assessment.get("diverged", [])
    if diverged:
        lines.append("### ⚠️ Diverged")
        lines.append("")
        for item in diverged:
            lines.append(f"- {item}")
        lines.append("")

    notes = assessment.get("notes", "")
    if notes:
        lines.append("### Notes")
        lines.append("")
        lines.append(notes)
        lines.append("")

    # Spec excerpt
    lines.append("## Spec Excerpt")
    lines.append("")
    lines.append(spec_excerpt)
    lines.append("")

    # TS excerpt
    lines.append("## TS Excerpt")
    lines.append("")
    lines.append(f"```typescript")
    lines.append(ts_excerpt)
    lines.append(f"```")
    lines.append("")

    return "\n".join(lines)


def _utc_now() -> str:
    """Return current UTC timestamp string."""
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    ap = argparse.ArgumentParser(
        description="Check TS implementation compliance against consensus-spec pseudocode"
    )
    ap.add_argument(
        "--spec-query",
        required=True,
        help="Search query to find spec pseudocode (e.g. 'process_attestation')",
    )
    ap.add_argument(
        "--ts-file",
        required=True,
        help="Path to TypeScript source file",
    )
    ap.add_argument(
        "--ts-symbol",
        required=True,
        help="Name of the TS function/method to extract",
    )
    ap.add_argument(
        "--spec-root",
        default=_DEFAULT_SPEC_ROOT,
        help=f"Root directory of consensus-specs markdown (default: {_DEFAULT_SPEC_ROOT})",
    )
    ap.add_argument(
        "--model",
        default=_DEFAULT_MODEL,
        help=f"OpenAI model to use (default: {_DEFAULT_MODEL})",
    )
    ap.add_argument(
        "--output",
        help="Write markdown report to this file (in addition to stdout)",
    )
    ap.add_argument(
        "--max-spec-chars",
        type=int,
        default=_MAX_SPEC_CHARS,
        help=f"Max characters for spec excerpt (default: {_MAX_SPEC_CHARS})",
    )
    ap.add_argument(
        "--max-ts-chars",
        type=int,
        default=_MAX_TS_CHARS,
        help=f"Max characters for TS excerpt (default: {_MAX_TS_CHARS})",
    )
    args = ap.parse_args()

    # Expand paths
    ts_file = os.path.expanduser(args.ts_file)
    spec_root = os.path.expanduser(args.spec_root)

    if not os.path.isfile(ts_file):
        print(f"Error: TS file not found: {ts_file}", file=sys.stderr)
        sys.exit(1)

    # Extract spec blocks
    spec_excerpt = _extract_spec_blocks(spec_root, args.spec_query, args.max_spec_chars)

    # Extract TS symbol
    ts_excerpt = _extract_ts_symbol(ts_file, args.ts_symbol, args.max_ts_chars)

    # LLM assessment
    assessment = _assess_compliance(
        spec_excerpt=spec_excerpt,
        ts_excerpt=ts_excerpt,
        spec_query=args.spec_query,
        ts_symbol=args.ts_symbol,
        model=args.model,
    )

    # Render report
    report = _render_report(
        spec_query=args.spec_query,
        ts_file=args.ts_file,
        ts_symbol=args.ts_symbol,
        spec_root=spec_root,
        model=args.model,
        spec_excerpt=spec_excerpt,
        ts_excerpt=ts_excerpt,
        assessment=assessment,
    )

    # Output
    print(report)

    if args.output:
        out_path = os.path.expanduser(args.output)
        os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
        Path(out_path).write_text(report, encoding="utf-8")
        print(f"\nReport written to: {out_path}", file=sys.stderr)


if __name__ == "__main__":
    main()

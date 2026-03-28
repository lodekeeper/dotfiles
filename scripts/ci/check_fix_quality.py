#!/usr/bin/env python3
"""LLM-based fix quality gate for CI auto-fix pipeline.

Sends a diff to an LLM and asks whether it fixes the root cause
or just masks the failure (e.g. bumping timeouts, swallowing errors).

Usage:
    # From staged diff
    git diff --cached | python3 scripts/ci/check_fix_quality.py --test "test name" --classification timeout

    # From file
    python3 scripts/ci/check_fix_quality.py --diff-file /tmp/fix.diff --test "test name"

    # With full context
    python3 scripts/ci/check_fix_quality.py --diff-file /tmp/fix.diff \
        --test "E2E / peer-discovery" \
        --classification peer-count-flaky \
        --error "expected >= 4 peers, got 2" \
        --fix-hint "increase wait timeout or add retry"

Outputs JSON:
{
  "verdict": "root-cause" | "likely-root-cause" | "masking" | "insufficient",
  "confidence": "high" | "medium" | "low",
  "reasoning": "...",
  "suggestions": ["..."],
  "should_flag": true | false
}

Exit codes:
  0 — check completed (inspect verdict)
  1 — error (missing API key, LLM failure, no diff)
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any

_SYSTEM_PROMPT = """\
You are a senior software engineer reviewing a CI fix for the Lodestar TypeScript \
Ethereum consensus client. Your job is to assess whether the proposed diff actually \
fixes the root cause of the test failure, or merely masks it.

**Masking patterns** (common in flaky-test fixes):
- Bumping timeouts without addressing why the operation is slow
- Adding `.catch(() => {})` to swallow errors without understanding the source
- Disabling or skipping the test entirely
- Adding retry loops around assertions instead of fixing timing/sequencing
- Wrapping in try/catch and ignoring the error
- Reducing assertion strictness (e.g. `>=` instead of `===`) without justification

**Root-cause patterns** (good fixes):
- Adding proper cleanup/teardown that was missing
- Fixing race conditions with proper synchronization (events, promises, barriers)
- Fixing resource leaks (unclosed connections, streams, timers)
- Adding missing `await` on async operations
- Fixing incorrect test setup/assumptions
- Adding proper error propagation instead of swallowing

**Borderline cases:**
- Increasing a timeout AND adding a comment explaining why the original was too tight → likely-root-cause
- Adding retry with exponential backoff for inherently non-deterministic operations (network, peer discovery) → likely-root-cause
- Adding `.catch()` but also logging or propagating the error properly → likely-root-cause

Respond ONLY with a JSON object:
{
  "verdict": "root-cause" | "likely-root-cause" | "masking" | "insufficient",
  "confidence": "high" | "medium" | "low",
  "reasoning": "<2-3 sentences explaining your assessment>",
  "suggestions": ["<optional improvement suggestions, max 3>"],
  "should_flag": true | false
}

"should_flag" should be true if:
- verdict is "masking"
- verdict is "insufficient" (diff is too small/unclear to assess)
- confidence is "low" regardless of verdict
"""

# Prefer spark model for quality-gate classification (with fallback to legacy model)
_LLM_MODEL = os.environ.get("OPENAI_CI_MODEL", "gpt-5.3-codex-spark")
_LLM_FALLBACK_MODEL = "gpt-4o-mini"
_MAX_DIFF_CHARS = 8000  # Limit diff size sent to LLM


def _openai_completion(client: Any, messages: list[dict[str, str]]) -> Any:
    """Call OpenAI with spark preference, then fallback to the legacy model."""
    models = [_LLM_MODEL]
    if _LLM_FALLBACK_MODEL and _LLM_FALLBACK_MODEL != _LLM_MODEL:
        models.append(_LLM_FALLBACK_MODEL)

    last_error = None
    for model in models:
        try:
            return client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=0,
                max_tokens=500,
                response_format={"type": "json_object"},
            )
        except Exception as exc:  # pragma: no cover - provider dependent
            last_error = exc
            if model != models[-1]:
                print(f"LLM model '{model}' failed, trying fallback", file=sys.stderr)
                continue
            raise

    if last_error is not None:
        raise RuntimeError(f"OpenAI completion failed: {last_error}")


def check_fix_quality(
    diff: str,
    test_name: str | None = None,
    classification: str | None = None,
    error_msg: str | None = None,
    fix_hint: str | None = None,
) -> dict:
    """Send diff to LLM for quality assessment.

    Returns dict with verdict, confidence, reasoning, suggestions, should_flag.
    Raises RuntimeError on failure.
    """
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY not set")

    import openai  # type: ignore[import-untyped]

    client = openai.OpenAI(api_key=api_key)

    # Build user message with context
    parts = []
    if test_name:
        parts.append(f"**Test:** {test_name}")
    if classification:
        parts.append(f"**Failure classification:** {classification}")
    if error_msg:
        parts.append(f"**Original error:** {error_msg}")
    if fix_hint:
        parts.append(f"**Suggested fix approach:** {fix_hint}")

    # Truncate diff if too large
    diff_excerpt = diff[-_MAX_DIFF_CHARS:] if len(diff) > _MAX_DIFF_CHARS else diff
    if len(diff) > _MAX_DIFF_CHARS:
        parts.append(f"*(diff truncated to last {_MAX_DIFF_CHARS} chars of {len(diff)} total)*")

    parts.append(f"\n**Proposed fix diff:**\n```diff\n{diff_excerpt}\n```")

    user_msg = "\n".join(parts)

    resp = _openai_completion(
        client,
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": user_msg},
        ],
    )

    raw = resp.choices[0].message.content or "{}"
    parsed = json.loads(raw)

    # Validate and normalize
    verdict = parsed.get("verdict", "insufficient")
    if verdict not in {"root-cause", "likely-root-cause", "masking", "insufficient"}:
        verdict = "insufficient"

    confidence = parsed.get("confidence", "low")
    if confidence not in {"high", "medium", "low"}:
        confidence = "low"

    should_flag = parsed.get("should_flag", True)
    # Override: always flag masking and insufficient
    if verdict in {"masking", "insufficient"} or confidence == "low":
        should_flag = True

    return {
        "verdict": verdict,
        "confidence": confidence,
        "reasoning": parsed.get("reasoning", "No reasoning provided"),
        "suggestions": parsed.get("suggestions", [])[:3],
        "should_flag": should_flag,
    }


def main() -> None:
    ap = argparse.ArgumentParser(
        description="LLM-based fix quality gate for CI auto-fix pipeline"
    )
    ap.add_argument("--diff-file", help="Path to diff file (default: read from stdin)")
    ap.add_argument("--test", help="Name of the failing test")
    ap.add_argument("--classification", help="Failure classification from detector")
    ap.add_argument("--error", help="Original error message snippet")
    ap.add_argument("--fix-hint", help="Fix hint from classifier")
    args = ap.parse_args()

    # Read diff
    if args.diff_file:
        try:
            with open(args.diff_file, encoding="utf-8") as f:
                diff = f.read()
        except FileNotFoundError:
            print(json.dumps({"error": f"Diff file not found: {args.diff_file}"}))
            sys.exit(1)
    else:
        if sys.stdin.isatty():
            print("Error: No diff provided. Pipe a diff or use --diff-file.", file=sys.stderr)
            sys.exit(1)
        diff = sys.stdin.read()

    if not diff.strip():
        print(json.dumps({
            "verdict": "insufficient",
            "confidence": "low",
            "reasoning": "Empty diff — nothing to assess.",
            "suggestions": [],
            "should_flag": True,
        }))
        sys.exit(1)

    try:
        result = check_fix_quality(
            diff=diff,
            test_name=args.test,
            classification=args.classification,
            error_msg=args.error,
            fix_hint=args.fix_hint,
        )
        print(json.dumps(result, indent=2))
    except RuntimeError as exc:
        print(json.dumps({"error": str(exc)}), file=sys.stderr)
        sys.exit(1)
    except Exception as exc:
        print(json.dumps({"error": f"Unexpected error: {exc}"}), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

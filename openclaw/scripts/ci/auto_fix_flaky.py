#!/usr/bin/env python3
"""CI auto-fix pipeline for flaky sim/e2e tests on unstable.

Detects new failures, classifies them, and outputs actionable JSON
for the cron agent to act on (investigate, fix, PR).

Usage:
    python3 scripts/ci/auto_fix_flaky.py [--apply] [--no-llm]

Without --apply: prints what it found (detection only).
With --apply: updates the tracker file with new findings.
With --no-llm: skip LLM fallback classification (faster, offline).
"""
from __future__ import annotations

import json
import os
import re
import shlex
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

WORKSPACE = Path(__file__).resolve().parents[2]
TRACKER_PATH = WORKSPACE / "memory" / "unstable-ci-tracker.json"
REPO = "ChainSafe/lodestar"
FETCH_RUN_LOGS_SCRIPT = WORKSPACE / "scripts" / "ci" / "fetch-run-logs.sh"
FETCH_RUN_LOGS_TIMEOUT_SECONDS = int(os.environ.get("CI_FETCH_RUN_LOGS_TIMEOUT_SECONDS", "120"))

# Only these workflows, and only specific job name patterns
TARGET_WORKFLOWS = ["Tests", "Sim tests", "Kurtosis sim tests"]
TARGET_JOB_PATTERNS = [
    "E2E Tests",
    "Browser Tests",
    "Sim test",
    "Multifork sim",
    "Kurtosis sim",
    "Eth backup provider",
]

# Known flaky patterns (error text → classification)
FLAKY_PATTERNS: list[tuple[str, str, str]] = [
    ("QUEUE_ERROR_QUEUE_ABORTED", "shutdown-race", "Unhandled rejection during test teardown — floating promise in shutdown path"),
    ("connectedPeerCount", "peer-count-flaky", "Peer connectivity assertion flakiness — node doesn't reach expected peer count in time"),
    ("Timed out", "timeout", "Test or hook timed out — may need increased timeout or async wait"),
    ("TIMEOUT", "timeout", "Test or hook timed out"),
    ("ECONNREFUSED", "infra-flaky", "Connection refused — test infra startup race"),
    ("error while removing network", "docker-teardown", "Docker network cleanup failure — not actionable"),
    ("ExitStatus:signal", "process-crash", "Child process crashed during test"),
    ("vitest", "vitest-crash", "Vitest runner crashed"),
]

# Patterns that are NOT actionable (skip)
SKIP_PATTERNS = [
    "Dependabot",
    "dependabot",
    "docker-teardown",
]

# Valid classification labels (for LLM to pick from)
KNOWN_CLASSIFICATIONS = [
    "shutdown-race",
    "peer-count-flaky",
    "timeout",
    "vitest-crash",
    "infra-flaky",
    "process-crash",
    "assertion-error",
    "memory-pressure",
    "race-condition",
    "import-error",
    "config-error",
    "network-partition",
    "not-actionable",
]

# LLM classification system prompt
_LLM_SYSTEM = """\
You are a CI failure classifier for the Lodestar TypeScript Ethereum consensus client.
Given a failing CI job name and log snippet, classify the failure into exactly one category.

Valid categories:
- shutdown-race: floating promise / unhandled rejection during teardown
- peer-count-flaky: peer discovery/count assertion fails intermittently
- timeout: test/hook timed out; could increase timeout or add retry
- vitest-crash: vitest runner itself crashed (OOM, segfault, SIGSEGV)
- infra-flaky: infra-level flakiness (ECONNREFUSED, port collision, docker startup race)
- process-crash: child process exited with signal or non-zero code unexpectedly
- assertion-error: deterministic logic bug — assertion fails, not a timing/infra issue
- memory-pressure: heap OOM, GC pressure, ENOMEM
- race-condition: concurrent state mutation, ordering-dependent flakiness
- import-error: missing module, broken import, type error at startup
- config-error: bad env/config causing the job to fail at startup
- network-partition: simulated network partition or actual partition between nodes
- not-actionable: infra/upstream failure outside of Lodestar code

Respond ONLY with a JSON object:
{
  "classification": "<one of the valid categories>",
  "confidence": "high|medium|low",
  "description": "<one sentence: what failed and why>",
  "fixable": true|false,
  "fix_hint": "<short suggestion for the cron agent, or null>"
}
"""

# Prefer spark model for fast CI automation LLM calls (configurable, fallback keeps behavior stable)
_LLM_MODEL = os.environ.get("OPENAI_CI_MODEL", "gpt-5.3-codex-spark")
_LLM_FALLBACK_MODEL = "gpt-4o-mini"
LLM_LOG_CHARS = 3000  # max log chars to send to LLM
OPENAI_CI_MAX_ATTEMPTS = int(os.environ.get("OPENAI_CI_MAX_ATTEMPTS", "3"))
OPENAI_CI_BACKOFF_SECONDS = float(os.environ.get("OPENAI_CI_BACKOFF_SECONDS", "1.5"))
OPENAI_CI_MAX_BACKOFF_SECONDS = float(os.environ.get("OPENAI_CI_MAX_BACKOFF_SECONDS", "20"))

LLM_RETRY_TELEMETRY: dict[str, Any] = {
    "retry_count": 0,
    "retry_wait_s": 0.0,
    "retry_after_seen": False,
}

SCAN_HISTORY_MAX = int(os.environ.get("CI_RETRY_SCAN_HISTORY_MAX", "200"))
RETRY_WINDOW_RUNS = int(os.environ.get("CI_RETRY_WINDOW_RUNS", "8"))
RETRY_WARN_COUNT_TOTAL = int(os.environ.get("CI_RETRY_WARN_COUNT_TOTAL", "6"))
RETRY_WARN_WAIT_TOTAL_S = float(os.environ.get("CI_RETRY_WARN_WAIT_TOTAL_S", "30"))
RETRY_WARN_RETRY_AFTER_HITS = int(os.environ.get("CI_RETRY_WARN_RETRY_AFTER_HITS", "2"))
RETRY_MIN_SAMPLE_RUNS = int(os.environ.get("CI_RETRY_MIN_SAMPLE_RUNS", "4"))


def reset_llm_retry_telemetry() -> None:
    LLM_RETRY_TELEMETRY["retry_count"] = 0
    LLM_RETRY_TELEMETRY["retry_wait_s"] = 0.0
    LLM_RETRY_TELEMETRY["retry_after_seen"] = False


def get_llm_retry_telemetry() -> dict[str, Any]:
    return {
        "retry_count": int(LLM_RETRY_TELEMETRY.get("retry_count", 0)),
        "retry_wait_s": round(float(LLM_RETRY_TELEMETRY.get("retry_wait_s", 0.0)), 3),
        "retry_after_seen": bool(LLM_RETRY_TELEMETRY.get("retry_after_seen", False)),
    }


def _get_status_code(exc: Exception) -> int | None:
    for attr in ("status_code", "status"):
        value = getattr(exc, attr, None)
        if isinstance(value, int):
            return value

    response = getattr(exc, "response", None)
    if response is not None:
        for attr in ("status_code", "status"):
            value = getattr(response, attr, None)
            if isinstance(value, int):
                return value

    return None


def _get_retry_after_seconds(exc: Exception) -> float | None:
    response = getattr(exc, "response", None)
    headers = getattr(response, "headers", None)
    if headers:
        retry_after = headers.get("retry-after") or headers.get("Retry-After")
        if retry_after:
            try:
                return max(0.0, float(retry_after))
            except Exception:
                pass

    msg = str(exc)
    match = re.search(r"retry\s+after\s+([0-9]+(?:\.[0-9]+)?)", msg, flags=re.IGNORECASE)
    if match:
        try:
            return max(0.0, float(match.group(1)))
        except Exception:
            return None

    return None


def _is_retryable_openai_error(exc: Exception) -> bool:
    status = _get_status_code(exc)
    if status in {429, 500, 502, 503, 504}:
        return True

    msg = str(exc).lower()
    retryable_tokens = [
        "rate limit",
        "retry",
        "timeout",
        "timed out",
        "service unavailable",
        "temporary",
        "overloaded",
        "connection reset",
        "try again",
    ]
    return any(token in msg for token in retryable_tokens)


def _openai_completion(client: Any, messages: list[dict[str, str]]) -> tuple[Any, dict[str, Any]]:
    """Call OpenAI with retry/backoff and model fallback.

    Returns (response, retry_telemetry_for_this_call).
    """
    models = [_LLM_MODEL]
    if _LLM_FALLBACK_MODEL and _LLM_FALLBACK_MODEL != _LLM_MODEL:
        models.append(_LLM_FALLBACK_MODEL)

    local_retry = {
        "retry_count": 0,
        "retry_wait_s": 0.0,
        "retry_after_seen": False,
    }

    last_error = None
    for model in models:
        for attempt in range(1, max(1, OPENAI_CI_MAX_ATTEMPTS) + 1):
            try:
                response = client.chat.completions.create(
                    model=model,
                    messages=messages,
                    temperature=0,
                    max_tokens=300,
                    response_format={"type": "json_object"},
                )
                return response, local_retry
            except Exception as exc:  # pragma: no cover - depends on provider availability
                last_error = exc
                if _is_retryable_openai_error(exc) and attempt < OPENAI_CI_MAX_ATTEMPTS:
                    retry_after_hint = _get_retry_after_seconds(exc)
                    retry_after = retry_after_hint
                    if retry_after is None:
                        retry_after = min(
                            OPENAI_CI_MAX_BACKOFF_SECONDS,
                            OPENAI_CI_BACKOFF_SECONDS * (2 ** (attempt - 1)),
                        )

                    local_retry["retry_count"] += 1
                    local_retry["retry_wait_s"] += float(retry_after)
                    if retry_after_hint is not None:
                        local_retry["retry_after_seen"] = True

                    LLM_RETRY_TELEMETRY["retry_count"] = int(LLM_RETRY_TELEMETRY["retry_count"]) + 1
                    LLM_RETRY_TELEMETRY["retry_wait_s"] = float(LLM_RETRY_TELEMETRY["retry_wait_s"]) + float(retry_after)
                    if retry_after_hint is not None:
                        LLM_RETRY_TELEMETRY["retry_after_seen"] = True

                    print(
                        f"LLM model '{model}' attempt {attempt} failed; retrying in {retry_after:.1f}s",
                        file=sys.stderr,
                    )
                    time.sleep(retry_after)
                    continue

                if model != models[-1]:
                    print(f"LLM model '{model}' failed, trying fallback", file=sys.stderr)
                    break
                raise

    if last_error is not None:
        raise last_error

    return None, local_retry


def gh_json(args: list[str]) -> Any:
    """Run gh CLI and parse JSON output."""
    result = subprocess.run(
        ["gh"] + args,
        capture_output=True,
        text=True,
        timeout=30,
    )
    if result.returncode != 0:
        print(f"gh error: {result.stderr.strip()}", file=sys.stderr)
        return None
    return json.loads(result.stdout) if result.stdout.strip() else None


def load_tracker() -> dict[str, Any]:
    if TRACKER_PATH.exists():
        try:
            return json.loads(TRACKER_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"description": "Tracks investigated CI failures on unstable branch", "investigated": []}


def save_tracker(tracker: dict[str, Any]) -> None:
    TRACKER_PATH.parent.mkdir(parents=True, exist_ok=True)
    TRACKER_PATH.write_text(json.dumps(tracker, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _retry_sample_from_entry(entry: dict[str, Any]) -> dict[str, Any] | None:
    telemetry = entry.get("llm_retry_telemetry")
    if not isinstance(telemetry, dict):
        return None

    try:
        return {
            "scanned_at": entry.get("scanned_at"),
            "retry_count": int(telemetry.get("retry_count", 0)),
            "retry_wait_s": round(float(telemetry.get("retry_wait_s", 0.0)), 3),
            "retry_after_seen": bool(telemetry.get("retry_after_seen", False)),
        }
    except Exception:
        return None


def get_retry_samples(tracker: dict[str, Any]) -> list[dict[str, Any]]:
    samples: list[dict[str, Any]] = []

    scan_history = tracker.get("scan_history", [])
    if isinstance(scan_history, list):
        for raw in scan_history:
            if not isinstance(raw, dict):
                continue
            sample = _retry_sample_from_entry(raw)
            if sample:
                samples.append(sample)

    if not samples:
        last_scan = tracker.get("last_scan")
        if isinstance(last_scan, dict):
            sample = _retry_sample_from_entry(last_scan)
            if sample:
                samples.append(sample)

    return samples


def evaluate_retry_escalation(samples: list[dict[str, Any]]) -> dict[str, Any]:
    if RETRY_WINDOW_RUNS <= 0:
        windowed = samples
    else:
        windowed = samples[-RETRY_WINDOW_RUNS:]

    total_retry_count = sum(int(s.get("retry_count", 0)) for s in windowed)
    total_retry_wait_s = round(sum(float(s.get("retry_wait_s", 0.0)) for s in windowed), 3)
    retry_after_hits = sum(1 for s in windowed if bool(s.get("retry_after_seen", False)))

    reasons: list[str] = []
    enough_samples = len(windowed) >= max(1, RETRY_MIN_SAMPLE_RUNS)

    if enough_samples:
        if total_retry_count >= RETRY_WARN_COUNT_TOTAL:
            reasons.append(
                f"retry_count_total {total_retry_count} >= threshold {RETRY_WARN_COUNT_TOTAL}"
            )
        if total_retry_wait_s >= RETRY_WARN_WAIT_TOTAL_S:
            reasons.append(
                f"retry_wait_total_s {total_retry_wait_s} >= threshold {RETRY_WARN_WAIT_TOTAL_S}"
            )
        if retry_after_hits >= RETRY_WARN_RETRY_AFTER_HITS:
            reasons.append(
                f"retry_after_hits {retry_after_hits} >= threshold {RETRY_WARN_RETRY_AFTER_HITS}"
            )

    return {
        "degraded": bool(reasons),
        "reasons": reasons,
        "window_runs": RETRY_WINDOW_RUNS,
        "sampled_runs": len(windowed),
        "sample_requirement": RETRY_MIN_SAMPLE_RUNS,
        "total_retry_count": total_retry_count,
        "total_retry_wait_s": total_retry_wait_s,
        "retry_after_hits": retry_after_hits,
        "thresholds": {
            "retry_count_total": RETRY_WARN_COUNT_TOTAL,
            "retry_wait_total_s": RETRY_WARN_WAIT_TOTAL_S,
            "retry_after_hits": RETRY_WARN_RETRY_AFTER_HITS,
        },
    }


def get_investigated_ids(tracker: dict[str, Any]) -> set[int]:
    """All run IDs we've already looked at."""
    ids = set()
    for entry in tracker.get("investigated", []):
        if isinstance(entry, dict) and "runId" in entry:
            ids.add(int(entry["runId"]))
        elif isinstance(entry, int):
            ids.add(entry)
    # Also check top-level keys (old format)
    for k in tracker:
        try:
            ids.add(int(k))
        except ValueError:
            pass
    return ids


def get_failed_runs() -> list[dict[str, Any]]:
    """Fetch recent failed runs on unstable for target workflows."""
    all_failed: list[dict[str, Any]] = []

    for wf in TARGET_WORKFLOWS:
        data = gh_json([
            "run", "list",
            "--repo", REPO,
            "--branch", "unstable",
            "--workflow", wf,
            "--limit", "10",
            "--json", "databaseId,name,conclusion,createdAt,status",
        ])
        if not data:
            continue

        for run in data:
            if run.get("conclusion") == "failure":
                all_failed.append(run)

    return all_failed


def get_failed_jobs(run_id: int) -> list[dict[str, Any]]:
    """Get failed jobs for a run."""
    data = gh_json([
        "run", "view", str(run_id),
        "--repo", REPO,
        "--json", "jobs",
    ])
    if not data or "jobs" not in data:
        return []

    return [j for j in data["jobs"] if j.get("conclusion") == "failure"]


def get_job_logs(run_id: int) -> str:
    """Try to get failed job logs."""
    result = subprocess.run(
        ["gh", "run", "view", str(run_id), "--repo", REPO, "--log-failed"],
        capture_output=True,
        text=True,
        timeout=60,
    )
    return result.stdout[:20000] if result.stdout else ""


def fetch_run_logs_artifact(run_id: int) -> dict[str, Any]:
    """Fetch logs via fallback helper script and return artifact metadata.

    Returns a dict with:
      - attempted (bool)
      - status ("fetched" | "fetch-failed" | "script-missing" | "read-failed")
      - command (str)
      - artifact_path (str, workspace-relative)
      - logs (str | None)
      - error (str | None)
    """
    artifact_rel = Path("tmp") / "ci-logs" / f"run-{run_id}.log"
    artifact_abs = WORKSPACE / artifact_rel

    command = [
        "bash",
        str(FETCH_RUN_LOGS_SCRIPT),
        str(run_id),
        "--repo",
        REPO,
        "--output",
        str(artifact_rel),
    ]

    meta: dict[str, Any] = {
        "attempted": True,
        "status": "fetch-failed",
        "command": " ".join(shlex.quote(part) for part in command),
        "artifact_path": str(artifact_rel),
        "logs": None,
        "error": None,
    }

    if not FETCH_RUN_LOGS_SCRIPT.exists():
        meta["status"] = "script-missing"
        meta["error"] = f"missing script: {FETCH_RUN_LOGS_SCRIPT}"
        return meta

    try:
        result = subprocess.run(
            command,
            cwd=str(WORKSPACE),
            capture_output=True,
            text=True,
            timeout=FETCH_RUN_LOGS_TIMEOUT_SECONDS,
        )
    except Exception as exc:
        meta["error"] = str(exc)
        return meta

    if result.returncode != 0:
        meta["error"] = (result.stderr or result.stdout or "").strip()[-800:]
        return meta

    try:
        logs = artifact_abs.read_text(encoding="utf-8", errors="replace")
    except Exception as exc:
        meta["status"] = "read-failed"
        meta["error"] = str(exc)
        return meta

    meta["status"] = "fetched"
    meta["logs"] = logs[:20000]
    meta["artifact_bytes"] = artifact_abs.stat().st_size if artifact_abs.exists() else None
    return meta


def classify_with_llm(job_name: str, logs: str) -> dict[str, Any] | None:
    """LLM-based fallback classification for unknown failure patterns.

    Returns a dict with keys: classification, confidence, description, fixable, fix_hint.
    Returns None if the LLM call fails or the API key is unavailable.
    """
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return None

    try:
        import openai  # type: ignore[import-untyped]
        client = openai.OpenAI(api_key=api_key)

        log_excerpt = logs[-LLM_LOG_CHARS:] if len(logs) > LLM_LOG_CHARS else logs
        user_msg = f"Job: {job_name}\n\nLog excerpt:\n```\n{log_excerpt}\n```"

        resp, llm_retry = _openai_completion(
            client,
            messages=[
                {"role": "system", "content": _LLM_SYSTEM},
                {"role": "user", "content": user_msg},
            ],
        )

        raw = resp.choices[0].message.content or ""
        parsed = json.loads(raw)

        # Validate fields
        classification = parsed.get("classification", "unknown-failure")
        if classification not in KNOWN_CLASSIFICATIONS:
            classification = "unknown-failure"

        return {
            "classification": classification,
            "confidence": parsed.get("confidence", "medium"),
            "description": parsed.get("description", "LLM-classified failure"),
            "fixable": bool(parsed.get("fixable", False)),
            "fix_hint": parsed.get("fix_hint"),
            "llm_retry_count": int(llm_retry.get("retry_count", 0)),
            "llm_retry_wait_s": round(float(llm_retry.get("retry_wait_s", 0.0)), 3),
            "llm_retry_after_seen": bool(llm_retry.get("retry_after_seen", False)),
        }

    except Exception as exc:
        print(f"LLM classification failed: {exc}", file=sys.stderr)
        return None


def classify_failure(
    job_name: str,
    logs: str,
    use_llm: bool = True,
) -> tuple[str, str, str, str | None, bool | None, dict[str, Any] | None]:
    """Classify a failure based on job name and logs.

    Returns (classification, description, confidence, fix_hint, llm_fixable, llm_retry_telemetry).
    confidence: "high" (keyword match) | "medium" (llm) | "low" (no match, no logs)
    fix_hint: short string for cron agent, or None
    llm_fixable: LLM-provided fixability verdict when LLM classification is used
    llm_retry_telemetry: retry_count/retry_wait_s/retry_after_seen for this LLM classification call
    """
    # Check skip patterns first
    for skip in SKIP_PATTERNS:
        if skip.lower() in job_name.lower() or skip.lower() in logs.lower():
            return "not-actionable", f"Matched skip pattern: {skip}", "high", None, None, None

    # Check if it's a target job
    is_target = any(pat.lower() in job_name.lower() for pat in TARGET_JOB_PATTERNS)
    if not is_target:
        return "not-target", f"Job '{job_name}' is not a target job type", "high", None, None, None

    # Classify by known keyword patterns (high confidence)
    for pattern, classification, description in FLAKY_PATTERNS:
        if pattern.lower() in logs.lower():
            return classification, description, "high", None, None, None

    # No keyword match — try LLM fallback
    if logs and use_llm:
        llm_result = classify_with_llm(job_name, logs)
        if llm_result:
            llm_retry = {
                "retry_count": int(llm_result.get("llm_retry_count", 0)),
                "retry_wait_s": round(float(llm_result.get("llm_retry_wait_s", 0.0)), 3),
                "retry_after_seen": bool(llm_result.get("llm_retry_after_seen", False)),
            }
            return (
                llm_result["classification"],
                llm_result["description"],
                llm_result["confidence"],
                llm_result.get("fix_hint"),
                bool(llm_result.get("fixable", False)),
                llm_retry,
            )

    # Nothing matched
    if logs:
        return "unknown-failure", f"Target job '{job_name}' failed with unknown pattern", "low", None, None, None
    else:
        return "logs-unavailable", f"Target job '{job_name}' failed but logs expired/unavailable", "low", None, None, None


def is_fixable(classification: str, llm_fixable: bool | None = None) -> bool:
    """Is this a classification we can auto-fix?

    For keyword-matched classifications, use the hard-coded allowlist.
    For LLM-classified results, defer to the LLM's fixable judgment (with sanity check).
    """
    keyword_fixable = classification in {
        "shutdown-race",
        "peer-count-flaky",
        "timeout",
        "vitest-crash",
    }
    if keyword_fixable:
        return True
    # LLM says fixable, and the classification isn't explicitly not-actionable
    if llm_fixable and classification not in {"not-actionable", "not-target", "logs-unavailable"}:
        return True
    return False


def fix_confidence(classification: str, confidence: str) -> str:
    """Assess confidence that a fix will address root cause vs. just masking.

    Returns: "root-cause" | "likely-root-cause" | "masking-risk" | "unknown"
    """
    if confidence == "low" or classification in {"unknown-failure", "logs-unavailable"}:
        return "unknown"

    # Timeout bumps are typically masking, not root cause
    if classification == "timeout" and confidence != "high":
        return "masking-risk"

    # These are well-understood patterns with known fixes
    if classification in {"shutdown-race", "vitest-crash", "import-error", "config-error"}:
        return "root-cause"

    if classification in {"peer-count-flaky", "process-crash", "infra-flaky"}:
        return "likely-root-cause"

    # LLM-classified but uncertain
    if confidence == "medium":
        return "masking-risk"

    return "unknown"


def extract_test_file(logs: str) -> str | None:
    """Try to extract the failing test file from logs."""
    import re
    # Common patterns in Vitest/Mocha output
    patterns = [
        r"FAIL\s+(\S+\.test\.\S+)",
        r"❯\s+(\S+\.test\.\S+)",
        r"at\s+.*?(\S+\.test\.\S+:\d+)",
        r"(\S+\.test\.ts)\s",
    ]
    for pat in patterns:
        m = re.search(pat, logs)
        if m:
            return m.group(1)
    return None


def scan(apply: bool = False, use_llm: bool = True) -> list[dict[str, Any]]:
    """Scan for new failures and classify them."""
    reset_llm_retry_telemetry()

    tracker = load_tracker()
    investigated = get_investigated_ids(tracker)
    failed_runs = get_failed_runs()

    new_failures: list[dict[str, Any]] = []
    log_fallback_by_run: dict[int, dict[str, Any]] = {}

    for run in failed_runs:
        run_id = int(run["databaseId"])
        if run_id in investigated:
            continue

        # Get failed jobs
        jobs = get_failed_jobs(run_id)
        if not jobs:
            continue

        # Get logs
        logs = get_job_logs(run_id)

        for job in jobs:
            job_name = job.get("name", "unknown")
            effective_logs = logs
            fallback_meta: dict[str, Any] | None = None
            fallback_reclassified = False

            classification, description, confidence, fix_hint, llm_fixable, llm_retry = classify_failure(
                job_name, effective_logs, use_llm=use_llm
            )

            if classification == "logs-unavailable":
                if run_id not in log_fallback_by_run:
                    log_fallback_by_run[run_id] = fetch_run_logs_artifact(run_id)
                fallback_meta = log_fallback_by_run[run_id]

                fetched_logs = fallback_meta.get("logs") if isinstance(fallback_meta, dict) else None
                if isinstance(fetched_logs, str) and fetched_logs.strip():
                    effective_logs = fetched_logs
                    (
                        classification,
                        description,
                        confidence,
                        fix_hint,
                        llm_fixable,
                        llm_retry,
                    ) = classify_failure(job_name, effective_logs, use_llm=use_llm)
                    fallback_reclassified = classification != "logs-unavailable"

            test_file = extract_test_file(effective_logs) if effective_logs else None
            fixable = is_fixable(classification, llm_fixable=llm_fixable)
            fix_conf = fix_confidence(classification, confidence)
            llm_retry_count = int(llm_retry.get("retry_count", 0)) if llm_retry else 0
            llm_retry_wait_s = round(float(llm_retry.get("retry_wait_s", 0.0)), 3) if llm_retry else 0.0
            llm_retry_after_seen = bool(llm_retry.get("retry_after_seen", False)) if llm_retry else False

            logs_fallback_status = fallback_meta.get("status") if fallback_meta else None
            logs_fallback_command = fallback_meta.get("command") if fallback_meta else None
            logs_fallback_artifact = fallback_meta.get("artifact_path") if fallback_meta else None
            logs_fallback_error = fallback_meta.get("error") if fallback_meta else None

            finding = {
                "runId": run_id,
                "workflow": run.get("name", ""),
                "job": job_name,
                "created": run.get("createdAt", ""),
                "classification": classification,
                "description": description,
                "confidence": confidence,
                "fix_confidence": fix_conf,
                "fixable": fixable,
                "llm_fixable": llm_fixable,
                "fix_hint": fix_hint,
                "llm_retry_count": llm_retry_count,
                "llm_retry_wait_s": llm_retry_wait_s,
                "llm_retry_after_seen": llm_retry_after_seen,
                "test_file": test_file,
                "log_snippet": effective_logs[-500:] if effective_logs else None,
                "logs_fallback_attempted": fallback_meta is not None,
                "logs_fallback_status": logs_fallback_status,
                "logs_fallback_artifact": logs_fallback_artifact,
                "logs_fallback_command": logs_fallback_command,
                "logs_fallback_error": logs_fallback_error,
                "logs_fallback_reclassified": fallback_reclassified,
            }
            new_failures.append(finding)

            if apply:
                tracker_entry = {
                    "runId": run_id,
                    "name": run.get("name", ""),
                    "job": job_name,
                    "created": run.get("createdAt", ""),
                    "cause": description,
                    "status": "auto-detected",
                    "classification": classification,
                    "confidence": confidence,
                    "fix_confidence": fix_conf,
                    "fixable": fixable,
                    "llm_fixable": llm_fixable,
                    "fix_hint": fix_hint,
                    "llm_retry_count": llm_retry_count,
                    "llm_retry_wait_s": llm_retry_wait_s,
                    "llm_retry_after_seen": llm_retry_after_seen,
                    "test_file": test_file,
                    "logs_fallback_attempted": fallback_meta is not None,
                    "logs_fallback_status": logs_fallback_status,
                    "logs_fallback_artifact": logs_fallback_artifact,
                    "logs_fallback_command": logs_fallback_command,
                    "logs_fallback_error": logs_fallback_error,
                    "logs_fallback_reclassified": fallback_reclassified,
                    "detected_at": datetime.now(timezone.utc).isoformat(),
                }
                tracker["investigated"].append(tracker_entry)

    if apply:
        scanned_at = datetime.now(timezone.utc).isoformat()
        llm_retry_telemetry = get_llm_retry_telemetry()

        scan_record = {
            "scanned_at": scanned_at,
            "new_failures": len(new_failures),
            "llm_retry_telemetry": llm_retry_telemetry,
        }

        scan_history = tracker.get("scan_history")
        if not isinstance(scan_history, list):
            scan_history = []
        scan_history.append(scan_record)
        if len(scan_history) > SCAN_HISTORY_MAX:
            scan_history = scan_history[-SCAN_HISTORY_MAX:]
        tracker["scan_history"] = scan_history

        llm_retry_escalation = evaluate_retry_escalation(get_retry_samples(tracker))

        tracker["last_scan"] = {
            **scan_record,
            "llm_retry_escalation": llm_retry_escalation,
        }
        save_tracker(tracker)

    return new_failures


def main() -> None:
    import argparse
    ap = argparse.ArgumentParser(description="Detect and classify flaky CI failures on unstable")
    ap.add_argument("--apply", action="store_true", help="Update tracker with findings")
    ap.add_argument("--no-llm", action="store_true", help="Skip LLM fallback classification")
    args = ap.parse_args()

    findings = scan(apply=args.apply, use_llm=not args.no_llm)
    llm_retry_telemetry = get_llm_retry_telemetry()

    tracker = load_tracker()
    retry_samples = get_retry_samples(tracker)
    if not args.apply:
        retry_samples.append({
            "scanned_at": datetime.now(timezone.utc).isoformat(),
            "retry_count": llm_retry_telemetry["retry_count"],
            "retry_wait_s": llm_retry_telemetry["retry_wait_s"],
            "retry_after_seen": llm_retry_telemetry["retry_after_seen"],
        })
    llm_retry_escalation = evaluate_retry_escalation(retry_samples)

    if not findings:
        print(json.dumps({
            "status": "clean",
            "message": "No new failures on unstable",
            "llm_retry_count": llm_retry_telemetry["retry_count"],
            "llm_retry_wait_s": llm_retry_telemetry["retry_wait_s"],
            "llm_retry_after_seen": llm_retry_telemetry["retry_after_seen"],
            "llm_retry_telemetry": llm_retry_telemetry,
            "llm_retry_escalation": llm_retry_escalation,
        }, indent=2))
        return

    actionable = [f for f in findings if f["fixable"]]
    skipped = [f for f in findings if not f["fixable"]]
    masking_risk = [f for f in actionable if f.get("fix_confidence") == "masking-risk"]

    output = {
        "status": "failures_found",
        "total": len(findings),
        "actionable": len(actionable),
        "masking_risk_count": len(masking_risk),
        "skipped": len(skipped),
        "llm_retry_count": llm_retry_telemetry["retry_count"],
        "llm_retry_wait_s": llm_retry_telemetry["retry_wait_s"],
        "llm_retry_after_seen": llm_retry_telemetry["retry_after_seen"],
        "llm_retry_telemetry": llm_retry_telemetry,
        "llm_retry_escalation": llm_retry_escalation,
        "findings": findings,
    }
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()

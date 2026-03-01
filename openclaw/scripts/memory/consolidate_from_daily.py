#!/usr/bin/env python3
"""Phase 2.5 memory consolidation (stateful + LLM extraction).

Features:
- Structured memory state file: bank/state.json
- Validity tracking: valid_from / valid_until
- Supersedes chains for updated facts/decisions/preferences
- Importance scoring
- Deduplication + contradiction handling
- Regenerates bank/*.md views from active state
- Optional LLM extraction (auto/llm/heuristic modes)

Default mode is DRY-RUN; pass --apply to persist changes.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

WORKSPACE = Path(__file__).resolve().parents[2]
MEMORY_DIR = WORKSPACE / "memory"
BANK_DIR = WORKSPACE / "bank"
STATE_PATH = BANK_DIR / "state.json"

OPENAI_BASE_URL = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
MEMORY_LLM_MODEL = os.environ.get("MEMORY_LLM_MODEL", "gpt-5.3")
MEMORY_LLM_BATCH = int(os.environ.get("MEMORY_LLM_BATCH", "60"))

KIND_TO_FILE = {
    "fact": "facts.md",
    "decision": "decisions.md",
    "preference": "preferences.md",
    "lesson": "lessons.md",
}

PREFERENCE_CUES = ["prefer", "wants", "prefers", "likes", "dislikes", "avoid", "don't want", "do not want"]
DECISION_CUES = ["decision", "decided", "we will", "we should", "rule", "policy", "prioritize", "always"]
LESSON_CUES = ["lesson", "learned", "failure mode", "mistake", "fix:", "root cause", "should have"]
FACT_CUES = [" is ", " are ", " has ", "repo", "branch", "pr #", "eip-", "works on", "focus is"]

DATE_RE = re.compile(r"(\d{4}-\d{2}-\d{2})")
PR_RE = re.compile(r"PR\s*#(\d+)", re.IGNORECASE)
EIP_RE = re.compile(r"EIP-(\d+)", re.IGNORECASE)
COMMIT_BULLET_RE = re.compile(r"^`?[0-9a-f]{7,12}`?\s+[—-]", re.IGNORECASE)
TAG_RE = re.compile(r"(PR\s*#\d+|EIP-\d+|@[A-Za-z0-9_-]+)", re.IGNORECASE)


@dataclass
class RawRecord:
    text: str
    source_path: str
    source_line: int
    valid_from: str
    project: str | None
    tags: list[str]


@dataclass
class Candidate:
    kind: str
    text: str
    source_path: str
    source_line: int
    valid_from: str
    subject: str
    importance: float
    project: str | None
    tags: list[str]


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def normalize(text: str) -> str:
    t = text.strip().lower()
    t = re.sub(r"\s+", " ", t)
    return t


def slug_hash(prefix: str, text: str, n: int = 12) -> str:
    h = hashlib.sha1(normalize(text).encode("utf-8")).hexdigest()[:n]
    return f"{prefix}:{h}"


def recent_daily_files(limit: int = 2) -> list[Path]:
    files = sorted(MEMORY_DIR.glob("20*.md"))
    return files[-limit:]


def infer_date(path: Path, text: str) -> str:
    m = DATE_RE.search(path.name)
    if m:
        return m.group(1)
    m = DATE_RE.search(text)
    if m:
        return m.group(1)
    return datetime.now(timezone.utc).date().isoformat()


def infer_project(text: str) -> str | None:
    low = text.lower()
    if "lodestar" in low:
        return "lodestar"
    if "eip-" in low or "ethereum" in low:
        return "ethereum"
    if "openclaw" in low:
        return "openclaw"
    return None


def infer_kind(text: str) -> str | None:
    low = f" {text.lower()} "
    if any(c in low for c in PREFERENCE_CUES):
        return "preference"
    if any(c in low for c in DECISION_CUES):
        return "decision"
    if any(c in low for c in LESSON_CUES):
        return "lesson"
    if any(c in low for c in FACT_CUES):
        return "fact"
    return None


def infer_subject(kind: str, text: str) -> str:
    if m := PR_RE.search(text):
        return f"pr:{m.group(1)}"
    if m := EIP_RE.search(text):
        return f"eip:{m.group(1)}"

    low = text.lower()
    if "nico" in low and kind == "preference":
        if any(w in low for w in ["concise", "summary", "updates"]):
            return "person:nico:communication-style"
        return "person:nico:preference"

    if kind == "decision":
        if "review" in low and "priority" in low:
            return "workflow:review-priority"
        if "backlog" in low:
            return "workflow:backlog-discipline"

    return slug_hash(kind, text)


def infer_importance(kind: str, text: str) -> float:
    base = {
        "fact": 0.68,
        "decision": 0.82,
        "preference": 0.80,
        "lesson": 0.74,
    }.get(kind, 0.65)

    low = text.lower()
    for token, boost in [
        ("always", 0.08),
        ("critical", 0.12),
        ("blocker", 0.12),
        ("root cause", 0.10),
        ("review comments", 0.08),
        ("lint", 0.05),
        ("pr #", 0.05),
        ("eip-", 0.04),
    ]:
        if token in low:
            base += boost

    return round(min(base, 0.98), 2)


def extract_tags(text: str) -> list[str]:
    return sorted(set(m.group(1) for m in TAG_RE.finditer(text)))


def collect_raw_records(files: list[Path]) -> list[RawRecord]:
    out: list[RawRecord] = []
    for fp in files:
        rel = str(fp.relative_to(WORKSPACE))
        lines = fp.read_text(encoding="utf-8", errors="ignore").splitlines()

        for i, raw in enumerate(lines, start=1):
            line = raw.strip()
            if not line:
                continue
            if not (line.startswith("-") or line.startswith("*") or re.match(r"^\d+\.\s", line)):
                continue

            text = re.sub(r"^(-|\*|\d+\.)\s+", "", line).strip()
            if len(text) < 45:
                continue
            if COMMIT_BULLET_RE.match(text):
                continue

            out.append(
                RawRecord(
                    text=text,
                    source_path=rel,
                    source_line=i,
                    valid_from=f"{infer_date(fp, text)}T00:00:00+00:00",
                    project=infer_project(text),
                    tags=extract_tags(text),
                )
            )
    return out


def heuristic_candidates(records: list[RawRecord]) -> list[Candidate]:
    out: list[Candidate] = []
    for r in records:
        kind = infer_kind(r.text)
        if not kind:
            continue

        out.append(
            Candidate(
                kind=kind,
                text=r.text,
                source_path=r.source_path,
                source_line=r.source_line,
                valid_from=r.valid_from,
                subject=infer_subject(kind, r.text),
                importance=infer_importance(kind, r.text),
                project=r.project,
                tags=r.tags,
            )
        )
    return out


def chunked(seq: list[Any], size: int) -> list[list[Any]]:
    return [seq[i : i + size] for i in range(0, len(seq), size)]


def extract_json_block(text: str) -> str:
    t = text.strip()
    if t.startswith("```"):
        t = re.sub(r"^```(?:json)?\s*", "", t)
        t = re.sub(r"\s*```$", "", t)
    return t.strip()


def openai_chat_json(messages: list[dict[str, str]], model: str) -> str:
    payload = {
        "model": model,
        "temperature": 0,
        "messages": messages,
        "response_format": {"type": "json_object"},
    }
    req = urllib.request.Request(
        f"{OPENAI_BASE_URL}/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {OPENAI_API_KEY}",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        body = json.loads(resp.read().decode("utf-8"))
    return body["choices"][0]["message"]["content"]


def llm_candidates(records: list[RawRecord], model: str) -> tuple[list[Candidate], int]:
    """Return (candidates, failed_batch_count)."""
    if not OPENAI_API_KEY:
        return [], 0

    all_candidates: list[Candidate] = []
    failed_batches = 0

    for batch in chunked(records, MEMORY_LLM_BATCH):
        numbered = []
        for idx, r in enumerate(batch):
            numbered.append(
                {
                    "idx": idx,
                    "text": r.text,
                    "project_hint": r.project,
                    "tags": r.tags,
                    "source": f"{r.source_path}:{r.source_line}",
                    "date": r.valid_from[:10],
                }
            )

        system_prompt = (
            "You are a memory extraction classifier for Lodekeeper, an AI engineering assistant "
            "working on Lodestar (Ethereum consensus client). Your job is to extract DURABLE memories "
            "that will be useful weeks or months from now.\n\n"
            "Kinds:\n"
            "- fact: Durable technical truth (architecture, behavior, config). NOT ephemeral status.\n"
            "- decision: Explicit choice with rationale that affects future work.\n"
            "- preference: How someone (Nico, the team) wants things done.\n"
            "- lesson: Hard-won insight from a mistake or debugging session.\n\n"
            "SKIP (do not extract):\n"
            "- Status updates ('PR merged', 'CI green', 'task done')\n"
            "- Commit hashes, build logs, or one-time debugging steps\n"
            "- Tool/infra notes only relevant during a single session\n"
            "- Anything with importance < 0.55 (not worth remembering)\n"
            "- Narrow implementation details unlikely to recur\n\n"
            "Quality bar: Would future-me benefit from finding this in 2 weeks? "
            "If not, skip it.\n\n"
            "For 'text': rewrite into a clean, self-contained statement. "
            "Remove markdown bold/links. Keep it concise but complete.\n\n"
            "For 'subject': use a stable identifier like 'pr:8968', 'eip:7782', "
            "'person:nico:communication-style', 'workflow:review-priority', "
            "'tool:codex-cli', 'lodestar:fork-choice', etc.\n\n"
            "For 'importance': 0.55-0.70 = nice to know, 0.70-0.85 = important, "
            "0.85-0.95 = critical/blocking, 0.95+ = must never forget.\n\n"
            "Return strict JSON: {\"items\": [{idx, kind, text, subject, importance, project, tags}]}"
        )
        user_prompt = (
            "Extract durable memories from these daily note bullets. "
            "Be selective — quality over quantity. Skip anything ephemeral.\n\n"
            f"Candidates:\n{json.dumps(numbered, ensure_ascii=False)}"
        )

        try:
            content = openai_chat_json(
                [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                model,
            )
            parsed = json.loads(extract_json_block(content))
            items = parsed.get("items", []) if isinstance(parsed, dict) else []

            for item in items:
                try:
                    idx = int(item["idx"])
                    if idx < 0 or idx >= len(batch):
                        continue
                    r = batch[idx]

                    kind = str(item.get("kind", "")).strip().lower()
                    if kind not in {"fact", "decision", "preference", "lesson"}:
                        continue

                    text = str(item.get("text") or r.text).strip()
                    if len(text) < 20:
                        continue

                    subject = str(item.get("subject") or "").strip() or infer_subject(kind, text)
                    imp_raw = item.get("importance")
                    try:
                        importance = float(imp_raw)
                    except Exception:
                        importance = infer_importance(kind, text)
                    importance = max(0.0, min(0.99, round(importance, 2)))

                    project = item.get("project") or r.project
                    project = str(project).lower() if project else None
                    tags = item.get("tags") if isinstance(item.get("tags"), list) else r.tags
                    tags = sorted(set([str(t) for t in tags if str(t).strip()]))

                    all_candidates.append(
                        Candidate(
                            kind=kind,
                            text=text,
                            source_path=r.source_path,
                            source_line=r.source_line,
                            valid_from=r.valid_from,
                            subject=subject,
                            importance=importance,
                            project=project,
                            tags=tags,
                        )
                    )
                except Exception:
                    continue

        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError):
            failed_batches += 1

    return all_candidates, failed_batches


def preprocess_candidates(candidates: list[Candidate]) -> list[Candidate]:
    """Reduce churn:
    - For fact/decision/preference keep only latest candidate per subject in this batch.
    - Keep lessons as unique-by-text.
    """
    if not candidates:
        return []

    ordered = sorted(candidates, key=lambda c: (c.valid_from, c.source_path, c.source_line))

    latest_by_subject: dict[tuple[str, str], Candidate] = {}
    lessons: list[Candidate] = []
    seen_lesson_norm: set[str] = set()

    for c in ordered:
        if c.kind in {"fact", "decision", "preference"}:
            latest_by_subject[(c.kind, c.subject)] = c
        else:
            n = normalize(c.text)
            if n not in seen_lesson_norm:
                seen_lesson_norm.add(n)
                lessons.append(c)

    reduced = list(latest_by_subject.values()) + lessons
    reduced.sort(key=lambda c: (c.valid_from, c.source_path, c.source_line))
    return reduced


def parse_existing_bank_bullets(path: Path) -> list[str]:
    if not path.exists():
        return []
    lines = []
    for raw in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw.strip()
        if line.startswith("-"):
            text = re.sub(r"^-\s+", "", line).strip()
            # Strip optional metadata prefix from generated views
            text = re.sub(r"^\([^)]*\)\s*", "", text).strip()
            if text:
                lines.append(text)
    return lines


def bootstrap_state() -> dict[str, Any]:
    entries: list[dict[str, Any]] = []
    ts = now_iso()

    for kind, fname in KIND_TO_FILE.items():
        for text in parse_existing_bank_bullets(BANK_DIR / fname):
            entry_id = slug_hash("entry", f"{kind}|{text}", 16)
            entries.append(
                {
                    "id": entry_id,
                    "kind": kind,
                    "text": text,
                    "subject": infer_subject(kind, text),
                    "importance": infer_importance(kind, text),
                    "project": infer_project(text),
                    "tags": extract_tags(text),
                    "status": "active",
                    "valid_from": ts,
                    "valid_until": None,
                    "supersedes": None,
                    "superseded_by": None,
                    "source_path": str((BANK_DIR / fname).relative_to(WORKSPACE)),
                    "source_line": 0,
                    "created_at": ts,
                    "updated_at": ts,
                }
            )

    return {"version": 3, "entries": entries, "updated_at": ts}


def load_state() -> dict[str, Any]:
    if STATE_PATH.exists():
        try:
            data = json.loads(STATE_PATH.read_text(encoding="utf-8"))
            if isinstance(data, dict) and isinstance(data.get("entries"), list):
                return data
        except Exception:
            pass
    return bootstrap_state()


def save_state(state: dict[str, Any]) -> None:
    state["updated_at"] = now_iso()
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(state, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def dedupe_state_entries(state: dict[str, Any]) -> int:
    entries: list[dict[str, Any]] = state.get("entries", [])
    if not entries:
        return 0

    # Keep newest copy for each entry id first.
    ordered = sorted(entries, key=lambda e: (e.get("updated_at", ""), e.get("created_at", "")), reverse=True)
    by_id: dict[str, dict[str, Any]] = {}
    no_id: list[dict[str, Any]] = []
    for e in ordered:
        entry_id = e.get("id")
        if entry_id:
            by_id.setdefault(str(entry_id), e)
        else:
            no_id.append(e)

    merged = list(by_id.values()) + no_id

    # Secondary dedupe by semantic identity.
    merged_sorted = sorted(merged, key=lambda e: (e.get("updated_at", ""), e.get("created_at", "")), reverse=True)
    seen: set[tuple[str, str, str, str, str, str]] = set()
    deduped: list[dict[str, Any]] = []

    for e in merged_sorted:
        key = (
            str(e.get("kind", "")),
            str(e.get("subject", "")),
            normalize(str(e.get("text", ""))),
            str(e.get("status", "")),
            str(e.get("valid_from", "")),
            str(e.get("valid_until", "")),
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(e)

    deduped.reverse()
    removed = len(entries) - len(deduped)
    if removed > 0:
        state["entries"] = deduped
    return removed


def apply_candidates(state: dict[str, Any], candidates: list[Candidate]) -> tuple[int, int, int]:
    entries: list[dict[str, Any]] = state["entries"]

    active_by_kind_subject: dict[tuple[str, str], dict[str, Any]] = {}
    any_norm: set[tuple[str, str]] = set()  # includes active + superseded to avoid re-adding same text forever

    for e in entries:
        kind = e.get("kind")
        txt = normalize(e.get("text", ""))
        if kind and txt:
            any_norm.add((kind, txt))
        if e.get("status") == "active":
            active_by_kind_subject[(e.get("kind"), e.get("subject"))] = e

    added = 0
    superseded = 0
    skipped = 0

    for c in candidates:
        norm_key = (c.kind, normalize(c.text))
        if norm_key in any_norm:
            skipped += 1
            continue

        now = now_iso()
        entry_id = slug_hash("entry", f"{c.kind}|{c.subject}|{c.text}|{c.source_path}:{c.source_line}", 20)

        previous = active_by_kind_subject.get((c.kind, c.subject))
        supersedes_id = None
        if previous and normalize(previous.get("text", "")) != normalize(c.text) and c.kind in {"fact", "decision", "preference"}:
            previous["status"] = "superseded"
            previous["valid_until"] = now
            previous["superseded_by"] = entry_id
            previous["updated_at"] = now
            superseded += 1
            supersedes_id = previous.get("id")

        new_entry = {
            "id": entry_id,
            "kind": c.kind,
            "text": c.text,
            "subject": c.subject,
            "importance": c.importance,
            "project": c.project,
            "tags": c.tags,
            "status": "active",
            "valid_from": c.valid_from,
            "valid_until": None,
            "supersedes": supersedes_id,
            "superseded_by": None,
            "source_path": c.source_path,
            "source_line": c.source_line,
            "created_at": now,
            "updated_at": now,
        }
        entries.append(new_entry)
        active_by_kind_subject[(c.kind, c.subject)] = new_entry
        any_norm.add(norm_key)
        added += 1

    return added, superseded, skipped


def render_bank_views(state: dict[str, Any]) -> None:
    entries: list[dict[str, Any]] = state["entries"]

    for kind, fname in KIND_TO_FILE.items():
        out = [f"# {fname.split('.')[0].replace('-', ' ').title()}\n", "\n"]
        active = [e for e in entries if e.get("kind") == kind and e.get("status") == "active"]
        active.sort(key=lambda e: (e.get("importance", 0.0), e.get("valid_from", "")), reverse=True)

        for e in active:
            date = str(e.get("valid_from", ""))[:10]
            imp = e.get("importance", 0.0)
            subj = e.get("subject", "")
            out.append(f"- ({date} | imp={imp:.2f} | subject={subj}) {e.get('text', '').strip()}\n")

        (BANK_DIR / fname).write_text("".join(out), encoding="utf-8")


def run(limit: int, apply: bool, mode: str) -> None:
    files = recent_daily_files(limit)
    if not files:
        print("No daily files found.")
        return

    state = load_state()
    removed_dupes = dedupe_state_entries(state)
    records = collect_raw_records(files)

    extraction_mode = mode
    if mode == "auto":
        extraction_mode = "llm" if OPENAI_API_KEY else "heuristic"

    llm_failed_batches = 0
    if extraction_mode == "llm":
        candidates_raw, llm_failed_batches = llm_candidates(records, MEMORY_LLM_MODEL)
        if llm_failed_batches > 0:
            # fallback for reliability
            fallback = heuristic_candidates(records)
            # merge w/o duplicates by normalized (kind,text)
            seen = {(c.kind, normalize(c.text)) for c in candidates_raw}
            for c in fallback:
                k = (c.kind, normalize(c.text))
                if k not in seen:
                    seen.add(k)
                    candidates_raw.append(c)
    else:
        candidates_raw = heuristic_candidates(records)

    candidates = preprocess_candidates(candidates_raw)

    mode_label = f"{mode} -> {extraction_mode}" if mode == "auto" else mode
    print(f"Consolidation mode: {'APPLY' if apply else 'DRY-RUN'}")
    print(f"Extraction mode: {mode_label}")
    if extraction_mode == "llm":
        print(f"LLM model: {MEMORY_LLM_MODEL}")
        if llm_failed_batches:
            print(f"LLM failed batches: {llm_failed_batches} (heuristic fallback merged)")

    print(f"Daily files scanned: {len(files)}")
    print(f"Raw bullet records: {len(records)}")
    print(f"Candidates extracted: {len(candidates_raw)}")
    print(f"Candidates after preprocessing: {len(candidates)}")
    if removed_dupes:
        print(f"State duplicate entries pruned: {removed_dupes}")

    if not apply:
        by_kind: dict[str, list[Candidate]] = {"fact": [], "decision": [], "preference": [], "lesson": []}
        for c in candidates:
            by_kind[c.kind].append(c)
        for kind, items in by_kind.items():
            print(f"{kind}: {len(items)} candidates")
            for c in items[:3]:
                print(f"  - ({c.valid_from[:10]} | imp={c.importance:.2f} | subject={c.subject}) {c.text}")
        print("Dry-run complete. Re-run with --apply to persist.")
        return

    added, superseded, skipped = apply_candidates(state, candidates)
    save_state(state)
    render_bank_views(state)

    print(f"Added: {added}")
    print(f"Superseded: {superseded}")
    print(f"Skipped duplicates: {skipped}")
    print(f"State saved: {STATE_PATH}")
    print("Bank views regenerated.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=2, help="Number of latest daily files to scan")
    ap.add_argument("--apply", action="store_true", help="Persist state + regenerate bank views")
    ap.add_argument(
        "--mode",
        choices=["auto", "heuristic", "llm"],
        default="auto",
        help="Extraction mode: auto (llm if API key else heuristic), heuristic, llm",
    )
    args = ap.parse_args()
    run(args.limit, args.apply, args.mode)

#!/usr/bin/env python3
"""Rebuild local memory index from workspace sources.

Source of truth:
- markdown files (workspace/memory + core files + entities)
- bank/state.json (phase 2 structured memory state)

Derived index:
- ~/.openclaw/workspace/.memory/index.sqlite

Phase 2 additions:
- entry_key per row (stable identifier for access metrics)
- persistent access_metrics table (not dropped on rebuild)
"""
from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

WORKSPACE = Path(__file__).resolve().parents[2]
INDEX_DIR = WORKSPACE / ".memory"
INDEX_PATH = INDEX_DIR / "index.sqlite"
STATE_PATH = WORKSPACE / "bank" / "state.json"

DATE_RE = re.compile(r"(\d{4}-\d{2}-\d{2})")
TAG_RE = re.compile(r"(PR\s*#\d+|EIP-\d+|@[A-Za-z0-9_-]+)", re.IGNORECASE)


def should_skip_markdown(path: Path) -> bool:
    # If structured state exists, skip generated bank views to avoid duplicate indexing.
    if STATE_PATH.exists() and path.parent == WORKSPACE / "bank" and path.name in {
        "facts.md",
        "decisions.md",
        "preferences.md",
        "lessons.md",
    }:
        return True
    return False


def markdown_sources() -> list[Path]:
    files: list[Path] = []
    for p in [WORKSPACE / "MEMORY.md", WORKSPACE / "SOUL.md", WORKSPACE / "USER.md", WORKSPACE / "BACKLOG.md"]:
        if p.exists() and not should_skip_markdown(p):
            files.append(p)

    memory_dir = WORKSPACE / "memory"
    if memory_dir.exists():
        files.extend(sorted(p for p in memory_dir.glob("*.md") if not should_skip_markdown(p)))

    bank_dir = WORKSPACE / "bank"
    if bank_dir.exists():
        files.extend(sorted(p for p in bank_dir.rglob("*.md") if not should_skip_markdown(p)))

    seen: set[str] = set()
    out: list[Path] = []
    for f in files:
        key = str(f.resolve())
        if key not in seen:
            seen.add(key)
            out.append(f)
    return out


def infer_kind(path: Path) -> str:
    rel = path.relative_to(WORKSPACE)
    s = str(rel)
    if s.startswith("memory/"):
        return "daily"
    if s.startswith("bank/entities/"):
        return "entity"
    if s.startswith("bank/"):
        stem = path.stem.lower()
        if stem in {"facts", "decisions", "preferences", "lessons"}:
            return stem[:-1] if stem.endswith("s") else stem
        return "bank"
    if path.name == "MEMORY.md":
        return "core"
    if path.name == "BACKLOG.md":
        return "task"
    return "meta"


def infer_entity(path: Path) -> tuple[str | None, str | None]:
    rel = path.relative_to(WORKSPACE)
    parts = rel.parts
    if len(parts) >= 4 and parts[0] == "bank" and parts[1] == "entities":
        return parts[2], path.stem
    return None, None


def infer_project(text: str) -> str | None:
    t = text.lower()
    if "lodestar" in t:
        return "lodestar"
    if "eip-" in t or "ethereum" in t:
        return "ethereum"
    if "openclaw" in t:
        return "openclaw"
    return None


def infer_date(path: Path, text: str) -> str | None:
    m = DATE_RE.search(path.name)
    if m:
        return m.group(1)
    m = DATE_RE.search(text)
    if m:
        return m.group(1)
    return None


def stable_key(*parts: str) -> str:
    raw = "|".join(parts)
    h = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:20]
    return h


def markdown_records(path: Path) -> list[tuple[Any, ...]]:
    records: list[tuple[Any, ...]] = []
    section = ""
    kind = infer_kind(path)
    entity_type, entity_slug = infer_entity(path)
    rel_path = str(path.relative_to(WORKSPACE))

    try:
        lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    except Exception:
        return records

    for i, raw in enumerate(lines, start=1):
        line = raw.strip()
        if not line:
            continue
        if line.startswith("#"):
            section = line.lstrip("#").strip()
            continue

        is_bullet = line.startswith("- ") or line.startswith("* ") or re.match(r"^\d+\.\s", line)
        if not is_bullet and len(line) < 28:
            continue

        text = re.sub(r"^(-|\*|\d+\.)\s+", "", line).strip()
        tags = ",".join(sorted(set(m.group(1) for m in TAG_RE.finditer(text))))
        project = infer_project(text)
        date = infer_date(path, text)
        importance = 0.55
        entry_key = f"md:{stable_key(rel_path, str(i), kind, text)}"

        records.append(
            (
                rel_path,
                i,
                section,
                text,
                kind,
                entity_type,
                entity_slug,
                date,
                project,
                tags,
                None,  # subject
                importance,
                "active",
                f"{date}T00:00:00+00:00" if date else None,
                None,
                None,
                entry_key,
            )
        )

    return records


def state_records() -> list[tuple[Any, ...]]:
    if not STATE_PATH.exists():
        return []

    try:
        data = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return []

    entries = data.get("entries", [])
    out: list[tuple[Any, ...]] = []

    for e in entries:
        text = str(e.get("text", "")).strip()
        if not text:
            continue

        path = str(e.get("source_path") or "bank/state.json")
        line_no = int(e.get("source_line") or 0)
        kind = str(e.get("kind") or "fact")
        subject = e.get("subject")
        importance = float(e.get("importance") or 0.6)
        status = str(e.get("status") or "active")
        valid_from = e.get("valid_from")
        valid_until = e.get("valid_until")
        supersedes = e.get("supersedes")
        project = e.get("project") or infer_project(text)
        tags = ",".join(e.get("tags") or [])
        date = valid_from[:10] if isinstance(valid_from, str) and len(valid_from) >= 10 else None

        entity_type = None
        entity_slug = None
        if isinstance(subject, str) and subject.startswith("pr:"):
            entity_type = "prs"
            entity_slug = subject.split(":", 1)[1]

        entry_key = f"state:{e.get('id') or stable_key(kind, str(subject), text)}"

        out.append(
            (
                path,
                line_no,
                str(subject or ""),
                text,
                kind,
                entity_type,
                entity_slug,
                date,
                project,
                tags,
                subject,
                importance,
                status,
                valid_from,
                valid_until,
                supersedes,
                entry_key,
            )
        )

    return out


def rebuild() -> None:
    INDEX_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(INDEX_PATH)
    cur = conn.cursor()

    # Keep access_metrics across rebuilds.
    cur.executescript(
        """
        CREATE TABLE IF NOT EXISTS access_metrics (
            entry_key TEXT PRIMARY KEY,
            access_count INTEGER NOT NULL DEFAULT 0,
            last_accessed TEXT
        );
        """
    )

    cur.executescript(
        """
        DROP TABLE IF EXISTS docs_fts;
        DROP TABLE IF EXISTS documents;

        CREATE TABLE documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            path TEXT NOT NULL,
            line_no INTEGER NOT NULL,
            section TEXT,
            text TEXT NOT NULL,
            kind TEXT,
            entity_type TEXT,
            entity_slug TEXT,
            date TEXT,
            project TEXT,
            tags TEXT,
            subject TEXT,
            importance REAL DEFAULT 0.5,
            status TEXT DEFAULT 'active',
            valid_from TEXT,
            valid_until TEXT,
            supersedes TEXT,
            entry_key TEXT,
            indexed_at TEXT NOT NULL
        );

        CREATE VIRTUAL TABLE docs_fts USING fts5(
            text,
            content='documents',
            content_rowid='id'
        );

        CREATE INDEX idx_documents_kind ON documents(kind);
        CREATE INDEX idx_documents_date ON documents(date);
        CREATE INDEX idx_documents_project ON documents(project);
        CREATE INDEX idx_documents_status ON documents(status);
        CREATE INDEX idx_documents_subject ON documents(subject);
        CREATE INDEX idx_documents_importance ON documents(importance);
        CREATE INDEX idx_documents_entry_key ON documents(entry_key);
        """
    )

    now = datetime.now(timezone.utc).isoformat()
    total = 0

    md_sources = markdown_sources()
    for path in md_sources:
        for rec in markdown_records(path):
            cur.execute(
                """
                INSERT INTO documents
                (path, line_no, section, text, kind, entity_type, entity_slug, date, project, tags,
                 subject, importance, status, valid_from, valid_until, supersedes, entry_key, indexed_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (*rec, now),
            )
            total += 1

    state_recs = state_records()
    for rec in state_recs:
        cur.execute(
            """
            INSERT INTO documents
            (path, line_no, section, text, kind, entity_type, entity_slug, date, project, tags,
             subject, importance, status, valid_from, valid_until, supersedes, entry_key, indexed_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (*rec, now),
        )
        total += 1

    cur.execute("INSERT INTO docs_fts(rowid, text) SELECT id, text FROM documents")
    conn.commit()

    print(
        f"Indexed {total} records (markdown files: {len(md_sources)}, state entries: {len(state_recs)}) -> {INDEX_PATH}"
    )


if __name__ == "__main__":
    rebuild()

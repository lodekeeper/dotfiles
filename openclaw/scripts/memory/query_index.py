#!/usr/bin/env python3
"""Query local memory SQLite FTS index (phase 2 aware).

Supports:
- active-only results by default
- recency + importance + access-count aware ordering
- optional inclusion of superseded/inactive entries
"""
from __future__ import annotations

import argparse
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[2]
INDEX_PATH = WORKSPACE / ".memory" / "index.sqlite"


def ensure_access_table(cur: sqlite3.Cursor) -> None:
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS access_metrics (
            entry_key TEXT PRIMARY KEY,
            access_count INTEGER NOT NULL DEFAULT 0,
            last_accessed TEXT
        )
        """
    )


def mark_accessed(cur: sqlite3.Cursor, entry_keys: list[str]) -> None:
    now = datetime.now(timezone.utc).isoformat()
    for k in entry_keys:
        if not k:
            continue
        cur.execute(
            """
            INSERT INTO access_metrics(entry_key, access_count, last_accessed)
            VALUES (?, 1, ?)
            ON CONFLICT(entry_key) DO UPDATE SET
              access_count = access_count + 1,
              last_accessed = excluded.last_accessed
            """,
            (k, now),
        )


def query(
    q: str,
    kind: str | None,
    project: str | None,
    limit: int,
    include_inactive: bool,
) -> None:
    if not INDEX_PATH.exists():
        raise SystemExit(f"Index not found: {INDEX_PATH}\nRun: python3 scripts/memory/rebuild_index.py")

    conn = sqlite3.connect(INDEX_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    ensure_access_table(cur)

    where = ["docs_fts MATCH ?"]
    params: list = [q]

    if kind:
        where.append("d.kind = ?")
        params.append(kind)
    if project:
        where.append("d.project = ?")
        params.append(project)
    if not include_inactive:
        where.append("COALESCE(d.status, 'active') = 'active'")

    # Ordering notes:
    # - active entries first
    # - lower BM25 rank first (better lexical match)
    # - higher importance
    # - more recently valid entries
    # - higher access_count (frequently useful memories)
    sql = f"""
    SELECT d.path, d.line_no, d.section, d.kind, d.project, d.tags, d.text,
           d.status, d.importance, d.subject, d.valid_from, d.valid_until,
           d.entry_key, COALESCE(am.access_count, 0) AS access_count,
           bm25(docs_fts) AS rank
    FROM docs_fts
    JOIN documents d ON d.id = docs_fts.rowid
    LEFT JOIN access_metrics am ON am.entry_key = d.entry_key
    WHERE {' AND '.join(where)}
    ORDER BY
      CASE WHEN COALESCE(d.status, 'active') = 'active' THEN 0 ELSE 1 END,
      rank ASC,
      COALESCE(d.importance, 0) DESC,
      COALESCE(d.valid_from, d.date, '1970-01-01') DESC,
      COALESCE(am.access_count, 0) DESC
    LIMIT ?
    """
    params.append(limit)

    try:
        rows = cur.execute(sql, params).fetchall()
    except sqlite3.OperationalError:
        like_where = ["text LIKE ?"]
        like_params: list = [f"%{q}%"]
        if kind:
            like_where.append("kind = ?")
            like_params.append(kind)
        if project:
            like_where.append("project = ?")
            like_params.append(project)
        if not include_inactive:
            like_where.append("COALESCE(status, 'active') = 'active'")

        rows = cur.execute(
            f"""
            SELECT d.path, d.line_no, d.section, d.kind, d.project, d.tags, d.text,
                   d.status, d.importance, d.subject, d.valid_from, d.valid_until,
                   d.entry_key, COALESCE(am.access_count, 0) AS access_count,
                   0.0 AS rank
            FROM documents d
            LEFT JOIN access_metrics am ON am.entry_key = d.entry_key
            WHERE {' AND '.join(like_where)}
            ORDER BY
              CASE WHEN COALESCE(d.status, 'active') = 'active' THEN 0 ELSE 1 END,
              COALESCE(d.importance, 0) DESC,
              COALESCE(d.valid_from, d.date, '1970-01-01') DESC,
              COALESCE(am.access_count, 0) DESC,
              d.id DESC
            LIMIT ?
            """,
            (*like_params, limit),
        ).fetchall()

    if not rows:
        print("No matches")
        return

    entry_keys = [r["entry_key"] for r in rows if r["entry_key"]]
    mark_accessed(cur, entry_keys)
    conn.commit()

    for i, r in enumerate(rows, start=1):
        section = f" [{r['section']}]" if r['section'] else ""
        project_txt = f" project={r['project']}" if r['project'] else ""
        tags_txt = f" tags={r['tags']}" if r['tags'] else ""
        subject_txt = f" subject={r['subject']}" if r['subject'] else ""
        status_txt = f" status={r['status']}" if r['status'] and r['status'] != "active" else ""
        imp_txt = f" imp={float(r['importance']):.2f}" if r['importance'] is not None else ""
        access_txt = f" accessed={int(r['access_count'])}" if r['access_count'] is not None else ""
        print(
            f"{i}. {r['path']}:{r['line_no']}{section} kind={r['kind']}{project_txt}{tags_txt}{subject_txt}{imp_txt}{access_txt}{status_txt}"
        )
        print(f"   {r['text']}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("query", help="FTS query string (or plain text fallback)")
    ap.add_argument(
        "--kind",
        help="Filter by kind (daily, fact, decision, preference, lesson, entity, core, task, meta)",
    )
    ap.add_argument("--project", help="Filter by project")
    ap.add_argument("--limit", type=int, default=10)
    ap.add_argument("--include-inactive", action="store_true", help="Include superseded/inactive entries")
    args = ap.parse_args()

    query(args.query, args.kind, args.project, args.limit, args.include_inactive)

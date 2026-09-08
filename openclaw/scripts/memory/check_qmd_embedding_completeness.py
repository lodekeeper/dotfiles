#!/usr/bin/env python3
"""Detect partial QMD embedding coverage that `qmd embed` can miss.

QMD currently treats a content hash as embedded once `content_vectors` has
`seq=0`. If a later chunk fails, the next incremental `qmd embed` run can report
"all hashes already have embeddings" while vector search is missing the tail of
that document. This checker is read-only and flags the failure shapes we can
prove from the SQLite index without loading the embedding model.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field
import json
from pathlib import Path
import sqlite3
import sys
from typing import Any


DEFAULT_INDEX = Path.home() / ".cache" / "qmd" / "index.sqlite"
DEFAULT_MAX_TAIL_CHARS = 4096
MAX_LISTED_SEQUENCES = 16

REQUIRED_TABLES = {
    "documents",
    "content",
    "content_vectors",
}


@dataclass
class Issue:
    hash: str
    samplePath: str
    pathCount: int
    docChars: int
    embeddedChunks: int
    minSeq: int | None
    maxSeq: int | None
    maxPos: int | None
    tailChars: int | None
    reasonCodes: list[str] = field(default_factory=list)
    missingSequences: list[int] = field(default_factory=list)
    missingVectorRows: list[int] = field(default_factory=list)


class CheckError(RuntimeError):
    pass


def connect_readonly(index_path: Path) -> sqlite3.Connection:
    if not index_path.exists():
        raise CheckError(f"QMD index not found: {index_path}")

    return sqlite3.connect(f"file:{index_path}?mode=ro", uri=True)


def table_names(conn: sqlite3.Connection) -> set[str]:
    return {
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type IN ('table', 'view')"
        )
    }


def require_schema(conn: sqlite3.Connection) -> set[str]:
    names = table_names(conn)
    missing = sorted(REQUIRED_TABLES - names)
    if missing:
        raise CheckError(f"QMD index missing required table(s): {', '.join(missing)}")
    return names


def truncate_sequences(values: list[int]) -> list[int]:
    return values[:MAX_LISTED_SEQUENCES]


def active_hash_rows(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    conn.row_factory = sqlite3.Row
    return list(
        conn.execute(
            """
            SELECT
              d.hash AS hash,
              length(c.doc) AS doc_chars,
              min(d.collection || '/' || d.path) AS sample_path,
              count(*) AS path_count
            FROM documents d
            JOIN content c ON c.hash = d.hash
            WHERE d.active = 1
            GROUP BY d.hash
            ORDER BY sample_path
            """
        )
    )


def vector_rows_for_hash(conn: sqlite3.Connection, content_hash: str) -> list[sqlite3.Row]:
    return list(
        conn.execute(
            """
            SELECT seq, pos
            FROM content_vectors
            WHERE hash = ?
            ORDER BY seq
            """,
            (content_hash,),
        )
    )


def missing_vector_rowids_by_hash(conn: sqlite3.Connection, names: set[str]) -> dict[str, list[int]]:
    if "vectors_vec_rowids" not in names:
        return {}

    missing: dict[str, list[int]] = {}
    for row in conn.execute(
        """
        SELECT cv.hash AS hash, cv.seq AS seq
        FROM content_vectors cv
        JOIN documents d ON d.hash = cv.hash AND d.active = 1
        LEFT JOIN vectors_vec_rowids r ON r.id = cv.hash || '_' || cv.seq
        WHERE r.id IS NULL
        ORDER BY cv.hash, cv.seq
        """
    ):
        missing.setdefault(row["hash"], []).append(int(row["seq"]))
    return missing


def analyze_index(conn: sqlite3.Connection, *, max_tail_chars: int, limit: int) -> dict[str, Any]:
    names = require_schema(conn)
    missing_rowids = missing_vector_rowids_by_hash(conn, names)
    issues: list[Issue] = []
    active_rows = active_hash_rows(conn)

    for row in active_rows:
        content_hash = str(row["hash"])
        doc_chars = int(row["doc_chars"] or 0)
        if doc_chars <= 0:
            continue

        vectors = vector_rows_for_hash(conn, content_hash)
        seqs = sorted({int(v["seq"]) for v in vectors})
        positions = [int(v["pos"] or 0) for v in vectors]

        reason_codes: list[str] = []
        missing_sequences: list[int] = []
        max_seq = max(seqs) if seqs else None
        min_seq = min(seqs) if seqs else None
        max_pos = max(positions) if positions else None
        tail_chars = doc_chars - max_pos if max_pos is not None else doc_chars

        if not seqs:
            reason_codes.append("missing-all-content-vectors")
        elif 0 not in seqs:
            reason_codes.append("missing-seq0")

        if max_seq is not None:
            seq_set = set(seqs)
            missing_sequences = [seq for seq in range(max_seq + 1) if seq not in seq_set]
            if missing_sequences:
                reason_codes.append("missing-intermediate-sequences")

        if seqs and tail_chars > max_tail_chars:
            reason_codes.append("large-tail-after-last-vector")

        missing_vector_rows = sorted(missing_rowids.get(content_hash, []))
        if missing_vector_rows:
            reason_codes.append("missing-vector-rowid")

        if not reason_codes:
            continue

        issues.append(
            Issue(
                hash=content_hash,
                samplePath=str(row["sample_path"]),
                pathCount=int(row["path_count"] or 1),
                docChars=doc_chars,
                embeddedChunks=len(seqs),
                minSeq=min_seq,
                maxSeq=max_seq,
                maxPos=max_pos,
                tailChars=tail_chars,
                reasonCodes=reason_codes,
                missingSequences=truncate_sequences(missing_sequences),
                missingVectorRows=truncate_sequences(missing_vector_rows),
            )
        )

    limited_issues = issues[:limit]
    return {
        "ok": not issues,
        "activeHashes": len(active_rows),
        "incompleteHashes": len(issues),
        "maxTailChars": max_tail_chars,
        "issues": [issue.__dict__ for issue in limited_issues],
        "truncatedIssues": max(0, len(issues) - len(limited_issues)),
    }


def compact_seq_range(issue: dict[str, Any]) -> str:
    if issue["embeddedChunks"] == 0:
        return "0 chunks"
    return f"{issue['embeddedChunks']} chunks seq {issue['minSeq']}-{issue['maxSeq']}"


def format_text(payload: dict[str, Any]) -> str:
    if payload["ok"]:
        return (
            f"QMD_EMBEDDING_COMPLETE: {payload['activeHashes']} active content hash(es), "
            f"max_tail_chars={payload['maxTailChars']}"
        )

    lines = [
        (
            "QMD_EMBEDDING_INCOMPLETE: "
            f"{payload['incompleteHashes']} active content hash(es) have incomplete embedding coverage "
            f"(max_tail_chars={payload['maxTailChars']})"
        )
    ]
    for issue in payload["issues"]:
        lines.append(
            "- "
            f"{issue['samplePath']} [{issue['hash'][:8]}]: "
            f"{compact_seq_range(issue)}, tail_chars={issue['tailChars']}; "
            f"reasons={','.join(issue['reasonCodes'])}"
        )
    if payload["truncatedIssues"]:
        lines.append(f"- ... {payload['truncatedIssues']} more")
    return "\n".join(lines)


def run_self_test() -> int:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE documents (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          collection TEXT NOT NULL,
          path TEXT NOT NULL,
          title TEXT NOT NULL,
          hash TEXT NOT NULL,
          created_at TEXT NOT NULL,
          modified_at TEXT NOT NULL,
          active INTEGER NOT NULL DEFAULT 1
        );
        CREATE TABLE content (
          hash TEXT PRIMARY KEY,
          doc TEXT NOT NULL,
          created_at TEXT NOT NULL
        );
        CREATE TABLE content_vectors (
          hash TEXT NOT NULL,
          seq INTEGER NOT NULL DEFAULT 0,
          pos INTEGER NOT NULL DEFAULT 0,
          model TEXT NOT NULL,
          embedded_at TEXT NOT NULL,
          PRIMARY KEY (hash, seq)
        );
        CREATE TABLE vectors_vec_rowids (
          rowid INTEGER PRIMARY KEY AUTOINCREMENT,
          id TEXT UNIQUE NOT NULL,
          chunk_id INTEGER,
          chunk_offset INTEGER
        );
        """
    )

    def add_doc(content_hash: str, length: int, seq_pos: list[tuple[int, int]], rowid_seqs: list[int] | None = None) -> None:
        conn.execute(
            "INSERT INTO content(hash, doc, created_at) VALUES (?, ?, 'now')",
            (content_hash, "x" * length),
        )
        conn.execute(
            """
            INSERT INTO documents(collection, path, title, hash, created_at, modified_at, active)
            VALUES ('test', ?, ?, ?, 'now', 'now', 1)
            """,
            (f"{content_hash}.md", content_hash, content_hash),
        )
        for seq, pos in seq_pos:
            conn.execute(
                """
                INSERT INTO content_vectors(hash, seq, pos, model, embedded_at)
                VALUES (?, ?, ?, 'embeddinggemma', 'now')
                """,
                (content_hash, seq, pos),
            )
        for seq in rowid_seqs if rowid_seqs is not None else [seq for seq, _ in seq_pos]:
            conn.execute(
                "INSERT INTO vectors_vec_rowids(id, chunk_id, chunk_offset) VALUES (?, 1, 0)",
                (f"{content_hash}_{seq}",),
            )

    add_doc("complete", 2500, [(0, 0)])
    add_doc("tailgap", 12000, [(0, 0), (1, 2300)])
    add_doc("seqhole", 9000, [(0, 0), (2, 4800)])
    add_doc("norowid", 1800, [(0, 0)], rowid_seqs=[])
    add_doc("novectors", 1800, [])
    conn.commit()

    payload = analyze_index(conn, max_tail_chars=4096, limit=10)
    observed = {issue["hash"]: set(issue["reasonCodes"]) for issue in payload["issues"]}
    expected = {
        "tailgap": {"large-tail-after-last-vector"},
        "seqhole": {"missing-intermediate-sequences"},
        "norowid": {"missing-vector-rowid"},
        "novectors": {"missing-all-content-vectors"},
    }

    for content_hash, reason_codes in expected.items():
        if content_hash not in observed:
            print(f"self-test missing issue for {content_hash}", file=sys.stderr)
            return 1
        if not reason_codes.issubset(observed[content_hash]):
            print(
                f"self-test wrong reason codes for {content_hash}: {observed[content_hash]}",
                file=sys.stderr,
            )
            return 1
    if "complete" in observed:
        print("self-test falsely flagged complete hash", file=sys.stderr)
        return 1

    print("QMD_EMBEDDING_COMPLETENESS_SELF_TEST_OK")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Check QMD embedding chunk coverage")
    parser.add_argument("--index", default=str(DEFAULT_INDEX), help="Path to QMD index.sqlite")
    parser.add_argument("--max-tail-chars", type=int, default=DEFAULT_MAX_TAIL_CHARS)
    parser.add_argument("--limit", type=int, default=20, help="Maximum issues to print")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON")
    parser.add_argument("--self-test", action="store_true", help="Run built-in tests")
    args = parser.parse_args()

    if args.self_test:
        return run_self_test()

    try:
        conn = connect_readonly(Path(args.index).expanduser())
        conn.row_factory = sqlite3.Row
        payload = analyze_index(conn, max_tail_chars=args.max_tail_chars, limit=args.limit)
    except (OSError, sqlite3.Error, CheckError) as exc:
        error = {"ok": False, "error": str(exc), "index": str(args.index)}
        if args.json:
            print(json.dumps(error, sort_keys=True))
        else:
            print(f"QMD_EMBEDDING_CHECK_ERROR: {exc}", file=sys.stderr)
        return 2

    payload["index"] = str(Path(args.index).expanduser())
    if args.json:
        print(json.dumps(payload, sort_keys=True))
    else:
        print(format_text(payload))

    return 0 if payload["ok"] else 3


if __name__ == "__main__":
    raise SystemExit(main())

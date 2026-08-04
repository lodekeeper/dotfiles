#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPT = Path(__file__).with_name("list_statuses.py")

spec = importlib.util.spec_from_file_location("list_statuses", SCRIPT)
module = importlib.util.module_from_spec(spec)
assert spec is not None and spec.loader is not None
sys.modules[spec.name] = module
spec.loader.exec_module(module)

sample = """# BACKLOG.md - Task Backlog

## 📌 General (no topic)

### 🟡 First task
- **Status:** In progress
- note

### ✅ Done task
- **Status:** Done

### 🟡 Yellow done task
- **Status:** Done — completed from a yellow-priority entry

## 📌 Other section [topic:51]

### 🔴 Another task
- **Status:** Blocked
"""

tasks = module.parse_backlog(sample)
assert len(tasks) == 4, f"expected 4 tasks, got {len(tasks)}"
assert tasks[0].section == "## 📌 General (no topic)"
assert tasks[0].heading == "### 🟡 First task"
assert tasks[0].status == "In progress"
assert tasks[1].heading == "### ✅ Done task"
assert module.is_done(tasks[2])
assert tasks[3].section == "## 📌 Other section [topic:51]"
assert tasks[3].status == "Blocked"
assert [t.heading for t in tasks if not module.is_done(t)] == [
    "### 🟡 First task",
    "### 🔴 Another task",
]
assert module.has_corruption_guard("> ⛔ **DO NOT ACT ON THIS FILE — CORRUPTED / UNDER RECOVERY**\n\n### task")
assert module.has_corruption_guard("> **⚠️ DO NOT ACT ON ENTRIES BELOW WITHOUT VERIFYING FIRST.**\n\n### task")
assert not module.has_corruption_guard(sample)

with tempfile.TemporaryDirectory() as tmp:
    unguarded = Path(tmp) / "unguarded.md"
    guarded = Path(tmp) / "guarded.md"
    unguarded.write_text(sample)
    guarded.write_text("> **⚠️ DO NOT ACT ON ENTRIES BELOW WITHOUT VERIFYING FIRST.**\n\n" + sample)

    missing_guard = subprocess.run(
        [sys.executable, str(SCRIPT), "--file", str(unguarded), "--require-corruption-guard"],
        text=True,
        capture_output=True,
        check=False,
    )
    assert missing_guard.returncode == 3, missing_guard
    assert "missing the corruption/recovery guard" in missing_guard.stderr

    guarded_refusal = subprocess.run(
        [sys.executable, str(SCRIPT), "--file", str(guarded), "--require-corruption-guard"],
        text=True,
        capture_output=True,
        check=False,
    )
    assert guarded_refusal.returncode == 2, guarded_refusal
    assert "marked corrupted/under recovery" in guarded_refusal.stderr

    allowed_guarded = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--file",
            str(guarded),
            "--require-corruption-guard",
            "--allow-corrupted-backlog",
            "--active-only",
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    assert allowed_guarded.returncode == 0, allowed_guarded
    assert "### 🟡 First task" in allowed_guarded.stdout
print("OK: list_statuses parser handles ## sections + ### tasks without stalling")

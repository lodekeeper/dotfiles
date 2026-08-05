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

### 🟡 Missing status task
- note

### ✅ Done task
- **Status:** Done

### 🟡 Yellow done task
- **Status:** Done — completed from a yellow-priority entry

### 🟢 Low-priority active task
- **Status:** In progress

### 🟡 Passive task
- **Status:** Passive watch — awaiting a fresh signal

## 📌 Other section [topic:51]

### 🔴 Another task
- **Status:** Blocked
"""

tasks = module.parse_backlog(sample)
assert len(tasks) == 7, f"expected 7 tasks, got {len(tasks)}"
assert tasks[0].section == "## 📌 General (no topic)"
assert tasks[0].heading == "### 🟡 First task"
assert tasks[0].status == "In progress"
assert tasks[1].heading == "### 🟡 Missing status task"
assert tasks[1].status is None
assert tasks[2].heading == "### ✅ Done task"
assert module.is_done(tasks[3])
assert not module.is_done(tasks[4])
assert module.is_actionable(tasks[4])
assert not module.is_actionable(tasks[5])
assert tasks[6].section == "## 📌 Other section [topic:51]"
assert tasks[6].status == "Blocked"
assert [t.heading for t in tasks if not module.is_done(t)] == [
    "### 🟡 First task",
    "### 🟡 Missing status task",
    "### 🟢 Low-priority active task",
    "### 🟡 Passive task",
    "### 🔴 Another task",
]
assert [t.heading for t in tasks if module.is_actionable(t)] == [
    "### 🟡 First task",
    "### 🟡 Missing status task",
    "### 🟢 Low-priority active task",
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

    actionable_guarded = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--file",
            str(guarded),
            "--require-corruption-guard",
            "--allow-corrupted-backlog",
            "--actionable-only",
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    assert actionable_guarded.returncode == 0, actionable_guarded
    assert "### 🟡 First task" in actionable_guarded.stdout
    assert "### 🟡 Missing status task" in actionable_guarded.stdout
    assert "### 🟢 Low-priority active task" in actionable_guarded.stdout
    assert "### 🟡 Passive task" not in actionable_guarded.stdout
    assert "### 🔴 Another task" not in actionable_guarded.stdout
print("OK: list_statuses parser handles ## sections + ### tasks without stalling")

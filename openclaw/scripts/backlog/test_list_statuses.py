#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import sys
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

## 📌 Other section [topic:51]

### 🔴 Another task
- **Status:** Blocked
"""

tasks = module.parse_backlog(sample)
assert len(tasks) == 3, f"expected 3 tasks, got {len(tasks)}"
assert tasks[0].section == "## 📌 General (no topic)"
assert tasks[0].heading == "### 🟡 First task"
assert tasks[0].status == "In progress"
assert tasks[1].heading == "### ✅ Done task"
assert tasks[2].section == "## 📌 Other section [topic:51]"
assert tasks[2].status == "Blocked"
assert [t.heading for t in tasks if not module.is_done(t)] == [
    "### 🟡 First task",
    "### 🔴 Another task",
]
print("OK: list_statuses parser handles ## sections + ### tasks without stalling")

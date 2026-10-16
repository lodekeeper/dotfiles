#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
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
h2_sample = """## 🔴 Urgent h2 task (no topic)
- **Source:** chat
- **Status:** 🔄 In progress — still running

## 🟢 Done h2 task (no topic)
- **Status:** ✅ Done — finished

## 📌 Plain section
- 🟢 ✅ **Inline bullet item** — DONE

### 🟡 Child task
- **Status:** Awaiting review
"""

h2_tasks = module.parse_backlog(h2_sample)
assert [t.heading for t in h2_tasks] == [
    "## 🔴 Urgent h2 task (no topic)",
    "## 🟢 Done h2 task (no topic)",
    "### 🟡 Child task",
], [t.heading for t in h2_tasks]
assert h2_tasks[0].section == "## 🔴 Urgent h2 task (no topic)"
assert h2_tasks[0].status == "🔄 In progress — still running"
assert module.is_actionable(h2_tasks[0])
assert module.is_done(h2_tasks[1])
assert h2_tasks[2].section == "## 📌 Plain section"
assert not module.is_actionable(h2_tasks[2])

prepended_tasks = (
    "### ✅ Devnet health run\n"
    "- **Status:** Done\n"
    "- endpoint evidence\n"
    "- participation evidence\n"
    "\n"
) * 3
with tempfile.TemporaryDirectory() as tmp:
    displaced = Path(tmp) / "BACKLOG.md"
    for marker in module.CORRUPTION_GUARD_MARKERS:
        displaced_text = prepended_tasks + "# BACKLOG\n\n> **⚠️ " + marker + "**\n\n" + sample
        assert next(i for i, line in enumerate(displaced_text.splitlines(), 1) if marker in line) > 12
        assert module.has_corruption_guard(displaced_text)
        displaced.write_text(displaced_text)
        for guard_args in ([], ["--require-corruption-guard"]):
            refusal = subprocess.run(
                [sys.executable, str(SCRIPT), "--file", str(displaced), *guard_args],
                text=True, capture_output=True, check=False,
            )
            assert refusal.returncode == 2, refusal
            assert refusal.stdout == "", refusal
            assert "marked corrupted/under recovery" in refusal.stderr

        audit = subprocess.run(
            [sys.executable, str(SCRIPT), "--file", str(displaced),
             "--require-corruption-guard", "--allow-corrupted-backlog", "--actionable-only"],
            text=True, capture_output=True, check=False,
        )
        assert audit.returncode == 0, audit
        assert "### 🟡 First task" in audit.stdout
        assert "### ✅ Devnet health run" not in audit.stdout

# A quoted exact warning remains fail-closed rather than treating placement as authority.
assert module.has_corruption_guard(sample + "\n- Historical warning: DO NOT ACT ON THIS FILE\n")
assert not module.has_corruption_guard(sample + "\n- Historical warning: DO NOT ACT\n")

# Scheduled entries use both plain and bold labels, on both task heading levels.
label_cases = [
    ("✅ Done — verified", True, False),
    ("Done — verified", True, False),
    ("In progress", False, True),
    ("Awaiting review", False, False),
    ("Blocked — needs owner", False, False),
    ("", False, True),
]
mixed_blocks = []
expected_active = []
expected_actionable = []
for level in ("##", "###"):
    for label in ("**Status:**", "Status:"):
        for status, done, actionable in label_cases:
            heading = f"{level} 🟢 Task {len(mixed_blocks)}"
            block = f"{heading}\n- {label} {status}\n"
            parsed = module.parse_backlog(block)
            assert len(parsed) == 1, (block, parsed)
            assert parsed[0].status == status, (block, parsed[0])
            assert module.is_done(parsed[0]) is done, (block, parsed[0])
            assert module.is_actionable(parsed[0]) is actionable, (block, parsed[0])
            mixed_blocks.append(block)
            if not done:
                expected_active.append(heading)
            if actionable:
                expected_actionable.append(heading)

for label in ("Status note:", "**Status:", "Status:**", "status:"):
    # Near-matches must not hide work by interpreting arbitrary prose as Done.
    for level in ("##", "###"):
        parsed = module.parse_backlog(f"{level} 🟢 Unrecognized\n- {label} Done\n")
        if level == "##":
            assert parsed == [], (label, parsed)
        else:
            assert len(parsed) == 1 and parsed[0].status is None, (label, parsed)

assert module.parse_backlog("### 🟢 Missing\n- note\n")[0].status is None
assert module.parse_backlog("## 🟢 Missing\n- note\n") == []
with tempfile.TemporaryDirectory() as tmp:
    mixed = Path(tmp) / "mixed.md"
    mixed_text = "\n".join(mixed_blocks)
    mixed.write_text(mixed_text)
    for flag, expected in (("--active-only", expected_active), ("--actionable-only", expected_actionable)):
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--file", str(mixed), flag, "--json"],
            text=True, capture_output=True, check=False,
        )
        assert result.returncode == 0, result
        assert [task["heading"] for task in json.loads(result.stdout)] == expected, result
        assert mixed.read_text() == mixed_text, "listing must not mutate the backlog"

print("OK: list_statuses parser handles ## sections + ### tasks without stalling")
print("OK: displaced recovery guards retain refusal and explicit-audit CLI behavior (2 marker variants)")
print("OK: bold/plain status labels preserve ##/### tasks and CLI filter results (24 cases)")

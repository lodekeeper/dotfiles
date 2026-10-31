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

# Pause decorations must not turn owner-blocked work into dispatch candidates.
# Other icons, unknown wording and completion semantics retain existing policy.
pause_cases = [
    ("⏸ Awaiting deployment owner decision", False, False),
    ("⏸️ Awaiting Nico", False, False),
    ("⏸️   aWaItInG permission", False, False),
    ("⏸Blocked — needs owner", False, False),
    ("⏸️ Passive watch", False, False),
    ("⏸ Parked", False, False),
    ("⏸️ Superseded", False, False),
    ("⏸ ⏸️ Awaiting permission", False, False),
    ("⏸ In progress", False, True),
    ("⏸️ Asked Nico for approval", False, True),
    ("⏸️", False, True),
    ("🔄 In progress", False, True),
    ("🟡 Awaiting decision", False, True),
    ("Note: ⏸ Awaiting decision", False, True),
    ("✅ Awaiting final acknowledgement", True, False),
    ("⏸ Done", False, True),
]
pause_blocks = []
pause_expected_active = []
pause_expected_actionable = []
pause_expected_all = []
for level in ("##", "###"):
    for label in ("**Status:**", "Status:"):
        for status, done, actionable in pause_cases:
            heading = f"{level} 🟢 Pause task {len(pause_blocks)}"
            block = f"{heading}\n- {label}  {status}  \n"
            parsed = module.parse_backlog(block)
            assert len(parsed) == 1, (block, parsed)
            assert parsed[0].status == status, (block, parsed[0])
            assert module.is_done(parsed[0]) is done, (block, parsed[0])
            assert module.is_actionable(parsed[0]) is actionable, (block, parsed[0])
            pause_blocks.append(block)
            pause_expected_all.append((heading, status))
            if not done:
                pause_expected_active.append((heading, status))
            if actionable:
                pause_expected_actionable.append((heading, status))

with tempfile.TemporaryDirectory() as tmp:
    paused = Path(tmp) / "paused.md"
    paused_text = "\n".join(pause_blocks)
    paused.write_text(paused_text)
    for flags, expected in (
        ([], pause_expected_all),
        (["--active-only"], pause_expected_active),
        (["--actionable-only"], pause_expected_actionable),
    ):
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--file", str(paused), *flags, "--json"],
            text=True, capture_output=True, check=False,
        )
        assert result.returncode == 0, result
        actual = [(task["heading"], task["status"]) for task in json.loads(result.stdout)]
        assert actual == expected, (flags, actual, expected)
        assert paused.read_text() == paused_text, "listing must not mutate pause statuses"

    # Filtering is still subordinate to the recovery guard, even for paused work.
    guarded_text = "> DO NOT ACT ON ENTRIES BELOW\n\n" + paused_text
    paused.write_text(guarded_text)
    refusal = subprocess.run(
        [sys.executable, str(SCRIPT), "--file", str(paused), "--actionable-only", "--json"],
        text=True, capture_output=True, check=False,
    )
    assert refusal.returncode == 2 and refusal.stdout == "", refusal
    audit = subprocess.run(
        [sys.executable, str(SCRIPT), "--file", str(paused), "--actionable-only", "--json",
         "--allow-corrupted-backlog", "--require-corruption-guard"],
        text=True, capture_output=True, check=False,
    )
    assert audit.returncode == 0, audit
    assert [(task["heading"], task["status"]) for task in json.loads(audit.stdout)] == pause_expected_actionable
    assert paused.read_text() == guarded_text

# Scheduled entries also put status immediately after Source's first field.
# Match that format only; standalone Status fields remain authoritative.
inline_cases = [
    ("done — all30 Lodestar online", True, False),
    ("✅ done. All 30 Lodestar online", True, False),
    ("In progress — collecting evidence", False, True),
    ("Awaiting owner", False, False),
    ("Unknown — needs inspection", False, True),
    ("", False, True),
]
inline_blocks = []
inline_expected = {"all": [], "active": [], "actionable": []}
for level in ("##", "###"):
    for source_label in ("Source:", "**Source:**"):
        for status, done, actionable in inline_cases:
            heading = f"{level} 🟢 Inline task {len(inline_blocks)}"
            block = f"{heading}\n- {source_label} cron 51e7881e; status: {status}\n"
            parsed = module.parse_backlog(block)
            assert len(parsed) == 1, (block, parsed)
            assert parsed[0].status == status, (block, parsed[0])
            assert module.is_done(parsed[0]) is done, (block, parsed[0])
            assert module.is_actionable(parsed[0]) is actionable, (block, parsed[0])
            inline_blocks.append(block)
            pair = (heading, status)
            inline_expected["all"].append(pair)
            if not done:
                inline_expected["active"].append(pair)
            if actionable:
                inline_expected["actionable"].append(pair)

for level in ("##", "###"):
    for status_label in ("Status:", "**Status:**"):
        for status, actionable in (("In progress", True), ("", True), ("Awaiting owner", False)):
            explicit = f"- {status_label} {status}\n"
            inline = "- Source: cron 51e7881e; status: done — earlier run\n"
            for body in (explicit + inline, inline + explicit):
                parsed = module.parse_backlog(f"{level} 🟢 Explicit wins\n{body}")
                assert len(parsed) == 1 and parsed[0].status == status, (body, parsed)
                assert not module.is_done(parsed[0]), (body, parsed[0])
                assert module.is_actionable(parsed[0]) is actionable, (body, parsed[0])

inline_near_misses = [
    "- status: done",
    "- note: cron; status: done",
    "- Source note: cron; status: done",
    "- Source:** cron; status: done",
    "- **Source: cron; status: done",
    "- source: cron; status: done",
    "- Source: cron; Status: done",
    "- Source: cron; note: earlier run; status: done",
    "- Source: cron mentions status: done",
    "> - Source: cron; status: done",
    "  - Source: cron; status: done",
    "- Source: ; status: done",
]
for level in ("##", "###"):
    for body in inline_near_misses:
        parsed = module.parse_backlog(f"{level} 🟢 Not a status field\n{body}\n")
        if level == "##":
            assert parsed == [], (body, parsed)
        else:
            assert len(parsed) == 1 and parsed[0].status is None, (body, parsed)
            assert module.is_actionable(parsed[0]), (body, parsed[0])

with tempfile.TemporaryDirectory() as tmp:
    inline_file = Path(tmp) / "inline.md"
    inline_text = "\n".join(inline_blocks)
    inline_file.write_text(inline_text)
    for flags, key in (([], "all"), (["--active-only"], "active"), (["--actionable-only"], "actionable")):
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--file", str(inline_file), *flags, "--json"],
            text=True, capture_output=True, check=False,
        )
        assert result.returncode == 0, result
        assert [(t["heading"], t["status"]) for t in json.loads(result.stdout)] == inline_expected[key]
        assert inline_file.read_text() == inline_text

    guarded_inline = "> DO NOT ACT ON ENTRIES BELOW\n\n" + inline_text
    inline_file.write_text(guarded_inline)
    refusal = subprocess.run(
        [sys.executable, str(SCRIPT), "--file", str(inline_file), "--actionable-only", "--json"],
        text=True, capture_output=True, check=False,
    )
    assert refusal.returncode == 2 and refusal.stdout == "", refusal
    audit = subprocess.run(
        [sys.executable, str(SCRIPT), "--file", str(inline_file), "--actionable-only", "--json",
         "--allow-corrupted-backlog", "--require-corruption-guard"],
        text=True, capture_output=True, check=False,
    )
    assert audit.returncode == 0, audit
    assert [(t["heading"], t["status"]) for t in json.loads(audit.stdout)] == inline_expected["actionable"]
    assert inline_file.read_text() == guarded_inline

print("OK: list_statuses parser handles ## sections + ### tasks without stalling")
print("OK: displaced recovery guards retain refusal and explicit-audit CLI behavior (2 marker variants)")
print("OK: bold/plain status labels preserve ##/### tasks and CLI filter results (24 cases)")
print("OK: pause-prefixed status classification, raw output and guarded CLI behavior (64 cases)")
print("OK: inline Source status classification/CLI (24 cases), explicit overrides (24), near-misses (24)")

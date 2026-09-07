#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

SCRIPT = Path(__file__).with_name("github_notifications_sweep.py")

spec = importlib.util.spec_from_file_location("github_notifications_sweep", SCRIPT)
module = importlib.util.module_from_spec(spec)
assert spec is not None and spec.loader is not None
sys.modules[spec.name] = module
spec.loader.exec_module(module)

sample = """# BACKLOG

### 🟡 Still-open PR with completed subthread
- **Source:** two review comments: `discussion_r3791626607` and `discussion_r3791626654`.
- **Status:** Awaiting nflaig on a separate follow-up.
- **DONE 2026-08-16:** Replied to both: codex `r3791641676`, nflaig `r3791641702`. Still awaiting the broader decision.

### 🟢 gh-notif checklist auto-done detection doesn't match real BACKLOG convention — 4 stuck items fixed manually
- **Source:** stale checklist items `pullrequestreview-5068622066`, `pullrequestreview-5068639907`, `issuecomment-5477544405`, and `issuecomment-5477611017`.
- **Immediate fix applied:** hand-set `status: done` directly in `/home/openclaw/gh-notif-checklist.json` for `5068622066`, `5068639907`, `5477544405`, `5477611017`.

### 🟢 Terminal issue response — DONE
- **Source:** incoming issue comment `issuecomment-5434632052`.
- **Status:** Done — reply posted and no follow-up remains.
"""

handled = module.extract_handled_ids_from_backlog(sample)

assert {5068622066, 5068639907, 5477544405, 5477611017, 5434632052} <= handled
assert 3791626607 not in handled
assert 3791626654 not in handled
assert 3791641676 not in handled
assert 3791641702 not in handled

print("OK: github notification backlog handled-id extraction is precise")

# Regression: HANDLED_HEADING_RE's `✅\b` alternative never matched, because ✅ is
# non-word and always followed by whitespace in practice (no \w/\W transition for
# \b to fire there) — so the "### ✅ ..." convention used throughout BACKLOG.md
# (the majority convention, distinct from the 🟡/🟢 + inline "DONE" style above)
# silently never closed its checklist items. Caught 2026-09-06 when PR #10019's
# fully-resolved section left 5 checklist items stuck open.
checkmark_sample = """# BACKLOG

### ✅ Dockerfile.dev missing `packages/builder` COPY line — PR opened (#10019) [topic:50]
- **Source:** direct-mentioned lodekeeper (https://github.com/ChainSafe/lodestar/pull/10017#discussion_r3943785954).
- **✅ DONE 2026-09-06 — opened PR #10019.** Replied in-thread on r3943785954 -> `r3943809232` linking the PR.

### 🟡 Unrelated still-open item
- **Source:** discussion_r1111111111, not resolved yet.
"""
checkmark_handled = module.extract_handled_ids_from_backlog(checkmark_sample)
assert 3943785954 in checkmark_handled
assert 1111111111 not in checkmark_handled

print("OK: '### ✅ ...' heading convention correctly closes its section's ids")

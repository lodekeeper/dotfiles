#!/usr/bin/env python3
import sys
sys.path.insert(0, "/home/openclaw/.openclaw/workspace/scripts/github")
import github_notifications_sweep as g

g.scan_open_prs_for_unreplied = lambda state, checklist: []
sys.argv = [
    "github_notifications_sweep.py",
    "--state",
    "/home/openclaw/gh-notif-state.json",
    "--checklist",
    "/home/openclaw/gh-notif-checklist.json",
    "--backlog",
    "/home/openclaw/.openclaw/workspace/BACKLOG.md",
]
raise SystemExit(g.main())

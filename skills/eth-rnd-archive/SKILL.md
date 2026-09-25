---
name: eth-rnd-archive
description: Track and summarize discussions from ethereum/eth-rnd-archive across selected Discord channels, with hourly monitoring and daily digest outputs. Use for protocol/R&D intelligence, spotting spec changes, and surfacing Lodestar-relevant action items from Eth R&D chatter.
---

# Eth R&D Archive Tracker

Track discussions from the [Ethereum R&D Discord Archive](https://github.com/ethereum/eth-rnd-archive) and surface important research conversations relevant to Lodestar development.

## Overview

The archive repo contains daily JSON exports of every Eth R&D Discord channel. Updated hourly by EF DevOps. Each channel is a directory with `YYYY-MM-DD.json` files containing messages.

## Related Skills

- `skills/deep-research/SKILL.md` — use when an archive thread needs full analysis/design synthesis (not just monitoring summary).
- `skills/web-scraping/SKILL.md` — use to fetch linked external sources (spec posts, blogs, docs) when `web_fetch` is blocked/incomplete.

## Repo Location

- **Local clone:** `~/ethereum-repos/eth-rnd-archive`
- **Remote:** `https://github.com/ethereum/eth-rnd-archive`

## Tracked Channels

Configured in `config.json` (this skill directory). Only these channels are monitored.

### Core Research
- `epbs` — ePBS design discussions
- `consensus-dev` — CL protocol development
- `allcoredevs` — cross-client coordination
- `execution-dev` — EL protocol development
- `specifications` — spec discussions

### Features & Topics
- `inclusion-lists` — IL design
- `shorter-slot-times` — slot time reduction research
- `l1-zkevm` — CK EVM / L1 zkEVM
- `l1-zkevm-protocol` — CK EVM protocol details (EIP-8025)
- `data-availability-sampling` — DAS / PeerDAS
- `apis` — Beacon/Engine API discussions
- `ai-workflows` — AI tooling / workflow discussions relevant to protocol engineering
- `ssz` — SSZ spec/library discussions

### Infrastructure
- `payload-builders` — MEV/PBS/builder discussions
- `networking` — general networking
- `interop-🌃` — cross-client interop/devnet coordination (Glamsterdam devnet triage lives here)
- `client-development` — client team discussions

## Thread Support

Threads are stored in `_threads/` subdirectories within each channel:
```
epbs/_threads/make it two clients/2026-02-23.json
l1-zkevm/_threads/Proof orchestration/2026-02-23.json
```
Thread messages have `"parent": "<thread name>"` set. The check script scans these automatically.

## Message Format

```json
{
  "author": "username",
  "category": "Discord category",
  "parent": "thread parent (empty if top-level)",
  "content": "message text",
  "created_at": "ISO8601 timestamp",
  "attachments": [...]
}
```

### Resolving Discord message links

Messages carry no IDs, but a link `discord.com/channels/<guild>/<channel>/<msgid>` encodes its send time: `ms = (msgid >> 22) + 1420070400000` (Unix epoch ms). Convert it, then match that exact millisecond against `created_at` in `*/YYYY-MM-DD.json` and `*/_threads/*/YYYY-MM-DD.json` for that day; a hit is the referenced message. A channel/thread mention (`<#id>`) works the same way: a thread opened from a message shares that message's ID, so the hit is the thread's starter stub (content = the thread title); verified 2026-09-24, `<#1552704440946139209>` matched execution-dev "BAL retention window" to the millisecond. User mentions (`<@id>`) can't be resolved this way (only usernames are stored): grep the ID across the archive and read how others refer to it. One more source: when a thread is opened on a message that starts with a mention, the thread title (stub content and the `_threads/<title>/` directory name) shows it rendered as `@display (username)`; seen once, 2026-09-24: `<@774033563732541451>` became `@ignacio (jsign)`.

```python
import datetime
datetime.datetime.fromtimestamp(((msgid >> 22) + 1420070400000) / 1000, datetime.timezone.utc)
```

## How to Check for Updates

### Script: `check-updates.sh`

Located in this skill directory. Run it to:
1. `git pull` the archive repo
2. Compare current HEAD against last-checked commit (stored in `state.json`)
3. Extract new/modified files from tracked channels only
4. Output new messages as JSON for summarization

### Usage

```bash
# Check for new messages (outputs JSON to stdout)
bash skills/eth-rnd-archive/check-updates.sh

# Check for new messages from specific date
bash skills/eth-rnd-archive/check-updates.sh 2026-02-25
```

**⚠️ `messages` is the TOTAL count in the file (append-only daily archive), not a delta.**
On a busy day, a tracked file can already hold many already-logged messages by the time
you check again — `cat`-ing the whole file re-reads old content as if it were new. In
`"mode": "diff"` output, each `tracked_changes` entry also carries `new_messages` (actual
delta since `from`) and `new_since_index` (0-based start index of new entries). Only read
the tail slice, e.g.:
```bash
python3 -c "import json; d=json.load(open('FILE')); print(json.dumps(d[START_INDEX:], indent=2))"
```
using `new_since_index` as `START_INDEX`. Cross-check against today's notes file before
re-investigating anything that looks new — if a message timestamp predates your last logged
entry, it's stale content, not fresh signal.

### ACD call outcomes (EIPsInsight recap)

The archive holds chatter around ACDE/ACDC/ACDT calls, rarely their outcomes. When a thread
links `https://eipsinsight.com/calls/<acde|acdc|acdt>/<n>`, plain
`curl -sSL --max-time 40 -A "Mozilla/5.0" <url>` returns the full server-rendered page (HTTP 200,
~1.5 MB): an mm:ss transcript plus a "Call summary / Decisions / Action Items" block. Strip
script/style/tags in python (`html.unescape`) and slice by keyword. The page says its summary may be
AI-inferred and transcript speaker labels can be garbled (a whole client roll call attributed to the
facilitator), so cross-check any decision you report against the transcript text. Verified on
ACDE #246 (2026-09-24), which resolved the retention-window and 200M gas-limit outcomes.

Forkcast (`https://forkcast.org/calls/<acde|acdc|acdt>/<n>`, often linked in the call's archive
thread within hours) is a client-rendered React shell: a plain fetch returns only navigation. Its
`/llms.txt` documents JSON endpoints instead: `/api/calls.json` lists calls, and the artifacts sit at
`https://forkcast.org/artifacts/<series>/<YYYY-MM-DD>_<n>/{key_decisions,tldr,notes}.json` (200 for
`acde/2026-09-24_246`; the `path` field in `calls.json`, e.g. `acde/246`, 404s for recent calls, so
build the dated path from the call's `date` + `number`). `key_decisions.json` has structured `eips` +
`stage_change`, `tldr.json` adds `action_items` and `targets` (dates), `notes.json` has
`sections[{heading, summary, timestamp, body}]`; `transcript.vtt` sits alongside when published. Same
caveat as EIPsInsight: edited/AI-compiled summaries, attribution can be off. Check weekdays with
python before writing a day-of-week label (a "Mon Sep 29" that was really a Tuesday was once logged).

## Writing Log Entries Safely

The hourly cron appends log text via `printf ... >> $NOTES_FILE` inside a double-quoted
bash argument. Two footguns in that context, both silent (no error, just corrupted output):
- **Backticks** (`` ` ``) inside a double-quoted string trigger command substitution —
  e.g. writing `` `should_build_on_full` `` as inline code makes bash try to *run*
  `should_build_on_full` as a command, and the whole token vanishes from the output.
  Either avoid backticks in log text, or build the string in Python (`python3 <<'PYEOF'`
  with a **quoted** heredoc delimiter) instead of a bash double-quoted argument.
- **`'\''`** is the escape for a literal `'` inside a *single*-quoted bash string — it is
  wrong and produces literal garbage (`'\''`) if the surrounding quotes are double quotes,
  where `'` is already literal and needs no escaping.
If a log entry ends up corrupted, fix it with a targeted `python3` string replace (exact
match on the broken substring) rather than re-deleting/re-writing the whole file.

## Searching the Notes

`grep` on this box is ugrep. A context-window pattern with bounded repeats, e.g.
`grep -o -E '.{0,120}NEEDLE.{0,120}' memory/eth-rnd-archive-notes/*.md`, aborts with
`exceeds complexity limits` on these UTF-8 notes and prints no matches (verified 2026-09-25). Use python
(`re.finditer` or `str.find` plus a slice) for context windows; a plain `grep -n -i -E 'a|b|c'` works fine.

## Workflow

### Hourly Check (via cron)
1. Run `check-updates.sh`
2. If new messages found in tracked channels:
   - Summarize key discussions per channel
   - Log to `/home/openclaw/.openclaw/workspace/memory/eth-rnd-archive-notes/YYYY-MM-DD.md`
   - If compatibility mirrors are in use, also append the same summary to `/home/openclaw/eth-rnd-archive-notes/YYYY-MM-DD.md`
   - If something critical (spec changes, breaking decisions, action items for Lodestar): alert Nico immediately
3. If no tracked-channel messages changed but the repo advanced, log the no-delta result silently so freshness/staleness checks stay auditable.
4. If no repo changes at all: no action.

### Daily Digest (08:00 Europe/Lisbon / 08:00 UTC while WET is active)
1. Read all notes from the past 24h (primary path: `/home/openclaw/.openclaw/workspace/memory/eth-rnd-archive-notes/`; optional compatibility mirror: `/home/openclaw/eth-rnd-archive-notes/`)
2. Create a concise digest:
   - **Key decisions** made across channels
   - **Action items** for Lodestar
   - **Interesting discussions** worth following up
   - **Notable participants** (who's driving which topics)
3. Send digest to Nico via Telegram topic #59
4. After the send succeeds, update `state.json` `lastDigest` to the current UTC timestamp and append a short "Daily Digest" note with the Telegram message id when available. A successful digest send without this stamp makes the heartbeat staleness check unreliable.

### What to Flag as Critical (immediate alert)
- Spec changes affecting Lodestar implementation
- Breaking API changes
- Devnet failures or coordination calls
- Direct mentions of Lodestar or ChainSafe
- Deadlines or action items assigned to CL teams
- Major design pivots in ePBS, PeerDAS, or inclusion lists

## State Tracking

`state.json` in this skill directory:
```json
{
  "lastCommit": "<commit hash>",
  "lastCheck": "<ISO timestamp>",
  "lastDigest": "<ISO timestamp>"
}
```

## Adding/Removing Channels

Edit `config.json` in this skill directory. Current shape:
```json
{
  "channels": ["epbs", "consensus-dev", "allcoredevs", "apis", ...],
  "digestTimeWET": "08:00",
  "digestTimeUTC": "08:00",
  "timezone": "Europe/Lisbon",
  "checkIntervalMinutes": 60,
  "repoPath": "~/ethereum-repos/eth-rnd-archive",
  "notesPath": "/home/openclaw/.openclaw/workspace/memory/eth-rnd-archive-notes"
}
```

---

## Self-Maintenance

If any commands, file paths, URLs, or configurations in this skill are outdated or no longer work, update this SKILL.md with the correct information after completing your current task. Skills should stay accurate and self-healing — fix what you find broken.

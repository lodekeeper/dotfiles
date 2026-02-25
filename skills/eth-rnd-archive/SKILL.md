# Eth R&D Archive Tracker

Track discussions from the [Ethereum R&D Discord Archive](https://github.com/ethereum/eth-rnd-archive) and surface important research conversations relevant to Lodestar development.

## Overview

The archive repo contains daily JSON exports of every Eth R&D Discord channel. Updated hourly by EF DevOps. Each channel is a directory with `YYYY-MM-DD.json` files containing messages.

## Repo Location

- **Local clone:** `~/eth-rnd-archive`
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

### Networking & Testing
- `networking` — general networking
- `libp2p` — libp2p protocol
- `peerdas-testing` — PeerDAS test coordination
- `peerdas-devnet-alerts` — PeerDAS devnet status
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

## Workflow

### Hourly Check (via cron)
1. Run `check-updates.sh`
2. If new messages found in tracked channels:
   - Summarize key discussions per channel
   - Log to `~/eth-rnd-archive-notes/YYYY-MM-DD.md`
   - If something critical (spec changes, breaking decisions, action items for Lodestar): alert Nico immediately
3. If no new messages: no action

### Daily Digest (8 AM CET via cron)
1. Read all notes from the past 24h (`~/eth-rnd-archive-notes/`)
2. Create a concise digest:
   - **Key decisions** made across channels
   - **Action items** for Lodestar
   - **Interesting discussions** worth following up
   - **Notable participants** (who's driving which topics)
3. Send digest to Nico via Telegram

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

Edit `config.json` in this skill directory. Format:
```json
{
  "channels": ["epbs", "consensus-dev", ...],
  "digestTime": "07:00",
  "checkIntervalMinutes": 60
}
```

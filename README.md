# dotfiles

Agent config, skills, scripts, and research notes for [@lodekeeper](https://github.com/lodekeeper), an AI contributor to [Lodestar](https://github.com/ChainSafe/lodestar).

Powered by [OpenClaw](https://github.com/openclaw/openclaw).

---

## What this repo is

This is the **public, shareable subset** of my local agent workspace:

- Core agent instructions and identity docs
- OpenClaw-facing config snapshots
- Reusable skills and scripts
- Notes, specs, and research markdown
- PR review personas

This repo is synced from local files using `scripts/sync-dotfiles.sh` with explicit safety guards.

---

## Structure

```text
.
├── openclaw/                  # OpenClaw workspace files
│   ├── AGENTS.md              # Agent instructions
│   ├── CODING_CONTEXT.md      # Lodestar coding conventions
│   ├── HEARTBEAT.md           # Heartbeat/monitoring config
│   ├── IDENTITY.md            # Agent identity
│   ├── MEMORY.md              # Curated long-term memory
│   ├── SOUL.md                # Personality and values
│   ├── TOOLS.md               # Tool-specific notes
│   ├── USER.md                # User context
│   ├── cron/jobs.json         # Cron job definitions
│   ├── docs/                  # Agent documentation
│   └── scripts/               # All workspace scripts
│       ├── ci/                # CI auto-fix pipeline
│       ├── cron/              # Cron health checks
│       ├── debug/             # Debug/triage tooling
│       ├── devnet/            # Devnet launch scripts
│       ├── github/            # GitHub notifications/CI monitoring
│       ├── memory/            # Memory consolidation pipeline
│       ├── oracle/            # Oracle bridge CLI
│       ├── review/            # PR review tracking
│       └── spec/              # Spec compliance checks
│
├── config/
│   └── codex-config.toml      # Codex CLI config
│
├── lodestar/
│   └── AGENTS.md              # Lodestar repo AGENTS.md
│
├── skills/                    # OpenClaw skill definitions
│   ├── beacon-node/           # Beacon API queries
│   ├── consensus-clients/     # Cross-client comparison
│   ├── deep-research/         # Multi-agent research pipeline
│   ├── dev-workflow/          # Multi-agent dev workflow
│   ├── ethereum-rnd/          # Ethereum R&D references
│   ├── eth-rnd-archive/       # eth-rnd Discord monitoring
│   ├── grafana-loki/          # Log queries
│   ├── join-devnet/           # Devnet sync
│   ├── kurtosis-devnet/       # Multi-client devnets
│   ├── local-mainnet-debug/   # Local mainnet debugging
│   ├── lodestar-heapsnapshots/# Memory profiling
│   ├── lodestar-review/       # Multi-persona PR reviews
│   ├── memory-profiling/      # Node.js memory analysis
│   ├── oracle-bridge/         # ChatGPT bridge
│   ├── release-metrics/       # Release readiness metrics
│   ├── release-notes/         # Release note generation
│   ├── web-scraping/          # Web scraping toolkit
│   └── web-search/            # Multi-source web search
│
├── personas/                  # PR review personas
│   ├── review-bugs.md
│   ├── review-defender.md
│   ├── review-devils-advocate.md
│   ├── review-linter.md
│   ├── review-security.md
│   ├── review-wisdom.md
│   └── reviewer-architect.md
│
├── scripts/                   # Standalone scripts (dashboard, sync)
├── notes/                     # Working notes and trackers
├── specs/                     # Spec study notes
├── research/                  # Research outputs (markdown + scripts)
├── kurtosis/                  # Devnet configs/artifacts
├── docs/                      # Documentation
├── avatars/                   # Profile images
│
├── AGENTS.md                  # Root agent instructions (symlink target)
├── CLAUDE.md                  # Claude CLI instructions
├── CODING_CONTEXT.md          # Root coding context
├── IDENTITY.md                # Root identity
├── TOOLS.md                   # Root tools notes
├── WORKFLOW_AUTO.md            # Automation workflow doc
├── setup.sh                   # Symlink setup script
└── .gitignore
```

---

## Setup

```bash
git clone https://github.com/lodekeeper/dotfiles.git ~/dotfiles
cd ~/dotfiles
./setup.sh
```

`setup.sh` creates/updates symlinks for:

- `~/.claude/CLAUDE.md`
- `~/.codex/AGENTS.md`
- `~/.codex/config.toml` (if `config/codex-config.toml` exists)
- `~/.gitconfig` (only if not already present)
- `~/.openclaw/workspace/skills/*` → `~/dotfiles/skills/*`

---

## Sync model

### Sync command

```bash
~/dotfiles/scripts/sync-dotfiles.sh
```

Runs automatically every 6 hours via cron. This script:

1. Copies workspace files, skills, scripts, notes, personas, and research into `~/dotfiles`
2. Runs sensitive-path guards before and after staging
3. Commits + pushes only if changes exist

### Safety policy

The sync script **hard-blocks** sensitive/operational paths from being committed:

| Blocked pattern | Reason |
|----------------|--------|
| `BACKLOG.md`, `BACKLOG.md.bak-*`, `BACKLOG_ARCHIVE.md` | Active task state |
| `STATE.md` | Runtime working state |
| `memory/` | Daily notes, archives, raw memory data |
| `bank/` | Structured memory bank (facts, decisions, entities) |
| `.openclaw/` | OpenClaw runtime config |
| `.tmp-*`, `tmp_*`, `*.tgz` | Temporary/archive artifacts |

Files like `SOUL.md`, `USER.md`, `MEMORY.md`, `HEARTBEAT.md`, and `personas/` **are** synced — they contain no secrets and are useful for reference.

---

## Notes

- Local workspace is always the source of truth; dotfiles repo is the backup/share layer.
- The sync script uses rsync for scripts, skills, notes, and personas — new files are picked up automatically.
- Research syncs all `.md` and `.py` files from both `~/research/` and workspace `research/`.

---

## License

MIT

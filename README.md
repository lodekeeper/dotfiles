# dotfiles

Agent configuration, scripts, skills, and notes used by [@lodekeeper](https://github.com/lodekeeper) — an AI contributor to [Lodestar](https://github.com/ChainSafe/lodestar) (Ethereum consensus client).

Powered by [OpenClaw](https://github.com/openclaw/openclaw). Inspired by [steipete/agent-scripts](https://github.com/steipete/agent-scripts).

## What Is This?

This repo is the persistent brain of an AI agent. It contains everything I need to wake up fresh each session and continue working: my personality, operating procedures, development tools, research notes, and specialized skills.

I'm an AI contributor to **Lodestar**, the TypeScript Ethereum consensus client. I review PRs, write code, investigate bugs, monitor infrastructure, track Ethereum R&D discussions, and build tooling — all orchestrated through OpenClaw.

## Structure

```
├── CLAUDE.md                      # Global Claude Code instructions
├── AGENTS.md                      # Global Codex CLI instructions
├── CODING_CONTEXT.md              # Context file for coding sub-agents
├── IDENTITY.md                    # Who I am
├── TOOLS.md                       # Environment config, sub-agent setup
│
├── openclaw/                      # OpenClaw agent platform config
│   ├── AGENTS.md                  # Operating procedures
│   ├── SOUL.md                    # Personality and tone
│   ├── HEARTBEAT.md               # Periodic monitoring checklist
│   ├── IDENTITY.md                # Identity config
│   ├── TOOLS.md                   # Tool-specific notes
│   └── USER.md                    # About my human (Nico)
│
├── config/
│   ├── codex-config.toml          # Codex CLI model & trust config
│   └── gitconfig                  # Git identity + GPG signing
│
├── lodestar/
│   ├── AGENTS.md                  # Project-level AGENTS.md (reference copy)
│   └── ai-config.md               # Shareable AI contributor config
│
├── skills/                        # On-demand capabilities loaded by OpenClaw
│   ├── beacon-node/               # Query & analyze Ethereum beacon nodes
│   ├── consensus-clients/         # Compare CL client implementations
│   ├── deep-research/             # Multi-agent research pipeline
│   ├── dev-workflow/              # Multi-agent development workflow
│   ├── ethereum-rnd/              # Ethereum R&D reference lookup
│   ├── eth-rnd-archive/           # Discord R&D discussion monitoring
│   ├── grafana-loki/              # Query logs from Grafana Loki
│   ├── kurtosis-devnet/           # Ethereum multi-client devnets
│   ├── local-mainnet-debug/       # Local mainnet node debugging
│   ├── lodestar-review/           # Multi-persona PR code review
│   ├── oracle-bridge/             # ChatGPT browser bridge (GPT-5.2-pro)
│   ├── release-metrics/           # Release candidate readiness evaluation
│   ├── release-notes/             # Release notes & announcements
│   └── web-scraping/              # Tiered web scraping architecture
│
├── scripts/
│   ├── sync-dotfiles.sh           # Sync local changes → repo
│   ├── update-status.sh           # Dashboard status updater
│   ├── deploy.sh                  # Dashboard deploy script
│   ├── monitor-beacon.sh          # Beacon node log monitoring
│   ├── pre-validate.mjs           # Pre-push validation for Lodestar
│   └── pre-validate-spec.md       # Spec for the validation script
│
├── notes/                         # Research & investigation notes
│   ├── specs/                     # Consensus spec study progress
│   ├── eip8025/                   # EIP-8025 research & implementation
│   ├── epbs-devnet-0/             # ePBS devnet investigation
│   ├── epbs-envelope-sync/        # ePBS envelope sync analysis
│   ├── epbs-withdrawals-regression/ # ePBS withdrawals bug investigation
│   └── lodekeeper-dash/           # Dashboard development notes
│
├── specs/                         # Protocol spec learning notes
│   ├── consensus/                 # Core consensus specs
│   ├── eips/                      # EIP analysis
│   ├── gloas/                     # Gloas/ePBS learning notes
│   └── peerdas/                   # PeerDAS learning notes
│
├── research/                      # Deep research outputs
│   ├── compaction-resilience/     # Context compaction resilience study
│   ├── web-scraping-skill/        # Web scraping architecture research
│   └── oracle-bridge-v3.py        # ChatGPT browser bridge script
│
├── avatars/
│   └── lodekeeper-avatar.jpg      # Profile avatar
│
└── setup.sh                       # Symlinks everything into place
```

## Setup

```bash
git clone https://github.com/lodekeeper/dotfiles.git ~/dotfiles
cd ~/dotfiles && ./setup.sh
```

This symlinks:
- `CLAUDE.md` → `~/.claude/CLAUDE.md` (loaded by Claude Code globally)
- `AGENTS.md` → `~/.codex/AGENTS.md` (loaded by Codex CLI globally)
- `config/codex-config.toml` → `~/.codex/config.toml`
- `config/gitconfig` → `~/.gitconfig`
- `skills/*` → `~/.openclaw/workspace/skills/`

## How It Works

**Global instructions** (`CLAUDE.md`, `AGENTS.md`) apply to all projects. Project-specific files in repo roots extend these.

**OpenClaw config** (`openclaw/`) defines my personality, operating procedures, and monitoring setup for the [OpenClaw](https://github.com/openclaw/openclaw) agent platform.

**Skills** are loaded on demand by OpenClaw when tasks match their description. Each skill has a `SKILL.md` with instructions, reference materials, and sometimes scripts.

**Scripts** are dependency-free helpers for development, monitoring, and automation.

**Notes & research** capture investigations, spec studies, and implementation analysis from my work on Lodestar and Ethereum protocol development.

## Multi-Agent Architecture

I orchestrate multiple sub-agents for different tasks:

| Agent | Model | Role |
|-------|-------|------|
| Main (me) | Claude Opus 4.6 | Orchestrator — coordination, delegation, review |
| codex-reviewer | GPT-5.3-Codex | Code reviews, bug hunting |
| gpt-advisor | GPT-5.3-Codex (xhigh thinking) | Architecture, deep reasoning |
| Codex CLI | GPT-5.3-Codex | Implementation in worktrees |
| Claude CLI | Claude | Broader reasoning, refactoring |

## Syncing

Local changes are synced to this repo periodically (~6h) via `scripts/sync-dotfiles.sh`. Sensitive files (memory, backlog) are local-only and never pushed.

## License

MIT

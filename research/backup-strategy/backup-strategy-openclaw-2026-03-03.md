# Backup Strategy for Lodekeeper / OpenClaw Setup (2026-03-03)

## Goal
Prevent loss of:
1. Agent configuration and secrets
2. Conversation/session continuity and memory
3. Custom skills/scripts/docs
4. Git identities/access
5. Active work artifacts not yet pushed

---

## What must be backed up (priority order)

## P0 — Critical (cannot recover easily if lost)
- `~/.openclaw/openclaw.json` (+ `.bak*`)
- `~/.openclaw/secrets.json`
- `~/.openclaw/credentials/`
- `~/.openclaw/identity/`
- `~/.openclaw/cron/` (job definitions + runs)
- `~/.openclaw/agents/main/` (session continuity)
- `~/.openclaw/memory/`
- `~/.openclaw/workspace/` (including memory files, BACKLOG, custom notes/skills/scripts)
- `~/dotfiles/`
- `~/.ssh/`, `~/.gnupg/`, `~/.gitconfig`, `~/.git-credentials`
- `~/.codex/`, `~/.claude/`, `~/.oracle/` (CLI and auth state)
- `/home/openclaw/gh-notif-state.json`

## P1 — Important (recoverable, but painful/time-consuming)
- Active repos/worktrees with unpushed local work, e.g.:
  - `~/lodestar*`, `~/js-libp2p*`, `~/consensus-specs`, `~/ethereum-repos`
- `~/lodekeeper-dash/` (if not fully pushed)

## P2 — Optional / rebuildable
- `~/.cache`, `~/.npm`, `~/.nvm`, `~/.local` (large; usually reinstallable)
- temp/media artifacts unless specifically needed for audit history

---

## Measured footprint snapshot (this host)
- `~/.openclaw`: ~1.8G
- `~/dotfiles`: ~6.4M
- `~/.ssh` + `~/.gnupg`: ~68K
- `~/.codex` + `~/.claude` + `~/.oracle`: ~39M
- `~/.openclaw/agents/main` + workspace + memory: ~229M

This means a high-frequency backup of **critical state only** is very practical.

---

## Recommended strategy (3-2-1)

### Layer A — Fast local snapshot (high frequency)
- Frequency: hourly
- Scope: P0 only
- Target: second disk/NAS mounted locally
- Retention: 48 hourly + 14 daily
- Purpose: quick restore after accidental deletion/corruption

### Layer B — Encrypted offsite incremental (daily)
- Frequency: daily
- Scope: P0 + selected P1
- Target: object storage (S3/B2) or remote server via SSH
- Retention: 30 daily + 12 monthly
- Purpose: server/disk loss recovery

### Layer C — Weekly cold archive
- Frequency: weekly
- Scope: full P0 + active repos with unpushed branches
- Target: separate provider/location (different failure domain)
- Retention: 8 weekly + 12 monthly
- Purpose: ransomware/operator error resilience

---

## Tooling options

## Option 1 (recommended): `restic` + encrypted repository
Pros:
- Native encryption, dedup, incremental snapshots, retention policies
- Easy restore of single files or full trees
- Works with local disk + S3/B2/SSH

Cons:
- Needs install/setup

Use when: you want reliable long-term operations with low maintenance.

## Option 2: `borg` (if target is SSH server/NAS)
Pros:
- Excellent dedup/compression, strong integrity checks

Cons:
- More SSH/server coupling than restic

Use when: you control both ends and prefer borg ecosystem.

## Option 3 (no new install): `tar` + `gpg` + `rsync`
Pros:
- Works now with existing tools
- Simple and explicit

Cons:
- Coarser retention/dedup, bigger storage footprint
- More script/ops burden

Use when: immediate stopgap before restic rollout.

---

## Backup tiers by schedule

### Hourly (P0-core)
Include:
- `~/.openclaw/openclaw.json*`
- `~/.openclaw/secrets.json`
- `~/.openclaw/{credentials,identity,cron,agents/main,memory,workspace}`
- `~/dotfiles`
- `~/.ssh`, `~/.gnupg`, `~/.gitconfig`, `~/.git-credentials`
- `~/.codex`, `~/.claude`, `~/.oracle`
- `/home/openclaw/gh-notif-state.json`

### Daily (P0 + active P1)
Add selected repos/worktrees where unpushed work exists.

### Weekly (full working set)
Add all active engineering repos likely to contain local-only branches.

---

## Restore runbook (disaster)
1. Provision new host + user `openclaw`
2. Restore P0 backup first into `/home/openclaw`
3. Verify permissions for sensitive dirs (`~/.ssh`, `~/.gnupg`, secrets)
4. Start OpenClaw gateway and validate:
   - channels connected
   - cron jobs present
   - memory/backlog/session continuity present
5. Restore active repos/worktrees (P1)
6. Run validation checklist:
   - can send/receive Telegram/Discord
   - `gh` authenticated
   - GPG signing works
   - dotfiles symlinks intact

---

## Validation drills (mandatory)
- Weekly: restore one random file from latest backup
- Monthly: full dry-run restore to test VM and run smoke tests
- Quarterly: full disaster simulation (new VM, cold restore, functional checks)

No backup strategy is real until restore is tested.

---

## Immediate implementation plan (practical)
1. Start **Option 3** today (tar+gpg+rsync) for P0 hourly + daily offsite
2. Within 1 week, migrate to **restic** for incremental encrypted snapshots
3. Add monthly full restore drill to calendar/cron

---

## Minimal stopgap command set (works now)

```bash
# Example: create encrypted daily archive of critical state
TS=$(date -u +%Y%m%d-%H%M)
OUT=/home/openclaw/backups/lodekeeper-critical-$TS.tar.gz

tar -czf "$OUT" \
  /home/openclaw/.openclaw/openclaw.json \
  /home/openclaw/.openclaw/openclaw.json.bak* \
  /home/openclaw/.openclaw/secrets.json \
  /home/openclaw/.openclaw/credentials \
  /home/openclaw/.openclaw/identity \
  /home/openclaw/.openclaw/cron \
  /home/openclaw/.openclaw/agents/main \
  /home/openclaw/.openclaw/memory \
  /home/openclaw/.openclaw/workspace \
  /home/openclaw/dotfiles \
  /home/openclaw/.ssh \
  /home/openclaw/.gnupg \
  /home/openclaw/.gitconfig \
  /home/openclaw/.git-credentials \
  /home/openclaw/.codex \
  /home/openclaw/.claude \
  /home/openclaw/.oracle \
  /home/openclaw/gh-notif-state.json

# Encrypt archive (recipient key or symmetric mode)
gpg --yes --symmetric --cipher-algo AES256 "$OUT"
rm -f "$OUT"
```

Then replicate `.gpg` file to remote storage (`rsync`/SFTP/object store).

---

## Decision needed
Choose one:
- **A:** I implement immediate stopgap scripts (tar+gpg+rsync) now
- **B:** I draft a production `restic` plan/config (preferred)
- **C:** I do both (stopgap now + restic migration plan)

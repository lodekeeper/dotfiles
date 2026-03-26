# Git Worktree Skill

> Enforce worktree-based git workflow for AI coding agents. Prevents main/unstable branch contamination.

## Description

This skill ensures all development work happens in git worktrees, never in the main repository checkout. It provides pre-flight safety checks, lifecycle management, and sub-agent enforcement patterns to eliminate an entire class of "accidentally committed to main" disasters.

Co-authored by lodekeeper 🌟 and MEK 🐒.

## Rules (non-negotiable)

1. **NEVER** commit, checkout, reset, or modify files in the main repo directory
2. Every feature gets its own worktree in a **sibling directory** (e.g., `~/project-feature/`)
3. **Verify `pwd`** before ANY git operation — no exceptions
4. **Pass `workdir` explicitly** to every sub-agent spawn and exec call
5. **Refuse to push** if current branch is `main`, `master`, or `unstable`
6. **Never force-push** unless explicitly approved by the human

## Protected Branches

Configure these per-project. Common defaults:
- `main`, `master`, `unstable`, `develop`
- Any branch matching `release/*`

## Workflow

### 1. Create Worktree

```bash
# Always start from the main repo to create worktrees
cd ~/project                          # main repo, stays clean
git fetch origin                      # ALWAYS fetch first — avoid stale base
git worktree add ~/project-<feature> -b feat/<feature> origin/main
cd ~/project-<feature>                # all work happens HERE
```

**Naming convention:** `~/project-<feature>` as sibling to `~/project/`.

### 2. Pre-flight Check (before ANY git operation)

Run this before every commit, push, merge, reset, or checkout:

```bash
#!/bin/bash
# pre-flight-check.sh — abort if not in a worktree or on a protected branch

TOPLEVEL=$(git rev-parse --show-toplevel 2>/dev/null)
BRANCH=$(git branch --show-current 2>/dev/null)
MAIN_REPO="$HOME/project"  # adjust per-project

# Check 1: Are we in a git repo?
[ -z "$TOPLEVEL" ] && { echo "ERROR: Not in a git repo"; exit 1; }

# Check 2: Are we in the main repo? (DANGER)
[ "$TOPLEVEL" = "$MAIN_REPO" ] && { echo "ERROR: In main repo — switch to worktree"; exit 1; }

# Check 3: Are we on a protected branch?
for protected in main master unstable develop; do
  [ "$BRANCH" = "$protected" ] && { echo "ERROR: On protected branch '$protected'"; exit 1; }
done

echo "OK: worktree=$TOPLEVEL branch=$BRANCH"
```

### 3. Work in Worktree

```bash
cd ~/project-<feature>     # NEVER ~/project
# ... edit files, run tests, build
git add -p                  # stage intentionally
git commit -m "feat: description"
```

### 4. Bring in Upstream Changes

**Use merge, NOT rebase** — rebase requires force-push which breaks reviewer history:

```bash
cd ~/project-<feature>
git fetch origin
git merge origin/main       # NOT rebase
```

### 5. Push and PR

```bash
cd ~/project-<feature>
# Pre-flight check first!
git push origin feat/<feature>
# Create PR via gh cli or web
```

### 6. Cleanup After Merge

```bash
cd ~/project                # back to main repo
git worktree remove ~/project-<feature>
git branch -d feat/<feature>    # only after PR is merged
```

### 7. Periodic Maintenance

Run during heartbeats or maintenance cycles:

```bash
git worktree list           # check for stale worktrees
# Remove any worktrees whose PRs have been merged
```

## Sub-agent Enforcement

When spawning coding agents (Codex CLI, Claude CLI, etc.), **ALWAYS**:

1. **Set `workdir`** to the worktree path explicitly:
   ```
   exec workdir:~/project-<feature> command:"codex exec --full-auto '...'"
   ```

2. **Include in the task prompt:**
   > "You are working in a git worktree at ~/project-<feature>/.
   > Do NOT cd to ~/project/ or checkout main/unstable.
   > All work must stay in this directory."

3. **First command** in any agent session should be:
   ```bash
   pwd && git branch --show-current
   ```
   Verify the output before proceeding.

## Failure Modes (learned the hard way)

| Failure | Cause | Guard |
|---------|-------|-------|
| Commit to main | Agent ran `git checkout main` in worktree | Pre-flight check on every git op |
| `reset --hard` in wrong dir | Agent in main repo, not worktree | pwd verification + protected-dir check |
| Stale base branch | Worktree created without `git fetch` | Always fetch before `worktree add` |
| Worktree accumulation | Forgot cleanup after PR merge | Periodic `git worktree list` audit |
| Wrong `pnpm install` | Sub-agent installed deps in main repo | Same pwd check applies to package managers |
| Sub-agent ignores workdir | Defaults to cwd, ignoring spawn config | Explicit workdir + prompt reinforcement |
| Force-push destroys history | Rebase + force-push on shared branch | Merge-only policy, never force-push |

## Verification

After any git operation, verify:
```bash
echo "pwd: $(pwd)"
echo "branch: $(git branch --show-current)"
echo "toplevel: $(git rev-parse --show-toplevel)"
echo "status: $(git status --short | head -5)"
```

If any output looks wrong, **STOP immediately** and alert the human.

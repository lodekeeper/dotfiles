#!/usr/bin/env bash
# Bump the quinn crates on ChainSafe/js-libp2p-quic main to clear published advisories and open a PR as lodekeeper.
#
#   quinn_bump_pr.sh                                  # bump the crates named by matching advisories, verify, push, open PR
#   quinn_bump_pr.sh --packages "quinn-proto quinn"   # bump these crates even without an advisory (released fix, no GHSA yet)
#   quinn_bump_pr.sh --dry-run [...]                  # prepare and verify only
#
# Exit codes: 0 PR opened / nothing to do / PR already open (see last line), 2 setup error,
#             3 lockfile still vulnerable after the bump (manual follow-up in the printed worktree), 4 cargo check failed.
# Last stdout line is JSON: {"status": ..., "worktree": ..., "pr": ..., ...}
set -euo pipefail

REPO=ChainSafe/js-libp2p-quic
CLONE="$HOME/js-libp2p-quic"
WATCH="$HOME/.openclaw/workspace/scripts/quic/quinn_advisory_watch.py"
CACHE="$HOME/.cache/quinn-watch"
IMAGE=rust:1-slim-bookworm
BASE="${QUINN_BUMP_BASE:-upstream/main}"  # override only to test against an old tag
DRY_RUN=0
FORCE_PKGS=""
while [ $# -gt 0 ]; do
  case "$1" in
    --dry-run) DRY_RUN=1 ;;
    --packages) FORCE_PKGS="$2"; shift ;;
    *) echo "unknown argument $1" >&2; exit 2 ;;
  esac
  shift
done

result() { python3 -c 'import json,sys; print(json.dumps(dict(a.split("=",1) for a in sys.argv[1:])))' "$@"; }

[ "$(gh api user --jq .login)" = "lodekeeper" ] || { result status=error error="gh is not authenticated as lodekeeper"; exit 2; }

existing=$(gh pr list -R "$REPO" --state open --author lodekeeper --json headRefName,url --jq '[.[] | select(.headRefName | startswith("fix/quinn-security-"))][0].url // empty')
if [ -n "$existing" ]; then
  result status=pr_exists pr="$existing"
  exit 0
fi

git -C "$CLONE" fetch -q --tags upstream main
stamp=$(date -u +%Y%m%d-%H%M)
branch="fix/quinn-security-$stamp"
wt="/tmp/quinn-security-$stamp"
git -C "$CLONE" worktree add -q -b "$branch" "$wt" "$BASE"
cd "$wt"

cleanup_nothing_to_do() {
  cd "$CLONE" && git worktree remove --force "$wt" && git branch -q -D "$branch"
  result status=nothing_to_do
  exit 0
}

before=$(python3 "$WATCH" --lockfile Cargo.lock)
if [ -n "$FORCE_PKGS" ]; then
  pkgs="$FORCE_PKGS"
elif [ "$(jq -r .action <<<"$before")" = "none" ]; then
  cleanup_nothing_to_do
else
  pkgs=$(jq -r '[.findings[].package] | unique | join(" ")' <<<"$before")
fi

mkdir -p "$CACHE/cargo-home" "$CACHE/target"
cargo() {
  docker run --rm --user "$(id -u):$(id -g)" \
    -e CARGO_HOME=/cargo-home -e CARGO_TARGET_DIR=/target \
    -v "$CACHE/cargo-home:/cargo-home" -v "$CACHE/target:/target" -v "$wt:/w" -w /w \
    "$IMAGE" cargo "$@"
}

update_args=()
for p in $pkgs; do update_args+=(-p "$p"); done
cargo update "${update_args[@]}" >&2

after=$(python3 "$WATCH" --lockfile Cargo.lock)
if [ "$(jq -r .action <<<"$after")" != "none" ]; then
  result status=still_vulnerable worktree="$wt" keys="$(jq -c .keys <<<"$after")" \
    hint="check Cargo.toml version requirements and [patch.crates-io] pins for the quinn crates"
  exit 3
fi

if git diff --quiet -- Cargo.lock; then
  cleanup_nothing_to_do
fi

if ! cargo check --release --locked >&2; then
  result status=check_failed worktree="$wt"
  exit 4
fi

# "quinn-proto to 0.11.19 and quinn-udp to 0.5.16"
updates=$(python3 - "$before" "$after" "$pkgs" <<'EOF'
import json, sys
before, after = (json.loads(a) for a in sys.argv[1:3])
old = before["refs"]["local"]["locked"]
new = after["refs"]["local"]["locked"]
pkgs = sorted(set(sys.argv[3].split()))
parts = [f"`{p}` to {new[p][-1]}" for p in pkgs if new.get(p) != old.get(p)]
print(parts[0] if len(parts) == 1 else ", ".join(parts[:-1]) + " and " + parts[-1])
EOF
)
title="fix: update ${updates//\`/}"
# Public PR: keep it to the version bump, no advisory ids or vulnerability details (Nico 2026-10-05).
body="Updates ${updates} to pick up the latest upstream fixes."

git add Cargo.lock Cargo.toml
git -c user.name=lodekeeper -c user.email=lodekeeper@users.noreply.github.com \
  commit -q -S -m "$title" -m "$body" -m "🤖 Generated with AI assistance"

if [ "$DRY_RUN" = 1 ]; then
  result status=dry_run worktree="$wt" title="$title" body="$body"
  exit 0
fi

git push -q origin "$branch"
pr=$(gh pr create -R "$REPO" --base main --head "lodekeeper:$branch" --title "$title" --body "$body")
result status=pr_opened pr="$pr" worktree="$wt" title="$title"

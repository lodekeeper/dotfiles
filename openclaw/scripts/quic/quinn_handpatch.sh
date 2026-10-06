#!/usr/bin/env bash
# Hand-patch ChainSafe/js-libp2p-quic with an unreleased quinn-rs/quinn PR.
#
#   quinn_handpatch.sh <quinn-pr-number>            # cherry-pick, test, push, open the js-libp2p-quic PR
#   quinn_handpatch.sh <quinn-pr-number> --dry-run  # same, but skip the js-libp2p-quic push and PR (the quinn branch is still pushed so cargo can fetch it)
#   quinn_handpatch.sh <quinn-pr-number> [--dry-run] --continue <meta.json>
#       resume after exit 3/4: first fix the backport in the printed quinn worktree and commit it there
#
# The PR's commits go on top of the quinn source we currently build with: the existing [patch.crates-io] git rev if
# there is one, else the release tag of the locked crate version. The result is pushed to lodekeeper/quinn, and the
# crates the PR touches are pointed at it via [patch.crates-io].
#
# Exit codes: 0 done (see status), 2 setup error, 3 cherry-pick conflict, 4 quinn tests failed, 5 cargo check failed.
# A main-targeted PR often applies cleanly but does not compile on 0.11.x; exit 4 then means "backport it by hand".
# Last stdout line is JSON: {"status": ..., ...}
set -euo pipefail

PR="${1:?usage: quinn_handpatch.sh <quinn-pr-number> [--dry-run] [--continue <meta.json>]}"
shift
DRY_RUN=0
META=""
while [ $# -gt 0 ]; do
  case "$1" in
    --dry-run) DRY_RUN=1 ;;
    --continue) META="$2"; shift ;;
    *) echo "unknown argument $1" >&2; exit 2 ;;
  esac
  shift
done
JS_REPO=ChainSafe/js-libp2p-quic
JS_CLONE="$HOME/js-libp2p-quic"
QUINN_CLONE="$HOME/quinn"
QUINN_FORK_URL=https://github.com/lodekeeper/quinn
CACHE="$HOME/.cache/quinn-watch"
IMAGE=rust:1-slim-bookworm
JS_BASE="${QUINN_HANDPATCH_JS_BASE:-upstream/main}"  # override only to test against an old tag

result() { python3 -c 'import json,sys; print(json.dumps(dict(a.split("=",1) for a in sys.argv[1:])))' "$@"; }

[ "$(gh api user --jq .login)" = "lodekeeper" ] || { result status=error error="gh is not authenticated as lodekeeper"; exit 2; }

js_branch="fix/quinn-handpatch-pr-$PR"
existing=$(gh pr list -R "$JS_REPO" --state open --author lodekeeper --json headRefName,url --jq ".[] | select(.headRefName == \"$js_branch\") | .url")
if [ -n "$existing" ]; then
  result status=pr_exists pr="$existing"
  exit 0
fi

if [ -n "$META" ]; then
  eval "$(jq -r '@sh "crates=\(.crates) base=\(.base) base_desc=\(.base_desc) js_wt=\(.js_wt) quinn_wt=\(.quinn_wt) quinn_branch=\(.quinn_branch)"' "$META")"
  cd "$quinn_wt"
else
pr_json=$(gh pr view "$PR" -R quinn-rs/quinn --json title,state,headRefOid,commits,files,url)
crates=$(jq -r '[.files[].path | split("/")[0] | select(. == "quinn" or . == "quinn-proto" or . == "quinn-udp")] | unique | join(" ")' <<<"$pr_json")
[ -n "$crates" ] || { result status=error error="PR $PR touches no quinn crate sources"; exit 2; }
head_sha=$(jq -r .headRefOid <<<"$pr_json")
stamp=$(date -u +%Y%m%d-%H%M%S)

git -C "$JS_CLONE" fetch -q --tags upstream main
js_wt="/tmp/quic-handpatch-$PR-$stamp"
git -C "$JS_CLONE" worktree add -q -b "$js_branch" "$js_wt" "$JS_BASE"

# Base: an existing git patch of a quinn crate, else the release tag of the locked version of the first touched crate.
read -r base base_desc < <(python3 - "$js_wt" $crates <<'EOF'
import re, sys
wt, crates = sys.argv[1], sys.argv[2:]
toml = open(f"{wt}/Cargo.toml").read()
for m in re.finditer(r'^(quinn(?:-proto|-udp)?)\s*=\s*\{[^}]*git\s*=\s*"([^"]+)"[^}]*rev\s*=\s*"([0-9a-f]+)"', toml, re.M):
    print(m.group(3), f"{m.group(1)}@{m.group(3)[:10]}")
    sys.exit()
lock = open(f"{wt}/Cargo.lock").read()
crate = "quinn-proto" if "quinn-proto" in crates else crates[0]
version = re.search(rf'^name = "{crate}"\nversion = "([^"]+)"', lock, re.M).group(1)
print(f"{crate}-{version}", f"{crate} {version}")
EOF
)

git -C "$QUINN_CLONE" fetch -q upstream --tags "+refs/pull/$PR/head:refs/remotes/upstream/pr/$PR"
quinn_branch="handpatch/pr-$PR-${head_sha:0:10}"
quinn_wt="/tmp/quinn-handpatch-$PR-$stamp"
git -C "$QUINN_CLONE" worktree add -q -b "$quinn_branch" "$quinn_wt" "$base"
cd "$quinn_wt"
meta="/tmp/quinn-handpatch-$PR-$stamp.json"
jq -n --arg crates "$crates" --arg base "$base" --arg base_desc "$base_desc" --arg js_wt "$js_wt" \
  --arg quinn_wt "$quinn_wt" --arg quinn_branch "$quinn_branch" '$ARGS.named' > "$meta"
for c in $(jq -r '.commits[].oid' <<<"$pr_json"); do
  [ "$(git rev-list --parents -n 1 "$c" | wc -w)" -gt 2 ] && continue  # skip merge commits
  if ! git -c user.name=lodekeeper -c user.email=lodekeeper@users.noreply.github.com cherry-pick -x --allow-empty "$c" >/dev/null 2>&1; then
    conflicts=$(git diff --name-only --diff-filter=U | tr '\n' ' ')
    result status=conflict meta="$meta" quinn_worktree="$quinn_wt" base="$base_desc" commit="$c" files="$conflicts"
    exit 3
  fi
done
fi
if git diff --quiet "$base" HEAD; then
  result status=already_included base="$base_desc"
  exit 0
fi

mkdir -p "$CACHE/cargo-home" "$CACHE/target" "$CACHE/quinn-target"
cargo_in() {
  local dir="$1" target="$2"; shift 2
  docker run --rm --user "$(id -u):$(id -g)" \
    -e CARGO_HOME=/cargo-home -e CARGO_TARGET_DIR=/target \
    -v "$CACHE/cargo-home:/cargo-home" -v "$target:/target" -v "$dir:/w" -w /w \
    "$IMAGE" cargo "$@"
}

for crate in $crates; do
  if ! cargo_in "$quinn_wt" "$CACHE/quinn-target" test -p "$crate" --lib >&2; then
    result status=tests_failed meta="${meta:-$META}" quinn_worktree="$quinn_wt" crate="$crate"
    exit 4
  fi
done

git push -q origin "$quinn_branch"
rev=$(git rev-parse HEAD)

cd "$js_wt"
python3 - "$PR" "$rev" "$QUINN_FORK_URL" "$base_desc" $crates <<'EOF'
import re, sys
pr, rev, url, base_desc, crates = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5:]
p = "Cargo.toml"
s = open(p).read()
lines = s.split("\n")
out, prev_comments = [], []
in_patch = False
for line in lines:
    if line.startswith("["):
        in_patch = line.strip() == "[patch.crates-io]"
    if in_patch and re.match(rf'^({"|".join(map(re.escape, crates))})\s*=', line):
        while out and out[-1].startswith("#"):
            prev_comments.insert(0, out.pop())
        continue
    out.append(line)
s = "\n".join(out).rstrip("\n") + "\n"
comment = prev_comments or [f"# {base_desc}"]
entries = comment + [f"# plus quinn-rs/quinn#{pr}, drop once it is released"] + [
    f'{c} = {{ git = "{url}", rev = "{rev}" }}' for c in crates
]
if "[patch.crates-io]" not in s:
    s += "\n[patch.crates-io]\n"
s = s.replace("[patch.crates-io]\n", "[patch.crates-io]\n" + "\n".join(entries) + "\n", 1)
open(p, "w").write(s)
EOF

if ! cargo_in "$js_wt" "$CACHE/target" check --release >&2 || ! cargo_in "$js_wt" "$CACHE/target" check --release --locked >&2; then
  result status=check_failed js_worktree="$js_wt" quinn_branch="$quinn_branch"
  exit 5
fi
for crate in $crates; do
  grep -A2 "^name = \"$crate\"" Cargo.lock | grep -q "lodekeeper/quinn?rev=$rev" || { result status=check_failed js_worktree="$js_wt" error="$crate not resolved from the patched rev"; exit 5; }
done

title="fix: patch ${crates// /, } with quinn-rs/quinn#$PR"
body="Patches \`${crates// /\`, \`}\` with quinn-rs/quinn#$PR on top of ${base_desc} until it is in a release. The patched source is $QUINN_FORK_URL/tree/$quinn_branch."
git add Cargo.toml Cargo.lock
git -c user.name=lodekeeper -c user.email=lodekeeper@users.noreply.github.com \
  commit -q -S -m "$title" -m "$body" -m "🤖 Generated with AI assistance"

if [ "$DRY_RUN" = 1 ]; then
  result status=dry_run js_worktree="$js_wt" quinn_branch="$quinn_branch" rev="$rev" title="$title" body="$body"
  exit 0
fi

git push -q origin "$js_branch"
pr_url=$(gh pr create -R "$JS_REPO" --base main --head "lodekeeper:$js_branch" --title "$title" --body "$body")
result status=pr_opened pr="$pr_url" quinn_branch="$quinn_branch" rev="$rev" title="$title"

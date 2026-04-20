#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

REPO_DIR="$TMP_DIR/repo"
CONFIG_PATH="$TMP_DIR/config.json"
STATE_PATH="$TMP_DIR/state.json"
NOTES_DIR="$TMP_DIR/notes"
mkdir -p "$REPO_DIR" "$NOTES_DIR"

git -C "$REPO_DIR" init -q

git -C "$REPO_DIR" config user.name "OpenClaw Test"
git -C "$REPO_DIR" config user.email "openclaw-test@example.com"

mkdir -p "$REPO_DIR/epbs"
printf '[]\n' > "$REPO_DIR/epbs/2026-04-19.json"
git -C "$REPO_DIR" add .
git -C "$REPO_DIR" commit -qm "base"
BASE_COMMIT="$(git -C "$REPO_DIR" rev-parse HEAD)"

mkdir -p "$REPO_DIR/interop-🌃"
printf '[]\n' > "$REPO_DIR/interop-🌃/2026-04-20.json"
git -C "$REPO_DIR" add .
git -C "$REPO_DIR" commit -qm "emoji-only-diff"
HEAD_COMMIT="$(git -C "$REPO_DIR" rev-parse HEAD)"

cat > "$CONFIG_PATH" <<EOF
{
  "channels": ["epbs"],
  "repoPath": "$REPO_DIR",
  "notesPath": "$NOTES_DIR"
}
EOF

cat > "$STATE_PATH" <<EOF
{
  "lastCommit": "$BASE_COMMIT",
  "lastCheck": "2026-04-20T00:00:00+00:00",
  "lastDigest": null
}
EOF

OUTPUT="$({
  ETH_RND_ARCHIVE_CONFIG="$CONFIG_PATH" \
  ETH_RND_ARCHIVE_STATE="$STATE_PATH" \
  bash "$SCRIPT_DIR/check-updates.sh"
} )"

OUTPUT_JSON="$OUTPUT" EXPECTED_BASE="$BASE_COMMIT" EXPECTED_HEAD="$HEAD_COMMIT" STATE_PATH="$STATE_PATH" python3 - <<'PY'
import json
import os

payload = json.loads(os.environ["OUTPUT_JSON"])
assert payload["mode"] == "diff", payload
assert payload["tracked_changes"] == [], payload
assert payload["from"] == os.environ["EXPECTED_BASE"], payload
assert payload["to"] == os.environ["EXPECTED_HEAD"], payload

state = json.load(open(os.environ["STATE_PATH"]))
assert state["lastCommit"] == os.environ["EXPECTED_HEAD"], state
PY

echo "ok - check-updates.sh handles non-tracked emoji diff paths without false tracked matches"

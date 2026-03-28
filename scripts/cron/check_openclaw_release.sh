#!/usr/bin/env bash
set -euo pipefail

STATE_FILE="/home/openclaw/openclaw-release-watch.json"
REPO="openclaw/openclaw"

latest_tag=$(gh api "repos/${REPO}/releases/latest" --jq '.tag_name')
latest_url=$(gh api "repos/${REPO}/releases/latest" --jq '.html_url')
latest_published=$(gh api "repos/${REPO}/releases/latest" --jq '.published_at')

if [[ -f "$STATE_FILE" ]]; then
  last_tag=$(python3 - <<'PY'
import json
p='/home/openclaw/openclaw-release-watch.json'
try:
    with open(p) as f:
        d=json.load(f)
    print(d.get('last_tag',''))
except Exception:
    print('')
PY
)
else
  last_tag=""
fi

if [[ -z "$last_tag" ]]; then
  python3 - <<PY
import json
with open("$STATE_FILE","w") as f:
    json.dump({
        "last_tag": "$latest_tag",
        "last_url": "$latest_url",
        "last_published_at": "$latest_published"
    }, f)
PY
  echo "HEARTBEAT_OK"
  exit 0
fi

if [[ "$latest_tag" != "$last_tag" ]]; then
  python3 - <<PY
import json
with open("$STATE_FILE","w") as f:
    json.dump({
        "last_tag": "$latest_tag",
        "last_url": "$latest_url",
        "last_published_at": "$latest_published"
    }, f)
PY
  echo "NEW_OPENCLAW_RELEASE|tag=$latest_tag|url=$latest_url|published_at=$latest_published|previous=$last_tag"
else
  echo "HEARTBEAT_OK"
fi

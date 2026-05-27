#!/usr/bin/env bash
set -euo pipefail

STATE_FILE="/home/openclaw/openclaw-release-watch.json"
REPO="openclaw/openclaw"

release_json=$(
  curl -fsSL \
    -H "Accept: application/vnd.github+json" \
    -H "User-Agent: openclaw-release-watch" \
    "https://api.github.com/repos/${REPO}/releases/latest"
)

latest_tag=$(jq -r '.tag_name' <<<"$release_json")
latest_url=$(jq -r '.html_url' <<<"$release_json")
latest_published=$(jq -r '.published_at' <<<"$release_json")

if [[ -f "$STATE_FILE" ]]; then
  last_tag=$(jq -r '.last_tag // ""' "$STATE_FILE" 2>/dev/null || true)
else
  last_tag=""
fi

if [[ -z "$last_tag" ]]; then
  jq -n \
    --arg last_tag "$latest_tag" \
    --arg last_url "$latest_url" \
    --arg last_published_at "$latest_published" \
    '{last_tag: $last_tag, last_url: $last_url, last_published_at: $last_published_at}' \
    > "$STATE_FILE"
  echo "HEARTBEAT_OK"
  exit 0
fi

if [[ "$latest_tag" != "$last_tag" ]]; then
  jq -n \
    --arg last_tag "$latest_tag" \
    --arg last_url "$latest_url" \
    --arg last_published_at "$latest_published" \
    '{last_tag: $last_tag, last_url: $last_url, last_published_at: $last_published_at}' \
    > "$STATE_FILE"
  echo "NEW_OPENCLAW_RELEASE|tag=$latest_tag|url=$latest_url|published_at=$latest_published|previous=$last_tag"
else
  echo "HEARTBEAT_OK"
fi

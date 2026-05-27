#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  check-catchup-depth.sh [options]

Validates that a checkpoint/catch-up repro starts far enough behind head.

Options:
  --head-slot <slot>              Known current head slot
  --checkpoint-slot <slot>        Known checkpoint/state slot
  --beacon-url <url>              Beacon API URL used to fetch head slot
  --checkpoint-sync-url <url>     Beacon API URL used to fetch finalized checkpoint slot
  --checkpoint-state-id <id>      State/header id for checkpoint-sync URL (default: finalized)
  --min-epochs <n>                Required catch-up depth in epochs (default: 1000)
  --slots-per-epoch <n>           Slots per epoch (default: 32)
  -h, --help                      Show help

Examples:
  check-catchup-depth.sh --head-slot 14415648 --checkpoint-slot 14383648 --min-epochs 1000
  check-catchup-depth.sh --beacon-url http://127.0.0.1:5052 --checkpoint-slot 14383648
  check-catchup-depth.sh --checkpoint-sync-url https://beaconstate-mainnet.chainsafe.io --min-epochs 1000

Exit codes:
  0  checkpoint is deep enough
  1  usage/fetch/parse error
  2  checkpoint is too shallow or ahead of head
EOF
}

HEAD_SLOT=""
CHECKPOINT_SLOT=""
BEACON_URL=""
CHECKPOINT_SYNC_URL=""
CHECKPOINT_STATE_ID="finalized"
MIN_EPOCHS=1000
SLOTS_PER_EPOCH=32

while [[ $# -gt 0 ]]; do
  case "$1" in
    --head-slot)
      HEAD_SLOT="${2:-}"
      shift 2
      ;;
    --checkpoint-slot)
      CHECKPOINT_SLOT="${2:-}"
      shift 2
      ;;
    --beacon-url)
      BEACON_URL="${2:-}"
      shift 2
      ;;
    --checkpoint-sync-url)
      CHECKPOINT_SYNC_URL="${2:-}"
      shift 2
      ;;
    --checkpoint-state-id)
      CHECKPOINT_STATE_ID="${2:-}"
      shift 2
      ;;
    --min-epochs)
      MIN_EPOCHS="${2:-}"
      shift 2
      ;;
    --slots-per-epoch)
      SLOTS_PER_EPOCH="${2:-}"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "error: unknown argument: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
done

is_uint() {
  [[ "$1" =~ ^[0-9]+$ ]]
}

require_uint() {
  local name="$1"
  local value="$2"
  if ! is_uint "$value"; then
    echo "error: $name must be a non-negative integer (got '$value')" >&2
    exit 1
  fi
}

fetch_header_slot() {
  local base_url="$1"
  local state_id="$2"
  local url="${base_url%/}/eth/v1/beacon/headers/${state_id}"
  local response

  if ! response="$(curl -fsS "$url" 2>/dev/null)"; then
    echo "error: failed to fetch beacon header: $url" >&2
    return 1
  fi

  python3 -c '
import json
import sys

try:
    payload = json.load(sys.stdin)
    slot = payload["data"]["header"]["message"]["slot"]
except Exception as exc:
    raise SystemExit(f"error: response did not contain data.header.message.slot: {exc}")

print(slot)
' <<<"$response"
}

require_uint "--min-epochs" "$MIN_EPOCHS"
require_uint "--slots-per-epoch" "$SLOTS_PER_EPOCH"
if [[ "$SLOTS_PER_EPOCH" -eq 0 ]]; then
  echo "error: --slots-per-epoch must be greater than zero" >&2
  exit 1
fi

if [[ -z "$CHECKPOINT_SLOT" && -n "$CHECKPOINT_SYNC_URL" ]]; then
  CHECKPOINT_SLOT="$(fetch_header_slot "$CHECKPOINT_SYNC_URL" "$CHECKPOINT_STATE_ID")"
fi

if [[ -z "$HEAD_SLOT" && -n "$BEACON_URL" ]]; then
  HEAD_SLOT="$(fetch_header_slot "$BEACON_URL" "head")"
fi

if [[ -z "$HEAD_SLOT" && -n "$CHECKPOINT_SYNC_URL" ]]; then
  HEAD_SLOT="$(fetch_header_slot "$CHECKPOINT_SYNC_URL" "head")"
fi

if [[ -z "$HEAD_SLOT" || -z "$CHECKPOINT_SLOT" ]]; then
  echo "error: need both head and checkpoint slots (provide slots directly or URLs to fetch them)" >&2
  usage >&2
  exit 1
fi

require_uint "--head-slot" "$HEAD_SLOT"
require_uint "--checkpoint-slot" "$CHECKPOINT_SLOT"

if (( CHECKPOINT_SLOT > HEAD_SLOT )); then
  echo "CATCHUP_DEPTH: invalid checkpoint ahead of head (checkpoint_slot=$CHECKPOINT_SLOT head_slot=$HEAD_SLOT)" >&2
  exit 2
fi

SLOTS_BACK=$((HEAD_SLOT - CHECKPOINT_SLOT))
REQUIRED_SLOTS=$((MIN_EPOCHS * SLOTS_PER_EPOCH))
EPOCHS_BACK_WHOLE=$((SLOTS_BACK / SLOTS_PER_EPOCH))
EPOCHS_BACK_REMAINDER=$((SLOTS_BACK % SLOTS_PER_EPOCH))

printf 'CATCHUP_DEPTH: head_slot=%s checkpoint_slot=%s slots_back=%s epochs_back=%s.%02d required_epochs=%s\n' \
  "$HEAD_SLOT" \
  "$CHECKPOINT_SLOT" \
  "$SLOTS_BACK" \
  "$EPOCHS_BACK_WHOLE" \
  $((EPOCHS_BACK_REMAINDER * 100 / SLOTS_PER_EPOCH)) \
  "$MIN_EPOCHS"

if (( SLOTS_BACK < REQUIRED_SLOTS )); then
  echo "CATCHUP_DEPTH: too_shallow - choose an older checkpoint state before launching the repro" >&2
  exit 2
fi

echo "CATCHUP_DEPTH: ok"

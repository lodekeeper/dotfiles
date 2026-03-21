#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

usage() {
  cat <<'EOF'
Usage: scripts/logskill.sh <command> [args...]

Commands:
  init      Initialize a session
  fetch     Fetch raw logs into the session
  build     Normalize raw logs and build templates/reducers
  overview  Generate an overview pack
  drill     Generate a drill-down pack
  compare   Generate a compare pack
  watch     Run the live soak monitor
  status    Show session status
EOF
}

if [[ $# -lt 1 ]]; then
  usage
  exit 1
fi

command="$1"
shift

case "$command" in
  init)
    exec python3 "$SCRIPT_DIR/state.py" init "$@"
    ;;
  fetch)
    exec python3 "$SCRIPT_DIR/fetch.py" "$@"
    ;;
  build)
    python3 "$SCRIPT_DIR/normalize.py" "$@"
    exec python3 "$SCRIPT_DIR/build.py" "$@"
    ;;
  overview)
    exec python3 "$SCRIPT_DIR/overview.py" "$@"
    ;;
  drill)
    exec python3 "$SCRIPT_DIR/drill.py" "$@"
    ;;
  compare)
    exec python3 "$SCRIPT_DIR/compare.py" "$@"
    ;;
  watch)
    exec python3 "$SCRIPT_DIR/watch.py" "$@"
    ;;
  status)
    exec python3 "$SCRIPT_DIR/state.py" status "$@"
    ;;
  *)
    usage
    exit 1
    ;;
esac

#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  extract-spec-section.sh <query> [--spec-root <path>] [--max-primary <n>] [--max-related <n>] [--output <path>]

Examples:
  extract-spec-section.sh execution_payload_envelope
  extract-spec-section.sh "gossip attestation" --max-primary 12
  extract-spec-section.sh process_execution_payload --output /tmp/spec-snippet.md

Notes:
  - Searches consensus-specs markdown under <spec-root> (default: ~/consensus-specs/specs)
  - Extracts matching pseudocode blocks (primary matches)
  - Follows `from ... import ...` symbols from those blocks and appends related type/function definitions
EOF
}

SPEC_ROOT="${CONSENSUS_SPECS_DIR:-$HOME/consensus-specs}/specs"
MAX_PRIMARY=20
MAX_RELATED=20
OUTPUT=""

if [[ $# -eq 0 ]]; then
  usage
  exit 1
fi

QUERY=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --spec-root)
      SPEC_ROOT="${2:-}"
      shift 2
      ;;
    --max-primary)
      MAX_PRIMARY="${2:-}"
      shift 2
      ;;
    --max-related)
      MAX_RELATED="${2:-}"
      shift 2
      ;;
    --output)
      OUTPUT="${2:-}"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      if [[ -z "$QUERY" ]]; then
        QUERY="$1"
      else
        QUERY+=" $1"
      fi
      shift
      ;;
  esac
done

if [[ -z "$QUERY" ]]; then
  echo "error: missing query" >&2
  usage
  exit 1
fi

if [[ ! -d "$SPEC_ROOT" ]]; then
  echo "error: spec root not found: $SPEC_ROOT" >&2
  exit 1
fi

SEARCH_BACKEND="grep"
if command -v rg >/dev/null 2>&1; then
  SEARCH_BACKEND="rg"
fi

extract_symbol_from_line() {
  local line="$1"
  if [[ "$line" =~ def[[:space:]]+([A-Za-z_][A-Za-z0-9_]*)[[:space:]]*\( ]]; then
    printf '%s\n' "${BASH_REMATCH[1]}"
    return
  fi
  if [[ "$line" =~ class[[:space:]]+([A-Za-z_][A-Za-z0-9_]*) ]]; then
    printf '%s\n' "${BASH_REMATCH[1]}"
    return
  fi
  if [[ "$line" =~ ^[[:space:]]*([A-Za-z_][A-Za-z0-9_]*)[[:space:]]*= ]]; then
    printf '%s\n' "${BASH_REMATCH[1]}"
    return
  fi
  printf '%s\n' ""
}

extract_code_block() {
  local file="$1"
  local target_line="$2"

  awk -v target="$target_line" '
    { lines[NR]=$0 }
    /^```/ { fence[++fc]=NR }
    END {
      start=-1; end=-1
      for (i=1; i<=fc; i++) {
        if (fence[i] <= target) start=fence[i]
        if (fence[i] > target) { end=fence[i]; break }
      }

      if (start != -1 && end != -1) {
        for (i=start; i<=end; i++) print lines[i]
      } else {
        s = target - 10; if (s < 1) s = 1
        e = target + 25; if (e > NR) e = NR
        for (i=s; i<=e; i++) print lines[i]
      }
    }
  ' "$file"
}

extract_import_symbols() {
  awk '
    /^[[:space:]]*from[[:space:]]+[A-Za-z0-9_\.]+[[:space:]]+import[[:space:]]+/ {
      line=$0
      sub(/^.* import[[:space:]]+/, "", line)
      gsub(/[()]/, "", line)
      gsub(/\\/, "", line)
      n=split(line, arr, /,/) 
      for (i=1; i<=n; i++) {
        token=arr[i]
        gsub(/^[[:space:]]+|[[:space:]]+$/, "", token)
        sub(/[[:space:]]+as[[:space:]]+.*/, "", token)
        if (token ~ /^[A-Za-z_][A-Za-z0-9_]*$/) print token
      }
    }
  '
}

regex_escape() {
  local raw="$1"
  printf '%s' "$raw" | sed -E 's/[][(){}.^$*+?|\\]/\\\\&/g'
}

search_primary_matches() {
  if [[ "$SEARCH_BACKEND" == "rg" ]]; then
    rg -n -i --glob '*.md' "$QUERY" "$SPEC_ROOT" 2>/dev/null || true
  else
    grep -Rin --include='*.md' -- "$QUERY" "$SPEC_ROOT" 2>/dev/null || true
  fi
}

find_symbol_def() {
  local symbol="$1"
  local escaped
  escaped="$(regex_escape "$symbol")"

  if [[ "$SEARCH_BACKEND" == "rg" ]]; then
    rg -n --glob '*.md' -m 1 -e "^[[:space:]]*def[[:space:]]+${escaped}\\b" \
                            -e "^[[:space:]]*class[[:space:]]+${escaped}\\b" \
                            -e "^[[:space:]]*${escaped}[[:space:]]*=" \
                            "$SPEC_ROOT" 2>/dev/null || true
  else
    grep -RInE --include='*.md' "^[[:space:]]*(def[[:space:]]+${escaped}\\b|class[[:space:]]+${escaped}\\b|${escaped}[[:space:]]*=)" \
      "$SPEC_ROOT" 2>/dev/null | head -n 1 || true
  fi
}

mapfile -t PRIMARY_MATCHES < <(search_primary_matches | head -n "$MAX_PRIMARY")

if [[ ${#PRIMARY_MATCHES[@]} -eq 0 ]]; then
  echo "No matches for query: $QUERY"
  exit 0
fi

declare -A seen_primary_symbol=()
declare -A related_candidates=()

render_report() {
  {
    echo "# Spec Extract"
    echo
    echo "- Query: $QUERY"
    echo "- Spec root: $SPEC_ROOT"
    echo "- Generated: $(date -u '+%Y-%m-%d %H:%M:%S UTC')"
    echo
    echo "## Primary matches"
    echo

    local idx=0
    for match in "${PRIMARY_MATCHES[@]}"; do
      idx=$((idx + 1))
      local file line text rel_file symbol block
      file="${match%%:*}"
      rel_file="${file#${SPEC_ROOT}/}"
      line="${match#*:}"
      line="${line%%:*}"
      text="${match#*:*:}"

      symbol="$(extract_symbol_from_line "$text")"
      if [[ -n "$symbol" ]]; then
        seen_primary_symbol["$symbol"]=1
      fi

      block="$(extract_code_block "$file" "$line")"

      echo "### $idx) ${rel_file}:${line}"
      echo
      echo "Matched line: $text"
      if [[ -n "$symbol" ]]; then
        echo "Detected symbol: $symbol"
      fi
      echo
      echo "$block"
      echo

      while IFS= read -r imported; do
        [[ -n "$imported" ]] || continue
        related_candidates["$imported"]=1
      done < <(printf '%s\n' "$block" | extract_import_symbols)
    done

    echo "## Related definitions (import chain)"
    echo

    local related_count=0
    local sym def file line rel_file block
    for sym in "${!related_candidates[@]}"; do
      [[ -n "$sym" ]] || continue
      [[ -n "${seen_primary_symbol[$sym]:-}" ]] && continue

      def="$(find_symbol_def "$sym" | head -n 1)"
      [[ -n "$def" ]] || continue

      file="${def%%:*}"
      rel_file="${file#${SPEC_ROOT}/}"
      line="${def#*:}"
      line="${line%%:*}"
      block="$(extract_code_block "$file" "$line")"

      related_count=$((related_count + 1))
      echo "### ${sym} (${rel_file}:${line})"
      echo
      echo "$block"
      echo

      if [[ "$related_count" -ge "$MAX_RELATED" ]]; then
        echo "_Truncated related definitions at MAX_RELATED=${MAX_RELATED}_"
        echo
        break
      fi
    done

    if [[ "$related_count" -eq 0 ]]; then
      echo "No import-linked symbol definitions found."
      echo
      echo "Tip: broaden query terms or increase --max-primary."
      echo
    fi
  }
}

if [[ -n "$OUTPUT" ]]; then
  mkdir -p "$(dirname "$OUTPUT")"
  render_report > "$OUTPUT"
  echo "Wrote spec extract: $OUTPUT"
else
  render_report
fi

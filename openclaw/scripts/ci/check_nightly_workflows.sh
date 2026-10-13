#!/usr/bin/env bash
# check_nightly_workflows.sh
#
# Detects NEW failures of the Lodestar nightly workflows Nico cares about and
# prints machine-readable ===FAILURE=== blocks for an alerting agent to post to
# the #nightly-workflow-alerts Discord channel.
#
# Watched workflows (ChainSafe/lodestar, branch=unstable, event=schedule):
#   kurtosis.yml               Kurtosis sim tests              00:00 UTC
#   nightly-builder-smoke.yml  Kurtosis Builder Nightly Smoke  02:00 UTC
#   comptests.yml              Fork-choice compliance tests    03:00 UTC
#   engine-interop.yml         Engine API interop              04:00 UTC
#   cl-interop.yml             Consensus client interop        05:23 UTC
#   nightly-spec-tests.yml     Nightly Spec Tests              06:00 UTC
# plus any other active workflow whose name/path matches interop|engine|kurtosis
# (e.g. the engine API / EL interop nightly), discovered at runtime.
#
# Selection: for each workflow, the most recent *completed* scheduled run on
# `unstable`. Alert-worthy conclusions: failure, timed_out, startup_failure.
# Dedup: state file keyed by workflow file -> last_alerted_run_id. A failure is
# only reported once; a later re-run with a new run id re-triggers.
#
# Usage:
#   check_nightly_workflows.sh            # detect; prints NO_NEW_FAILURES or ===FAILURE=== blocks
#   check_nightly_workflows.sh --mark <workflow_file> <run_id>   # record a run as alerted
#   check_nightly_workflows.sh --known-issues [run_id]   # upstream known issues of the latest scheduled
#       cl-interop run (green by design, so detect mode never sees them); prints NO_KNOWN_ISSUES or
#       ===KNOWN=== blocks (client, issue_url, failure, run_id, url). ChainSafe/lodestar issues are skipped.
#
# Note: the detect path intentionally does NOT write state, so a failed Discord
# post doesn't silently swallow the alert. The agent marks only after posting.
set -uo pipefail

REPO="ChainSafe/lodestar"
BRANCH="unstable"
STATE_DIR="/home/openclaw/.openclaw/workspace/memory/nightly-workflow-alerts"
STATE_FILE="$STATE_DIR/state.json"

# workflow_file -> human name
declare -A WORKFLOWS=(
  [kurtosis.yml]="Kurtosis sim tests"
  [nightly-builder-smoke.yml]="Kurtosis Builder Nightly Smoke Test"
  [comptests.yml]="Fork-choice compliance tests"
  [engine-interop.yml]="Engine API interop"
  [cl-interop.yml]="Consensus client interop"
  [nightly-spec-tests.yml]="Nightly Spec Tests"
)
# Stable iteration order (matches nightly run time)
WF_ORDER=(kurtosis.yml nightly-builder-smoke.yml comptests.yml engine-interop.yml cl-interop.yml nightly-spec-tests.yml)

# Auto-include EL / engine interop nightlies so new ones are watched without editing this list.
# Workflows without scheduled runs on unstable produce no output below.
while IFS=$'\t' read -r path wname; do
  wf="${path##*/}"
  [ -n "${WORKFLOWS[$wf]+x}" ] && continue
  WORKFLOWS[$wf]="$wname"
  WF_ORDER+=("$wf")
done < <(gh api "repos/$REPO/actions/workflows?per_page=100" \
  --jq '.workflows[] | select(.state=="active" and (.path|startswith(".github/workflows/")))
        | select((.name + " " + .path) | test("interop|engine|kurtosis"; "i"))
        | [.path, .name] | @tsv' 2>/dev/null)

mkdir -p "$STATE_DIR"
[ -f "$STATE_FILE" ] || echo '{}' > "$STATE_FILE"

# ---- --mark mode -----------------------------------------------------------
if [ "${1:-}" = "--mark" ]; then
  wf="${2:-}"; run_id="${3:-}"
  if [ -z "$wf" ] || [ -z "$run_id" ]; then
    echo "usage: $0 --mark <workflow_file> <run_id>" >&2; exit 2
  fi
  tmp="$(mktemp)"
  jq --arg wf "$wf" --arg id "$run_id" '.[$wf] = {last_alerted_run_id: ($id|tonumber)}' \
     "$STATE_FILE" > "$tmp" && mv "$tmp" "$STATE_FILE"
  echo "marked $wf -> $run_id"
  exit 0
fi

# ---- --known-issues mode -----------------------------------------------------
# Failures with a filed cause are listed in scripts/kurtosis/cl-interop/known-issues.mjs and keep the job green,
# check.mjs prints them as "known issue: <failure> (<note>, <issue url>)" lines in the job log.
if [ "${1:-}" = "--known-issues" ]; then
  wf="cl-interop.yml"
  if [ -n "${2:-}" ]; then
    run_json="$(gh api "repos/$REPO/actions/runs/$2" --jq '{id, html_url}' 2>/dev/null)"
  else
    run_json="$(gh api "repos/$REPO/actions/workflows/$wf/runs?branch=$BRANCH&per_page=20" \
      --jq '[.workflow_runs[] | select(.event=="schedule" and .status=="completed" and .head_branch=="'"$BRANCH"'")]
            | sort_by(.created_at) | last | {id, html_url}' 2>/dev/null)"
  fi
  if [ -z "$run_json" ] || [ "$run_json" = "null" ]; then echo "NO_KNOWN_ISSUES"; exit 0; fi
  run_id="$(echo "$run_json" | jq -r '.id')"
  html_url="$(echo "$run_json" | jq -r '.html_url')"
  out=""
  while IFS=$'\t' read -r job_id job_name; do
    [ -z "$job_id" ] && continue
    lines="$(gh api "repos/$REPO/actions/jobs/$job_id/logs" 2>/dev/null | grep -a 'known issue: ' | sed 's/\x1b\[[0-9;]*m//g')"
    [ -z "$lines" ] && continue
    out+="$(JOB="$job_name" RUN_ID="$run_id" URL="$html_url" python3 -c '
import os, re, sys
seen = set()
for line in sys.stdin.read().splitlines():
    for seg in line.split("known issue: ")[1:]:
        urls = re.findall(r"https://github\.com/[\w.-]+/[\w.-]+/issues/\d+", seg)
        if not urls or urls[-1] in seen or urls[-1].startswith("https://github.com/ChainSafe/lodestar/"):
            continue
        seen.add(urls[-1])
        failure = re.split(r" \((?=[^()]*https://github\.com/)", seg)[0].strip()
        print("===KNOWN===")
        print("client: " + os.environ["JOB"])
        print("issue_url: " + urls[-1])
        print("failure: " + failure[:300])
        print("run_id: " + os.environ["RUN_ID"])
        print("url: " + os.environ["URL"])
        print("===END===")
' <<< "$lines")"$'\n'
  done < <(gh api "repos/$REPO/actions/runs/$run_id/jobs?per_page=100" --jq '.jobs[] | [.id, .name] | @tsv' 2>/dev/null)
  if [ -n "${out//[$'\n']/}" ]; then printf '%s' "$out" | sed '/^$/d'; else echo "NO_KNOWN_ISSUES"; fi
  exit 0
fi

# ---- detect mode -----------------------------------------------------------
new_failures=0

for wf in "${WF_ORDER[@]}"; do
  name="${WORKFLOWS[$wf]}"

  # Most recent COMPLETED scheduled run on unstable. We pass branch= server-side
  # (reliable) and filter event/status client-side (the server-side event filter
  # has returned stale pages, so we never trust it).
  run_json="$(gh api "repos/$REPO/actions/workflows/$wf/runs?branch=$BRANCH&per_page=20" \
    --jq '[.workflow_runs[] | select(.event=="schedule" and .status=="completed" and .head_branch=="'"$BRANCH"'")]
          | sort_by(.created_at) | last
          | {id, conclusion, created_at, html_url}' 2>/dev/null)"

  # No completed scheduled run found (API error / none yet) -> skip silently.
  [ -z "$run_json" ] || [ "$run_json" = "null" ] && continue

  conclusion="$(echo "$run_json" | jq -r '.conclusion')"
  run_id="$(echo "$run_json" | jq -r '.id')"

  case "$conclusion" in
    failure|timed_out|startup_failure) : ;;   # alert-worthy
    *) continue ;;                             # success/cancelled/skipped/neutral -> ignore
  esac

  # Already alerted this exact run?
  last="$(jq -r --arg wf "$wf" '.[$wf].last_alerted_run_id // empty' "$STATE_FILE")"
  [ "$last" = "$run_id" ] && continue

  created_at="$(echo "$run_json" | jq -r '.created_at')"
  html_url="$(echo "$run_json" | jq -r '.html_url')"

  # Failed step names (first failed job) + a short error excerpt for the TL;DR.
  failed_steps="$(gh api "repos/$REPO/actions/runs/$run_id/jobs" \
    --jq '[.jobs[] | select(.conclusion=="failure") | .steps[]? | select(.conclusion=="failure") | .name] | unique | join(", ")' 2>/dev/null)"
  failed_jobs="$(gh api "repos/$REPO/actions/runs/$run_id/jobs?per_page=100" \
    --jq '[.jobs[] | select(.conclusion=="failure" or .conclusion=="timed_out") | .name] | join(", ")' 2>/dev/null)"
  first_failed_job="$(gh api "repos/$REPO/actions/runs/$run_id/jobs" \
    --jq '[.jobs[] | select(.conclusion=="failure")][0].id' 2>/dev/null)"
  log_excerpt=""
  if [ -n "$first_failed_job" ] && [ "$first_failed_job" != "null" ]; then
    log_excerpt="$(gh api "repos/$REPO/actions/jobs/$first_failed_job/logs" 2>/dev/null \
      | grep -aiE 'error|fail(ed|ure)?|not found|no successful|exit code|assert|unable|cannot|timed out|suites? failed|code: ' \
      | grep -aviE 'continue-on-error|error-on|no error|0 fail|deprecationwarning|url\.parse|fail-on-cache-miss|noprofile|##\[group|setup-node|is deprecated' \
      | tail -20 | sed 's/^[0-9T:.Z-]* //; s/\x1b\[[0-9;]*m//g' | cut -c1-240)"
  fi

  new_failures=$((new_failures+1))
  printf '===FAILURE===\n'
  printf 'workflow: %s\n' "$name"
  printf 'file: %s\n' "$wf"
  printf 'run_id: %s\n' "$run_id"
  printf 'url: %s\n' "$html_url"
  printf 'created_at: %s\n' "$created_at"
  printf 'conclusion: %s\n' "$conclusion"
  printf 'failed_jobs: %s\n' "${failed_jobs:-<unknown>}"
  printf 'failed_steps: %s\n' "${failed_steps:-<unknown>}"
  printf 'log_excerpt:\n%s\n' "${log_excerpt:-<none captured>}"
  printf '===END===\n'
done

[ "$new_failures" -eq 0 ] && echo "NO_NEW_FAILURES"
exit 0

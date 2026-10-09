# CI Auto-Fix Cron Instructions

Run the flaky test detector and act on findings.

## Credential-dependent execution (MANDATORY)

The CI quality gate calls OpenAI using the existing Gateway-managed environment.
Native Codex `exec_command` does **not** inherit that credential environment:
`openaiApiKey: false` there is not proof that the Gateway lacks the key.

- Run BOTH the quality-gate `--check-only` preflight and the final quality-gate
  request through OpenClaw `gateway_exec` (`openclaw__gateway_exec` in Code Mode).
- Set `workdir` to `/home/openclaw/.openclaw/workspace`, use absolute script/diff
  paths, and omit `env` so the existing Gateway environment is inherited.
- Never print, copy, export, or supply a replacement key. Do not use dummy keys
  or bypass the gate. If Gateway execution is unavailable or its preflight
  fails, record that exact blocker and stop before implementing a new fix.
- Keep ordinary local discovery, git, build, lint, and tests in the native shell.

## Step 0a: GitHub guard coverage (MANDATORY — run before GitHub access)

```bash
cd ~/.openclaw/workspace && scripts/github/check-github-guard-coverage.sh
```

- Exit 0 → guard coverage is intact; continue to Step 0b.
- Non-zero → report the coverage failure and stop before any `gh` calls.

## Step 0b: GitHub pre-flight (MANDATORY — run before detector/state scans)

```bash
~/.openclaw/workspace/scripts/github/check-github-access.sh
```

- Exit 0 → GitHub accessible; continue to Step 1.
- Exit 2 → GitHub suspended. Reply with exactly `GITHUB_SUSPENDED_SKIP` and stop. Do not run the detector or attempt any `gh` calls.
- Exit 1 → Unexpected error. Log the error output and stop.

The detector also has the same script-level guard as a fail-safe, but Step 0b
stays mandatory so suspended runs skip before loading/scanning CI state.

## Step 0c: Detector pre-flight (MANDATORY — run before scanning CI)

```bash
cd ~/.openclaw/workspace && python3 scripts/ci/auto_fix_flaky.py --check-only
```

- Exit 0 → detector prerequisites are intact; continue to Step 1.
- Non-zero → report the missing prerequisite(s) and stop before scanning CI or mutating the tracker.

## Step 1: Detect
```bash
cd ~/.openclaw/workspace && python3 scripts/ci/auto_fix_flaky.py --apply
```

If status is "clean" → reply with just the JSON output and stop.

## Step 1b: EL triage for every `Sim tests` finding (fixable or not)

Nightly Kurtosis/EL-interop failures are triaged by the `nightly-workflow-alerts` automation, not here. Since 2026-10-09, sim tests run EL trunk images (`.env.test`: `GETH_DOCKER_IMAGE=ethereum/client-go:latest` = geth master, `NETHERMIND_DOCKER_IMAGE=nethermindeth/nethermind:master`). Read the actual values at the failed head. Nico (2026-10-09, Discord #ssz-engine-api): if a sim failure is EL-related, open an issue on the EL's repo directly.

1. Decide EL vs Lodestar from the full logs (Step 2.1 command) plus the uploaded debug-log artifact (`gh run download <runId> --repo ChainSafe/lodestar`). EL evidence: EL panic/crash/exit, EL failing to start or init genesis, EL error responses to engine calls (JSON-RPC error, REST 4xx/5xx problem detail), EL rejecting payloads Lodestar built from that same EL. Lodestar-side or unclear → continue with Step 2/3 as usual.
2. Pin the EL build: image digest from the "Download required docker images" step, mapped to a commit (`nethermindeth/nethermind:master-<sha>` tags; geth prints its commit at startup). Get the same for the last green `Sim tests` run on unstable → commit range (`https://github.com/<org>/<repo>/compare/<good>...<bad>`).
3. Require recurrence: the same EL error on ≥2 runs with the same or a later EL commit. A one-off → log only.
4. Dedup: `gh search issues --repo <NethermindEth/nethermind|ethereum/go-ethereum> "<key error string>"` (open + recently closed). Existing issue → add the Lodestar run as a comment only if it adds new data.
5. File as `lodekeeper` only (`gh auth status` first; never the connector): `gh issue create --repo <EL repo>`. Body: symptom, image tag + digest + commit, last-good commit + compare link, short log excerpt, failing Lodestar run URL, repro (`pnpm test:sim:<suite>` in `packages/cli` with the image). Evidence only, no guessed root cause.
6. Tracker: status `el-upstream-issue` + issue URL, so later runs don't refile. Announce the link once in topic `#347` (Step 2.6 routing). If the breakage keeps unstable sim red for >24h, mention pinning `master-<last-good-sha>` in `.env.test` as an option in `#347`; do not open that PR without Nico.

## Step 2: Act on actionable findings

For each finding where `fixable: true` or `already_fixing_pr` is set:

1. **Establish the root cause from full logs**, not just the detector's tail/classification:
   ```bash
   scripts/ci/fetch-run-logs.sh <runId> --repo ChainSafe/lodestar --output /tmp/ci-autofix-<runId>.log
   gh run view <runId> --repo ChainSafe/lodestar --json headSha,url
   ```
   Record the failed head, relevant timestamps, and the affected test AND shared helper/source paths. Treat classifications as investigation hints: trace shutdown ordering/error propagation, peer-discovery conditions, event/subscription races, or resource leaks. Do not prescribe timeout bumps, retries, or swallowed errors without evidence that they address the cause.

2. **Check for an existing fix before implementation** (repeat immediately before submission):
   ```bash
   gh pr list --repo ChainSafe/lodestar --state open --limit 1000 \
     --json number,title,url,files,changedFiles > /tmp/ci-autofix-<runId>-open-prs.json
   jq 'length' /tmp/ci-autofix-<runId>-open-prs.json
   jq '[.[] | select((.files | length) < .changedFiles) | {number,changedFiles}]' \
     /tmp/ci-autofix-<runId>-open-prs.json
   jq --arg path '<affected-path>' \
     '[.[] | select(any(.files[]; .path == $path)) | {number,title,url}]' \
     /tmp/ci-autofix-<runId>-open-prs.json
   gh pr list --repo ChainSafe/lodestar --state all \
     --search '<root-cause symbol> in:title,body' --limit 100 \
     --json number,title,state,url
   ```
   `gh --json files` can return only the first 100 paths per PR. For EVERY PR whose returned file count is below `changedFiles`, fetch the full list before completing the affected-path scan:
   ```bash
   gh api --paginate 'repos/ChainSafe/lodestar/pulls/<number>/files?per_page=100' \
     --jq '.[].filename' > /tmp/ci-autofix-<runId>-pr-<number>-files.txt
   wc -l /tmp/ci-autofix-<runId>-pr-<number>-files.txt
   rg -n -F -x -- '<affected-path>' /tmp/ci-autofix-<runId>-pr-<number>-files.txt
   ```
   Verify the paginated file count equals `changedFiles`; a remaining mismatch/API limit is incomplete coverage, not a clean result. `rg` exit 1 means no exact path match; exit 2 means a lookup failure.

   Repeat the exact-path filter for each affected test/helper/source path. Scan ALL authors: the detector only checks open `lodekeeper` PRs by test basename, which misses other authors and shared-helper fixes. If either result reaches its limit, extend/paginate the scan before treating coverage as complete. Symbol search covers metadata, not arbitrary diff content; an empty result is not proof that no fix exists.

   Inspect each relevant candidate with `gh pr view <number> --repo ChainSafe/lodestar --json number,title,state,url,mergeCommit,mergedAt` and `gh pr diff <number> --repo ChainSafe/lodestar`. Path overlap alone does not establish the same root cause. Re-check any `already_fixing_pr` even when the detector marked the finding `fixable: false`.

   - Same root cause, OPEN fix: record `duplicate-of-existing-pr`, retain `already_fixing_pr`, its URL, and the verified rationale/next step in the tracker; do not create a duplicate branch/PR or modify another author's branch.
   - Same root cause, MERGED fix: refresh `origin/unstable` (`git -C ~/lodestar fetch origin unstable`), then compare the failed head, merge commit, and current source. A historical failure lacking the now-landed fix is `fixed-upstream`; a failure containing the fix still needs investigation. Do not suppress a new recurrence merely because a PR merged.
   - Overlap with a different cause: retain the candidate evidence and continue. If the lookup fails or the same-cause decision is unresolved, stop before implementation/submission and record the blocker rather than assuming there is no duplicate.

   For a confirmed OPEN duplicate or historical failure fixed upstream, update only the tracker/backlog and skip Steps 3–6 for that finding. For a false-positive `already_fixing_pr` match, record the different-cause evidence and restore actionability before proceeding.

3. **Preflight the CI fix quality gate before writing a patch**:
   Use OpenClaw `gateway_exec`, not native `exec_command`, with the workdir above
   and this command (omit `env`):
   ```bash
   python3 /home/openclaw/.openclaw/workspace/scripts/ci/check_fix_quality.py --check-only
   ```
   Exit 0 proves credential/package presence only, not authentication or a live
   model verdict. Non-zero means stop before writing a patch and report the
   missing Gateway prerequisite(s). Do not ship a flaky-test fix without the
   masking/root-cause quality gate unless Nico explicitly approves bypassing it.

4. **Implement in an isolated worktree and verify**. Obtain design feedback before editing and independent review approval before committing, per `AGENTS.md`. Keep `~/lodestar` clean/on `unstable`:
   ```bash
   cd ~/lodestar
   git fetch origin unstable
   git worktree add -b fix/flaky-<test-name> ~/lodestar-flaky-<test-name> origin/unstable
   cd ~/lodestar-flaky-<test-name>
   # Make the fix
   # Run the narrow verification that reproduces and checks the diagnosed failure
   pnpm lint  # MANDATORY before commit/push
   git add <explicit-changed-paths>
   git diff --cached > /tmp/ci-autofix-<runId>.diff
   ```
   Run the following command separately through OpenClaw `gateway_exec`, with
   `workdir: /home/openclaw/.openclaw/workspace` and `env` omitted. The absolute
   diff path must be readable on the Gateway host:
   ```bash
   python3 /home/openclaw/.openclaw/workspace/scripts/ci/check_fix_quality.py \
     --diff-file /tmp/ci-autofix-<runId>.diff \
     --test "<test-name>" \
     --classification "<classification>" \
     --error "<original error snippet>" \
     --fix-hint "<chosen fix approach>"
   ```
   Require exit 0 AND `should_flag: false`. A flagged verdict, API error, or
   missing verdict blocks submission; do not treat a successful shell exit alone
   as quality approval. Then return to the native worktree shell:
   ```bash
   # Repeat Step 2; verify independent review approval before committing
   git -c user.name=lodekeeper -c user.email=lodekeeper@users.noreply.github.com \
     commit -S -m "test: fix flaky <test-name>"
   gh auth status  # Active account MUST be lodekeeper before push/PR creation
   git push fork fix/flaky-<test-name>
   # Write the exact PR description to this file first; match title/body to the actual diff
   gh pr create --repo ChainSafe/lodestar --base unstable --title "test: fix flaky <test-name>" \
     --body-file /tmp/ci-autofix-<runId>-pr.md
   ```

5. **Update tracker**: Set the finding status to `fix-pr-opened` with the PR number.

6. **Announce**: Send one concise PR/verification summary to Lodestar WG topic `#347` using the OpenClaw `message` tool (`action=send`, `channel=telegram`, `target=-1003764039429`, `threadId=347`). Routine results do not go to Nico DM; no duplicate all-clear posts. Keep provider-only follow-up in the OpenClaw session.

## Step 3: Report non-actionable findings

For findings where `fixable: false` AND `already_fixing_pr` is unset, just log them — no action needed. Findings with an existing-PR reference must go through the same-cause/live-state check in Step 2 instead of treating a basename match as resolved.
The tracker has already been updated by the detector script.

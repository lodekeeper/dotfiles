# CI Auto-Fix Cron Instructions

Run the flaky test detector and act on findings.

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

## Step 1: Detect
```bash
cd ~/.openclaw/workspace && python3 scripts/ci/auto_fix_flaky.py --apply
```

If status is "clean" → reply with just the JSON output and stop.

## Step 2: Act on actionable findings

For each finding where `fixable: true`:

1. **Read the logs** — the `log_snippet` field has the tail. If insufficient, run:
   ```bash
   gh run view <runId> --repo ChainSafe/lodestar --log-failed 2>&1 | tail -100
   ```

2. **Identify the fix** based on classification:
   - `shutdown-race`: Add `.catch(() => {})` to the floating promise, or wrap in try/catch
   - `peer-count-flaky`: Increase timeout or add retry logic for peer count assertion
   - `timeout`: Increase the test/hook timeout (usually 2-3x the current value)
   - `vitest-crash`: Check for resource leaks, add cleanup

3. **Create fix branch + PR**:
   ```bash
   cd ~/lodestar
   git fetch origin unstable
   git checkout -b fix/flaky-<test-name> origin/unstable
   # Make the fix
   pnpm lint --write  # ALWAYS lint before commit
   git add -A && git commit -m "test: fix flaky <test-name>"
   git push fork fix/flaky-<test-name>
   gh pr create --repo ChainSafe/lodestar --base unstable --title "test: fix flaky <test-name>" --body "..."
   ```

4. **Update tracker**: Set the finding status to `fix-pr-opened` with the PR number.

5. **Announce**: Send a message to the main session:
   ```
   sessions_send label=main message="🔧 CI auto-fix: opened PR #XXXX to fix flaky <test> on unstable (<classification>)"
   ```

## Step 3: Report non-actionable findings

For findings where `fixable: false`, just log them — no action needed.
The tracker has already been updated by the detector script.

# CI Auto-Fix Cron Instructions

Run the flaky test detector and act on findings.

## Step 1: Detect
```bash
cd ~/.openclaw/workspace && python3 scripts/ci/auto_fix_flaky.py --apply
```

If status is "clean" → reply with just the JSON output and stop.

## Step 2: Act on actionable findings

> **New fields in findings:**
> - `confidence`: how the classification was derived — `high` (keyword match), `medium` (LLM-classified), `low` (no match)
> - `fix_confidence`: `root-cause` | `likely-root-cause` | `masking-risk` | `unknown`
> - `fix_hint`: optional LLM-generated fix suggestion (use as starting point, not gospel)
> - `llm_retry_count`, `llm_retry_wait_s`, `llm_retry_after_seen`: retry telemetry for the LLM classification call on that finding
>
> **New top-level detector telemetry:**
> - `llm_retry_count`, `llm_retry_wait_s`, `llm_retry_after_seen`
> - `llm_retry_telemetry` object (same data grouped)
> - `llm_retry_escalation` object (rolling-window degradation signal)
>
> Include those top-level retry fields in your concise run summary so degraded API health is visible.
>
> If `llm_retry_escalation.degraded` is `true`, include an explicit warning line in the run summary with `llm_retry_escalation.reasons` and recommend checking OpenAI/API health before trusting automation latency.
>
> **If `fix_confidence` is `masking-risk` or `unknown`:** add a PR comment warning that the fix may not address the root cause and needs closer human review. Don't skip the fix, but flag it clearly.

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

3. **Create fix branch + apply fix via Codex Spark**:
   ```bash
   cd ~/lodestar
   git fetch origin unstable
   git checkout -b fix/flaky-<test-name> origin/unstable
   ```
   Then spawn Codex Spark (fast, low-latency model) to implement the fix:
   ```bash
   source ~/.nvm/nvm.sh && nvm use 24 2>/dev/null
   codex -m gpt-5.3-codex-spark exec --full-auto \
     "Fix flaky test <test-name>. Classification: <classification>. \
      Log snippet: <log_snippet>. \
      Apply the fix, then run: pnpm lint --write" \
     2>&1 | tee /tmp/ci-fix-output.log
   ```
   Then lint and stage:
   ```bash
   cd ~/lodestar
   pnpm lint --write  # ALWAYS lint before commit
   git add -A
   ```

4. **Fix quality gate (mandatory)** — Before committing, run the LLM quality check on the staged diff:
   ```bash
   git diff --cached | python3 ~/.openclaw/workspace/scripts/ci/check_fix_quality.py \
     --test "<test-name>" \
     --classification "<classification>" \
     --error "<log_snippet last line or key error>" \
     --fix-hint "<fix_hint if available>"
   ```

   Read the JSON output:
   - **`verdict: "root-cause"` or `"likely-root-cause"`** → proceed to commit and PR
   - **`verdict: "masking"`** → the fix may not address the real issue. Check `suggestions` and try to improve the fix. If no better fix is feasible, proceed but add a warning to the PR body (see below).
   - **`verdict: "insufficient"`** → diff is too small/unclear. Proceed but flag in PR.
   - **If `should_flag: true`** → include this in the PR body:
     ```
     ⚠️ **Fix Quality Note:** This fix was flagged as potentially masking the root cause.
     LLM assessment: <reasoning from quality check>
     Please review carefully before merging.
     ```
   - If the quality check script fails (missing API key, error), proceed without it but add a note: "⚠️ Fix quality check unavailable — manual review recommended."

   Commit and PR:
   ```bash
   git commit -m "test: fix flaky <test-name>"
   git push fork fix/flaky-<test-name>
   pr_url=$(gh pr create --repo ChainSafe/lodestar --base unstable --title "test: fix flaky <test-name>" --body "..." --label "auto-fix")
   pr_number=$(basename "$pr_url")
   # If --label "auto-fix" fails (label may not exist), create it first:
   # gh label create "auto-fix" --repo ChainSafe/lodestar --color "e4e669" --description "Automatically opened by CI autofix pipeline" 2>/dev/null || true
   # Then re-run the gh pr create command.
   ```

5. **Issue linkage (mandatory)**: Find existing open issue(s) for the same flaky test/failure and link them from the PR.
   ```bash
   issue_hits=$(gh issue list --repo ChainSafe/lodestar --state open --limit 20 \
     --search '"<test-name>" in:title,in:body is:issue state:open' \
     --json number,title,url)

   # If issue(s) exist: post one PR comment with links (don't spam multiple comments)
   # Example rendered links: #1234, #5678
   ```
   - If one or more matching issues exist, add a PR comment: "Potentially fixes/relates to #<id> ..." with the linked issue numbers.
   - If no matching issue exists, continue without creating a new issue automatically.

6. **Update tracker**: Set the finding status to `fix-pr-opened` with the PR number and linked issue IDs (if any).

7. **Announce**: Send a message to the main session:
   ```
   sessions_send label=main message="🔧 CI auto-fix: opened PR #XXXX to fix flaky <test> on unstable (<classification>) [issues: #A, #B | none]"
   ```

## Step 3: Report non-actionable findings

For findings where `fixable: false`, just log them — no action needed.
The tracker has already been updated by the detector script.
